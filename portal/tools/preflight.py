#!/usr/bin/env python3
"""preflight.py — the single honest answer to "is this Auralis install healthy?"

WHERE IT RUNS
  Anywhere, from any cwd, on Mac or Linux: on Desiree's MacBook before a
  migration (migrate_to_server.sh runs it first and refuses to continue if it
  is red), on the Hetzner server after one (verify_server.sh runs it inside the
  venv as the `auralis` user and folds the results in), or by hand at 23:00
  when something feels wrong.

WHY IT EXISTS
  Every incident this project has actually had was a *silent* degradation that
  only surfaced later, in front of a client:
    • July: one record was encrypted with a throwaway `.dev_data.key` while the
      server ran the env key — every staff console read 500'd. `store.
      key_matches_store()` exists for exactly this, and the `store_key` check
      below is the single most important line in this whole deploy kit.
    • `render.to_pdf()` quietly writes a .html when it finds no Chrome — the
      12-page premium PDF is simply gone, and nothing says so.
    • `agent.draft_report()` quietly falls back to the offline "stub" writer
      when `claude` is missing or unauthenticated — boiler-plate reports going
      out under a scientist's name.
    • a stale process holding port 5056 answered with the WRONG data.
  So this file never *assumes*. It PROVES: it renders a real PDF with the real
  chromium, it runs a real `claude -p`, it opens the real store with the real
  key, and it says so in words an operator can act on.

IT IS NOT A REIMPLEMENTATION
  Every check drives the portal's own modules — lib.cfg, lib.store, lib.render,
  lib.backup, lib.agent, lib.mailer — so it can never drift from what the
  running server actually does. Where a portal function has a *write* side
  effect (cfg.clients() seeds clients.json, backup._dir() creates the backup
  dir, store._conn() creates auralis.db), preflight deliberately probes the
  filesystem first and skips rather than mutate the box it is inspecting.

SECRETS
  Never printed. Secrets are reported as `len=NN sha256:xxxxxxxx` — enough to
  compare the Mac and the server at a glance, useless to an attacker.

CLI
  python3 tools/preflight.py                      human report + PASS/WARN/FAIL summary
  python3 tools/preflight.py --json               machine contract (schema below)
  python3 tools/preflight.py --net                additionally log in to SMTP + IMAP
  python3 tools/preflight.py --no-agent --no-pdf  skip the two slow round-trips
  python3 tools/preflight.py --env-file /etc/auralis/portal.env
  python3 tools/preflight.py --strict             exit 1 on WARN as well as FAIL

EXIT CODE
  0 only when no check FAILed (with --strict: only when everything PASSed).

--json SCHEMA (the contract other scripts code against — do not break it)
  {
    "ok":     bool,              # true iff no check has severity "fail"
    "checks": [ {"name":     str,                    # stable, snake_case
                 "ok":       bool,                   # severity != "fail"
                 "detail":   str,                    # one actionable line
                 "severity": "ok"|"warn"|"fail"} ],
    "summary":   {"pass": int, "warn": int, "fail": int},
    "env":       "production"|"development",
    "host":      str,            # hostname, for telling Mac and server apart
    "portal":    str,            # absolute path of the portal/ dir inspected
    "generated": str             # UTC ISO-8601 timestamp
  }
  Only `ok` and `checks[*]` are guaranteed; the rest is additive context.
  IMPORTANT: in --json mode stdout carries the JSON document and NOTHING else
  (callers do raw.find("{") + json.loads(raw[start:]) on a 2>&1 capture).

IMPORTABLE
  from tools.preflight import run_checks
  result = run_checks(net=False, agent=True, pdf=True)   # -> the dict above
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import hashlib
import io
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# portal/ — resolved from THIS file, never from the cwd, because preflight is
# run from a staging dir, from systemd, and from a double-clicked Terminal.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OK, WARN, FAIL = "ok", "warn", "fail"
_RANK = {OK: 0, WARN: 1, FAIL: 2}

# Secrets that mean "nobody has configured this yet". Mirrors cfg._DEV_DEFAULTS
# but is kept local so preflight still works when lib.cfg cannot be imported.
_PLACEHOLDERS = {"dev-staff-key-change-me", "dev-secret-change-me",
                 "REPLACE_WITH_A_LONG_RANDOM_STRING", "change-me",
                 "change-me-to-a-long-random-string",
                 "change-me-to-another-long-random-string"}

_PDF_PROBE_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Auralis preflight</title>
<style>@page{size:A4;margin:14mm}body{font-family:Georgia,serif;color:#3D2719}</style>
</head><body><h1>Auralis Natura — preflight</h1>
<p>If this is a PDF, headless Chromium can produce the 12-page client report.</p>
</body></html>"""


# ─────────────────────────────────────────────────────────────── small helpers ──
def _fp(value) -> str:
    """Fingerprint a secret: length + 8 hex of sha256. NEVER the value itself.

    8 hex chars of a hash of a 32-byte key is not invertible, but it IS enough
    to answer the only question that matters during a migration: "is the key on
    the server the same one that encrypted the database on the Mac?"
    """
    if value is None:
        return "absent"
    b = value.encode("utf-8", "replace") if isinstance(value, str) else bytes(value)
    if not b:
        return "empty"
    return f"len={len(b)} sha256:{hashlib.sha256(b).hexdigest()[:8]}"


def _ver(s: str) -> tuple:
    """Leading numeric components of a version string ('3.1.0rc1' -> (3,1,0))."""
    out = []
    for part in re.split(r"[^0-9]+", str(s)):
        if part:
            out.append(int(part))
        if len(out) == 3:
            break
    return tuple(out) or (0,)


def _age(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 90:
        return f"{seconds}s"
    if seconds < 5400:
        return f"{seconds // 60}m"
    if seconds < 172800:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def _size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n}B"


def _link(p: Path) -> str:
    """Describe a path including where a symlink points — the server keeps the
    live data OUTSIDE the worktree behind symlinks, and a BROKEN one is a
    catastrophic, easily-missed state."""
    try:
        if p.is_symlink():
            tgt = os.readlink(p)
            state = "→ ok" if p.exists() else "→ BROKEN"
            return f"{p} -> {tgt} ({state})"
    except OSError:
        pass
    return str(p)


def _writable(d: Path) -> tuple[bool, str]:
    """Prove writability by actually writing — os.access lies under ACLs, and
    root's os.access lies about everything."""
    try:
        d.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=str(d), prefix=".auralis-preflight-"):
            pass
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _http_json(url: str, timeout: float = 4.0):
    """Tiny GET → parsed JSON. urllib only: preflight must run on a box where
    the venv is broken, so it may not assume anything beyond the stdlib."""
    import urllib.request
    import urllib.error
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:      # noqa: S310
            body = r.read(65536).decode("utf-8", "replace")
            code = r.getcode()
    except urllib.error.HTTPError as e:
        return e.code, None, f"HTTP {e.code}"
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}"
    try:
        return code, json.loads(body), ""
    except Exception:
        return code, None, f"non-JSON body ({body[:60]!r})"


def load_env_file(path) -> tuple[list[str], list[str]]:
    """Load KEY=VALUE lines from an env file into os.environ.

    Mirrors systemd's `EnvironmentFile=` semantics on purpose: the FILE WINS
    over whatever happens to be in the calling shell, because the whole point
    of `--env-file /etc/auralis/portal.env` is to test exactly what
    auralis-portal.service will see — not what your ssh session inherited.

    Returns (names_loaded, malformed_lines). Values are never logged.
    """
    p = Path(path).expanduser()
    loaded: list[str] = []
    bad: list[str] = []
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            bad.append(raw[:40])
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            bad.append(raw[:40])
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        os.environ[key] = val
        loaded.append(key)
    return loaded, bad


