"""Import this FIRST in every test that touches storage. No exceptions.

History, so nobody relaxes this: the test suite used to delete `auralis.db`
and overwrite `config/clients.json` in place — fine on the throwaway machine
it was written on, catastrophic anywhere real data lives. On 2026-08-10 a
routine suite run silently destroyed the simulation specimens (four client
records, their sessions and bookings); on the production server the same run
would have destroyed real client data. Tests never touch live storage again:

* `store._DB` is redirected to a fresh temp database BEFORE any module opens
  a connection — every table (records, bookings, events) lands there.
* `cfg.CONFIG_DIR` is redirected to a temp COPY of `config/`, so a test writes
  its own throwaway `clients.json` and the live files are never opened for
  writing at all.

The redirect replaced an earlier snapshot-and-restore-at-exit scheme, which
had a hole: `atexit` does not run when a process is killed. Interrupting a
slow test — a timeout, a Ctrl-C — left the founder's live `social.json`
holding whatever the test had just written. That happened on 2026-08-16 while
chasing a slow reel encode; the cadence and weekly objective had to be put
back by hand. Restore-after-the-fact cannot survive SIGKILL; not writing to
the file in the first place can.

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

_LIVE_CONFIG = ROOT / "config"
_TMP_CONFIG = _TMP / "config"
# Copy the whole directory: tests need the *.example.json seeds and any real
# values they read, they just must not write back to the originals.
shutil.copytree(_LIVE_CONFIG, _TMP_CONFIG)
cfg.CONFIG_DIR = _TMP_CONFIG
#: tests that need to seed a config file directly must write HERE, never
#: into ROOT/"config" — that is the live directory.
CONFIG = _TMP_CONFIG

# A test must never depend on the shipped mail mode. When email_mode moved from
# "off" to "draft" for production, test_e2e started failing on an IMAP call it
# never meant to make — the suite was silently asserting a production setting.
# Pin the sandbox to "off": mails are built and written as .eml (which is what
# the tests inspect) and no test ever opens a network connection by accident.
# A test that specifically exercises draft/send sets the mode itself.
import json as _json  # noqa: E402
_cfg_file = _TMP_CONFIG / "config.json"
if _cfg_file.exists():
    _c = _json.loads(_cfg_file.read_text(encoding="utf-8"))
    _c["email_mode"] = "off"
    _cfg_file.write_text(_json.dumps(_c, ensure_ascii=False, indent=2), encoding="utf-8")
    cfg.config.cache_clear()
assert cfg.CONFIG_DIR != _LIVE_CONFIG and "auralis-test-" in str(cfg.CONFIG_DIR), \
    "sandbox failed to redirect the config directory"

# Belt and braces: if some future code path resolves a live config file anyway,
# put it back on a clean exit. The redirect above is what holds under a kill.
_SHIELDED = ("clients.json", "availability.json", "plan.json", "social.json",
             "push_tokens.json")
_SAVED: dict[str, bytes | None] = {}
for _name in _SHIELDED:
    _p = _LIVE_CONFIG / _name
    _SAVED[_name] = _p.read_bytes() if _p.exists() else None


def _restore() -> None:
    for name, data in _SAVED.items():
        p = _LIVE_CONFIG / name
        if data is None:
            p.unlink(missing_ok=True)
        elif not p.exists() or p.read_bytes() != data:
            p.write_bytes(data)
    shutil.rmtree(_TMP, ignore_errors=True)


atexit.register(_restore)
