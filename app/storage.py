"""SQLite inspection snapshots, logs and version records."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

def connect():
    DATA_DIR.mkdir(exist_ok=True)
    db = sqlite3.connect(DATA_DIR / "assistant.sqlite3")
    db.execute("CREATE TABLE IF NOT EXISTS inspections (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS versions (id INTEGER PRIMARY KEY, inspection_id TEXT, payload TEXT NOT NULL)")
    return db

def save_inspection(inspection: dict) -> dict:
    snapshot = {**inspection, "inspectionId": str(uuid4())}
    with connect() as db:
        db.execute("INSERT INTO inspections VALUES (?, ?)", (snapshot["inspectionId"], json.dumps(snapshot)))
    return snapshot

def load_inspection(inspection_id: str) -> dict:
    key = str(UUID(inspection_id))
    with connect() as db:
        row = db.execute("SELECT payload FROM inspections WHERE id = ?", (key,)).fetchone()
    if row:
        return json.loads(row[0])
    # Keep snapshots created by the original starter readable.
    legacy = DATA_DIR / f"{key}.json"
    if legacy.exists():
        return json.loads(legacy.read_text(encoding="utf-8"))
    raise FileNotFoundError("Inspection not found")


def save_log(entry: dict) -> int:
    """Store one model-call record (goal, selected IDs, usage, timing) and return its ID."""
    record = {"loggedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
    with connect() as db:
        cursor = db.execute("INSERT INTO logs (payload) VALUES (?)", (json.dumps(record),))
        return cursor.lastrowid


def list_logs(inspection_id: str | None = None) -> list[dict]:
    with connect() as db:
        rows = db.execute("SELECT id, payload FROM logs ORDER BY id").fetchall()
    logs = [{"logId": row[0], **json.loads(row[1])} for row in rows]
    if inspection_id:
        logs = [log for log in logs if log.get("inspectionId") == inspection_id]
    return logs
