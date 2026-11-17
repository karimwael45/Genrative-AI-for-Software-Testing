"""FastAPI backend and static web interface."""
import subprocess
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.schemas import InspectRequest, AssistRequest, Inspection, ModelResponse
from app.runner_client import run_inspection
from app.storage import load_inspection, save_inspection
from model.model import suggest
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
        snapshot = Inspection.model_validate(run_inspection(body.url)).model_dump(exclude_none=True)
        return save_inspection(snapshot)
    except subprocess.TimeoutExpired:
        return JSONResponse(status_code=504, content={"error": "Inspection timed out"})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

@app.post("/api/assist")
def assist(body: AssistRequest):
    try:
        snapshot = load_inspection(body.inspectionId)
        elements = resolve_elements(snapshot, body.elementIds)
        return ModelResponse.model_validate(suggest(body.goal, snapshot["sourceUrl"], elements))
    except FileNotFoundError:
        return JSONResponse(status_code=404, content={"error": "Inspection not found"})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except NotImplementedError as exc:
        return JSONResponse(status_code=501, content={"error": str(exc)})
