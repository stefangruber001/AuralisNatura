"""Encrypted backbone for the Auralis portal.

Health data is special-category (GDPR Art. 9). Every client record's intake,
call notes and report draft are stored as Fernet-encrypted blobs in SQLite.
Only non-sensitive metadata (client id, stage, timestamps) is stored in clear
so the console can list/filter without decrypting everything.

Public API is deliberately small and typed around a "record" dict:
  record = {
    "client_id", "stage", "created", "updated",
    "intake": {...} | None,
    "prep": str | None,
    "notes": str | None,
    "report": {"sections": [...], "approved": bool, "generated_at": str} | None,
    "meta": {...}
  }
"""
from __future__ import annotations
import json, sqlite3, threading, datetime as _dt
from contextlib import closing
from pathlib import Path
from cryptography.fernet import Fernet
from . import cfg

STAGES = ["lead", "call", "won", "invited", "intake", "prep", "draft", "review", "sent", "done", "lost"]

_DB = cfg.ROOT / "auralis.db"
_LOCK = threading.RLock()
_INIT_DONE = False


def _now() -> str:
    # caller-independent ISO timestamp (UTC, seconds)
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _fernet() -> Fernet:
    return Fernet(cfg.data_key())


def _conn() -> sqlite3.Connection:
    """Open a connection. The schema/PRAGMA are applied once per process."""
    global _INIT_DONE
    c = sqlite3.connect(_DB, timeout=15)
    c.execute("PRAGMA busy_timeout=15000")
    if not _INIT_DONE:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute(
            """CREATE TABLE IF NOT EXISTS records(
                client_id TEXT PRIMARY KEY,
                stage     TEXT NOT NULL,
                created   TEXT NOT NULL,
                updated   TEXT NOT NULL,
                blob      BLOB NOT NULL
            )"""
        )
        c.commit()
        _INIT_DONE = True
    return c


def _encrypt(payload: dict) -> bytes:
    return _fernet().encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


class DecryptError(RuntimeError):
    """Raised when a record cannot be decrypted (wrong/rotated AURALIS_DATA_KEY)."""


def _decrypt(blob: bytes) -> dict:
    from cryptography.fernet import InvalidToken
    try:
        return json.loads(_fernet().decrypt(blob).decode("utf-8"))
    except InvalidToken as e:
        raise DecryptError(
            "cannot decrypt a record — the AURALIS_DATA_KEY does not match the data "
            "(key rotated or lost). Restore the correct key; do not overwrite the store."
        ) from e


def _empty(client_id: str) -> dict:
    return {
        "client_id": client_id, "stage": "invited",
        "created": _now(), "updated": _now(),
        "intake": None, "prep": None, "notes": None, "report": None, "meta": {},
    }


def get(client_id: str) -> dict | None:
    with _LOCK, closing(_conn()) as c, c:
        row = c.execute("SELECT blob FROM records WHERE client_id=?", (client_id,)).fetchone()
    if not row:
        return None
    return _decrypt(row[0])


def upsert(record: dict) -> dict:
    record["updated"] = _now()
    record.setdefault("created", _now())
    with _LOCK, closing(_conn()) as c, c:
        c.execute(
            "INSERT INTO records(client_id,stage,created,updated,blob) VALUES(?,?,?,?,?) "
            "ON CONFLICT(client_id) DO UPDATE SET stage=excluded.stage, updated=excluded.updated, blob=excluded.blob",
            (record["client_id"], record["stage"], record["created"], record["updated"], _encrypt(record)),
        )
    return record


def update_existing(record: dict) -> bool:
    """Write ONLY if the row still exists (never resurrects an erased record).
    Returns True if a row was updated, False if the client was erased meanwhile."""
    record["updated"] = _now()
    with _LOCK, closing(_conn()) as c, c:
        cur = c.execute(
            "UPDATE records SET stage=?, updated=?, blob=? WHERE client_id=?",
            (record["stage"], record["updated"], _encrypt(record), record["client_id"]),
        )
    return cur.rowcount > 0


def ensure(client_id: str) -> dict:
    rec = get(client_id)
    if rec is None:
        rec = _empty(client_id)
        upsert(rec)
    return rec


def set_stage(client_id: str, stage: str, force: bool = False) -> dict:
    """Advance the journey stage. Automatic calls never move a record backwards;
    staff can pass force=True to correct a stage explicitly."""
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}")
    rec = ensure(client_id)
    cur_ix = stage_index(rec.get("stage", ""))
    if force or STAGES.index(stage) >= cur_ix:
        rec["stage"] = stage
    return upsert(rec)


def list_records() -> list[dict]:
    """Lightweight list for the console (no health payload decrypted)."""
    with _LOCK, closing(_conn()) as c, c:
        rows = c.execute(
            "SELECT client_id,stage,created,updated FROM records ORDER BY updated DESC"
        ).fetchall()
    return [
        {"client_id": r[0], "stage": r[1], "created": r[2], "updated": r[3]} for r in rows
    ]


def delete(client_id: str) -> bool:
    """GDPR erasure — removes the encrypted record entirely."""
    with _LOCK, closing(_conn()) as c, c:
        cur = c.execute("DELETE FROM records WHERE client_id=?", (client_id,))
    return cur.rowcount > 0


def stage_index(stage: str) -> int:
    return STAGES.index(stage) if stage in STAGES else -1


# ---------- anonymous funnel events (dashboard KPIs) ----------
# Events carry NO personal data — only what happened, when, and business meta
# (package key, amount). They survive GDPR erasure so the KPIs stay truthful.
_EVENTS_INIT = False


def _events_conn() -> sqlite3.Connection:
    global _EVENTS_INIT
    c = sqlite3.connect(_DB, timeout=15)
    c.execute("PRAGMA busy_timeout=15000")
    if not _EVENTS_INIT:
        c.execute("CREATE TABLE IF NOT EXISTS events(ts TEXT NOT NULL, event TEXT NOT NULL, meta TEXT)")
        c.commit()
        _EVENTS_INIT = True
    return c


def log_event(event: str, **meta) -> None:
    with _LOCK, closing(_events_conn()) as c, c:
        c.execute("INSERT INTO events(ts,event,meta) VALUES(?,?,?)",
                  (_now(), event, json.dumps(meta, ensure_ascii=False)))


def list_events(since: str = "") -> list[dict]:
    with _LOCK, closing(_events_conn()) as c, c:
        rows = c.execute("SELECT ts,event,meta FROM events WHERE ts>=? ORDER BY ts", (since,)).fetchall()
    out = []
    for r in rows:
        try:
            m = json.loads(r[2]) if r[2] else {}
        except Exception:
            m = {}
        out.append({"ts": r[0], "event": r[1], **m})
    return out
