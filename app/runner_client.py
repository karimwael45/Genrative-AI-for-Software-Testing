"""Start the isolated runner with a bounded timeout.

The backend never imports Playwright or runner code: it checks the URL,
starts the runner as a separate process in a restricted working directory
with a minimal environment (no API keys), and exchanges JSON over stdin/stdout.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORK_DIR = ROOT / "data" / "runner_work"

# Only what Python, Playwright and a visible browser need. Secrets such as
# GROQ_API_KEY are deliberately not passed to the runner.
ENV_ALLOWLIST = (
    "PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP",
    "LOCALAPPDATA", "APPDATA", "USERPROFILE", "HOME",
    "PLAYWRIGHT_BROWSERS_PATH", "DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY",
)
STDERR_TAIL = 500


def load_settings() -> dict:
    return yaml.safe_load((ROOT / "config/settings.yaml").read_text())


def check_allowed_url(url: str, settings: dict) -> str:
    """Backend-side allowlist check (the runner repeats it as a second line of defense)."""
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
        raise ValueError("A valid HTTP(S) demo URL is required")
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in settings["allowed_origins"]:
        raise ValueError("URL origin is not in the configured allowlist")
    return url


def runner_env() -> dict:
    env = {key: os.environ[key] for key in ENV_ALLOWLIST if key in os.environ}
    env["PYTHONPATH"] = str(ROOT)
    return env


def parse_runner_output(result: subprocess.CompletedProcess) -> dict:
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        payload = None
    if not isinstance(payload, dict):
        detail = (result.stderr or "").strip()[-STDERR_TAIL:]
        raise ValueError("Runner returned no valid JSON" + (f": {detail}" if detail else ""))
    if result.returncode or "error" in payload:
        raise ValueError(payload.get("error", "Runner failed"))
    return payload


def run_inspection(url: str, scope: dict | None = None) -> dict:
    settings = load_settings()
    check_allowed_url(url, settings)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-m", "runner.runner_main"],
        input=json.dumps({"url": url, "scope": scope}), text=True, capture_output=True,
        cwd=WORK_DIR, env=runner_env(), timeout=settings["runner_timeout_seconds"],
    )
    payload = parse_runner_output(result)
    if len(payload.get("elements", [])) > settings["max_elements"]:
        raise ValueError("Inspection exceeds the configured element limit")
    return payload
