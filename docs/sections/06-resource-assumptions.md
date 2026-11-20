# 6. Resource assumptions

## Development and demo machine

| Item | Value |
|---|---|
| OS | Windows 11 Pro |
| CPU | 13th Gen Intel Core i7-13650HX |
| RAM | 16 GB |
| GPU | NVIDIA GeForce RTX 4050 Laptop GPU (only used if a local Ollama model is chosen) |
| Python | 3.12.4 (README requires 3.10+) |
| Key packages (tested) | FastAPI 0.141.1, Pydantic 2.13.4, Uvicorn 0.52.1, Playwright 1.61.0 (versions allowed are pinned as ranges in `requirements.txt`) |
| Browser | Chromium installed with `python -m playwright install chromium`, run headed (visible) |

## Model setup

Configured in `config/settings.yaml` → `model` (details in the model integration section by P3). No paid API is used, and no key is stored in the repository.

| Setting | Value |
|---|---|
| Default provider | Groq free tier, open-weights model `openai/gpt-oss-20b`, `reasoning_effort: low` |
| Alternatives | Gemini free tier `gemini-2.0-flash`; local Ollama `llama3.2:3b` (runs on the machine above, no key, no network) |
| Fallback chain | `fallbacks: [ollama, mock]`: local Ollama first (skipped quickly if not running), then a labelled offline mock. Mock replies are never valid evidence. `[]` disables fallbacks. |
| Temperature | 0.2 |
| Max output tokens | 1500 (part is spent on hidden reasoning by gpt-oss) |
| Model timeout | 60 s |
| Page text per field sent to the model | truncated to 200 characters (`max_field_chars`) |
| Keys | `GROQ_API_KEY` / `GEMINI_API_KEY` read from the environment or a local git-ignored `.env` |
| Rate limits | Free-tier per-minute and per-day request and token limits apply. Record the exact values shown for your account at console.groq.com (Settings → Limits) when the evidence is captured. A rate-limit error is returned as 503, not retried silently. |

## Runner limits

Configured in `config/settings.yaml`.

| Setting | Value | Effect |
|---|---|---|
| `allowed_origins` | `http://localhost:8000` (add the instructor's demo site before the demo) | Any other origin is refused before a browser opens. |
| `runner_timeout_seconds` | 30 | The runner process is killed after 30 s; the API returns 504. |
| `max_elements` | 200 | Larger inspections are rejected so prompts and the UI stay small. |
| Working folder | `data/runner_work/` | The runner's current directory; ignored by git. |
| Environment | allowlist only (PATH, temp folders, Playwright browser path, display variables) | API keys and other secrets are not passed to the runner. |

**Limit:** the runner is a separate operating-system process, not an OS sandbox. It runs as the same user, so it could still read user files if the inspector code did so. Network scope is controlled by the allowlist and by the inspector blocking redirects to other origins (P1).

## Measurements recorded

| Measurement | Where |
|---|---|
| Browser inspection time | `inspectionTimeMs` in each stored inspection (measured by the runner) |
| Model response time | `responseTimeMs` per call in `logs` (model call only, excludes browser time) |
| Tokens | `inputTokens`, `outputTokens` from the provider; `tokenCountsEstimated: true` when the provider gives no counts |
| Average | `GET /api/logs` → `averageResponseTimeMs`, computed over fresh (not cached) calls |

## Assumptions

- One tester, one machine, one inspection at a time; no concurrency or multi-user access control is needed.
- Target pages are small to medium forms (under 200 interactive elements).
- The demo needs network access for Groq or Gemini, or a pulled Ollama model for offline use.
- A visible desktop session is available, because the browser runs headed.
