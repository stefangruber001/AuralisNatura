#!/usr/bin/env python3
"""Create/refresh the FIXED-credential demo client Apple App Review uses to sign in.

Run this ON THE MACHINE THAT HOSTS THE LIVE PORTAL (Desiree's Mac), because the live
client data lives there (config/clients.json), not in the repo:

    cd portal && python3 tools/create_review_client.py

Idempotent — safe to re-run; it always resets the account to the known password below.
The same client_id + password go into App Store Connect → App Review Information → Sign-In
(and are stored in ios-app/fastlane/metadata/review_information/ so `release` uploads them).
This is a throwaway review account (consent pre-accepted, no real client data)."""
import sys, os
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load portal/.env BEFORE importing lib, so this tool uses the SAME secrets and
# — critically — the same AURALIS_DATA_KEY as the live server. Running it from a
# plain shell (without the .env exported) would otherwise fall back to the dev
# key and write a record the server can't decrypt (the exact mismatch that broke
# the console once). Existing environment values win; .env only fills the gaps.
_ENV_FILE = ROOT / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

from lib import cfg, auth  # noqa: E402
try:
    from lib import store  # optional: seed an empty record so the app has state
except Exception:
    store = None

# --- fixed review credentials (login is client_id + password) ---
CID = "barca"
PASSWORD = "1234"
NAME = "App Review (Apple)"
EMAIL = "appreview@auralisnatura.com"
LANG = "en"

with cfg._CLIENTS_LOCK:
    data = cfg.clients()
    clients = data.setdefault("clients", {})
    rec = clients.get(CID, {})
    rec.update({
        "name": NAME,
        "email": EMAIL,
        "language": LANG,
        "phone": "",
        "password": auth.hash_password(PASSWORD),
        "status": "active",
        "created": rec.get("created") or datetime.date.today().isoformat(),
        # pre-accept consent so no gate blocks the reviewer
        "consent": {"coaching_not_medical": True, "gdpr_health_data": True, "version": "1.0"},
    })
    clients[CID] = rec
    cfg.save_clients(data)

if store is not None:
    try:
        r0 = store.ensure(CID)
        store.upsert(r0)
    except Exception as e:  # non-fatal — the account still works
        print("note: could not seed a portal record:", e)

print("\n✅ Apple App Review client ready on this portal.")
print(f"   Username (Client ID): {CID}")
print(f"   Password:             {PASSWORD}")
print("   → Enter these in App Store Connect → App Review Information → Sign-In required.")
print("   (Already stored in the fastlane review metadata, so `release` uploads them too.)\n")
