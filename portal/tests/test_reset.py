#!/usr/bin/env python3
"""A fresh start must be actually fresh — and must not eat her work.

Deleting every client LOOKS clean and is not: a booking lives in its own table,
so the appointments survive, keep blocking slots on /book and keep showing up
under Termine. The same is true of the events behind Cockpit revenue and the
funnel. These checks pin the difference.

The other half is what must SURVIVE. Journal articles, social plans, the
availability calendar, company master data, prices and switches are her work,
not customer data — a reset that takes them is a much worse bug than one that
leaves a stale booking, because nothing in the console would say what happened.
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


def slots(n: int = 0) -> str:
    got = [s["utc"] for day in booking.compute_slots()["days"] for s in day["slots"]]
    return got[n]


def run() -> int:
    from server.app import app
    c = app.test_client()

    # ── seed a practice that has been running ────────────────────────────────
    c.post("/api/booking/book", json={"name": "Interessentin", "email": "lead@example.com",
                                      "language": "de", "slot": slots(0),
                                      "consent": {"gdpr": True}})
    cid = cfg.allocate_client("Bestandskundin", "kundin@example.com", "de", status="active")
    for st in ("call", "won"):
        c.post(f"/api/client/{cid}/stage", json={"stage": st}, headers=K)
    c.post(f"/api/client/{cid}/profile", json={"package": "bloom", "paid": True}, headers=K)
    (cfg.OUTPUT_DIR / cid).mkdir(parents=True, exist_ok=True)
    (cfg.OUTPUT_DIR / cid / "report.pdf").write_bytes(b"%PDF-1.4 test")
    store.log_event("won", package="bloom", amount=399)

    # her work, which must survive
    (cfg.OUTPUT_DIR / "social").mkdir(parents=True, exist_ok=True)
    (cfg.OUTPUT_DIR / "social" / "post.png").write_bytes(b"png")
    (cfg.OUTPUT_DIR / "journal").mkdir(parents=True, exist_ok=True)
    (cfg.OUTPUT_DIR / "journal" / "articles.json").write_text("[]", encoding="utf-8")
    avail_before = booking.get_availability()

    print("· before the reset the console is full")
    check("a client exists", len(c.get("/api/clients", headers=K).get_json()["clients"]) >= 2)
    check("bookings exist",
          any(b.get("status") == "confirmed"
              for b in c.get("/api/bookings", headers=K).get_json()["bookings"]))
    check("revenue is counted",
          float((c.get("/api/dashboard", headers=K).get_json().get("revenue") or {})
                .get("total") or 0) > 0)

    print("\n· the reset refuses to fire by accident")
    check("no key is refused", c.post("/api/admin/reset").status_code in (401, 403))
    check("without the confirmation phrase it does nothing",
          c.post("/api/admin/reset", json={}, headers=K).status_code == 400)
    check("the wrong phrase does nothing",
          c.post("/api/admin/reset", json={"confirm": "yes"}, headers=K).status_code == 400)
    check("and nothing was erased by those attempts",
          len(c.get("/api/clients", headers=K).get_json()["clients"]) >= 2)

    print("\n· the reset")
    r = c.post("/api/admin/reset", json={"confirm": "RESET"}, headers=K)
    check("it succeeds", r.status_code == 200, r.get_data(as_text=True)[:200])
    out = r.get_json() or {}

    snap = Path(out.get("snapshot", "/nonexistent"))
    check("a snapshot was written BEFORE deleting", snap.is_dir(), str(snap))
    check("the snapshot holds the database", (snap / "auralis.db").exists())
    check("the snapshot holds the logins", (snap / "clients.json").exists())

    print("\n· nothing customer-shaped is left")
    check("no clients", not c.get("/api/clients", headers=K).get_json()["clients"])
    check("no bookings — this is the part deleting clients would have missed",
          not [b for b in c.get("/api/bookings", headers=K).get_json()["bookings"]
               if b.get("status") == "confirmed"])
    check("no revenue in the Cockpit",
          float((c.get("/api/dashboard", headers=K).get_json().get("revenue") or {})
                .get("total") or 0) == 0)
    check("no client documents", not (cfg.OUTPUT_DIR / cid).exists())
    alerts = [a.get("key") for a in c.get("/api/alerts", headers=K).get_json()["alerts"]]
    check("no client alerts", not [a for a in alerts
                                   if a in ("new_enquiry", "cred_missing", "unpaid",
                                            "unpaid_start", "unpaid_running")],
          str(alerts))
    check("the funnel is empty",
          all(s.get("count", 0) == 0 for s in
              c.get("/api/funnel?days=30", headers=K).get_json()["funnel"]["stages"]))

    print("\n· her work survived")
    check("social posts kept", (cfg.OUTPUT_DIR / "social" / "post.png").exists())
    check("journal kept", (cfg.OUTPUT_DIR / "journal" / "articles.json").exists())
    check("availability kept", booking.get_availability() == avail_before)
    check("packages and prices kept",
          len(c.get("/api/app/offers?lang=de").get_json()["offers"]) == 3)
    check("the shop switch is untouched",
          any(o.get("buy_url") for o in c.get("/api/app/offers?lang=de").get_json()["offers"]))

    print("\n· the calendar and the numbering start over")
    check("/book offers times again",
          sum(len(d.get("slots") or []) for d in
              c.get("/api/booking/slots").get_json()["days"]) > 0)
    check("the next client is AN-0001 again",
          cfg.allocate_client("Erste", "erste@example.com", "de") == "AN-0001")

    print("\n· --keep-events leaves the history alone")
    store.log_event("won", package="root", amount=199)
    r = c.post("/api/admin/reset", json={"confirm": "RESET", "keep_events": True}, headers=K)
    check("it succeeds", r.status_code == 200)
    check("events were kept", (r.get_json() or {}).get("events_removed") == 0)
    # Cockpit revenue is computed from the CLIENT RECORDS, not from events, so it
    # is zero either way once the clients are gone. The funnel is the surface the
    # events actually feed — that is where keeping them shows.
    check("the funnel history survives",
          any(s.get("count", 0) for s in
              c.get("/api/funnel?days=30", headers=K).get_json()["funnel"]["stages"]))

    print()
    if FAILS:
        print(f"{len(FAILS)} failure(s):")
        for f in FAILS:
            print("  ·", f)
        return 1
    print("fresh start: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
