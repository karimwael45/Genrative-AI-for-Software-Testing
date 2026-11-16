"""Local inspection snapshots for the Phase 1 demo."""
import json
from pathlib import Path
from uuid import UUID, uuid4

DATA_DIR = Path(__file__).resolve().parent / "data"


def save_inspection(inspection: dict) -> dict:
    snapshot = {**inspection, "inspectionId": str(uuid4())}
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"{snapshot['inspectionId']}.json"
    with path.open("x", encoding="utf-8") as file:
        json.dump(snapshot, file, indent=2, ensure_ascii=False)
    return snapshot


def load_inspection(inspection_id: str) -> dict:
    path = DATA_DIR / f"{UUID(inspection_id)}.json"
    return json.loads(path.read_text(encoding="utf-8"))