# ───────────────────────────────────────────────────────── result collection ──
class Checks:
    """Ordered result accumulator. `ok` is derived, never set by hand: a WARN is
    ok=True so that callers (migrate_to_server.sh prints `ok`/`FAIL` per check)
    do not treat a cosmetic gripe as a stop-the-world failure."""

    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, name: str, severity: str, detail: str) -> None:
        detail = " ".join(str(detail).split())          # keep every check one line
        self.items.append({"name": name, "ok": severity != FAIL,
                           "detail": detail, "severity": severity})

    def counts(self) -> dict:
        c = {"pass": 0, "warn": 0, "fail": 0}
        for i in self.items:
            c[{OK: "pass", WARN: "warn", FAIL: "fail"}[i["severity"]]] += 1
        return c

    def as_dict(self, ctx) -> dict:
        counts = self.counts()
        return {
            "ok": counts["fail"] == 0,
            "checks": self.items,
            "summary": counts,
            "env": "production" if ctx.prod else "development",
            "host": socket.gethostname(),
            "portal": str(ROOT),
            "generated": _dt.datetime.now(_dt.timezone.utc)
                             .replace(microsecond=0).isoformat(),
        }


class Ctx:
    """Everything the individual checks share: options, imported portal modules
    and the production flag (which decides WARN vs FAIL almost everywhere)."""

    def __init__(self, net=False, agent=True, pdf=True, timeout=25.0, env_file=None):
        self.net = net
        self.agent = agent
        self.pdf = pdf
        self.timeout = float(timeout)
        self.env_file = env_file
        self.env_loaded: list[str] = []
        self.env_bad: list[str] = []
        self.mods: dict = {}          # name -> module (only successful imports)
        self.errors: dict = {}        # name -> import error string
        # Fallback copy of cfg.is_production() for the case where lib.cfg itself
        # will not import — the severity model must still work.
        self.prod = os.environ.get("AURALIS_ENV", "").lower() in ("production", "prod")

    def sev(self, prod_is_fatal: bool = True) -> str:
        """FAIL in production, WARN on a dev box — the common severity rule."""
        if self.prod and prod_is_fatal:
            return FAIL
        return WARN

    def mod(self, name: str):
        return self.mods.get(name)


def _need(ck: Checks, ctx: Ctx, name: str, *mods: str) -> bool:
    """Guard for a check that needs portal modules. Emits one FAIL and returns
    False when they are missing, so no check ever explodes on a NameError."""
    missing = [m for m in mods if m not in ctx.mods]
    if missing:
        why = ctx.errors.get(missing[0], "not imported")[:120]
        ck.add(name, FAIL, f"cannot run — lib.{'/lib.'.join(missing)} did not import ({why}). "
                           "See the portal_modules check.")
        return False
    return True


def _config(ck: Checks, ctx: Ctx, name: str):
    """cfg.config() or a clean FAIL. Half the checks read config.json, so a
    corrupt one must be reported as "this file is corrupt" — once per check, in
    plain words — and never as six identical "the check crashed" tracebacks."""
    try:
        return ctx.mods["cfg"].config()
    except Exception as e:
        ck.add(name, FAIL, f"{ROOT / 'config' / 'config.json'} is not readable/parseable "
                           f"({type(e).__name__}: {e}) — the server cannot start at all "
                           "until this file parses")
        return None


# The three paths that live OUTSIDE the git worktree on the server and are
# reached by symlink, so `git reset --hard` in auralis-update.service cannot
# touch them. A broken one is silent and catastrophic.
_DATA_PATHS = (
    ("auralis.db", "/var/lib/auralis/auralis.db", "the encrypted health store"),
    ("config/clients.json", "/var/lib/auralis/clients.json", "client logins + consent"),
    ("output_docs", "/var/lib/auralis/output_docs", "reports + the .eml audit trail"),
)


# ──────────────────────────────────────────────────────────────────── checks ──
def check_python(ck: Checks, ctx: Ctx) -> None:
    v = sys.version_info
    where = f"{platform.python_version()} at {sys.executable} " \
            f"({platform.system()} {platform.release()} {platform.machine()})"
    venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    where += " [venv]" if venv else " [system python]"
    if v < (3, 9):
        ck.add("python", FAIL, f"{where} — the portal needs Python 3.9+ "
                               "(lib/* use PEP 604 `X | None` annotations)")
    elif v < (3, 10):
        ck.add("python", WARN, f"{where} — 3.9 works but 3.11+ is what the server runs; "
                               "keep Mac and server on the same major/minor when you can")
    else:
        ck.add("python", OK, where)


def check_paths(ck: Checks, ctx: Ctx) -> None:
    """Symlink integrity, using nothing but the filesystem.

    Runs BEFORE any portal import on purpose: lib/cfg.py calls
    OUTPUT_DIR.mkdir() at module scope, so a broken output_docs symlink makes
    every single import below fail with a FileExistsError that names the symptom
    and hides the cause. This check names the cause first.
    """
    broken, notes = [], []
    for rel, expected, what in _DATA_PATHS:
        p = ROOT / rel
        if p.is_symlink():
            target = os.readlink(p)
            if p.exists():
                notes.append(f"{rel} -> {target}")
            else:
                broken.append(f"{rel} -> {target} (target missing — {what} is unreachable)")
        elif p.exists():
            notes.append(f"{rel} (real {'dir' if p.is_dir() else 'file'}, not a symlink)")
        else:
            notes.append(f"{rel} (absent)")
    if broken:
        ck.add("paths", FAIL,
               "BROKEN SYMLINK(S): " + "; ".join(broken) +
               ". On the server these must point into /var/lib/auralis (" +
               ", ".join(e for _, e, _ in _DATA_PATHS) + "). A broken output_docs link also "
               "breaks every `import lib.*` below, because cfg.py mkdirs it at import time.")
    else:
        ck.add("paths", OK, " · ".join(notes))


def check_dependencies(ck: Checks, ctx: Ctx) -> None:
    """flask + cryptography are the ENTIRE dependency list (requirements.txt).
    On the server they must come from /opt/auralis/venv, not the system python."""
    for pkg, minimum, why in (("flask", (3, 0), "server/app.py"),
                              ("cryptography", (41,), "lib/store.py Fernet encryption")):
        try:
            mod = __import__(pkg)
        except Exception as e:
            ck.add(pkg, FAIL, f"NOT importable ({type(e).__name__}: {e}) — {why} cannot run. "
                              f"Fix: pip install -r {ROOT / 'requirements.txt'}")
            continue
        # importlib.metadata first: Flask 3.1 deprecates __version__ and emits a
        # DeprecationWarning on stderr, which would pollute a --json capture.
        try:
            from importlib import metadata
            version = metadata.version(pkg)
        except Exception:
            version = getattr(mod, "__version__", "") or "unknown"
        loc = getattr(mod, "__file__", "?")
        if version != "unknown" and _ver(version) < minimum:
            want = ".".join(str(x) for x in minimum)
            ck.add(pkg, WARN, f"{version} at {loc} — requirements.txt asks for >={want}")
        else:
            ck.add(pkg, OK, f"{version} at {loc}")


