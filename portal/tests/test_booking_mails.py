#!/usr/bin/env python3
"""What a booking must send, and in which language.

Locks in the five things the founder reported on 2026-08-10:

  1. ONE draft per booking, never two (the confirmation). The acknowledgement
     and the internal briefing are sent, not drafted.
  2. Every customer-facing mail in the language chosen on the booking form —
     including the DATE, which used to be English for everyone.
  3. No "bioorganische Chemie" in the mail footer.
  4. The calendar invite rides on a mail that is actually SENT, so the event
     exists whether or not the draft is ever sent.
  5. The Meet link is in the body of the mail, with one-click add-to-calendar
     links — not only inside the .ics attachment.

Plus the message hygiene that keeps mail out of spam: a Date and a Message-ID
on every message, including the drafts, which an IMAP APPEND does not add.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib import cfg, booking, mailer  # noqa: E402

FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


SLOT = "2026-08-12T08:05:00+00:00"
MEET = "https://meet.google.com/abc-defg-hij"


def parts(msg, ctype):
    return [p for p in msg.walk() if p.get_content_type() == ctype]


def body(msg, ctype="text/html"):
    p = parts(msg, ctype)
    return p[0].get_content() if p else ""


def run() -> int:
    comp = cfg.ROOT / "config" / "company.json"
    original = comp.read_text()
    d = json.loads(original)
    d["meet_link"] = MEET
    comp.write_text(json.dumps(d, ensure_ascii=False, indent=2))
    cfg.reset_caches()
    try:
        return _run()
    finally:
        comp.write_text(original)
        cfg.reset_caches()


def _run() -> int:
    print("· exactly one of the three booking mails is a draft")
    import inspect
    src = inspect.getsource(mailer)
    check("only deliver() drafts", src.count("_imap_draft(msg)") == 1)
    check("notify_internal sends, never drafts",
          "_imap_draft" not in inspect.getsource(mailer.notify_internal))
    check("send_now sends, never drafts",
          "_imap_draft" not in inspect.getsource(mailer.send_now))
    route = inspect.getsource(sys.modules["lib.mailer"])  # noqa: F841
    app_src = (cfg.ROOT / "server" / "app.py").read_text()
    booking_route = app_src.split("def booking_book(")[1].split("@app.get(\"/api/availability\")")[0]
    check("the booking route calls deliver() once", booking_route.count("mailer.deliver(") == 1)

    print("\n· the IMAP append marks the message as a draft")
    check(r"APPEND carries (\Draft)", r"(\Draft)" in inspect.getsource(mailer._imap_draft))

    print("\n· every mail carries a Date and a Message-ID (drafts get none for free)")
    for lang in ("de", "en", "es"):
        when = booking.format_when(SLOT, lang)
        ics = booking.ics_for(SLOT, "Maria Moser", "BK-1", client_email="m@yahoo.de", language=lang)
        mails = {
            "ack": mailer.build_ack_email("m@yahoo.de", "Maria", when, lang, "BK-1"),
            "confirm": mailer.build_booking_email("m@yahoo.de", "Maria", when, lang, ics, "BK-1", SLOT),
            "remind": mailer.build_reminder_email("m@yahoo.de", "Maria", when, lang, SLOT, ics),
            "internal": mailer.build_internal_booking_email(
                "Maria", "m@yahoo.de", when, lang, {"goal": "mehr Energie"}, "", "BK-1", ics),
        }
        for nm, m in mails.items():
            check(f"{lang} {nm}: Date + Message-ID", bool(m["Date"]) and bool(m["Message-ID"]),
                  f"date={m['Date']!r} id={m['Message-ID']!r}")
            dom = m["Message-ID"].rsplit("@", 1)[-1].rstrip(">")
            check(f"{lang} {nm}: Message-ID on the sending domain", dom == "auralisnatura.com", dom)

    print("\n· the same booking rebuilt twice is the same message, not a second draft")
    a = mailer.build_booking_email("m@x.de", "Maria", "x", "de", b"", "BK-9")["Message-ID"]
    b = mailer.build_booking_email("m@x.de", "Maria", "x", "de", b"", "BK-9")["Message-ID"]
    check("stable Message-ID per booking", a == b, f"{a} vs {b}")

    print("\n· the date is written in the client's language, not the server's locale")
    check("de", booking.format_when(SLOT, "de").startswith("Mittwoch, 12. August 2026"))
    check("en", booking.format_when(SLOT, "en").startswith("Wednesday, 12 August 2026"))
    check("es", booking.format_when(SLOT, "es").startswith("miércoles, 12 de agosto de 2026"))

    print("\n· the invite is localised and survives a comma in the name")
    ics = booking.ics_for(SLOT, "Moser, Maria", "BK-1", client_email="m@yahoo.de", language="es").decode()
    check("comma escaped", "Moser\\, Maria" in ics)
    check("Spanish summary", "Llamada de presentación" in ics)
    check("both attendees", ics.count("ATTENDEE") == 2)
    check("one UID for one booking", ics.count("UID:") == 1)

    print("\n· the invite rides on the mail that is actually SENT")
    ics_b = booking.ics_for(SLOT, "Maria", "BK-1", client_email="m@x.de")
    internal = mailer.build_internal_booking_email("Maria", "m@x.de", "x", "de", {}, "", "BK-1", ics_b)
    cal = parts(internal, "text/calendar")
    check("briefing carries the invite", len(cal) == 1)
    check("briefing invite is a REQUEST", bool(cal) and cal[0].get_param("method") == "REQUEST")
    check("briefing goes to the practice inbox", "@" in (internal["To"] or ""))
    same = parts(mailer.build_booking_email("m@x.de", "Maria", "x", "de", ics_b, "BK-1", SLOT), "text/calendar")
    check("confirmation invite has the SAME UID (one event, not two)",
          bool(same) and b"UID:BK-1@auralisnatura.com" in same[0].get_payload(decode=True))

    print("\n· the join link and add-to-calendar are IN THE MAIL, not only in the .ics")
    for lang in ("de", "en", "es"):
        when = booking.format_when(SLOT, lang)
        for nm, m in (("confirm", mailer.build_booking_email("m@x.de", "Maria", when, lang, ics_b, "BK-1", SLOT)),
                      ("remind", mailer.build_reminder_email("m@x.de", "Maria", when, lang, SLOT, ics_b))):
            h, t = body(m), body(m, "text/plain")
            check(f"{lang} {nm}: Meet button in the HTML", MEET in h)
            check(f"{lang} {nm}: Meet link in the plain text too", MEET in t)
            check(f"{lang} {nm}: Google Calendar one-click", "calendar.google.com/calendar/render" in h)
            check(f"{lang} {nm}: Outlook one-click", "outlook.live.com" in h)

    print("\n· with no Meet link configured the mail says so instead of going quiet")
    comp = cfg.ROOT / "config" / "company.json"
    saved = comp.read_text()
    d = json.loads(saved)
    d["meet_link"] = ""
    comp.write_text(json.dumps(d, ensure_ascii=False, indent=2))
    cfg.reset_caches()
    try:
        h = body(mailer.build_booking_email("m@x.de", "Maria", "x", "de", ics_b, "BK-1", SLOT))
        check("honest fallback line", "schicke ich dir rechtzeitig" in h)
        check("calendar buttons still offered", "calendar.google.com" in h)
    finally:
        comp.write_text(saved)
        cfg.reset_caches()

    print("\n· the footer credential says Chemie, not bioorganische Chemie")
    check("no bioorganic wording anywhere in the mailer",
          "bioorgan" not in (cfg.ROOT / "lib" / "mailer.py").read_text().lower())

    print("\n" + ("BOOKING MAIL CHECKS ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
