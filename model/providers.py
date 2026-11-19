"""Model provider adapters (local/open-source or free-tier only).

Every provider exposes the same call:

    complete(system, user, cfg) -> ProviderResult

Only the HTTP request to the model is timed, so the reported response time
never includes browser or test execution. Provider token counts are used
whenever the provider returns them; otherwise counts are estimated and the
result is labelled ``tokens_estimated=True``.

Only the Python standard library is used, so no extra dependencies are needed.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProviderError(RuntimeError):
    """Raised when a provider is misconfigured, unreachable, or rate limited."""


@dataclass
class ProviderResult:
    text: str
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    tokens_estimated: bool
    response_time_ms: float


# ---------------------------------------------------------------- helpers

def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal .env reader: KEY=VALUE lines, existing env vars win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def estimate_tokens(text: str) -> int:
    """Rough estimate (~4 characters per token). Always labelled as estimated."""
    return max(1, round(len(text) / 4))


def _api_key(pcfg: dict) -> str:
    env_name = pcfg.get("api_key_env", "")
    key = os.environ.get(env_name, "").strip()
    if not key:
        raise ProviderError(f"Missing API key: set {env_name} in your local .env file")
    return key


def _post_json(url: str, payload: dict, headers: dict, timeout: float) -> tuple[dict, float]:
    """POST JSON and return (response_json, elapsed_ms) for the HTTP call only."""
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 # Some providers sit behind Cloudflare, which rejects the default
                 # "Python-urllib" User-Agent (HTTP 403, error code 1010).
                 "User-Agent": "genai-testing-assistant/1.0 (+python)", **headers},
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        if exc.code == 429:
            raise ProviderError(f"Rate limit reached (HTTP 429): {detail}") from exc
        raise ProviderError(f"Provider returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError(f"Provider unreachable: {exc}") from exc
    elapsed_ms = (time.perf_counter() - start) * 1000
    try:
        return json.loads(body), elapsed_ms
    except json.JSONDecodeError as exc:
        raise ProviderError("Provider returned a non-JSON body") from exc


def _finish(text, provider, model, in_tok, out_tok, elapsed, system, user) -> ProviderResult:
    estimated = in_tok is None or out_tok is None
    if in_tok is None:
        in_tok = estimate_tokens(system + user)
    if out_tok is None:
        out_tok = estimate_tokens(text)
    return ProviderResult(text, provider, model, in_tok, out_tok, estimated, round(elapsed, 1))


# ---------------------------------------------------------------- providers

def _groq(system: str, user: str, cfg: dict) -> ProviderResult:
    """Groq free tier (OpenAI-compatible chat completions API)."""
    pcfg = cfg["providers"]["groq"]
    payload = {
        "model": pcfg["model"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": cfg.get("temperature", 0.2),
        "max_tokens": cfg.get("max_output_tokens", 600),
        "response_format": {"type": "json_object"},
    }
    if pcfg.get("reasoning_effort"):
        payload["reasoning_effort"] = pcfg["reasoning_effort"]
    data, elapsed = _post_json(
        pcfg["base_url"].rstrip("/") + "/chat/completions", payload,
        {"Authorization": f"Bearer {_api_key(pcfg)}"}, cfg.get("timeout_seconds", 60),
    )
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("Unexpected Groq response shape") from exc
    usage = data.get("usage") or {}
    return _finish(text, "groq", data.get("model", pcfg["model"]),
                   usage.get("prompt_tokens"), usage.get("completion_tokens"), elapsed, system, user)


def _gemini(system: str, user: str, cfg: dict) -> ProviderResult:
    """Google Gemini free tier (generateContent API)."""
    pcfg = cfg["providers"]["gemini"]
    url = f"{pcfg['base_url'].rstrip('/')}/models/{pcfg['model']}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": cfg.get("temperature", 0.2),
            "maxOutputTokens": cfg.get("max_output_tokens", 600),
            "responseMimeType": "application/json",
        },
    }
    data, elapsed = _post_json(url, payload, {"x-goog-api-key": _api_key(pcfg)},
                               cfg.get("timeout_seconds", 60))
    try:
        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("Unexpected Gemini response shape") from exc
    usage = data.get("usageMetadata") or {}
    return _finish(text, "gemini", data.get("modelVersion", pcfg["model"]),
                   usage.get("promptTokenCount"), usage.get("candidatesTokenCount"), elapsed, system, user)


def _ollama(system: str, user: str, cfg: dict) -> ProviderResult:
    """Local open-source model served by Ollama (no key, no rate limit)."""
    pcfg = cfg["providers"]["ollama"]
    base = os.environ.get(pcfg.get("base_url_env", ""), "") or pcfg["base_url"]
    payload = {
        "model": pcfg["model"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "format": "json",
        "options": {"temperature": cfg.get("temperature", 0.2),
                    "num_predict": cfg.get("max_output_tokens", 600)},
    }
    data, elapsed = _post_json(base.rstrip("/") + "/api/chat", payload, {},
                               cfg.get("timeout_seconds", 60))
    text = (data.get("message") or {}).get("content", "")
    return _finish(text, "ollama", data.get("model", pcfg["model"]),
                   data.get("prompt_eval_count"), data.get("eval_count"), elapsed, system, user)


def _mock(system: str, user: str, cfg: dict) -> ProviderResult:
    """Offline deterministic provider for tests. Never use it as demo evidence."""
    start = time.perf_counter()
    marker = '"selectedElementIds": '
    ids: list[str] = []
    if marker in user:
        try:
            ids = json.loads(user.split(marker, 1)[1].split("\n", 1)[0].rstrip(","))
        except json.JSONDecodeError:
            ids = []
    text = json.dumps({
        "summary": f"Mock summary of {len(ids)} selected element(s).",
        "observations": [{"elementId": i, "note": "Observed in the stored inspection."} for i in ids],
        "nextAction": {"description": "Mock next action.", "elementIds": ids[:1]},
        "clarification": "Mock clarification: what is the expected behavior?",
        "assumptions": [],
    })
    elapsed = (time.perf_counter() - start) * 1000
    return _finish(text, "mock", cfg["providers"]["mock"]["model"], None, None, elapsed, system, user)


PROVIDERS = {"groq": _groq, "gemini": _gemini, "ollama": _ollama, "mock": _mock}


def complete(system: str, user: str, cfg: dict) -> ProviderResult:
    """Call the configured provider, then the fallback provider if the first fails."""
    load_dotenv()
    order = [cfg.get("provider", "mock")]
    fallback = cfg.get("fallback_provider")
    if fallback and fallback not in order:
        order.append(fallback)
    errors = []
    for name in order:
        if name not in PROVIDERS:
            errors.append(f"{name}: unknown provider")
            continue
        try:
            return PROVIDERS[name](system, user, cfg)
        except ProviderError as exc:
            errors.append(f"{name}: {exc}")
    raise ProviderError("All model providers failed. " + " | ".join(errors))
