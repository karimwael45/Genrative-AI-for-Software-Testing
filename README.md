# GenAI Phase 1 starter

Python 3.10+, Flask, plain HTML/JavaScript, and Playwright. The starter opens
a web UI with a synthetic inspection fixture. Live inspection and model calls
are explicit stubs and must be implemented for submission.

## Start the UI

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m flask --app app run
```

Open http://127.0.0.1:5000 and click **Load sample**. The browser worker
requires a desktop session for the final headed demo.

## Work split

| Owner | Files | Finish when |
| --- | --- | --- |
| Person 1 | `inspector.py` | A separate worker opens headed Chromium on the approved demo target and returns findings using the sample's shape. Include labels, observed attributes, locator candidates, and match counts where checked. |
| Person 2 | `app.py`, `web/index.html`, `web/app.js` | The live inspect route invokes the worker with a timeout, uses `storage.py` to persist results, and displays them. The assist route resolves selected IDs against the saved inspection, calls the model, and shows the result or error. |
| Person 3 | `model.py`, model setup in this README | A real local/open-source or free-tier model responds to the tester goal and selected observations. Report model/version, token counts or labeled estimates, and elapsed model time. Read any API secret from environment variables. |
| Person 4 | `docs/design.md`, `evidence/`, final README | The design reflects the actual setup and covers Phase 2. The demo and evidence come from a real integrated run, and a teammate can follow the setup from a clean checkout. |

## Shared interfaces

- `POST /api/inspect` accepts `{"url":"..."}`. Invoke the worker with the same
  JSON on stdin and read one JSON response on stdout. Use the shape in
  `web/sample-inspection.json`. Storage assigns the real inspection ID.
- `POST /api/assist` accepts `inspectionId`, `elementIds` (an array), and
  `goal`. Return `message`, `model`, `inputTokens`, `outputTokens`, and
  `responseTimeMs`, plus a flag if token counts are estimates.
- API errors use a non-2xx status and `{"error":"..."}`.

Run the entire flow on the approved demo target before packaging. Replace
the evidence instructions with real outputs and add your final model setup to
this README.
