#!/usr/bin/env python3
"""Restore the Auralis backbone + client logins from a backup snapshot.

Usage:
  python3 tools/restore.py --list                 # list available snapshots
  python3 tools/restore.py --latest               # restore the newest snapshot
  python3 tools/restore.py <snapshot-dir>         # restore a specific snapshot

Restores auralis.db (encrypted health store) and config/clients.json. The server
should be stopped first. A safety copy of the current DB is made before overwriting.
"""
import sys, os, shutil, datetime as _dt
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib import cfg, backup, store  # noqa


def snapshots():
    d = backup._configured()
    if not d or not d.exists():
        return []
    return sorted((p for p in d.glob("auralis-*") if p.is_dir()), reverse=True)


def restore(snap: Path):
    if not snap.exists():
        sys.exit(f"snapshot not found: {snap}")
    if store._DB.exists():                      # safety copy of current state
        ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        shutil.copy2(store._DB, store._DB.with_name(f"auralis.pre-restore-{ts}.db"))
    if (snap / "auralis.db").exists():
        for sfx in ("", "-wal", "-shm"):        # clear stale WAL/shm before restore
            p = Path(str(store._DB) + sfx)
            p.exists() and p.unlink()
        shutil.copy2(snap / "auralis.db", store._DB)
    if (snap / "clients.json").exists():
        shutil.copy2(snap / "clients.json", cfg.CONFIG_DIR / "clients.json")
    print(f"restored from {snap}")


if __name__ == "__main__":
    args = sys.argv[1:]
    snaps = snapshots()
    if not args or args[0] == "--list":
        if not snaps:
            print("No snapshots found. Set AURALIS_BACKUP_DIR and let the server back up.")
        for s in snaps:
            print(s)
    elif args[0] == "--latest":
        if not snaps:
            sys.exit("no snapshots to restore")
        restore(snaps[0])
    else:
        restore(Path(args[0]))
