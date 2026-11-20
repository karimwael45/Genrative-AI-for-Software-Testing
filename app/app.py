"""FastAPI backend and static web interface."""
import subprocess
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.schemas import InspectRequest, AssistRequest, Inspection, ModelResponse
from app.runner_client import run_inspection
from app.storage import list_logs, load_inspection, save_inspection, save_log
from model.model import suggest
from model.providers import ProviderError
from model.validation import resolve_elements

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="Web Testing Assistant")
app.mount("/web", StaticFiles(directory=ROOT / "web"), name="web")

@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": "Invalid request fields"})

@app.get("/")
def index():
    return FileResponse(ROOT / "web/index.html")

@app.post("/api/inspect")
def inspect(body: InspectRequest):
    try:
        scope = body.scope.model_dump() if body.scope else None
        payload = run_inspection(body.url, scope)
        payload.setdefault("scope", scope)
        snapshot = Inspection.model_validate(payload).model_dump(exclude_none=True)
        return save_inspection(snapshot)
    except subprocess.TimeoutExpired:
        return JSONResponse(status_code=504, content={"error": "Inspection timed out"})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

@app.get("/api/inspections/{inspection_id}")
def get_inspection(inspection_id: str):
    """Return a stored inspection (reused, the runner is not started again)."""
    try:
        return load_inspection(inspection_id)
    except (FileNotFoundError, ValueError):
        return JSONResponse(status_code=404, content={"error": "Inspection not found"})

@app.post("/api/assist")
def assist(body: AssistRequest):
    try:
        snapshot = load_inspection(body.inspectionId)
        elements = resolve_elements(snapshot, body.elementIds)
        result = suggest(body.goal, snapshot["sourceUrl"], elements, body.clarificationAnswer)
        result["logId"] = save_log({
            "inspectionId": body.inspectionId, "sourceUrl": snapshot["sourceUrl"],
            "goal": body.goal, "elementIds": body.elementIds,
            "clarificationAnswer": body.clarificationAnswer, **result,
        })
        return ModelResponse.model_validate(result)
    except FileNotFoundError:
        return JSONResponse(status_code=404, content={"error": "Inspection not found"})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except ProviderError as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})
    except NotImplementedError as exc:
        return JSONResponse(status_code=501, content={"error": str(exc)})

@app.get("/api/logs")
def logs(inspectionId: str | None = None):
    """Model-call usage log with per-call timing and the average response time.

    Cached (reused) results are listed but excluded from the average so it
    reflects fresh model calls only.
    """
    entries = list_logs(inspectionId)
    fresh = [e["responseTimeMs"] for e in entries if not e.get("cached")]
    return {
        "calls": entries,
        "freshCalls": len(fresh),
        "averageResponseTimeMs": round(sum(fresh) / len(fresh), 1) if fresh else None,
    }
