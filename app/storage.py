"""SQLite storage: inspection snapshots, model-call logs and artifact versions.

Every connection is opened, committed (or rolled back) and closed by connect().
Older local databases are migrated in place: missing columns are added and
filled from the stored JSON payloads.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DB_NAME = "assistant.sqlite3"
ARTIFACT_TYPES = {"testcases", "code"}

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS inspections (
        id TEXT PRIMARY KEY, source_url TEXT, inspected_at TEXT, payload TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY, inspection_id TEXT, logged_at TEXT, payload TEXT NOT NULL)""",
    # Phase 2: versions of test cases and generated code (diff and restore).
    """CREATE TABLE IF NOT EXISTS artifact_versions (
        id INTEGER PRIMARY KEY, artifact_type TEXT NOT NULL, artifact_id TEXT NOT NULL,
        version INTEGER NOT NULL, created_at TEXT NOT NULL, note TEXT, payload TEXT NOT NULL,
        UNIQUE (artifact_type, artifact_id, version))""",
)

# Columns added after the first starter version: column -> JSON field to backfill from.
MIGRATIONS = {
    "inspections": {"source_url": "$.sourceUrl", "inspected_at": "$.inspectedAt"},
    "logs": {"inspection_id": "$.inspectionId", "logged_at": "$.loggedAt"},
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_schema(db: sqlite3.Connection) -> None:
    for statement in SCHEMA:
        db.execute(statement)
    for table, columns in MIGRATIONS.items():
        existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
        for column, json_path in columns.items():
            if column not in existing:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
                db.execute(f"UPDATE {table} SET {column} = json_extract(payload, ?)", (json_path,))


@contextmanager
def connect():
    DATA_DIR.mkdir(exist_ok=True)
    db = sqlite3.connect(DATA_DIR / DB_NAME)
    try:
        ensure_schema(db)
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------- Inspections ----------

def save_inspection(inspection: dict) -> dict:
    snapshot = {**inspection, "inspectionId": str(uuid4()), "inspectedAt": now()}
    with connect() as db:
        db.execute(
            "INSERT INTO inspections (id, source_url, inspected_at, payload) VALUES (?, ?, ?, ?)",
            (snapshot["inspectionId"], snapshot.get("sourceUrl"), snapshot["inspectedAt"], json.dumps(snapshot)),
        )
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


def list_inspections(source_url: str | None = None) -> list[dict]:
    """Stored inspections, newest first (used to find the previous scan for a rescan diff)."""
    query = "SELECT id, source_url, inspected_at FROM inspections"
    params: tuple = ()
    if source_url:
        query += " WHERE source_url = ?"
        params = (source_url,)
    with connect() as db:
        rows = db.execute(query + " ORDER BY inspected_at DESC, rowid DESC", params).fetchall()
    return [{"inspectionId": r[0], "sourceUrl": r[1], "inspectedAt": r[2]} for r in rows]


# ---------- Model-call logs ----------

def save_log(entry: dict) -> int:
    """Store one model-call record (goal, selected IDs, usage, timing) and return its ID."""
    record = {"loggedAt": now(), **entry}
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO logs (inspection_id, logged_at, payload) VALUES (?, ?, ?)",
            (record.get("inspectionId"), record["loggedAt"], json.dumps(record)),
        )
        return cursor.lastrowid


def list_logs(inspection_id: str | None = None) -> list[dict]:
    query = "SELECT id, payload FROM logs"
    params: tuple = ()
    if inspection_id:
        query += " WHERE inspection_id = ?"
        params = (inspection_id,)
    with connect() as db:
        rows = db.execute(query + " ORDER BY id", params).fetchall()
    return [{"logId": row[0], **json.loads(row[1])} for row in rows]


# ---------- Artifact versions (Phase 2) ----------

def _check_type(artifact_type: str) -> None:
    if artifact_type not in ARTIFACT_TYPES:
        raise ValueError(f"artifact_type must be one of {sorted(ARTIFACT_TYPES)}")


def save_version(artifact_type: str, artifact_id: str, payload, note: str | None = None) -> dict:
    """Store a new version; numbers start at 1 per artifact. Restoring = saving an old payload again."""
    _check_type(artifact_type)
    created_at = now()
    with connect() as db:
        (latest,) = db.execute(
            "SELECT COALESCE(MAX(version), 0) FROM artifact_versions WHERE artifact_type = ? AND artifact_id = ?",
            (artifact_type, artifact_id),
        ).fetchone()
        cursor = db.execute(
            "INSERT INTO artifact_versions (artifact_type, artifact_id, version, created_at, note, payload) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (artifact_type, artifact_id, latest + 1, created_at, note, json.dumps(payload)),
        )
    return {"versionId": cursor.lastrowid, "artifactType": artifact_type, "artifactId": artifact_id,
            "version": latest + 1, "createdAt": created_at, "note": note, "payload": payload}


def list_versions(artifact_type: str, artifact_id: str) -> list[dict]:
    """Version metadata (no payloads), oldest first."""
    _check_type(artifact_type)
    with connect() as db:
        rows = db.execute(
            "SELECT id, version, created_at, note FROM artifact_versions "
            "WHERE artifact_type = ? AND artifact_id = ? ORDER BY version",
            (artifact_type, artifact_id),
        ).fetchall()
    return [{"versionId": r[0], "artifactType": artifact_type, "artifactId": artifact_id,
             "version": r[1], "createdAt": r[2], "note": r[3]} for r in rows]


def get_version(artifact_type: str, artifact_id: str, version: int) -> dict:
    _check_type(artifact_type)
    with connect() as db:
        row = db.execute(
            "SELECT id, created_at, note, payload FROM artifact_versions "
            "WHERE artifact_type = ? AND artifact_id = ? AND version = ?",
            (artifact_type, artifact_id, version),
        ).fetchone()
    if not row:
        raise FileNotFoundError("Version not found")
    return {"versionId": row[0], "artifactType": artifact_type, "artifactId": artifact_id,
            "version": version, "createdAt": row[1], "note": row[2], "payload": json.loads(row[3])}
