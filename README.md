# Human-in-the-Loop Web Testing Assistant

A web assistant that helps a human tester inspect a web page and ask a model for grounded testing suggestions. **Phase 1** (guided inspection) is implemented: the tester inspects a page in a visible browser, reviews the findings with their locators, selects elements, states a testing goal and gets a model suggestion with usage and timing. Later phases (test design, Playwright code generation, execution, maintenance) are described in the design document.

Python 3.10+, FastAPI, plain HTML/JavaScript, SQLite and Playwright (headed Chromium). Only free-tier or local models are used.

Design document: [`docs/design-document.md`](docs/design-document.md) (component diagram, data flow, approval gates, resource assumptions, path to later phases). Per-topic detail is in [`docs/sections/`](docs/sections/) and the editable diagrams in [`docs/diagrams/`](docs/diagrams/).

## Setup and run

From this folder:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m uvicorn app.app:app --host 127.0.0.1 --port 5000
```

1. Start the website you want to inspect (for example on `http://localhost:8000`). Its origin must be listed under `allowed_origins` in `config/settings.yaml`; any other origin is refused before a browser opens.
2. Copy `.env.example` to `.env` and add a free API key for the model provider (see [Model setup](#model-setup)). `.env` is git-ignored and is read automatically by the model module.
3. Open http://127.0.0.1:5000. API docs are at `/docs`.

A visible desktop session is required, because the inspector runs Chromium headed.

## How to use

1. Enter the URL of an approved page and click **Inspect page**. (**Load sample** shows a bundled example without a browser; it cannot be used for model calls.)
2. Review the findings. Each element shows its role, label and ID; **Evidence** expands the observed attributes and the candidate locators with their match counts.
3. Tick the elements you care about and write a testing goal.
4. Click **Suggest next step**. The answer is shown with the model name, response time and input/output tokens (estimates are labelled).

Inspections and model calls are stored in `data/assistant.sqlite3` (git-ignored). A stored inspection can be reloaded without opening the browser.

## API summary

| Endpoint | Purpose |
|---|---|
| `GET /` | The web UI. |
| `POST /api/inspect` | `{url, scope?}`: validate the URL, run the isolated runner, store and return the inspection. |
| `GET /api/inspections/{id}` | Return a stored inspection. |
| `POST /api/assist` | `{inspectionId, elementIds, goal, clarificationAnswer?}`: grounded model suggestion and usage. |
| `GET /api/logs` | Per-call model usage and the average fresh response time. |

Request and response details: [`contracts/api.md`](contracts/api.md). Canonical models: `app/schemas.py`.

## Repository structure

- `app/`: FastAPI routes, runner subprocess client, SQLite storage, Pydantic schemas.
- `runner/`: isolated browser process (JSON on stdin/stdout), headed Playwright inspector, locator ranking.
- `model/`: providers, grounded prompts, output validation, usage logging, `cli.py`.
- `web/`: HTML, JavaScript, CSS and the sample inspection fixture.
- `config/settings.yaml`: allowed origins, runner limits and model configuration.
- `contracts/`: API contract and synthetic samples.
- `docs/`: design document, sections and diagrams.
- `evidence/`: sample inspection output, model usage log and screenshots.
- `tests/`: unit and API tests (48).
- `data/`: git-ignored runtime database and runner working folder.

## Implementation status

**Working**
- URL allowlist checked in the backend and again in the runner; the final URL after loading is checked too, so a redirect to another origin is rejected.
- Headed Chromium inspection with resolved labels, observed attributes and ranked candidate locators carrying live match counts and a `unique` flag; optional scope (CSS selector and element types).
- Runner started as a separate process with a timeout, a restricted working folder and an environment without API keys.
- Schema validation of runner output, and SQLite storage of inspections, model-call logs and (for Phase 2) artifact versions.
- Grounded model call: only the selected, stored elements are sent; cited element IDs are checked; page text is treated as untrusted data; tokens and model response time are logged.

**Not done yet**
- The runner does not block sub-requests or in-page navigation while a page loads; only the initial and final URLs are checked. It is a separate process, not an OS sandbox.
- Real-provider evidence: `evidence/model_usage_log.json` was recorded with the offline `mock` provider and must be re-recorded with a real model on the real inspection. The demo video and screenshots are still to be added.
- Phase 2: test design, Playwright POM generation, execution, rescan and repair, version diffs and restore.

## Model setup

Choose the provider in `config/settings.yaml` → `model.provider`:

| Provider | Notes |
|---|---|
| `groq` (default) | Free tier, open-weights `openai/gpt-oss-20b`. Needs `GROQ_API_KEY`. |
| `gemini` | Free tier, `gemini-2.0-flash`. Needs `GEMINI_API_KEY`. |
| `ollama` | Local, no key. Install Ollama and run `ollama pull llama3.2:3b`; uses `OLLAMA_BASE_URL` (default `http://localhost:11434`). |
| `mock` | Offline and deterministic, for tests and offline demos only. **Never use it as evidence.** |

**Fallback.** The intended behaviour is a two-level chain: the configured provider first, then local Ollama, then the offline `mock` provider. Set `fallback_provider: null` to disable the fallback. Calls answered by the fallback are logged with the provider that actually answered.

Setup:
1. Copy `.env.example` to `.env` and paste your key (for example `GROQ_API_KEY=...` from console.groq.com). Never commit it.
2. Check the setup without the UI or browser: `python -m model.cli --goal "Check invalid email handling" --ids el-1 el-2`
3. Save evidence from a real inspection: `python -m model.cli --inspection evidence/inspection_output.json --goal "..." --ids <ids> --save evidence/model_usage_log.json`

## Tests and evidence

```powershell
python -m unittest discover -s tests
```

`python -m pytest -q` also works. To run only the runner directly: `python -m runner.runner_main` with one JSON request `{"url": ..., "scope": ...}` on stdin.

Evidence files live in `evidence/`: a real structured inspection (`inspection_output.json`), the model usage and timing log (`model_usage_log.json`), screenshots and a short demo (`demo.mp4` or a link). Check that evidence contains no credentials before submitting.
