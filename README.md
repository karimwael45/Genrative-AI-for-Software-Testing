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
python -m uvicorn app.app:app --host 127.0.0.1 --port 8000
```

1. Copy `.env.example` to `.env` and add a free API key for the model provider (see [Model setup](#model-setup)). `.env` is git-ignored and is read automatically by the model module. Without a key the assistant falls back to local Ollama and then to the offline mock (see [Fallback](#model-setup)).
2. Open http://127.0.0.1:8000. API docs are at `/docs`.
3. Enter the URL of an approved page. The default demo target is the assistant's own page at `http://localhost:8000/`, because `http://localhost:8000` is the origin listed under `allowed_origins` in `config/settings.yaml`. Any other origin is refused before a browser opens.

To inspect a different website, add its origin to `allowed_origins`. If that site needs port 8000, start the assistant on another port (for example `--port 5000`) and open that port instead.

A visible desktop session is required, because the inspector runs Chromium headed.

## How to use

1. Enter the URL of an approved page and click **Inspect page**. (**Load sample** shows a bundled example without a browser; it cannot be used for model calls.)
2. Review the findings. Each element shows its role, label and ID; **Evidence** expands the observed attributes and the candidate locators with their match counts.
   Optionally narrow the inspection first with the element-type filters and a CSS selector (scope).
3. Tick the elements you care about and write a testing goal.
4. Click **Suggest next step**. The answer is shown as a summary, observations, a next step and assumptions, with the cited elements highlighted. Below it are the provider and model, response time and input/output tokens (estimates are labelled), a cache tag, and a per-inspection call log.
5. If the model asks a clarification question, type your answer in the reply box and click the refine button. The answer is sent back as `clarificationAnswer` and a new suggestion replaces the old one.
6. Read the warnings. A red grounding warning means the model cited an element you did not select; a fallback warning means the configured provider failed and another one answered; a mock banner means the reply is offline test output and is not real model evidence.

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
- `tests/`: unit and API tests (67).
- `data/`: git-ignored runtime database and runner working folder.

## Implementation status

**Working**
- URL allowlist checked in the backend and again in the runner; the final URL after loading is checked too, so a redirect to another origin is rejected.
- Headed Chromium inspection with resolved labels, observed attributes and ranked candidate locators carrying live match counts and a `unique` flag; optional scope (CSS selector and element types).
- Runner started as a separate process with a timeout, a restricted working folder and an environment without API keys.
- Schema validation of runner output, and SQLite storage of inspections, model-call logs and (for Phase 2) artifact versions.
- Grounded model call: only the selected, stored elements are sent; cited element IDs are checked; page text is treated as untrusted data; tokens and model response time are logged.
- Clarification flow: the model asks one question when the expected behaviour is unknown, the tester answers in the UI and the suggestion is refined.
- Provider fallback chain (Groq, then local Ollama, then a labelled offline mock). The reply says which provider answered and why a fallback was used; fallback replies are never cached and mock replies are never saved as evidence by the CLI.
- Web UI shows scope controls, structured replies, usage and timing, and a per-inspection call log.

**Not done yet**
- The runner does not block sub-requests or in-page navigation while a page loads; only the initial and final URLs are checked. It is a separate process, not an OS sandbox.
- Evidence: `evidence/model_usage_log.json` holds real Groq (`openai/gpt-oss-20b`) calls. The demo video and screenshots are still to be added, and local Ollama and fallback runs still need to be recorded.
- Phase 2: test design, Playwright POM generation, execution, rescan and repair, version diffs and restore.

## Model setup

Choose the provider in `config/settings.yaml` → `model.provider`:

| Provider | Notes |
|---|---|
| `groq` (default) | Free tier, open-weights `openai/gpt-oss-20b`. Needs `GROQ_API_KEY`. |
| `gemini` | Free tier, `gemini-2.0-flash`. Needs `GEMINI_API_KEY`. |
| `ollama` | Local, no key. Install Ollama and run `ollama pull llama3.2:3b`; uses `OLLAMA_BASE_URL` (default `http://localhost:11434`). |
| `mock` | Offline and deterministic, for tests and offline demos only. **Never use it as evidence.** |

**Fallback.** A call tries `model.provider` first (default Groq). If it fails (missing key, network error, rate limit, timeout), the providers in `model.fallbacks` are tried in order, by default `[ollama, mock]`: local Ollama if it is running, then the offline mock. Set `fallbacks: []` to disable the chain. Calls answered by a fallback are flagged (`fallbackUsed`, `fallbackReason`), logged with the provider that actually answered, and never cached. Mock replies start with `[MOCK reply, not a real model]` and `model.cli` refuses to save them as usage evidence unless `--allow-mock` is given.

Setup:
1. Copy `.env.example` to `.env` and paste your key (for example `GROQ_API_KEY=...` from console.groq.com). Never commit it.
2. Check the setup without the UI or browser: `python -m model.cli --goal "Check invalid email handling" --ids el-1 el-2` (element IDs are separated by spaces, not commas). Add `--provider ollama` to force a provider, and `--answer "..."` to reply to a clarification question.
3. Save evidence from a real inspection: `python -m model.cli --inspection evidence/inspection_output.json --goal "..." --ids <id1> <id2> --save evidence/model_usage_log.json`

## Tests and evidence

```powershell
python -m unittest discover -s tests
```

`python -m pytest -q` also works. To run only the runner directly: `python -m runner.runner_main` with one JSON request `{"url": ..., "scope": ...}` on stdin.

Evidence files live in `evidence/`: a real structured inspection (`inspection_output.json`), the model usage and timing log (`model_usage_log.json`, one record per call with the goal, selected IDs, provider, model, tokens, response time and fallback flag), screenshots in `evidence/screenshots/`, and a short demo (`demo.mp4` or a link). The inspection and the usage log should come from the same page version. Check that evidence contains no credentials before submitting.
