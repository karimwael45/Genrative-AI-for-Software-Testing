# GenAI Phase 1 starter

Python 3.10+, FastAPI, plain HTML/JavaScript, and Playwright.

## Setup and run

From this folder:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m uvicorn app.app:app --host 127.0.0.1 --port 5000
```

Open http://127.0.0.1:5000 and click **Load sample**. API docs: /docs.
Configure approved demo origins, model name, timeout and element limit in config/settings.yaml. Copy .env.example to .env if needed; provider code must explicitly read environment variables (the starter does not load .env automatically).

## Repository structure

- config/settings.yaml: allowlist and runtime limits.
- contracts/: shared synthetic inspection/model examples and API documentation.
- runner/: JSON process entry point, Playwright inspector stub, locator ranking.
- app/: FastAPI routes, runner subprocess client, SQLite storage, Pydantic schemas.
- model/: model stub, provider boundary, selected-ID validation, Phase 1/2 prompts.
- web/: HTML, JavaScript, CSS and the browser's synthetic inspection fixture.
- data/: ignored runtime database and existing legacy JSON snapshots.
- docs/: design and diagrams folder.
- evidence/: instructions and screenshots folder for real integrated demo evidence.
- tests/: module boundary checks.

## Implementation status and work split

P1: implement runner/inspector.py with headed Playwright and live locator match counts. The entry point validates the initial origin; redirects/navigation/resource restrictions must still be implemented in the inspector. A subprocess alone is not an OS sandbox.
P2: maintain web/ UI and integrate the backend flow with teammates.
P3: implement model/model.py and model/providers.py, wire prompts, log actual model/token/time usage and validate output grounding.
P4: maintain app/, configuration, setup, docs and integrated evidence.
Shared contracts should be agreed by everyone.

Live inspection and model calls remain explicitly unimplemented. The sample button works without them. No real inspection output, model usage log or demo video is supplied: capture these after implementation as evidence/inspection_output.json, evidence/model_usage_log.json and evidence/demo.mp4 (or link). The sample-model-call.json is synthetic.

SQLite tables exist for inspections, logs and versions; only inspection persistence is currently wired. Old data/<UUID>.json snapshots remain readable. The model and provider stubs are not yet connected to each other.

Run checks with `python -m unittest discover -s tests`. Worker protocol: `python -m runner.runner_main` with one JSON request on stdin. See contracts/api.md.