def check_portal_modules(ck: Checks, ctx: Ctx) -> None:
    """Import the portal's own modules. This is also the first real integrity
    test of the checkout: a broken output_docs symlink makes `import lib.cfg`
    raise at import time (cfg does OUTPUT_DIR.mkdir at module scope)."""
    for name in ("cfg", "store", "render", "backup", "agent", "mailer"):
        try:
            ctx.mods[name] = __import__(f"lib.{name}", fromlist=[name])
        except Exception as e:
            ctx.errors[name] = f"{type(e).__name__}: {e}"
    if "cfg" in ctx.mods:
        try:
            ctx.prod = bool(ctx.mods["cfg"].is_production())
        except Exception:
            pass
    if not ctx.errors:
        ck.add("portal_modules", OK,
               f"lib.cfg/store/render/backup/agent/mailer import cleanly from {ROOT}")
        return
    # One broken symlink fails all six imports with the identical message —
    # group by error so the operator reads one cause, not six symptoms.
    grouped: dict = {}
    for mod, err in ctx.errors.items():
        grouped.setdefault(err, []).append(f"lib.{mod}")
    parts = [f"{', '.join(mods)} ({err[:160]})" for err, mods in grouped.items()]
    hint = ""
    if any("output_docs" in e or "FileExistsError" in e for e in grouped):
        hint = (" HINT: lib/cfg.py runs OUTPUT_DIR.mkdir() at import time — a BROKEN "
                f"output_docs symlink raises exactly this. Fix {ROOT / 'output_docs'} first; "
                "see the paths check.")
    ck.add("portal_modules", FAIL, "cannot import " + " · ".join(parts) + "." + hint)


def check_env(ck: Checks, ctx: Ctx) -> None:
    if ctx.env_file:
        if ctx.env_bad:
            ck.add("env_file", WARN,
                   f"{ctx.env_file}: loaded {len(ctx.env_loaded)} variables "
                   f"({', '.join(ctx.env_loaded)}) but {len(ctx.env_bad)} line(s) are not "
                   f"KEY=VALUE and were ignored: {ctx.env_bad}")
        else:
            ck.add("env_file", OK, f"{ctx.env_file}: loaded {len(ctx.env_loaded)} variables "
                                   f"({', '.join(ctx.env_loaded) or 'none'})")
    raw = os.environ.get("AURALIS_ENV", "")
    if ctx.prod:
        ck.add("env", OK, f"AURALIS_ENV={raw!r} — PRODUCTION mode: cfg.validate_secrets() "
                          "fails closed on missing secrets and every gap below is fatal")
    elif raw:
        ck.add("env", WARN, f"AURALIS_ENV={raw!r} — not production, so secret gaps are only "
                            "warnings here. On the server this must be 'production'")
    else:
        ck.add("env", WARN, "AURALIS_ENV is unset — treating this as a dev box. On the server "
                            "/etc/auralis/portal.env must set AURALIS_ENV=production")


def check_secrets(ck: Checks, ctx: Ctx) -> None:
    """API key + signing secret. In production cfg.validate_secrets() is the
    authority (it also enforces require_api_key), so we call it rather than
    second-guess it."""
    if not _need(ck, ctx, "secrets", "cfg"):
        return
    cfg = ctx.mods["cfg"]
    c = _config(ck, ctx, "secrets")
    if c is None:
        return
    bits = []
    for env_name, key in (("AURALIS_API_KEY", "api_key"), ("AURALIS_SECRET", "secret_key")):
        val = str(c.get(key) or "")
        src = "env" if os.environ.get(env_name) else "config.json"
        if not val:
            bits.append(f"{key}=MISSING")
        elif val in _PLACEHOLDERS:
            bits.append(f"{key}=PLACEHOLDER ({src})")
        else:
            bits.append(f"{key}={_fp(val)} ({src})")
    bits.append(f"require_api_key={c.get('require_api_key')}")
    detail = " · ".join(bits)
    if ctx.prod:
        try:
            cfg.validate_secrets()
        except Exception as e:
            ck.add("secrets", FAIL, f"{detail} — cfg.validate_secrets() REFUSES to start the "
                                    f"server: {e}")
            return
        ck.add("secrets", OK, f"{detail} — cfg.validate_secrets() passes")
    elif any("PLACEHOLDER" in b or "MISSING" in b for b in bits):
        ck.add("secrets", WARN, f"{detail} — fine on a dev box; production refuses to start "
                                "with these (set them in /etc/auralis/portal.env)")
    else:
        ck.add("secrets", OK, detail)


def check_data_key(ck: Checks, ctx: Ctx) -> None:
    """AURALIS_DATA_KEY itself — presence and shape. Whether it actually OPENS
    the store is the next check, and is the more important one."""
    if not _need(ck, ctx, "data_key", "cfg"):
        return
    cfg = ctx.mods["cfg"]
    raw = (os.environ.get("AURALIS_DATA_KEY") or "").strip()
    devfile = ROOT / ".dev_data.key"
    if not raw:
        if ctx.prod:
            ck.add("data_key", FAIL,
                   "AURALIS_DATA_KEY is NOT set and AURALIS_ENV=production — cfg.data_key() "
                   "raises and the server refuses to start. Set it in /etc/auralis/portal.env "
                   "to the SAME key that encrypted the database.")
        elif devfile.exists():
            ck.add("data_key", WARN,
                   f"AURALIS_DATA_KEY unset — falling back to the dev key file {devfile} "
                   f"({_fp(devfile.read_bytes().strip())}). NEVER let this happen next to "
                   "production data: that mix-up is the July 500-storm.")
        else:
            ck.add("data_key", WARN,
                   f"AURALIS_DATA_KEY unset and no {devfile} yet — the first run would MINT a "
                   "throwaway key. Set the real key before touching real data.")
        return
    # Shape: a real Fernet key, or a passphrase cfg._derive()s into one.
    shape = "unknown"
    try:
        from cryptography.fernet import Fernet
        try:
            Fernet(raw.encode())
            shape = "valid 44-char Fernet key"
        except Exception:
            shape = ("a PASSPHRASE — cfg.data_key() derives the real key via sha256, which "
                     "works, but then the exact same string must be set on every host")
    except Exception:
        shape = "cannot be classified (cryptography not importable)"
    try:
        effective = cfg.data_key()
        eff = f" · effective key {_fp(effective)}"
    except Exception as e:
        ck.add("data_key", FAIL, f"AURALIS_DATA_KEY set ({_fp(raw)}) but cfg.data_key() "
                                 f"raised {type(e).__name__}: {e}")
        return
    sev = WARN if shape.startswith("a PASSPHRASE") else OK
    ck.add("data_key", sev, f"AURALIS_DATA_KEY set ({_fp(raw)}), {shape}{eff}")


