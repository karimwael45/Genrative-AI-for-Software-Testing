"""SQLite inspection snapshots, logs and version records."""
import json
import sqlite3
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
