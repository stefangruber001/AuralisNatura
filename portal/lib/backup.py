"""Scheduled backup of the encrypted backbone + client logins.

The backbone (auralis.db) is already Fernet-encrypted, so the copy is encrypted
at rest. Backups go to a directory OUTSIDE the git repo (config: AURALIS_BACKUP_DIR
/ config.backup_dir) so `git reset --hard` in the self-updating launcher can never
reach them. Uses SQLite's online backup API so a consistent snapshot is taken even
while the server is writing (WAL-safe). Rotates to the newest `backup_keep`.
"""
from __future__ import annotations
import os, sqlite3, shutil, threading, time, datetime as _dt
from pathlib import Path
from . import cfg, store

_STARTED = False


def _dir() -> Path | None:
    d = os.environ.get("AURALIS_BACKUP_DIR") or cfg.config().get("backup_dir") or ""
    if not d:
        return None
    p = Path(d).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def backup_now() -> dict:
    d = _dir()
    if not d:
        return {"backup": "skipped — no AURALIS_BACKUP_DIR configured"}
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = d / f"auralis-{ts}"
    out.mkdir(exist_ok=True)
    # consistent snapshot of the encrypted DB via the online backup API
    if store._DB.exists():
        with sqlite3.connect(store._DB) as src, sqlite3.connect(out / "auralis.db") as dst:
            src.backup(dst)
    # client logins (PII, needed to restore access; git-ignored at source)
    cj = cfg.CONFIG_DIR / "clients.json"
    if cj.exists():
        shutil.copy2(cj, out / "clients.json")
    _rotate(d)
    return {"backup": f"written to {out}"}


def _rotate(d: Path) -> None:
    keep = int(cfg.config().get("backup_keep", 48))
    snaps = sorted((p for p in d.glob("auralis-*") if p.is_dir()), reverse=True)
    for old in snaps[keep:]:
        shutil.rmtree(old, ignore_errors=True)


def start_scheduler() -> None:
    """Start a daemon thread that backs up every backup_interval_hours."""
    global _STARTED
    if _STARTED or not _dir():
        return
    _STARTED = True
    hours = float(cfg.config().get("backup_interval_hours", 1) or 1)

    def loop():
        while True:
            try:
                backup_now()
            except Exception:  # pragma: no cover - never let backups crash the server
                pass
            time.sleep(max(300, int(hours * 3600)))

    threading.Thread(target=loop, daemon=True).start()
