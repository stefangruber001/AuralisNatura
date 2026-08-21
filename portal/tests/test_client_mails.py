#!/usr/bin/env python3
"""The client-mail panel: one click per customer-facing mail, none unbranded.

Two new actions carry real weight and get pinned here:

  · the personal mail — Desiree's own words in the premium shell, salutation
    and footer in the CLIENT'S language, never generated;
  · the schedule re-send — the same mail sessions_save() produces, rebuilt
    from what is already booked, with the stable UIDs so an accepted calendar
    updates instead of duplicating.

Both must follow email_mode and leave an .eml audit copy under the client's
own folder, where the detail drawer's document list finds them.
"""
from __future__ import annotations
import sys
import datetime as dt
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


def eml_texts(cid: str) -> str:
    """All of the client's audit mails, with every MIME part DECODED — a
    calendar attachment is base64 on disk, so grepping raw bytes lies."""
    from email import message_from_bytes
    out = ""
    for p in (cfg.OUTPUT_DIR / cid).rglob("*.eml"):
        msg = message_from_bytes(p.read_bytes())
        out += str(msg["Subject"] or "") + "\n"
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            payload = part.get_payload(decode=True) or b""
            out += payload.decode("utf-8", "replace") + "\n"
            out += "[part:" + part.get_content_type() + "]\n"
    return out


def run() -> int:
    from server.app import app
    c = app.test_client()

    cid = cfg.allocate_client("Elena Beispiel", "elena@example.com", "es", status="active")

    print("· the personal mail")
    check("staff-only", c.post(f"/api/client/{cid}/personal-mail").status_code in (401, 403))
    check("subject and body are required",
          c.post(f"/api/client/{cid}/personal-mail", json={"subject": "x"},
                 headers=K).status_code == 400)
    r = c.post(f"/api/client/{cid}/personal-mail",
               json={"subject": "Deine Frage zu Magnesium",
                     "body": "kurz zu deiner Frage von gestern.\n\nMagnesium am Abend ist gut."},
               headers=K)
    check("it is accepted", r.status_code == 200, r.get_data(as_text=True)[:200])
    raw = eml_texts(cid)
    check("an audit .eml lands in HER folder", "Magnesium" in raw)
    check("salutation follows HER language (es)", "Hola Elena" in raw, raw[:400])
    check("the Spanish disclaimer rides along", "coaching y educaci" in raw)
    rec = store.get(cid) or {}
    trail = " ".join(str(a) for a in (rec.get("meta", {}).get("activity") or []))
    check("the activity trail records it", "pers" in trail and "Magnesium" in trail, trail)

    print("\n· the schedule re-send")
    check("without planned sessions it refuses honestly",
          c.post(f"/api/client/{cid}/sessions/notify", headers=K).status_code == 409)
    # plan one future session through the real engine, then re-send
    t0 = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=9)).replace(
        hour=9, minute=0, second=0, microsecond=0)
    rec = store.ensure(cid)
    rec["package"] = {"key": "bloom", "name": "Wandel (4 Wochen)", "price": 399}
    store.upsert(rec)
    booking.save_sessions(cid, "Elena Beispiel", "elena@example.com", "es",
                          [{"utc": t0.isoformat(), "key": "kickoff", "n": 1, "minutes": 60}],
                          "bloom")
    r = c.post(f"/api/client/{cid}/sessions/notify", headers=K)
    check("with a plan it sends", r.status_code == 200, r.get_data(as_text=True)[:200])
    check("it reports the session count", (r.get_json() or {}).get("sessions") == 1)
    raw = eml_texts(cid)
    check("the schedule mail carries a calendar part", "[part:text/calendar]" in raw)
    check("the invite keeps the stable session UID", f"{cid}-kickoff1@" in raw,
          raw[-1200:])

    print("\n· the console offers the panel")
    html = (ROOT / "web" / "staff.html").read_text(encoding="utf-8")
    for needle, why in (
        ("mailPanel(cl,rec)", "the full client view renders the panel"),
        ("E-Mails an die Kundin", "the panel exists"),
        ("remindClient(", "one-click reminder"),
        ("sessionsNotify(", "one-click schedule re-send"),
        ("personalMail(", "one-click personal mail"),
        ("mailModeLine()", "the panel says how mails go out"),
    ):
        check(why, needle in html, needle)

    print()
    if FAILS:
        print(f"{len(FAILS)} failure(s):")
        for f in FAILS:
            print("  ·", f)
        return 1
    print("client mails: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
