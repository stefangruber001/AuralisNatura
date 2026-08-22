#!/usr/bin/env python3
"""Anfrage stornieren: Zugang weg, Termine weg, Datensatz bleibt.

The dangerous half of this feature is revocation. Tokens are signed and
cannot be recalled one by one, so a storno that only cleared the password
would leave every issued session alive until it expires — the client would
keep reading her portal while the console says the access is gone. The
status check in the client decorator is what makes revocation immediate,
and these guards pin exactly that.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: E402,F401
import os  # noqa: E402
os.environ.setdefault("AURALIS_API_KEY", "test-key")

from lib import cfg, store, booking, auth  # noqa: E402
cfg.reset_caches()

K = {"X-Auralis-Key": os.environ["AURALIS_API_KEY"]}
FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


def free_slots(c) -> int:
    return sum(len(d.get("slots") or []) for d in
               c.get("/api/booking/slots").get_json()["days"])


def run() -> int:
    from server.app import app
    c = app.test_client()

    print("· eine Kundin mit Termin und Portal-Zugang")
    slot = next(s["utc"] for d in booking.compute_slots()["days"] for s in d["slots"])
    c.post("/api/booking/book", json={"name": "Storno Test", "email": "storno@example.com",
                                      "language": "de", "slot": slot,
                                      "consent": {"gdpr": True}})
    cid = next(k for k in cfg.clients()["clients"])
    r = c.post(f"/api/client/{cid}/credentials", headers=K)
    pw = (r.get_json() or {}).get("password", "")
    check("credentials issued", bool(pw))
    r = c.post("/api/login", json={"client_id": cid, "password": pw})
    check("she can sign in", r.status_code == 200, r.get_data(as_text=True)[:120])
    token = (r.get_json() or {}).get("token", "")
    B = {"Authorization": f"Bearer {token}"}
    check("her session works", c.get("/api/me", headers=B).status_code == 200)
    slots_blocked = free_slots(c)
    magic = auth.issue_token(cid, ttl_seconds=3600, scope="portal-magic")

    print("\n· der Storno")
    check("staff-only", c.post(f"/api/client/{cid}/storno").status_code in (401, 403))
    r = c.post(f"/api/client/{cid}/storno", headers=K)
    check("it succeeds", r.status_code == 200, r.get_data(as_text=True)[:200])
    out = r.get_json() or {}
    check("the future appointment was cancelled", out.get("cancelled") == 1, str(out))
    check("…and frees the slot on /book again", free_slots(c) > slots_blocked)

    print("\n· der Zugang ist SOFORT tot — nicht erst beim Token-Ablauf")
    check("password login refused",
          c.post("/api/login", json={"client_id": cid, "password": pw}).status_code == 401)
    check("the LIVE bearer token is refused immediately",
          c.get("/api/me", headers=B).status_code == 401)
    check("a magic link is refused",
          c.post("/api/login/magic", json={"k": magic}).status_code == 401)

    print("\n· der Datensatz bleibt — das ist kein Löschen")
    row = next((x for x in c.get("/api/clients", headers=K).get_json()["clients"]
                if x["client_id"] == cid), None)
    check("she is still listed", row is not None)
    check("her stage is lost", row and row["stage"] == "lost", str(row))
    rec = store.get(cid) or {}
    trail = " ".join(str(a) for a in (rec.get("meta", {}).get("activity") or []))
    check("the activity trail says what happened",
          "storniert" in trail and "entzogen" in trail, trail)
    d = c.get(f"/api/client/{cid}/documents", headers=K).get_json()
    check("the cancellation mail is on her paper trail",
          any("abgesagt" in i["label"].lower() or "cancel" in i["label"].lower()
              for i in d.get("items", [])), str([i["label"] for i in d.get("items", [])]))

    print("\n· der Weg zurück: Zugangsdaten senden reaktiviert")
    r = c.post(f"/api/client/{cid}/credentials", headers=K)
    pw2 = (r.get_json() or {}).get("password", "")
    check("new credentials issue", bool(pw2))
    r = c.post("/api/login", json={"client_id": cid, "password": pw2})
    check("she can sign in again", r.status_code == 200, r.get_data(as_text=True)[:120])
    info = cfg.clients()["clients"][cid]
    check("status is active again", info.get("status") == "active", str(info.get("status")))

    print("\n· die Konsole bietet den Knopf an")
    html = (ROOT / "web" / "staff.html").read_text(encoding="utf-8")
    check("the drawer carries the storno button", "stornoAnfrage(" in html
          and "Anfrage stornieren" in html)
    check("a revoked client is marked in the drawer header", "Zugang entzogen" in html)

    print()
    if FAILS:
        print(f"{len(FAILS)} failure(s):")
        for f in FAILS:
            print("  ·", f)
        return 1
    print("storno: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
