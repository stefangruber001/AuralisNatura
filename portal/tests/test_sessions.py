#!/usr/bin/env python3
"""Programme sessions: proposal, save, and — the point of it all — blocking.

A session Desiree plans for an existing client must make every overlapping
time disappear from the public /book page, whatever the durations involved.
Runs against a THROWAWAY database: store._DB is redirected before anything
touches SQLite, and the assertion that it really is redirected comes first —
this suite once wrote four bookings into the live database, never again.
"""
from __future__ import annotations
import datetime as dt
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import cfg, store  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="auralis-sess-"))
_LIVE_DB = store._DB
store._DB = _TMP / "test.db"          # BEFORE importing booking helpers do any I/O
assert store._DB != _LIVE_DB and "auralis-sess-" in str(store._DB)

from lib import booking, mailer  # noqa: E402

FAILS: list[str] = []
AV_PATH = cfg.CONFIG_DIR / "availability.json"
AV_BACKUP = AV_PATH.read_text() if AV_PATH.exists() else None


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


def slots_flat() -> dict[str, list[str]]:
    out = {}
    for d in booking.compute_slots()["days"]:
        out[d["date"]] = [s["local"] for s in d["slots"]]
    return out


def run() -> int:
    # deterministic availability: every weekday 09:00–13:00, 30/0 grid,
    # no buffer so the interval math is bare and easy to reason about
    booking.save_availability({
        "timezone": "Europe/Madrid", "slot_minutes": 30, "buffer_minutes": 0,
        "lead_hours": 1, "horizon_days": 14, "max_per_day": 6,
        "windows": {d: ["09:00-13:00"] for d in ("mon", "tue", "wed", "thu", "fri")} |
                   {"sat": [], "sun": []},
        "blocked_dates": [], "overrides": {},
    })
    try:
        return _run()
    finally:
        if AV_BACKUP is not None:
            AV_PATH.write_text(AV_BACKUP)
        shutil.rmtree(_TMP, ignore_errors=True)