def check_store_key(ck: Checks, ctx: Ctx) -> None:
    """★ THE CHECK THIS KIT EXISTS FOR ★

    store.key_matches_store() answers: does the key we are running with actually
    decrypt the data on disk? False means every staff console read 500s. This is
    the July incident, and migrate_to_server.sh must never cut the tunnel over
    while this is red.
    """
    if not _need(ck, ctx, "store_key", "store"):
        return
    store = ctx.mods["store"]
    db = Path(store._DB)
    # Do NOT call key_matches_store() when there is no database: store._conn()
    # would CREATE an empty one (as root, with root ownership, on a server where
    # the file must be a symlink into /var/lib/auralis). Inspecting a box must
    # never change it.
    if not db.exists():
        ck.add("store_key", WARN,
               f"no database at {_link(db)} — nothing to decrypt yet (fresh install). "
               "Skipped on purpose: probing would create an empty store.")
        return
    if db.stat().st_size == 0:
        ck.add("store_key", WARN, f"{db} exists but is 0 bytes — an empty/aborted store")
        return
    # If NO key is configured at all, probing would make cfg.data_key() MINT a
    # throwaway .dev_data.key — inspecting the box would change it, and the
    # answer would be a guaranteed, meaningless mismatch. Refuse instead.
    if not os.environ.get("AURALIS_DATA_KEY") and not (ROOT / ".dev_data.key").exists():
        ck.add("store_key", FAIL,
               f"{db} holds data but NO key is configured — AURALIS_DATA_KEY is unset and there "
               "is no .dev_data.key. Not probing: cfg.data_key() would mint a fresh key and the "
               "mismatch would be guaranteed. Set the key that encrypted this store.")
        return
    try:
        result = store.key_matches_store()
    except Exception as e:
        # key_matches_store() re-raises whatever cfg.data_key() raises (e.g. the
        # production "AURALIS_DATA_KEY must be set" RuntimeError), so this is a
        # real, reachable state — not defensive padding.
        ck.add("store_key", FAIL, f"could not probe the store: {type(e).__name__}: {e}")
        return
    try:
        n = len(store.list_records())
    except Exception:
        n = -1
    count = f"{n} record(s)" if n >= 0 else "record count unavailable"
    if result is True:
        ck.add("store_key", OK, f"AURALIS_DATA_KEY OPENS the store — {count} in {db}")
    elif result is False:
        ck.add("store_key", FAIL,
               f"KEY MISMATCH — the active AURALIS_DATA_KEY canNOT decrypt {db} ({count}). "
               "Every staff console read would 500. Do NOT overwrite the store and do NOT "
               "let this host serve: restore the key that encrypted this data "
               "(tools/restore.py has the snapshots; see CLAUDE.md, July incident).")
    else:
        ck.add("store_key", FAIL,
               f"store.key_matches_store() returned None — {db} could not be read at all "
               "(corrupt file, wrong permissions, or not a SQLite database).")


def check_database(ck: Checks, ctx: Ctx) -> None:
    if not _need(ck, ctx, "database", "store"):
        return
    db = Path(ctx.mods["store"]._DB)
    if db.is_symlink() and not db.exists():
        ck.add("database", FAIL,
               f"BROKEN SYMLINK {_link(db)} — the live data is unreachable. On the server "
               "portal/auralis.db must point at /var/lib/auralis/auralis.db.")
        return
    if not db.exists():
        ck.add("database", WARN, f"{db} does not exist yet — created on first write")
        return
    st = db.stat()
    parts = [_link(db), _size(st.st_size),
             f"modified {_age(time.time() - st.st_mtime)} ago"]
    wal = Path(str(db) + "-wal")
    shm = Path(str(db) + "-shm")
    if wal.exists():
        parts.append(f"WAL {_size(wal.stat().st_size)}" + (" (+shm)" if shm.exists() else ""))
    else:
        parts.append("no WAL file (nothing has written since the last clean close)")
    ok_read = os.access(db, os.R_OK)
    ok_write = os.access(db, os.W_OK)
    parts.append("rw" if (ok_read and ok_write) else ("read-only" if ok_read else "UNREADABLE"))
    detail = " · ".join(parts)
    if not ok_read:
        ck.add("database", FAIL, detail + " — the service user cannot read the store")
    elif not ok_write:
        ck.add("database", FAIL, detail + " — the service user cannot WRITE; every intake, "
                                          "note and stage change would fail")
    else:
        ck.add("database", OK, detail)


def check_clients_json(ck: Checks, ctx: Ctx) -> None:
    """clients.json holds the portal logins + consent flags. It is gitignored
    and on the server it is a symlink into /var/lib/auralis, so a broken link
    silently locks every client out."""
    if not _need(ck, ctx, "clients_json", "cfg"):
        return
    p = Path(ctx.mods["cfg"].CONFIG_DIR) / "clients.json"
    if p.is_symlink() and not p.exists():
        ck.add("clients_json", FAIL,
               f"BROKEN SYMLINK {_link(p)} — every client login and consent record is "
               "unreachable. Point it at /var/lib/auralis/clients.json.")
        return
    if not p.exists():
        # cfg.clients() would SEED the file here; don't — an empty seed next to a
        # populated store is exactly how you lose everyone's login.
        ck.add("clients_json", WARN,
               f"{p} does not exist — cfg.clients() seeds it from clients.example.json on "
               "first use. Expected on a fresh box, ALARMING on a live one.")
        return
    try:
        data = ctx.mods["cfg"].clients()
    except Exception as e:
        ck.add("clients_json", FAIL, f"{_link(p)} is not parseable JSON: "
                                     f"{type(e).__name__}: {e} — every login is down")
        return
    clients = data.get("clients", {}) if isinstance(data, dict) else {}
    with_pw = sum(1 for v in clients.values() if isinstance(v, dict) and v.get("password"))
    langs = sorted({(v.get("language") or "?") for v in clients.values() if isinstance(v, dict)})
    ck.add("clients_json", OK,
           f"{_link(p)} · {len(clients)} client(s), {with_pw} with a password set · "
           f"languages {','.join(langs) or 'none'} · {_size(p.stat().st_size)}")


def check_output_docs(ck: Checks, ctx: Ctx) -> None:
    """Every generated report and .eml audit copy lands here. On the server it
    is a symlink into /var/lib/auralis/output_docs so `git reset --hard` in the
    update timer cannot reach it."""
    if not _need(ck, ctx, "output_docs", "cfg"):
        return
    d = Path(ctx.mods["cfg"].OUTPUT_DIR)
    if d.is_symlink() and not d.exists():
        ck.add("output_docs", FAIL, f"BROKEN SYMLINK {_link(d)} — reports and .eml audit "
                                    "copies have nowhere to go")
        return
    if not d.exists():
        ck.add("output_docs", WARN, f"{d} does not exist yet")
        return
    ok, why = _writable(d)
    files = sum(1 for _ in d.rglob("*") if _.is_file())
    detail = f"{_link(d)} · {files} file(s)"
    if ok:
        ck.add("output_docs", OK, detail + " · writable")
    else:
        ck.add("output_docs", FAIL, f"{detail} · NOT writable ({why}) — report rendering "
                                    "and the .eml audit trail would fail")


