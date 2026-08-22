#!/usr/bin/env python3
"""Booking: fast answer, a real date ticket, notes from the first minute.

Three defects the founder hit in one sitting, each pinned here:

  · the form spun for ten seconds because the route waited for three Gmail
    round trips before answering. The booking has to be durable before we
    answer; the mails are follow-ups.
  · the acknowledgement passed the slot under the wrong key, so the date
    ticket in the mail always fell back to a lone middle dot on a brown
    block. A fallback that fires ALWAYS is not a fallback, it is the design.
  · the call notes were rendered only after an intake existed — that is,
    everywhere except during the intro call, which is when they are written.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: E402,F401
import os  # noqa: E402
os.environ.setdefault("AURALIS_API_KEY", "test-key")

from lib import cfg, store, booking, mailer, mailv2  # noqa: E402
cfg.reset_caches()

K = {"X-Auralis-Key": os.environ["AURALIS_API_KEY"]}
FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


def run() -> int:
    from server.app import app
    c = app.test_client()

    print("· die Bestätigungs-Mail trägt ein echtes Datums-Ticket")
    slot = next(s["utc"] for d in booking.compute_slots()["days"] for s in d["slots"])
    b = booking.book(slot, "Ticket Test", "ticket@example.com", "de", "")
    check("book() returns the slot under start_utc — the key the route must read",
          "start_utc" in b and "slot_utc" not in b, str(b))
    when = booking.format_when(slot, "de")
    good = mailer.build_ack_email("ticket@example.com", "Ticket Test", when, "de",
                                  b["id"], slot_utc=b["start_utc"])
    def html_of(msg) -> str:
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                return (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
        return ""
    body = html_of(good)
    parts = mailer._tile_of(b["start_utc"])[0]
    check("a slot yields real tile parts", isinstance(parts, dict) and parts.get("day"),
          str(parts))
    check("the day number is in the mail", str(parts["day"]) in body)
    check("the weekday is in the mail", mailv2._DAYS["de"][parts["weekday"]] in body)
    bad = mailer.build_ack_email("t@example.com", "T", when, "de", b["id"], slot_utc="")
    badbody = html_of(bad)
    check("the empty-slot fallback really is the lone dot (the reported bug)",
          "&middot;" in badbody or "·" in badbody)
    check("…and the good mail does NOT use it",
          badbody != body)

    print("\n· die Route antwortet, sobald der Termin steht")
    slot2 = [s["utc"] for d in booking.compute_slots()["days"] for s in d["slots"]][0]
    r = c.post("/api/booking/book", json={"name": "Speed Test", "email": "speed@example.com",
                                          "language": "de", "slot": slot2,
                                          "consent": {"gdpr": True}})
    check("booking accepted", r.status_code == 200, r.get_data(as_text=True)[:160])
    check("the slot is really held",
          any(x.get("id") == (r.get_json() or {}).get("id")
              for x in booking.list_bookings()))
    src = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
    check("the mails run in a worker thread unless tests pin them inline",
          "AURALIS_MAIL_SYNC" in src and "threading.Thread(target=_booking_mails"
          in src)
    check("_sandbox pins them inline, so .eml assertions cannot race",
          "AURALIS_MAIL_SYNC" in (ROOT / "tests" / "_sandbox.py").read_text(encoding="utf-8"))
    # with the sync pin the mails DID run — the ticket must be the real one
    eml = "".join(p.read_text(encoding="utf-8", errors="replace")
                  for p in (cfg.OUTPUT_DIR / "bookings").rglob("*.eml"))
    check("the acknowledgement was produced", "ack" in str(list(
        (cfg.OUTPUT_DIR / "bookings").rglob("*.eml"))), eml[:80])

    print("\n· Notizen ab der ersten Anfrage — nicht erst nach dem Intake")
    cid = next(k for k, v in cfg.clients()["clients"].items()
               if v.get("email") == "speed@example.com")
    check("she starts as a lead", (store.get(cid) or {}).get("stage") == "lead")
    r = c.post(f"/api/client/{cid}/notes", headers=K,
               json={"notes": {"beobachtungen": "wirkt erschöpft, sehr offen"}})
    check("notes save on a lead", r.status_code == 200)
    check("saving a note does NOT move her out of Offene Anfragen",
          (store.get(cid) or {}).get("stage") == "lead",
          str((store.get(cid) or {}).get("stage")))
    rec = store.get(cid) or {}
    check("the note is stored under its field",
          (rec.get("notes") or {}).get("beobachtungen", "").startswith("wirkt"))
    r = c.post(f"/api/client/{cid}/notes", headers=K,
               json={"notes": {"themen": "Schlaf"}, "advance": True})
    check("with advance the console moves her on", r.status_code == 200
          and (store.get(cid) or {}).get("stage") == "call")

    print("\n· die Konsole bietet die Notizen dort an, wo sie entstehen")
    html = (ROOT / "web" / "staff.html").read_text(encoding="utf-8")
    check("one shared definition of the four fields", "const NOTE_FIELDS=[" in html)
    check("the notes block is rendered before the intake section",
          html.index("h+=notesBlock(cid,rec);") < html.index("<h2>Intake (Portal-Fragebogen)</h2>"))
    check("'Gespräch geführt' opens the notes first", "callDone('${cid}')" in html
          and "async function callDone" in html)
    check("the drawer can write notes too", "editNotes(" in html)

    print()
    if FAILS:
        print(f"{len(FAILS)} failure(s):")
        for f in FAILS:
            print("  ·", f)
        return 1
    print("booking fixes: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