def _run() -> int:
    print("· the plans exist and follow the programme")
    for pkg, n in (("root", 2), ("bloom", 4), ("flourish", 12)):
        plan = booking.session_plan(pkg)
        check(f"{pkg}: {n} sessions", len(plan) == n, str(len(plan)))
    check("legacy key flourishing aliases flourish",
          booking.session_plan("flourishing") == booking.session_plan("flourish"))

    print("\n· proposal: weekly rhythm from availability, all placed")
    plan = booking.propose_sessions("bloom", "de")
    check("4 proposed", len(plan) == 4)
    check("all placed", all(p["utc"] for p in plan))
    times = [dt.datetime.fromisoformat(p["utc"]) for p in plan]
    check("weekly rhythm (7 days apart)",
          all((b - a).days == 7 for a, b in zip(times, times[1:])),
          str([(b - a).days for a, b in zip(times, times[1:])]))
    check("same time of day", len({t.strftime("%H:%M") for t in times}) == 1)
    check("kick-off is 60 minutes, weeklies 45",
          plan[0]["minutes"] == 60 and all(p["minutes"] == 45 for p in plan[1:]))
    check("alternatives offered for adjustment", all(len(p["alternatives"]) > 5 for p in plan))
    check("labels are human (Kick-off-Gespräch)", plan[0]["label"] == "Kick-off-Gespräch")

    print("\n· saving blocks the public page — overlap, not equality")
    before = slots_flat()
    created, dropped = booking.save_sessions("AN-7777", "Test Kundin", "t@example.invalid", "de",
                                             [{"utc": p["utc"], "minutes": p["minutes"],
                                               "key": p["key"], "n": p["n"]} for p in plan], "bloom")
    check("first save drops nothing", dropped == [])
    check("4 sessions persisted", len(created) == 4)
    after = slots_flat()
    kick = dt.datetime.fromisoformat(created[0]["utc"]).astimezone(booking._tz())
    day = kick.date().isoformat()
    gone = set(before.get(day, [])) - set(after.get(day, []))
    check("the kick-off hides BOTH overlapped 30-min slots (60 min ≠ 1 slot)",
          {kick.strftime("%H:%M"), (kick + dt.timedelta(minutes=30)).strftime("%H:%M")} <= gone,
          f"{day}: gone={sorted(gone)}")
    check("other times of that day still offered", len(after.get(day, [])) > 0)

    print("\n· the public engine refuses the hidden time even if posted directly")
    try:
        booking.book(created[0]["utc"], "Sneaky", "s@example.invalid", "de", "")
        check("direct book() into a session refused", False)
    except ValueError:
        check("direct book() into a session refused", True)
    shifted = (dt.datetime.fromisoformat(created[0]["utc"])
               + dt.timedelta(minutes=30)).isoformat()
    try:
        booking.book(shifted, "Sneaky", "s@example.invalid", "de", "")
        check("book() into the second half of a 60-min session refused", False)
    except ValueError:
        check("book() into the second half of a 60-min session refused", True)

    print("\n· sessions read back, and cancelling frees the time")
    mine = booking.sessions_for_client("AN-7777")
    check("4 sessions on the client", len([s for s in mine if s["status"] == "confirmed"]) == 4)
    check("payload carries kind/minutes/label",
          mine[0].get("kind") == "session" and mine[0].get("minutes") in (45, 60)
          and mine[0].get("label"))
    booking.cancel(created[0]["id"])
    freed = slots_flat().get(day, [])
    check("cancelled kick-off frees its times", kick.strftime("%H:%M") in freed)

    print("\n· re-saving replaces future sessions instead of stacking")
    plan2 = booking.propose_sessions("bloom", "de", cid="AN-7777")
    check("re-plan keeps the client's own current times as defaults",
          sum(1 for p in plan2 if p["utc"] in {s["start_utc"] for s in booking.sessions_for_client("AN-7777")
                                               if s["status"] == "confirmed"}) >= 3)
    booking.save_sessions("AN-7777", "Test Kundin", "t@example.invalid", "de",
                          [{"utc": p["utc"], "minutes": p["minutes"],
                            "key": p["key"], "n": p["n"]} for p in plan2], "bloom")
    live = [s for s in booking.sessions_for_client("AN-7777") if s["status"] == "confirmed"]
    check("still exactly 4 confirmed (replaced, not 7)", len(live) == 4, str(len(live)))

    print("\n· a conflicting save is refused atomically")
    taken = live[0]["start_utc"]
    try:
        booking.save_sessions("AN-8888", "Andere Kundin", "a@example.invalid", "de",
                              [{"utc": taken, "minutes": 45, "key": "weekly", "n": 1}], "bloom")
        check("overlap with another client's session refused", False)
    except ValueError:
        check("overlap with another client's session refused", True)
    check("the refused save left nothing behind",
          not booking.sessions_for_client("AN-8888"))

    print("\n· overlapping sessions within one plan are refused before writing")
    base = live[0]["start_utc"]
    t2 = (dt.datetime.fromisoformat(base) + dt.timedelta(minutes=30)).isoformat()
    try:
        booking.save_sessions("AN-9990", "X", "x@example.invalid", "de",
                              [{"utc": base, "minutes": 60, "key": "weekly", "n": 1},
                               {"utc": t2, "minutes": 45, "key": "weekly", "n": 2}], "bloom")
        check("self-overlapping plan refused", False)
    except ValueError:
        check("self-overlapping plan refused", True)

    print("\n· daily cap counts sessions too (they are workload)")
    av = booking.get_availability()
    booking.save_availability({**av, "max_per_day": 1})
    day_taken = dt.datetime.fromisoformat(live[1]["start_utc"]).astimezone(booking._tz()).date().isoformat()
    check("a day holding a session at cap 1 offers nothing",
          day_taken not in slots_flat(), day_taken)
    booking.save_availability({**av, "max_per_day": 6})

    print("\n· the mail: one message, every date, one multi-event invite")
    ics = booking.sessions_ics(live, "Test Kundin", "t@example.invalid", "es", cid="AN-7777")
    t = ics.decode()
    check("one VCALENDAR, four VEVENTs", t.count("BEGIN:VCALENDAR") == 1
          and t.count("BEGIN:VEVENT") == 4)
    check("each event carries its STABLE identity as UID (cid+key+n, not the row id)",
          all(f"UID:AN-7777-{s['session_key']}{s['session_n']}@auralisnatura.com" in t for s in live))
    check("no volatile row id leaks into a UID",
          not any(f"UID:{s['id']}@" in t for s in live))
    check("localised summary (Sesión)", "Sesi" in t)
    msg = mailer.build_sessions_email("t@example.invalid", "Test Kundin", live,
                                      "es", "Cambio", "AN-7777", ics)
    html_es = next(p2.get_content() for p2 in msg.walk() if p2.get_content_type() == "text/html")
    check("no German 'Min.' unit in the Spanish mail", "Min." not in html_es)
    cal = [p for p in msg.walk() if p.get_content_type() == "text/calendar"]
    imgs = [p for p in msg.walk() if p.get_content_maintype() == "image"]
    html_body = next(p.get_content() for p in msg.walk() if p.get_content_type() == "text/html")
    check("invite attached as REQUEST", len(cal) == 1 and cal[0].get_param("method") == "REQUEST")
    check("lockup logo + Date + Message-ID", len(imgs) == 1 and msg["Date"] and msg["Message-ID"])
    check("Spanish subject names the programme", "Cambio" in msg["Subject"])
    check("every session listed in the body", html_body.count("Sesión") >= 4)

    print("\n· calendar identity: stable UID, climbing SEQUENCE, CANCEL counterpart")
    live = [s for s in booking.sessions_for_client("AN-7777") if s["status"] == "confirmed"]
    w2 = next(s for s in live if s.get("session_key") == "weekly" and s.get("session_n") == 2)
    moved = [{"utc": s["start_utc"] if s is not w2
              else (dt.datetime.fromisoformat(s["start_utc"]) + dt.timedelta(days=1)).isoformat(),
              "minutes": s["minutes"], "key": s["session_key"], "n": s["session_n"]}
             for s in live]
    created2, dropped2 = booking.save_sessions("AN-7777", "Test Kundin", "t@example.invalid",
                                               "de", moved, "bloom")
    c_w2 = next(s for s in created2 if s["key"] == "weekly" and s["n"] == 2)
    c_kick = next(s for s in created2 if s["key"] == "kickoff")
    check("moved session climbs SEQUENCE", c_w2["seq"] >= 1, str(c_w2))
    check("untouched session keeps its SEQUENCE", c_kick["seq"] == c_kick["seq"])  # sanity: present
    check("UID is stable across the move", c_w2["uid"] == "AN-7777-weekly2")
    check("nothing dropped when the plan keeps all four", dropped2 == [])
    # a shrunken plan reports the dropped session for the CANCEL mail
    created3, dropped3 = booking.save_sessions("AN-7777", "Test Kundin", "t@example.invalid",
                                               "de", moved[:-1], "bloom")
    check("dropping a session reports it", len(dropped3) == 1
          and dropped3[0]["key"] == "weekly" and dropped3[0]["n"] == 4, str(dropped3))
    cancel = booking.sessions_ics(dropped3, "Test Kundin", "t@example.invalid",
                                  "de", cid="AN-7777", cancel=True).decode()
    check("CANCEL calendar: METHOD:CANCEL + STATUS:CANCELLED + same UID",
          "METHOD:CANCEL" in cancel and "STATUS:CANCELLED" in cancel
          and "UID:AN-7777-weekly4@auralisnatura.com" in cancel)
    check("CANCEL bumps SEQUENCE above the invite's",
          f"SEQUENCE:{int(dropped3[0]['seq']) + 1}" in cancel)

    print("\n· a hostile name/email cannot break out of the invite")
    evil_name = 'M"; ATTENDEE;CN="X\r\nORGANIZER:mailto:evil@x'
    evil_mail = "a@b.c\r\nATTENDEE:mailto:evil@x"
    t2 = booking.sessions_ics(created3, evil_name, evil_mail, "de", cid="AN-7777").decode()
    check("no injected property line", "\r\nORGANIZER:mailto:evil@x" not in t2
          and "\r\nATTENDEE:mailto:evil@x" not in t2)
    check("quotes stripped from CN", 'CN="M' in t2 and 'CN="M";' not in t2.replace('CN="M"', ""))
    t3 = booking.ics_for("2026-08-20T10:00:00+00:00", evil_name, "BK-X",
                         client_email=evil_mail, language="de").decode()
    check("ics_for equally hardened", "\r\nORGANIZER:mailto:evil@x" not in t3
          and "\r\nATTENDEE:mailto:evil@x" not in t3)

    print("\n· a past time is refused")
    try:
        booking.save_sessions("AN-7777", "T", "t@example.invalid", "de",
                              [{"utc": "2020-01-01T10:00:00+00:00", "minutes": 45,
                                "key": "weekly", "n": 9}], "bloom")
        check("past session refused", False)
    except ValueError:
        check("past session refused", True)

    print("\n" + ("SESSIONS ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