def check_chromium(ck: Checks, ctx: Ctx) -> None:
    """Prove the 12-page PDF end-to-end.

    render.to_pdf() falls back to writing .html when Chrome is missing OR when
    the PDF simply does not appear — a silent degradation that costs the whole
    premium deliverable. So we do not merely resolve a binary: we render, and
    we check the magic bytes.
    """
    if not _need(ck, ctx, "chromium", "render"):
        return
    render = ctx.mods["render"]
    chrome = render._chrome()
    if not chrome:
        tried = [c for c in render._CHROME_CANDIDATES if c]
        ck.add("chromium", ctx.sev(),
               "NO Chrome/Chromium found — render.to_pdf() would silently write .html and the "
               "12-page PDF would be lost. Tried: " + ", ".join(tried) +
               ". Fix: apt-get install -y chromium (or set AURALIS_CHROME=/abs/path).")
        return
    src = "AURALIS_CHROME" if os.environ.get("AURALIS_CHROME") == chrome else "candidate list"
    if not ctx.pdf:
        ck.add("chromium", WARN, f"{chrome} (from {src}) — resolved but NOT tested (--no-pdf)")
        return
    tmp = Path(tempfile.mkdtemp(prefix="auralis-preflight-"))
    try:
        t0 = time.monotonic()
        try:
            out = Path(render.to_pdf(_PDF_PROBE_HTML, tmp / "preflight.pdf"))
        except Exception as e:
            ck.add("chromium", ctx.sev(), f"{chrome} — render.to_pdf() raised "
                                          f"{type(e).__name__}: {e}")
            return
        dt = time.monotonic() - t0
        if out.suffix != ".pdf" or not out.exists():
            rc, tail = _chrome_diagnostic(chrome)
            ck.add("chromium", ctx.sev(),
                   f"{chrome} did NOT produce a PDF — render.to_pdf() fell back to "
                   f"{out.name} after {dt:.1f}s. Client reports would go out as .html. "
                   f"chromium exit={rc}: {tail or 'no output'}")
            return
        blob = out.read_bytes()
        if not blob.startswith(b"%PDF-") or len(blob) < 800:
            ck.add("chromium", ctx.sev(),
                   f"{chrome} produced {out.name} but it is not a usable PDF "
                   f"({_size(len(blob))}, starts {blob[:8]!r})")
            return
        ck.add("chromium", OK, f"{chrome} (from {src}) rendered a real "
                               f"{_size(len(blob))} PDF in {dt:.1f}s")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_screenshot(ck: Checks, ctx: Ctx) -> None:
    """Chromium --screenshot probe: the social visual factory renders its post
    images this way, and the size must be EXACT (Instagram formats). Verified
    stdlib-only via the PNG IHDR (bytes 16-24 are width/height, big-endian)."""
    import struct
    sys.path.insert(0, str(PORTAL))
    from lib import render, socialrender
    chrome = render._chrome()
    if not chrome:
        ck.add("screenshot", ctx.sev(),
               "no chromium — social images will fall back to HTML files")
        return
    tmp = Path(tempfile.mkdtemp(prefix="auralis-shotprobe-"))
    try:
        out = tmp / "probe.png"
        html_text = "<!doctype html><body style='margin:0;background:#F5EEE0'>probe</body>"
        got = socialrender.to_png(html_text, out, 1080, 1350)
        if got.suffix != ".png" or not out.exists():
            ck.add("screenshot", ctx.sev(),
                   f"{chrome} did not produce a PNG (fallback {got.name}) — "
                   "social images degrade to HTML until this is fixed")
            return
        blob = out.read_bytes()
        if not blob.startswith(b"\x89PNG"):
            ck.add("screenshot", ctx.sev(), f"{out.name} is not a PNG ({blob[:8]!r})")
            return
        w, h = struct.unpack(">II", blob[16:24])
        if (w, h) != (1080, 1350):
            ck.add("screenshot", ctx.sev(),
                   f"screenshot came out {w}x{h}, expected 1080x1350 — "
                   "check --window-size support on this chromium build")
            return
        ck.add("screenshot", OK, f"{chrome} rendered an exact 1080x1350 PNG ({_size(len(blob))})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _chrome_diagnostic(chrome: str, timeout: float = 60.0) -> tuple:
    """Re-run render.py's EXACT chromium invocation with stderr captured, so the
    operator gets a reason ("Failed to create a ProfileDir", "cannot open
    display", missing shared library) instead of just "it fell back"."""
    tmp = Path(tempfile.mkdtemp(prefix="auralis-preflight-diag-"))
    try:
        src = tmp / "probe.html"
        src.write_text(_PDF_PROBE_HTML, encoding="utf-8")
        out = tmp / "probe.pdf"
        cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox",
               "--no-pdf-header-footer", f"--print-to-pdf={out}", f"file://{src}"]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        text = (p.stderr or "") + (p.stdout or "")
        tail = " / ".join(line.strip() for line in text.strip().splitlines()[-3:])
        return p.returncode, tail[:300]
    except subprocess.TimeoutExpired:
        return None, f"chromium did not exit within {timeout:.0f}s"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_agent(ck: Checks, ctx: Ctx) -> None:
    """Which report writer would this box ACTUALLY use?

    agent.draft_report() picks claude_cli only when the config says so AND
    `claude` is on PATH — and it catches every exception from the CLI and falls
    back to the offline "stub" writer. Both fallbacks are invisible in normal
    operation, so preflight reproduces the decision and then proves the CLI is
    not only present but authenticated.
    """
    if not _need(ck, ctx, "agent", "cfg", "agent"):
        return
    c = _config(ck, ctx, "agent")
    if c is None:
        return
    configured = str(c.get("agent_provider", "stub"))
    exe = shutil.which("claude")
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    # Only CLAUDE_CODE_OAUTH_TOKEN is a verified name (`claude setup-token`);
    # ANTHROPIC_API_KEY is reported as "also present" and never assumed to work.
    alt = "ANTHROPIC_API_KEY" if os.environ.get("ANTHROPIC_API_KEY") else ""
    creds = (f"CLAUDE_CODE_OAUTH_TOKEN {_fp(token)}" if token
             else "CLAUDE_CODE_OAUTH_TOKEN absent")
    if alt:
        creds += f" (+{alt} also set)"

    if configured != "claude_cli":
        ck.add("agent", ctx.sev(), f"agent_provider={configured!r} — reports would be the "
                                   "offline STUB boiler-plate, not real drafts. Set "
                                   f"AURALIS_AGENT_PROVIDER=claude_cli. ({creds})")
        return
    if not exe:
        ck.add("agent", ctx.sev(),
               f"agent_provider=claude_cli but `claude` is NOT on PATH — agent.draft_report() "
               f"silently uses the STUB writer. PATH begins {os.environ.get('PATH','')[:80]!r}. "
               f"Install the Claude Code CLI for this user. ({creds})")
        return
    if not ctx.agent:
        ck.add("agent", WARN, f"claude at {exe} — present but NOT round-tripped (--no-agent). "
                              f"Authentication unverified. ({creds})")
        return
    state, note = _claude_probe(exe, ctx.timeout)
    if state == "working":
        ck.add("agent", OK, f"claude at {exe} answered a real `claude -p` round-trip ({note}) "
                            f"— provider claude_cli is live. ({creds})")
    elif state == "unauthenticated":
        ck.add("agent", ctx.sev(),
               f"claude at {exe} is present but NOT AUTHENTICATED ({note}). agent.draft_report() "
               "catches this and falls back to the STUB writer. Fix: run `claude setup-token` "
               "ON THE MAC (it is interactive) and put the token in "
               f"/etc/auralis/portal.env as CLAUDE_CODE_OAUTH_TOKEN. ({creds})")
    else:
        ck.add("agent", ctx.sev(),
               f"claude at {exe} did not return a usable answer ({note}) — treat the provider "
               f"as STUB until this is green. ({creds})")


