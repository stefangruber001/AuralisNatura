"""Import this FIRST in every test that touches storage. No exceptions.

History, so nobody relaxes this: the test suite used to delete `auralis.db`
and overwrite `config/clients.json` in place — fine on the throwaway machine
it was written on, catastrophic anywhere real data lives. On 2026-08-10 a
routine suite run silently destroyed the simulation specimens (four client
records, their sessions and bookings); on the production server the same run
would have destroyed real client data. Tests never touch live storage again:

* `store._DB` is redirected to a fresh temp database BEFORE any module opens
  a connection — every table (records, bookings, events) lands there.
* The mutable config files are snapshotted at import and restored at exit,
  so a test may overwrite `clients.json` freely and the real one survives.

Usage — the first thing after setting sys.path to the portal root:

    import _sandbox  # noqa: F401
"""
from __future__ import annotations
import atexit
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import store, cfg  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="auralis-test-"))
_LIVE_DB = store._DB
store._DB = _TMP / "test.db"
assert store._DB != _LIVE_DB and "auralis-test-" in str(store._DB), \
    "sandbox failed to redirect the database"

# .eml audit copies, PDFs, .ics files — everything a run produces goes to the
# temp dir too, so tests can never delete a real client's kept documents.
cfg.OUTPUT_DIR = _TMP / "output_docs"
cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_CONFIG = ROOT / "config"
_SHIELDED = ("clients.json", "availability.json", "plan.json", "social.json")
_SAVED: dict[str, bytes | None] = {}
for _name in _SHIELDED:
    _p = _CONFIG / _name
    _SAVED[_name] = _p.read_bytes() if _p.exists() else None


def _restore() -> None:
    for name, data in _SAVED.items():
        p = _CONFIG / name
        if data is None:
            p.unlink(missing_ok=True)
        else:
            p.write_bytes(data)
    shutil.rmtree(_TMP, ignore_errors=True)


atexit.register(_restore)
