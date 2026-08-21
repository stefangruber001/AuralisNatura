#!/usr/bin/env python3
"""An enquiry from an existing client must not disappear.

Booking `/book` as someone the system already knows past the call stage files
the appointment as `followup_bookings` on her record and leaves her stage
alone. Customer Journey card 01 filters on stage=='lead', so it stayed at zero
while two real appointments waited to be confirmed — reported from the live
console on 2026-08-21, with the Cockpit alert showing them and the Journey not.

The fix hangs on one field: /api/clients must report the call that is ACTUALLY
standing in the calendar. `booking_slot` cannot do it — it holds the first
booking forever, so a second request showed the old date.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: E402,F401
import os  # noqa: E402
os.environ.setdefault("AURALIS_API_KEY", "test-key")

from lib import cfg, store, booking  # noqa: E402
cfg.reset_caches()

K = {"X-Auralis-Key": os.environ["AURALIS_API_KEY"]}
FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


def first_slot() -> str:
    for day in booking.compute_slots()["days"]:
        for s in day["slots"]:
            return s["utc"]
    raise SystemExit("no free slot — availability is empty in the sandbox")


def client_row(c, cid):
    for row in c.get("/api/clients", headers=K).get_json()["clients"]:
        if row["client_id"] == cid:
            return row
    return {}


def run() -> int:
    from server.app import app
    c = app.test_client()

    email = "bestandskundin@example.com"
    cid = cfg.allocate_client("Monika Bestand", email, "de", status="active")
    rec = store.ensure(cid)
    rec["booking"] = {"id": "old", "slot_utc": "2020-01-01T09:00:00+00:00"}
    store.upsert(rec)
    # Walk her forward through the console, not by writing `stage` directly:
    # the booking route decides whether to treat a record as a fresh funnel
    # entry from won_at/intake, so a hand-set stage with no history is NOT the
    # state a real onboarded client is in — and the test would prove nothing.
    for st in ("call", "won"):
        c.post(f"/api/client/{cid}/stage", json={"stage": st}, headers=K)

    print("· before she asks for anything there is no open request")
    check("no next_call", not client_row(c, cid).get("next_call"),
          str(client_row(c, cid).get("next_call")))

    print("\n· she books a second call through the public page")
    slot = first_slot()
    r = c.post("/api/booking/book", json={
        "name": "Monika Bestand", "email": email, "language": "de",
        "slot": slot, "consent": {"gdpr": True}})
    check("the booking is accepted", r.status_code == 200, r.get_data(as_text=True)[:200])
    bid = (r.get_json() or {}).get("id", "")

    row = client_row(c, cid)
    check("her stage did NOT move (she is still won)", row.get("stage") == "won",
          str(row.get("stage")))
    check("next_call reports the NEW appointment", row.get("next_call") == slot,
          f"{row.get('next_call')!r} != {slot!r}")
    check("booking_slot still holds the stale first call — which is why "
          "next_call had to exist", row.get("booking_slot", "").startswith("2020"),
          str(row.get("booking_slot")))

    print("\n· the Cockpit alert and the Journey now agree")
    alerts = c.get("/api/alerts", headers=K).get_json().get("alerts", [])
    enq = next((a for a in alerts if a.get("key") == "new_enquiry"), None)
    check("the 'Neue Anfrage' alert fires", bool(enq and enq.get("items")), str(enq))

    print("\n· a cancelled call is not an open request")
    booking.cancel(bid)
    check("next_call clears after cancellation", not client_row(c, cid).get("next_call"),
          str(client_row(c, cid).get("next_call")))

    print("\n· a call that already happened is not an open request either")
    r = c.post("/api/booking/book", json={
        "name": "Monika Bestand", "email": email, "language": "de",
        "slot": first_slot(), "consent": {"gdpr": True}})
    bid2 = (r.get_json() or {}).get("id", "")
    from contextlib import closing
    with booking._LOCK, closing(booking._conn()) as conn, conn:
        conn.execute("UPDATE bookings SET start_utc=? WHERE id=?",
                     ("2020-02-02T09:00:00+00:00", bid2))
    check("a past call does not show as open",
          not client_row(c, cid).get("next_call"),
          str(client_row(c, cid).get("next_call")))

    print("\n· the console actually renders them in card 01")
    html = (ROOT / "web" / "staff.html").read_text(encoding="utf-8")
    check("card 01 collects clients with an open next_call",
          "c.next_call&&!['lead','call','lost'].includes(c.stage)" in html)
    check("the count includes them", "cs.length+req.length" in html)
    check("the duplicated row gets its own DOM id", "-req'" in html)
    check("the appointment chip prefers next_call",
          "c.next_call||c.booking_slot" in html)

    print()
    if FAILS:
        print(f"{len(FAILS)} failure(s):")
        for f in FAILS:
            print("  ·", f)
        return 1
    print("open call requests: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