def _claude_probe(exe: str, timeout: float) -> tuple[str, str]:
    """One trivial `claude -p` round-trip. stdin is /dev/null so an
    unauthenticated CLI that wants to prompt fails fast instead of hanging."""
    t0 = time.monotonic()
    try:
        p = subprocess.run([exe, "-p", "Reply with exactly: OK", "--output-format", "text"],
                           capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return "error", f"no answer within {timeout:.0f}s"
    except Exception as e:
        return "error", f"{type(e).__name__}: {e}"
    dt = time.monotonic() - t0
    out = (p.stdout or "").strip()
    err = " ".join((p.stderr or "").split())[:200]
    if p.returncode == 0 and out:
        preview = out[:40].replace("\n", " ")
        return "working", f"{dt:.1f}s, replied {preview!r}"
    blob = f"{err} {out}".lower()
    if re.search(r"log ?in|logout|auth|token|credential|unauthor|api key|subscription|expired|"
                 r"invalid bearer|not signed in", blob):
        return "unauthenticated", f"exit {p.returncode}: {err or out[:120] or 'no output'}"
    return "error", f"exit {p.returncode} after {dt:.1f}s: {err or out[:120] or 'no output'}"


def check_email(ck: Checks, ctx: Ctx) -> None:
    """Credential presence only — mailer._imap_draft()/_smtp_send() return a
    quiet "skipped — no AURALIS_SMTP_PASSWORD set" string when it is missing, so
    nothing would be raised, logged or noticed."""
    if not _need(ck, ctx, "email", "cfg"):
        return
    c = _config(ck, ctx, "email")
    if c is None:
        return
    mode = str(c.get("email_mode", "off"))
    pw = os.environ.get("AURALIS_SMTP_PASSWORD", c.get("smtp_password", "") or "")
    user = c.get("smtp_user", "")
    where = (f"mode={mode} · user={user or 'UNSET'} · "
             f"smtp={c.get('smtp_host')}:{c.get('smtp_port')} · "
             f"imap={c.get('imap_host')}:{c.get('imap_port')} · "
             f"password={_fp(pw) if pw else 'ABSENT'}")
    if mode == "off":
        ck.add("email", WARN if ctx.prod else OK,
               f"{where} — email_mode=off means NO client mail is produced at all "
               "(the server should run AURALIS_EMAIL_MODE=draft)")
    elif not pw:
        ck.add("email", ctx.sev(),
               f"{where} — with email_mode={mode} every client mail would be silently "
               '"skipped — no AURALIS_SMTP_PASSWORD set". Set the Gmail App Password.')
    elif not user:
        ck.add("email", ctx.sev(), f"{where} — no smtp_user to log in as")
    else:
        ck.add("email", OK, where + (" (login not tested; pass --net to prove it)"
                                     if not ctx.net else ""))


def check_smtp_login(ck: Checks, ctx: Ctx) -> None:
    """--net only. A real STARTTLS + AUTH against Gmail."""
    if not ctx.net or not _need(ck, ctx, "smtp_login", "cfg"):
        return
    import smtplib
    c = _config(ck, ctx, "smtp_login")
    if c is None:
        return
    pw = os.environ.get("AURALIS_SMTP_PASSWORD", c.get("smtp_password", "") or "")
    user = c.get("smtp_user", "")
    host, port = c.get("smtp_host", "smtp.gmail.com"), int(c.get("smtp_port", 587))
    if not (pw and user):
        ck.add("smtp_login", WARN, f"skipped — no credentials for {host}:{port}")
        return
    try:
        s = smtplib.SMTP(host, port, timeout=20)
        s.starttls()
        s.login(user, pw)
        s.quit()
        ck.add("smtp_login", OK, f"{user} authenticated on {host}:{port} (STARTTLS)")
    except Exception as e:
        ck.add("smtp_login", FAIL, f"{user} could NOT log in to {host}:{port} — "
                                   f"{type(e).__name__}: {e}. For Gmail this is almost always "
                                   "an expired App Password.")


def check_imap_login(ck: Checks, ctx: Ctx) -> None:
    """--net only. Logs in AND checks the Drafts mailbox exists, because
    email_mode=draft APPENDs to it — if that folder is missing or named
    something else, every report mail vanishes with only a string in a dict to
    show. Resolved through mailer.drafts_mailbox() rather than a constant of our
    own, so this check can only pass when the code path it stands in for would."""
    # "mailer" too: the drafts folder is resolved by mailer.drafts_mailbox().
    if not ctx.net or not _need(ck, ctx, "imap_login", "cfg", "mailer"):
        return
    import imaplib
    c = _config(ck, ctx, "imap_login")
    if c is None:
        return
    pw = os.environ.get("AURALIS_SMTP_PASSWORD", c.get("smtp_password", "") or "")
    user = c.get("smtp_user", "")
    host, port = c.get("imap_host", "imap.gmail.com"), int(c.get("imap_port", 993))
    if not (pw and user):
        ck.add("imap_login", WARN, f"skipped — no credentials for {host}:{port}")
        return
    M = None
    try:
        try:
            M = imaplib.IMAP4_SSL(host, port, timeout=20)      # timeout: py3.9+
        except TypeError:                                       # older signature
            M = imaplib.IMAP4_SSL(host, port)
        M.login(user, pw)
        box = ctx.mods["mailer"].drafts_mailbox(M)
        typ, _ = M.select(box, readonly=True)
        shown = box.strip('"')
        if typ == "OK":
            ck.add("imap_login", OK, f"{user} authenticated on {host}:{port} and the drafts "
                                     f"folder '{shown}' is selectable (email_mode=draft works)")
        else:
            ck.add("imap_login", WARN, f"{user} authenticated on {host}:{port} but the drafts "
                                       f"folder '{shown}' is not selectable ({typ}) — "
                                       "mailer._imap_draft() APPENDs there")
    except Exception as e:
        ck.add("imap_login", FAIL, f"{user} could NOT log in to {host}:{port} — "
                                   f"{type(e).__name__}: {e}")
    finally:
        with contextlib.suppress(Exception):
            if M is not None:
                M.logout()


def check_golive(ck: Checks, ctx: Ctx) -> None:
    """What is still standing between here and taking money.

    This exists because "why is nothing moving?" deserves an answer in one
    command instead of a reading of CLAUDE.md. Every line below is either
    something a machine can settle (and therefore already green) or something
    only the founder can do in someone else's dashboard — named exactly, with
    the click that clears it.
    """
    if not _need(ck, ctx, "golive", "cfg"):
        return
    c = _config(ck, ctx, "golive")
    if c is None:
        return

    # ── 1. do CLIENTS get their mail? ────────────────────────────────────────
    mode = str(c.get("email_mode", "off"))
    pw = os.environ.get("AURALIS_SMTP_PASSWORD", c.get("smtp_password", ""))
    if not pw:
        ck.add("golive_mail", FAIL,
               "AURALIS_SMTP_PASSWORD is not set — NOTHING is delivered: no booking "
               "confirmation, no credentials, and no sale notification to you. "
               "Put it in /etc/auralis/portal.env and restart the service.")
    elif mode == "off":
        ck.add("golive_mail", FAIL,
               "email_mode='off' — a client who books hears nothing back and gets no "
               "calendar invite; the mail is only filed as .eml. Set email_mode to "
               "'send' (immediate) or 'draft' (you press Send in Gmail).")
    elif mode == "draft":
        ck.add("golive_mail", WARN,
               "email_mode='draft' — client mail waits in your Gmail Drafts until you "
               "send it. Fine while you want the last look; the booking acknowledgement "
               "and the internal alerts go out immediately either way.")
    else:
        ck.add("golive_mail", OK, "email_mode='send' with an SMTP password — clients are "
                                  "answered the moment they book.")

    # ── 2. can anyone BUY? ───────────────────────────────────────────────────
    shop = bool(c.get("shop_enabled"))
    pkgs = [p for p in (c.get("packages") or []) if float(p.get("price") or 0) > 0]

    def _links(p):
        u = p.get("buy_url", "")
        return [v for v in u.values() if v] if isinstance(u, dict) else ([u] if u else [])

    missing = [p.get("key") for p in pkgs if not _links(p)]
    partial = [f"{p.get('key')} ({len(_links(p))}/3 Sprachen)" for p in pkgs
               if _links(p) and isinstance(p.get("buy_url"), dict) and len(_links(p)) < 3]
    secret = str(c.get("stripe_webhook_secret") or
                 os.environ.get("AURALIS_STRIPE_WEBHOOK_SECRET", ""))
    pw = os.environ.get("AURALIS_SMTP_PASSWORD", c.get("smtp_password", ""))
    mode = str(c.get("email_mode", "off"))

    blockers, notes = [], []
    if missing:
        blockers.append(f"no payment link configured for {', '.join(missing)}")
    if partial:
        notes.append("only some languages linked: " + ", ".join(partial))
    if not secret:
        blockers.append("AURALIS_STRIPE_WEBHOOK_SECRET is unset, so /api/stripe/webhook "
                        "answers 503 — a payment would be taken and never reach the portal "
                        "(Stripe → Developers → Webhooks → add "
                        "https://api.auralisnatura.com/api/stripe/webhook, event "
                        "checkout.session.completed, then paste the whsec_… into "
                        "/etc/auralis/portal.env and restart)")
    if not pw:
        blockers.append("AURALIS_SMTP_PASSWORD is unset, so the buyer would pay and never "
                        "receive her access")
    elif mode == "off":
        blockers.append("email_mode='off' — the credentials mail is only filed, never sent")

    # Metadata is exactness insurance, not a gate: the webhook falls back to the
    # amount, and 199/399/899 are distinct. Say so rather than listing it as work.
    prices = [float(p.get("price") or 0) for p in pkgs]
    if len(set(prices)) == len(prices):
        notes.append("package metadata is optional — the prices "
                     + "/".join(f"{x:.0f}" for x in prices)
                     + " are distinct, so the webhook matches on the amount; adaptive "
                       "pricing (a USD checkout) is read from currency_conversion")
    else:
        blockers.append("two packages share a price, so `metadata package=<key>` on each "
                        "Payment Link is REQUIRED to tell them apart")
    notes.append("not machine-checkable: distance-selling terms (withdrawal, "
                 "pre-contractual info, invoice/IVA) with the gestoría")

    detail = ("; ".join(blockers) if blockers else "everything technical is ready")
    if notes:
        detail += " — " + " · ".join(notes)
    if shop and blockers:
        ck.add("golive_shop", FAIL, "shop_enabled=true but " + detail)
    elif shop:
        ck.add("golive_shop", OK, "shop_enabled=true — " + detail)
    elif blockers:
        ck.add("golive_shop", WARN, "shop_enabled=false. Open: " + detail)
    else:
        ck.add("golive_shop", WARN,
               "shop_enabled=false but nothing technical is left — flip it once the "
               "distance-selling terms are settled. " + detail)


def check_backups(ck: Checks, ctx: Ctx) -> None:
    """backup.start_scheduler() does NOTHING when no directory is configured —
    silently, forever. And a backup dir inside the worktree is destroyed by the
    `git reset --hard` in auralis-update.service."""
    if not _need(ck, ctx, "backups", "backup", "cfg"):
        return
    conf = _config(ck, ctx, "backups")   # backup._configured() reads it too
    if conf is None:
        return
    backup = ctx.mods["backup"]
    d = backup._configured()          # never _dir(): that would CREATE it
    if d is None:
        ck.add("backups", ctx.sev(),
               "no AURALIS_BACKUP_DIR and no config.backup_dir — backup.start_scheduler() "
               "returns immediately and NOTHING is ever backed up. Set "
               "AURALIS_BACKUP_DIR=/var/lib/auralis/backups.")
        return
    inside = False
    with contextlib.suppress(Exception):
        inside = str(d.resolve()).startswith(str(ROOT.resolve()) + os.sep)
    if inside:
        ck.add("backups", FAIL,
               f"{d} is INSIDE the git worktree ({ROOT}) — auralis-update.service runs "
               "`git reset --hard`/`git clean`, which would delete every snapshot. Move it "
               "to /var/lib/auralis/backups.")
        return
    keep = conf.get("backup_keep", 48)
    every = conf.get("backup_interval_hours", 1)
    if not d.exists():
        ok, why = _writable(d.parent) if d.parent.exists() else (False, f"{d.parent} missing")
        sev = OK if ok else ctx.sev()
        ck.add("backups", WARN if ok else sev,
               f"{d} configured but does not exist yet (created on the first backup; parent "
               f"{'writable' if ok else 'NOT writable: ' + why}) · keep={keep} every {every}h")
        return
    ok, why = _writable(d)
    snaps = sorted((p for p in d.glob("auralis-*") if p.is_dir()), reverse=True)
    if not ok:
        ck.add("backups", ctx.sev(), f"{d} is NOT writable ({why}) — no snapshot can be "
                                     "written · keep={} every {}h".format(keep, every))
        return
    if not snaps:
        ck.add("backups", WARN, f"{d} is writable but holds NO snapshot yet · "
                                f"keep={keep} every {every}h")
        return
    age = time.time() - snaps[0].stat().st_mtime
    detail = (f"{len(snaps)} snapshot(s) in {d} · newest {snaps[0].name} "
              f"({_age(age)} old) · keep={keep} every {every}h")
    # The server's auralis-backup.timer is daily and the in-process scheduler is
    # hourly, so anything older than ~26h means neither is running.
    ck.add("backups", WARN if age > 26 * 3600 else OK,
           detail + (" — STALE: neither the in-process scheduler nor auralis-backup.timer "
                     "seems to be running" if age > 26 * 3600 else ""))


def check_port(ck: Checks, ctx: Ctx) -> None:
    """Who owns the port? A stale/foreign listener on 5056 once answered with
    the WRONG data. We never kill anything — we identify and report."""
    if not _need(ck, ctx, "port", "cfg"):
        return
    c = _config(ck, ctx, "port")
    if c is None:
        return
    port = int(os.environ.get("AURALIS_PORT", c.get("port", 5056)))
    host = c.get("host", "127.0.0.1")
    listening = False
    with contextlib.suppress(Exception):
        with socket.create_connection(("127.0.0.1", port), timeout=2.0):
            listening = True
    if not listening:
        ck.add("port", OK, f"127.0.0.1:{port} is free — no portal is running on this host "
                           f"right now (config host={host})")
        return
    code, body, err = _http_json(f"http://127.0.0.1:{port}/health")
    vcode, vbody, _ = _http_json(f"http://127.0.0.1:{port}/api/version")
    ours = isinstance(vbody, dict) and vbody.get("name") == "auralis-portal"
    if ours and isinstance(body, dict) and body.get("ok") is True:
        ck.add("port", OK, f"the Auralis portal is listening on 127.0.0.1:{port} — "
                           f"/health ok:true, /api/version {vbody.get('version')}")
        return
    owner = _port_owner(port)
    if ours:
        ck.add("port", FAIL, f"127.0.0.1:{port} is the Auralis portal but /health did not "
                             f"answer ok:true ({err or code}) — it is up but unhealthy{owner}")
    else:
        ck.add("port", FAIL,
               f"127.0.0.1:{port} is held by something that is NOT the Auralis portal "
               f"(/api/version said {vbody if vbody is not None else vcode or err}){owner}. "
               "Do NOT kill it — this host also runs another company's production ERP. "
               "Identify the owner, or move the portal with AURALIS_PORT.")


def _port_owner(port: int) -> str:
    """Best effort, non-fatal: as a non-root user the kernel hides other users'
    processes, so an empty answer here is normal and must not be alarming."""
    for cmd in (["ss", "-ltnpH", f"sport = :{port}"],
                ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"]):
        if not shutil.which(cmd[0]):
            continue
        with contextlib.suppress(Exception):
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            line = " ".join((p.stdout or "").split())[:160]
            if line:
                return f" [{cmd[0]}: {line}]"
    return ""


# Order matters: the human report is read top to bottom, and the cheap/most
# fundamental facts must be established before anything depends on them.
CHECKS = [
    ("python", check_python),
    ("paths", check_paths),
    ("dependencies", check_dependencies),
    ("portal_modules", check_portal_modules),
    ("env", check_env),
    ("secrets", check_secrets),
    ("data_key", check_data_key),
    ("store_key", check_store_key),
    ("database", check_database),
    ("clients_json", check_clients_json),
    ("output_docs", check_output_docs),
    ("chromium", check_chromium),
    ("screenshot", check_screenshot),
    ("agent", check_agent),
    ("email", check_email),
    ("smtp_login", check_smtp_login),
    ("imap_login", check_imap_login),
    ("backups", check_backups),
    ("port", check_port),
    ("golive", check_golive),
]


def run_checks(net: bool = False, agent: bool = True, pdf: bool = True,
               timeout: float = 25.0, env_file=None) -> dict:
    """Run every check and return the --json document. Importable, never prints,
    never raises: an exploding check becomes a FAIL entry, because a preflight
    that dies tells the operator nothing at all."""
    ctx = Ctx(net=net, agent=agent, pdf=pdf, timeout=timeout, env_file=env_file)
    ck = Checks()
    if env_file:
        try:
            ctx.env_loaded, ctx.env_bad = load_env_file(env_file)
            ctx.prod = os.environ.get("AURALIS_ENV", "").lower() in ("production", "prod")
        except Exception as e:
            ck.add("env_file", FAIL, f"could not read {env_file}: {type(e).__name__}: {e}")
            ctx.env_file = None
    for name, fn in CHECKS:
        before = len(ck.items)
        try:
            fn(ck, ctx)
        except Exception as e:
            ck.add(name, FAIL, f"the {name} check itself crashed: {type(e).__name__}: {e} — "
                               "that is a preflight bug; treat the underlying condition as "
                               "UNVERIFIED, not healthy")
        else:
            # smtp_login/imap_login legitimately emit nothing without --net.
            if len(ck.items) == before and name not in ("smtp_login", "imap_login"):
                ck.add(name, WARN, "check produced no result")
    return ck.as_dict(ctx)


# ────────────────────────────────────────────────────────────── human output ──
def _colors(stream) -> dict:
    if os.environ.get("NO_COLOR") or not hasattr(stream, "isatty") or not stream.isatty():
        return {k: "" for k in ("g", "y", "r", "b", "d", "n")}
    return {"g": "\033[32m", "y": "\033[33m", "r": "\033[31m",
            "b": "\033[1m", "d": "\033[2m", "n": "\033[0m"}


def render_text(result: dict, stream=sys.stdout) -> None:
    c = _colors(stream)
    width = max(60, min(shutil.get_terminal_size((100, 24)).columns, 120))
    label = {OK: f"{c['g']}PASS{c['n']}", WARN: f"{c['y']}WARN{c['n']}",
             FAIL: f"{c['r']}FAIL{c['n']}"}
    print(f"{c['b']}Auralis preflight{c['n']}  ·  {result['host']}  ·  "
          f"{result['env'].upper()}  ·  {result['portal']}", file=stream)
    print("─" * width, file=stream)
    import textwrap
    for item in result["checks"]:
        head = f" {label[item['severity']]}  {item['name']:<15}"
        pad = 23                                   # visible width of `head`
        body = textwrap.wrap(item["detail"], width=max(30, width - pad)) or [""]
        print(head + body[0], file=stream)
        for extra in body[1:]:
            print(" " * pad + c["d"] + extra + c["n"], file=stream)
    s = result["summary"]
    print("─" * width, file=stream)
    if s["fail"]:
        verdict = f"{c['r']}{c['b']}NOT HEALTHY — fix every FAIL above{c['n']}"
    elif s["warn"]:
        verdict = f"{c['y']}healthy, with warnings{c['n']}"
    else:
        verdict = f"{c['g']}{c['b']}HEALTHY{c['n']}"
    print(f" {s['pass']} pass · {s['warn']} warn · {s['fail']} fail   →  {verdict}", file=stream)
    print(f"PREFLIGHT_RESULT: {'FAIL' if s['fail'] else ('WARN' if s['warn'] else 'PASS')}",
          file=stream)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="preflight.py",
        description="Prove an Auralis portal install is healthy (Mac or server).")
    ap.add_argument("--json", action="store_true",
                    help="emit the machine-readable document and nothing else")
    ap.add_argument("--net", action="store_true",
                    help="also log in to SMTP and IMAP for real (default off: CI-safe)")
    ap.add_argument("--no-agent", action="store_true",
                    help="skip the live `claude -p` round-trip")
    ap.add_argument("--no-pdf", action="store_true",
                    help="skip the live chromium PDF render")
    ap.add_argument("--timeout", type=float, default=25.0,
                    help="seconds allowed for the `claude -p` probe (default 25)")
    ap.add_argument("--env-file", metavar="PATH",
                    help="load KEY=VALUE from PATH first, systemd-style (the file wins)")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero on WARN as well as FAIL")
    args = ap.parse_args(argv)

    # In --json mode stdout must carry the JSON document and NOTHING else: the
    # shell callers do raw.find("{") + json.loads(rest) over a 2>&1 capture, so
    # one stray library warning after the document would break every one of
    # them. Everything the checks might print is swallowed here.
    noise = io.StringIO()
    try:
        if args.json:
            with contextlib.redirect_stdout(noise), contextlib.redirect_stderr(noise):
                result = run_checks(net=args.net, agent=not args.no_agent,
                                    pdf=not args.no_pdf, timeout=args.timeout,
                                    env_file=args.env_file)
        else:
            result = run_checks(net=args.net, agent=not args.no_agent,
                                pdf=not args.no_pdf, timeout=args.timeout,
                                env_file=args.env_file)
    except Exception as e:                       # last resort: still valid output
        result = {"ok": False,
                  "checks": [{"name": "preflight", "ok": False, "severity": FAIL,
                              "detail": f"preflight crashed: {type(e).__name__}: {e}"}],
                  "summary": {"pass": 0, "warn": 0, "fail": 1},
                  "env": "unknown", "host": socket.gethostname(), "portal": str(ROOT),
                  "generated": _dt.datetime.now(_dt.timezone.utc)
                                   .replace(microsecond=0).isoformat()}

    if args.json:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        render_text(result)
    if not result["ok"]:
        return 1
    if args.strict and result.get("summary", {}).get("warn"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
