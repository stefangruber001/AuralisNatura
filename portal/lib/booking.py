"""Own-brand booking engine (replaces the Google Calendar appointment page).

- Availability is defined by Desiree in the Betriebskonsole (config/availability.json):
  weekly windows per weekday, slot length, buffer, lead time, horizon, blocked dates.
- Bookings hold personal data (name/email) → stored Fernet-encrypted in the same
  SQLite backbone, in their own table.
- The public page (web/book.html) calls GET slots / POST book on the same origin.
- On booking: a branded confirmation email (with .ics calendar attachment and the
  Meet link from Stammdaten) is drafted/sent via the existing mailer modes, and a
  copy of the .ics is written to output_docs/bookings/.

Times are handled in the practice timezone (Europe/Madrid by default) and exported
to the client as a proper VTIMEZONE-free UTC .ics (universally compatible).
"""
from __future__ import annotations
import json, sqlite3, threading, uuid, datetime as _dt
from contextlib import closing
from pathlib import Path
from zoneinfo import ZoneInfo
from . import cfg, store

_LOCK = threading.RLock()
_INIT = False

DEFAULT_AVAILABILITY = {
    "timezone": "Europe/Madrid",
    "slot_minutes": 25,
    "buffer_minutes": 10,
    "lead_hours": 24,
    "horizon_days": 21,
    "max_per_day": 6,
    "windows": {   # 24h "HH:MM-HH:MM" ranges per weekday; empty = closed
        "mon": ["09:30-12:00", "14:00-17:00"],
        "tue": ["09:30-12:00", "14:00-17:00"],
        "wed": ["09:30-12:00"],
        "thu": ["09:30-12:00", "14:00-17:00"],
        "fri": ["09:30-12:00"],
        "sat": [], "sun": [],
    },
    "blocked_dates": [],   # ["2026-08-15", ...]
    "overrides": {},       # {"2026-07-15": ["09:00-11:00"]} — [] = day closed
}

_WD = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


# ---------- availability config ----------
def _avail_path() -> Path:
    return cfg.CONFIG_DIR / "availability.json"


def get_availability() -> dict:
    p = _avail_path()
    if not p.exists():
        save_availability(DEFAULT_AVAILABILITY)
        return dict(DEFAULT_AVAILABILITY)
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    merged = dict(DEFAULT_AVAILABILITY); merged.update(data)
    return merged


def save_availability(data: dict) -> dict:
    allowed = set(DEFAULT_AVAILABILITY)
    clean = {k: v for k, v in (data or {}).items() if k in allowed}
    merged = get_availability() if _avail_path().exists() else dict(DEFAULT_AVAILABILITY)
    merged.update(clean)
    tmp = _avail_path().with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    tmp.replace(_avail_path())
    return merged


# ---------- encrypted bookings table ----------
def _conn() -> sqlite3.Connection:
    global _INIT
    c = sqlite3.connect(store._DB, timeout=15)
    c.execute("PRAGMA busy_timeout=15000")
    if not _INIT:
        c.execute("""CREATE TABLE IF NOT EXISTS bookings(
            id TEXT PRIMARY KEY, start_utc TEXT NOT NULL, status TEXT NOT NULL,
            created TEXT NOT NULL, blob BLOB NOT NULL)""")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_bookings_slot ON bookings(start_utc) "
                  "WHERE status='confirmed'")
        c.commit()
        _INIT = True
    return c


def _booked_starts() -> set[str]:
    with _LOCK, closing(_conn()) as c, c:
        rows = c.execute("SELECT start_utc FROM bookings WHERE status='confirmed'").fetchall()
    return {r[0] for r in rows}


def _intervals_from_rows(rows, av: dict) -> list[tuple[_dt.datetime, _dt.datetime]]:
    """(start, end+buffer) for confirmed appointment rows of (start_utc, blob).

    Duration comes from the appointment itself: programme sessions store their
    minutes in the encrypted payload; intro calls predate that field and fall
    back to the configured slot length. A row whose blob cannot be decrypted
    still blocks at the default length — an unreadable appointment is still an
    appointment, and the failure mode of guessing short is a double booking.
    """
    buf = int(av.get("buffer_minutes", 0))
    default_min = int(av.get("slot_minutes", 25))
    out = []
    for iso, blob in rows:
        try:
            start = _dt.datetime.fromisoformat(iso)
        except Exception:
            continue
        minutes = default_min
        try:
            rec = json.loads(store._fernet().decrypt(blob).decode("utf-8"))
            minutes = int(rec.get("minutes") or default_min)
        except Exception:
            pass
        out.append((start, start + _dt.timedelta(minutes=minutes + buf)))
    return out


def _busy_intervals() -> list[tuple[_dt.datetime, _dt.datetime]]:
    av = get_availability()
    with _LOCK, closing(_conn()) as c, c:
        rows = c.execute("SELECT start_utc, blob FROM bookings WHERE status='confirmed'").fetchall()
    return _intervals_from_rows(rows, av)


def _overlaps(t0: _dt.datetime, t1: _dt.datetime,
              busy: list[tuple[_dt.datetime, _dt.datetime]]) -> bool:
    return any(t0 < e and s < t1 for s, e in busy)


def _booked_per_day(tz: ZoneInfo) -> dict[str, int]:
    """Confirmed bookings counted per LOCAL calendar day.

    max_per_day caps how many appointments may be BOOKED in a day — it is not a
    limit on how many times are offered. Counting has to happen in the practice
    timezone, not UTC: a 20:00 Madrid slot is 18:00 UTC in winter and would land
    on the right day either way, but an early-morning slot after a DST shift
    would not, and the cap would silently apply to the wrong date.
    """
    out: dict[str, int] = {}
    with _LOCK, closing(_conn()) as c, c:
        rows = c.execute("SELECT start_utc FROM bookings WHERE status='confirmed'").fetchall()
    for (iso,) in rows:
        try:
            day = _dt.datetime.fromisoformat(iso).astimezone(tz).date().isoformat()
        except Exception:
            continue
        out[day] = out.get(day, 0) + 1
    return out


def list_bookings(include_past: bool = False) -> list[dict]:
    with _LOCK, closing(_conn()) as c, c:
        rows = c.execute("SELECT id,start_utc,status,created,blob FROM bookings ORDER BY start_utc").fetchall()
    out = []
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    for r in rows:
        if not include_past and r[1] < now and r[2] == "confirmed":
            pass  # keep past confirmed visible for the day itself; simple approach: include all
        rec = json.loads(store._fernet().decrypt(r[4]).decode("utf-8"))
        rec.update(id=r[0], start_utc=r[1], status=r[2], created=r[3])
        out.append(rec)
    return out


def cancel(booking_id: str) -> bool:
    with _LOCK, closing(_conn()) as c, c:
        cur = c.execute("UPDATE bookings SET status='cancelled' WHERE id=? AND status='confirmed'",
                        (booking_id,))
    return cur.rowcount > 0


# ---------- slot computation ----------
def _tz() -> ZoneInfo:
    return ZoneInfo(get_availability().get("timezone", "Europe/Madrid"))


def compute_slots() -> dict:
    """Return {'timezone', 'slot_minutes', 'days':[{'date','label','slots':[{'utc','local'}]}]}"""
    av = get_availability()
    tz = _tz()
    step = int(av["slot_minutes"]) + int(av["buffer_minutes"])
    now = _dt.datetime.now(_dt.timezone.utc)
    earliest = now + _dt.timedelta(hours=int(av["lead_hours"]))
    busy = _busy_intervals()
    per_day = _booked_per_day(tz)
    cap = int(av.get("max_per_day", 6))
    days = []
    today_local = _dt.datetime.now(tz).date()
    for d in range(int(av["horizon_days"])):
        day = today_local + _dt.timedelta(days=d)
        if day.isoformat() in av.get("blocked_dates", []):
            continue
        iso_day = day.isoformat()
        # The cap is on BOOKINGS, not on offers. A day that has reached it shows
        # nothing; a day below it shows every slot its windows define. Previously
        # this truncated the offered list to max_per_day, so a six-hour Monday
        # exposed six times and hid the rest even with nothing booked at all.
        if cap > 0 and per_day.get(iso_day, 0) >= cap:
            continue
        ov = (av.get("overrides") or {})
        windows = ov[iso_day] if iso_day in ov else av["windows"].get(_WD[day.weekday()], [])
        slots = []
        for w in windows:
            try:
                a, b = w.split("-")
                t0 = _dt.datetime.combine(day, _dt.time.fromisoformat(a.strip()), tz)
                t1 = _dt.datetime.combine(day, _dt.time.fromisoformat(b.strip()), tz)
            except Exception:
                continue
            t = t0
            while t + _dt.timedelta(minutes=int(av["slot_minutes"])) <= t1:
                utc = t.astimezone(_dt.timezone.utc)
                # Overlap against every confirmed appointment, not equality of
                # start times. A 60-minute programme session at 10:00 must hide
                # the 10:30 intro slot too — exact-match hiding only worked
                # while everything sat on the same fixed grid.
                cand_end = utc + _dt.timedelta(minutes=int(av["slot_minutes"]) + int(av["buffer_minutes"]))
                if utc >= earliest and not _overlaps(utc, cand_end, busy):
                    slots.append({"utc": utc.isoformat(), "local": t.strftime("%H:%M")})
                t += _dt.timedelta(minutes=step)
        if slots:
            days.append({"date": day.isoformat(),
                         "label": day.strftime("%a %d %b"),
                         "slots": slots})
    return {"timezone": str(tz), "slot_minutes": av["slot_minutes"], "days": days}


# ---------- booking ----------
def book(slot_utc: str, name: str, email: str, language: str, note: str,
         profile: dict | None = None) -> dict:
    """Atomically claim a slot. Raises ValueError on invalid/taken slots."""
    # slot must be one we'd actually offer
    offered = {s["utc"] for day in compute_slots()["days"] for s in day["slots"]}
    if slot_utc not in offered:
        raise ValueError("slot not available")
    bid = uuid.uuid4().hex[:12]
    payload = {"name": name, "email": email, "language": language, "note": note,
               "profile": profile or {}}
    blob = store._fernet().encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    av = get_availability()
    cap = int(av.get("max_per_day", 6))
    day_iso = _dt.datetime.fromisoformat(slot_utc).astimezone(_tz()).date().isoformat()
    with _LOCK, closing(_conn()) as c, c:
        # Re-check cap AND overlap INSIDE the lock. compute_slots() above ran
        # without it, so two requests arriving together — or a request racing
        # Desiree saving a programme session — would both have seen room.
        rows = c.execute("SELECT start_utc, blob FROM bookings WHERE status='confirmed'").fetchall()
        if cap > 0:
            taken = sum(1 for iso, _b in rows
                        if _dt.datetime.fromisoformat(iso).astimezone(_tz()).date().isoformat() == day_iso)
            if taken >= cap:
                raise ValueError("day is fully booked — please pick another day")
        t0 = _dt.datetime.fromisoformat(slot_utc)
        t1 = t0 + _dt.timedelta(minutes=int(av["slot_minutes"]) + int(av.get("buffer_minutes", 0)))
        if _overlaps(t0, t1, _intervals_from_rows(rows, av)):
            raise ValueError("slot was just taken — please pick another")
        try:
            c.execute("INSERT INTO bookings(id,start_utc,status,created,blob) VALUES(?,?,?,?,?)",
                      (bid, slot_utc, "confirmed", store._now(), blob))
        except sqlite3.IntegrityError:
            raise ValueError("slot was just taken — please pick another")
    return {"id": bid, "start_utc": slot_utc}


# ─────────────────────────── programme sessions (planned by Desiree) ─────────
# When a client buys a programme, the calls that come WITH it are planned from
# the console: the engine proposes a rhythm from the package and Desiree's own
# availability, she adjusts, and the saved sessions live in the same bookings
# table (kind="session" in the encrypted payload). Living there is the whole
# point — _busy_intervals() sees them, so the public /book page stops offering
# every overlapping time the moment they are saved.

# Default plan per package: which calls a programme contains and in which week.
# config.json packages[].sessions overrides these (same shape) without a deploy.
_SESSION_PLANS = {
    # deep = 90: the iOS app and the website sell Klarheit with a 90-minute
    # deep-dive — the planner must not quietly book a shorter call than sold
    "root": [{"key": "deep", "n": 1, "week": 0, "minutes": 90},
             {"key": "review", "n": 1, "week": 2, "minutes": 45}],
    "bloom": [{"key": "kickoff", "n": 1, "week": 0, "minutes": 60},
              {"key": "weekly", "n": 2, "week": 1, "minutes": 45},
              {"key": "weekly", "n": 3, "week": 2, "minutes": 45},
              {"key": "weekly", "n": 4, "week": 3, "minutes": 45}],
    "flourish": [{"key": "kickoff", "n": 1, "week": 0, "minutes": 60}]
                + [{"key": "weekly", "n": i, "week": i - 1, "minutes": 45} for i in range(2, 13)],
}
_SESSION_PLANS["flourishing"] = _SESSION_PLANS["flourish"]   # legacy key alias

_SESSION_LABELS = {
    "deep":    {"de": "Tiefengespräch", "en": "Deep-dive session", "es": "Sesión profunda"},
    "review":  {"de": "Besprechungsgespräch", "en": "Report review call", "es": "Sesión de revisión"},
    "kickoff": {"de": "Kick-off-Gespräch", "en": "Kick-off call", "es": "Sesión inicial"},
    "weekly":  {"de": "Begleitgespräch {n}", "en": "Guidance call {n}", "es": "Sesión de acompañamiento {n}"},
}


# The customer-facing programme names per language (renamed 2026-08-05).
# config.json keeps only the German master; everything client-facing localises
# through here — the same table /api/app/offers uses.
_PKG_NAMES = {
    "root": {"de": "Klarheit", "en": "Clarity", "es": "Claridad"},
    "bloom": {"de": "Wandel", "en": "Change", "es": "Cambio"},
    "flourish": {"de": "Balance", "en": "Balance", "es": "Equilibrio"},
    "flourishing": {"de": "Balance", "en": "Balance", "es": "Equilibrio"},
}


# Taglines belong here too, not in config.json — that file holds only the German
# master, so every English and Spanish reader got "Clarity · Tiefen-Erstanalyse".
# Same copy as the app's L10n prog.*.tagline keys, so both surfaces read alike.
_PKG_TAGLINES = {
    "root": {"de": "Dein Deep-Dive: Standortbestimmung mit persönlichem Bericht.",
             "en": "Your deep-dive: a full picture with a personal report.",
             "es": "Tu sesión profunda: una visión completa con informe personal."},
    "bloom": {"de": "Vier Wochen Begleitung — von der Analyse in die Umsetzung.",
              "en": "Four weeks of guidance — from analysis into practice.",
              "es": "Cuatro semanas de acompañamiento — del análisis a la práctica."},
    "flourish": {"de": "Zwölf Wochen Transformation — tiefgehend und nachhaltig.",
                 "en": "Twelve weeks of transformation — deep and lasting.",
                 "es": "Doce semanas de transformación — profunda y duradera."},
    "grove": {"de": "Wissenschaftsbasierte Workshops für Teams und Unternehmen.",
              "en": "Science-led workshops for teams and companies.",
              "es": "Talleres con base científica para equipos y empresas."},
}
_PKG_TAGLINES["flourishing"] = _PKG_TAGLINES["flourish"]


def package_display_name(key: str, lang: str, fallback: str = "") -> str:
    return _PKG_NAMES.get(key, {}).get(lang) or fallback or key


def package_display_tagline(key: str, lang: str, fallback: str = "") -> str:
    return _PKG_TAGLINES.get(key, {}).get(lang) or fallback


def session_label(key: str, n: int, lang: str = "de") -> str:
    tpl = _SESSION_LABELS.get(key, {}).get(lang) or _SESSION_LABELS.get(key, {}).get("de") or key
    return tpl.format(n=n)


def session_plan(package_key: str) -> list[dict]:
    """The session spec for a package — config.json wins over the defaults."""
    for p in cfg.config().get("packages", []):
        if p.get("key") == package_key and isinstance(p.get("sessions"), list):
            return [dict(s) for s in p["sessions"]]
    return [dict(s) for s in _SESSION_PLANS.get(package_key, [])]


def staff_free_slots(minutes: int, days: int, start: _dt.date | None = None,
                     ignore_ids: list[str] | None = None) -> list[dict]:
    """Free start times for an appointment of `minutes`, over Desiree's windows.

    Same grid, blocked dates, overrides and daily cap as the public page — but
    no lead-time gate (she plans her own calendar) and the fit is checked for
    the SESSION length, not the intro length: a 60-minute call must end inside
    the window it starts in.

    ignore_ids: appointments to treat as free — a re-plan must not consider the
    very sessions it is re-planning to be obstacles.
    """
    av = get_availability()
    tz = _tz()
    step = int(av["slot_minutes"]) + int(av["buffer_minutes"])
    buf = int(av.get("buffer_minutes", 0))
    cap = int(av.get("max_per_day", 6))
    skip = set(ignore_ids or [])
    with _LOCK, closing(_conn()) as c, c:
        rows = c.execute("SELECT id, start_utc, blob FROM bookings WHERE status='confirmed'").fetchall()
    kept = [(iso, blob) for bid, iso, blob in rows if bid not in skip]
    busy = _intervals_from_rows(kept, av)
    per_day: dict[str, int] = {}
    for iso, _b in kept:
        try:
            d = _dt.datetime.fromisoformat(iso).astimezone(tz).date().isoformat()
            per_day[d] = per_day.get(d, 0) + 1
        except Exception:
            continue
    now = _dt.datetime.now(_dt.timezone.utc)
    first = start or _dt.datetime.now(tz).date()
    out = []
    for d in range(days):
        day = first + _dt.timedelta(days=d)
        iso_day = day.isoformat()
        if iso_day in av.get("blocked_dates", []):
            continue
        if cap > 0 and per_day.get(iso_day, 0) >= cap:
            continue
        ov = (av.get("overrides") or {})
        windows = ov[iso_day] if iso_day in ov else av["windows"].get(_WD[day.weekday()], [])
        for w in windows:
            try:
                a, b = w.split("-")
                t0 = _dt.datetime.combine(day, _dt.time.fromisoformat(a.strip()), tz)
                t1 = _dt.datetime.combine(day, _dt.time.fromisoformat(b.strip()), tz)
            except Exception:
                continue
            t = t0
            while t + _dt.timedelta(minutes=minutes) <= t1:
                utc = t.astimezone(_dt.timezone.utc)
                end = utc + _dt.timedelta(minutes=minutes + buf)
                if utc > now and not _overlaps(utc, end, busy):
                    out.append({"utc": utc.isoformat(), "date": iso_day,
                                "local": t.strftime("%H:%M"),
                                "label": f"{_DAYS['de'][day.weekday()][:2]} {day.strftime('%d.%m.')} {t.strftime('%H:%M')}"})
                t += _dt.timedelta(minutes=step)
    return out


def _local_target(anchor_utc: _dt.datetime, weeks_later: int, tz: ZoneInfo) -> _dt.datetime:
    """anchor + N weeks, in LOCAL wall-clock terms.

    Adding a 7-day timedelta to a UTC datetime preserves the UTC time of day —
    across a DST change that is one hour AWAY from the local time the client
    was promised. "Same time every week" means the wall clock in Madrid, so
    step the local date and re-attach the local time.
    """
    local = anchor_utc.astimezone(tz)
    return _dt.datetime.combine(local.date() + _dt.timedelta(days=7 * weeks_later),
                                local.time(), tz)


def propose_sessions(package_key: str, language: str = "de",
                     cid: str = "") -> list[dict]:
    """A full programme schedule proposal: one entry per session in the plan.

    The rhythm clients actually keep is "same day, same time, every week" — so
    the proposal anchors on the first free slot at least three days out and
    repeats its weekday and LOCAL time week for week (DST-safe), nudging to the
    nearest free time within the week only when something already sits there.
    Every entry carries that week's remaining free slots as alternatives — the
    console's adjustment dropdown.

    With a cid, the proposal is a RE-plan and behaves like one: the client's
    own future sessions are not "busy" (they are what is being re-planned), a
    session she already HELD is skipped rather than re-proposed, and a plan
    entry matching one of her future sessions defaults to its current time —
    so "move only call 4" really moves only call 4.
    """
    plan = session_plan(package_key)
    if not plan:
        return []
    # weeks are relative offsets; a config plan starting at week 1 must not
    # push every later session a week beyond the anchor
    week0 = min(int(s.get("week", 0)) for s in plan)
    weeks = max(int(s.get("week", 0)) for s in plan) - week0 + 1
    horizon = weeks * 7 + 14
    tz = _tz()
    now = _dt.datetime.now(_dt.timezone.utc)
    earliest = now + _dt.timedelta(days=3)
    own: dict[tuple, dict] = {}
    held: set[tuple] = set()
    ignore: list[str] = []
    if cid:
        for s in sessions_for_client(cid):
            if s.get("status") != "confirmed":
                continue
            k = (s.get("session_key"), int(s.get("session_n", 1)))
            if s["start_utc"] <= now.isoformat():
                held.add(k)                    # already happened — not re-planned
            else:
                own[k] = s
                ignore.append(s["id"])
    by_minutes: dict[int, list[dict]] = {}
    for s in plan:
        m = int(s.get("minutes", 45))
        if m not in by_minutes:
            by_minutes[m] = staff_free_slots(m, horizon, ignore_ids=ignore)
    anchor = None
    out = []
    taken: set[str] = set()

    def week_slots(m, center, lo_days=3, hi_days=4):
        lo = center - _dt.timedelta(days=lo_days)
        hi = center + _dt.timedelta(days=hi_days)
        return [f for f in by_minutes[m]
                if lo <= _dt.datetime.fromisoformat(f["utc"]) < hi]

    for s in sorted(plan, key=lambda x: (int(x.get("week", 0)), int(x.get("n", 1)))):
        key, n = s.get("key", "weekly"), int(s.get("n", 1))
        if (key, n) in held:
            continue                          # that call already took place
        m = int(s.get("minutes", 45))
        week = int(s.get("week", 0)) - week0
        entry = {"key": key, "n": n, "minutes": m, "week": week,
                 "label": session_label(key, n, language)}
        cur = own.get((key, n))
        if cur:
            # keep what stands: her current time is the default, and the week
            # around it is offered for moving just this one call
            t_cur = _dt.datetime.fromisoformat(cur["start_utc"])
            local = t_cur.astimezone(tz)
            cur_slot = {"utc": cur["start_utc"], "date": local.date().isoformat(),
                        "local": local.strftime("%H:%M"),
                        "label": f"{_DAYS['de'][local.weekday()][:2]} {local.strftime('%d.%m.')} {local.strftime('%H:%M')}"}
            alts = week_slots(m, t_cur)
            if not any(a["utc"] == cur_slot["utc"] for a in alts):
                alts = [cur_slot] + alts
            taken.add(cur["start_utc"])
            if anchor is None:
                anchor = t_cur
            entry.update(utc=cur["start_utc"], local=cur_slot["label"],
                         alternatives=sorted(alts, key=lambda f: f["utc"])[:60])
            out.append(entry)
            continue
        free = [f for f in by_minutes[m] if f["utc"] not in taken
                and _dt.datetime.fromisoformat(f["utc"]) >= earliest]
        if anchor is None:
            pick = free[0] if free else None
            if pick:
                anchor = _dt.datetime.fromisoformat(pick["utc"])
        else:
            target = _local_target(anchor, week, tz)
            in_week = [f for f in free
                       if target - _dt.timedelta(days=3)
                       <= _dt.datetime.fromisoformat(f["utc"])
                       < target + _dt.timedelta(days=4)]
            pick = min(in_week, key=lambda f: abs(_dt.datetime.fromisoformat(f["utc"]) - target),
                       default=None)
        if pick:
            taken.add(pick["utc"])
            entry.update(utc=pick["utc"], local=pick["label"],
                         alternatives=week_slots(m, _dt.datetime.fromisoformat(pick["utc"]))[:60])
        else:
            entry.update(utc="", local="", alternatives=[])
        out.append(entry)
    return out


def sessions_for_client(cid: str) -> list[dict]:
    return [b for b in list_bookings()
            if b.get("kind") == "session" and b.get("client_id") == cid
            and b.get("status") in ("confirmed", "cancelled")]


def save_sessions(cid: str, name: str, email: str, language: str,
                  sessions: list[dict], package_key: str = "") -> tuple[list[dict], list[dict]]:
    """Persist a full programme schedule, replacing the client's FUTURE sessions.

    Returns (created, dropped): the sessions now standing, and the previously
    planned ones that appear in no entry of the new plan — the caller turns
    those into METHOD:CANCEL components so they leave the client's calendar.

    Replace-not-append keeps the console model simple: the plan on screen is
    the plan, saving it twice is idempotent, and adjusting one call is just
    saving the plan again. Past sessions are history and stay untouched.
    Everything happens inside the engine lock: the free check that ran while
    Desiree was looking at the screen is re-run against the real table here,
    so a client booking an intro call in that window cannot be double-booked.

    Deliberately NOT enforced here: availability windows, blocked dates and
    the daily cap. Desiree placing her own call on a Saturday morning is her
    decision, not a validation error; overlap and future-time are the only
    physical constraints.
    """
    av = get_availability()
    buf = int(av.get("buffer_minutes", 0))
    cleaned = []
    for s in sessions:
        try:
            t0 = _dt.datetime.fromisoformat(str(s.get("utc", "")))
        except Exception:
            raise ValueError(f"invalid time: {s.get('utc')!r}")
        if t0.tzinfo is None:
            raise ValueError("session times must be timezone-aware UTC")
        m = int(s.get("minutes", 45))
        if not 15 <= m <= 180:
            raise ValueError("session length must be 15–180 minutes")
        if t0 <= _dt.datetime.now(_dt.timezone.utc):
            raise ValueError(f"{t0.astimezone(_tz()):%d.%m. %H:%M} liegt in der Vergangenheit")
        cleaned.append({"utc": t0.astimezone(_dt.timezone.utc), "minutes": m,
                        "key": str(s.get("key", "weekly"))[:20], "n": int(s.get("n", 1))})
    cleaned.sort(key=lambda s: s["utc"])
    # the new sessions must not overlap each other either
    for a, b in zip(cleaned, cleaned[1:]):
        if b["utc"] < a["utc"] + _dt.timedelta(minutes=a["minutes"] + buf):
            raise ValueError(f"two sessions overlap ({a['utc']:%d.%m. %H:%M} / {b['utc']:%d.%m. %H:%M} UTC)")
    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()
    created = []
    dropped = []
    with _LOCK, closing(_conn()) as c, c:
        rows = c.execute("SELECT id, start_utc, status, blob FROM bookings").fetchall()
        keep_rows = []
        prev: dict[tuple, dict] = {}     # (key, n) -> the session being replaced
        # Highest SEQUENCE this (key, n) has EVER carried — across replaced and
        # cancelled rows too. A cancellation went out with seq+1; a later
        # re-plan reusing the same UID at a lower SEQUENCE would be discarded
        # as stale by every RFC 5546 calendar.
        max_seq: dict[tuple, int] = {}
        for bid, iso, status, blob in rows:
            try:
                rec = json.loads(store._fernet().decrypt(blob).decode("utf-8"))
            except Exception:
                if status == "confirmed":
                    keep_rows.append((iso, blob))
                continue
            is_mine = rec.get("kind") == "session" and rec.get("client_id") == cid
            if is_mine:
                k = (rec.get("session_key"), int(rec.get("session_n", 1)))
                max_seq[k] = max(max_seq.get(k, 0), int(rec.get("seq", 0))
                                 + (1 if status == "cancelled" else 0))
            if status != "confirmed":
                continue
            if is_mine and iso > now_iso:
                c.execute("UPDATE bookings SET status='replaced' WHERE id=?", (bid,))
                prev[(rec.get("session_key"), int(rec.get("session_n", 1)))] = \
                    {"utc": iso, "seq": int(rec.get("seq", 0)),
                     "minutes": int(rec.get("minutes", 45)),
                     "key": rec.get("session_key"), "n": int(rec.get("session_n", 1))}
            else:
                keep_rows.append((iso, blob))
        busy = _intervals_from_rows(keep_rows, av)
        for s in cleaned:
            end = s["utc"] + _dt.timedelta(minutes=s["minutes"] + buf)
            if _overlaps(s["utc"], end, busy):
                raise ValueError(
                    f"{s['utc'].astimezone(_tz()):%a %d.%m. %H:%M} kollidiert mit einem bestehenden Termin")
            busy.append((s["utc"], end))
        for s in cleaned:
            bid = uuid.uuid4().hex[:12]
            # The row id changes on every save; the CALENDAR identity must not.
            # uid + seq implement RFC 5546 updating: the client's calendar sees
            # the same UID with a higher SEQUENCE and MOVES the event, instead
            # of stacking a duplicate next to the stale one.
            old = prev.pop((s["key"], s["n"]), None)
            base = max_seq.get((s["key"], s["n"]), 0)
            # unchanged time on an unbroken lineage keeps its seq; anything
            # else (moved, or a lineage that saw a cancel) climbs above every
            # SEQUENCE the client's calendar may already hold
            seq = old["seq"] if (old and old["utc"] == s["utc"].isoformat()
                                 and old["seq"] >= base) else base + 1 if (old or base) else 0
            payload = {"name": name, "email": email, "language": language,
                       "kind": "session", "client_id": cid, "package": package_key,
                       "minutes": s["minutes"], "session_key": s["key"], "session_n": s["n"],
                       "seq": seq, "uid": f"{cid}-{s['key']}{s['n']}",
                       "label": session_label(s["key"], s["n"], "de"), "note": "", "profile": {}}
            blob = store._fernet().encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            c.execute("INSERT INTO bookings(id,start_utc,status,created,blob) VALUES(?,?,?,?,?)",
                      (bid, s["utc"].isoformat(), "confirmed", store._now(), blob))
            created.append({"id": bid, "utc": s["utc"].isoformat(),
                            "minutes": s["minutes"], "key": s["key"], "n": s["n"],
                            "seq": seq, "uid": f"{cid}-{s['key']}{s['n']}"})
        # sessions that existed before but are in no row of the new plan — the
        # caller sends these as CANCEL components so they leave her calendar
        dropped = list(prev.values())
    return created, dropped


_DAYS = {
    "de": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "es": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
}
_MONTHS = {
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
           "August", "September", "Oktober", "November", "Dezember"],
    "en": ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
           "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
}


def format_when(slot_utc: str, language: str = "de") -> str:
    """The appointment time as the client should read it, in their language.

    strftime("%A, %d %B %Y") was doing this before, and it gave every client
    English weekday and month names — "Wednesday, 12 August 2026" inside an
    otherwise German mail — because the service runs under the C locale and
    setlocale() would need de_DE/es_ES generated on the host to behave. Twelve
    month names and seven weekday names are cheaper and cannot fail to install.
    """
    av = get_availability()
    tz = ZoneInfo(av.get("timezone", "Europe/Madrid"))
    t = _dt.datetime.fromisoformat(slot_utc).astimezone(tz)
    lang = language if language in _DAYS else "de"
    day, mon = _DAYS[lang][t.weekday()], _MONTHS[lang][t.month - 1]
    stamp = f"{day}, {t.day}. {mon} {t.year}" if lang == "de" else (
            f"{day}, {t.day} de {mon} de {t.year}" if lang == "es" else
            f"{day}, {t.day} {mon} {t.year}")
    return f"{stamp} · {t:%H:%M} ({av.get('timezone', 'Europe/Madrid')})"


_ICS_TEXT = {
    "de": ("Kennenlerngespräch", "Dein Gespräch mit {owner} · Auralis Natura.",
           "Teilnehmen", "Online"),
    "en": ("Introductory call", "Your call with {owner} · Auralis Natura.",
           "Join", "Online"),
    "es": ("Llamada de presentación", "Tu llamada con {owner} · Auralis Natura.",
           "Unirse", "En línea"),
}


def calendar_links(slot_utc: str, client_name: str = "", language: str = "de") -> dict:
    """One-click "add to my calendar" URLs — no file, no download, no app.

    An .ics attachment is the correct thing to send and the wrong thing to ask
    someone to use: on a phone it is a file you have to find, open and trust,
    and Gmail on Android will not open it at all. These two URLs open the
    person's own calendar with the event already filled in, which is what
    almost every booking service actually links. The .ics still rides along for
    Apple Mail (which renders it natively) and for Outlook desktop.
    """
    from urllib.parse import quote
    av = get_availability()
    start = _dt.datetime.fromisoformat(slot_utc)
    end = start + _dt.timedelta(minutes=int(av["slot_minutes"]))
    co = cfg.company()
    meet = co.get("meet_link", "")
    title, dtpl, join, online = _ICS_TEXT.get(language, _ICS_TEXT["de"])
    text = f"Auralis Natura — {title}"
    details = dtpl.format(owner=co.get("owner", "Dr. rer. nat. Desiree Gruber"))
    if meet:
        details += f"\n{join}: {meet}"
    loc = meet or online
    z = lambda t: t.strftime("%Y%m%dT%H%M%SZ")
    iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "google": ("https://calendar.google.com/calendar/render?action=TEMPLATE"
                   f"&text={quote(text)}&dates={z(start)}/{z(end)}"
                   f"&details={quote(details)}&location={quote(loc)}"),
        "outlook": ("https://outlook.live.com/calendar/0/deeplink/compose"
                    "?path=/calendar/action/compose&rru=addevent"
                    f"&subject={quote(text)}&startdt={iso(start)}&enddt={iso(end)}"
                    f"&body={quote(details)}&location={quote(loc)}"),
    }


def _ics_esc(s: str) -> str:
    r"""Escape an RFC 5545 TEXT value.

    Not cosmetic: a client called "Moser, Maria" puts a bare comma into SUMMARY,
    where a comma separates values — the event silently loses everything after
    it, or the whole invite is rejected. Backslash first, or it re-escapes the
    escapes.
    """
    return (str(s or "").replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def _ics_ctrl(s: str) -> str:
    r"""Strip control characters from a value that lands OUTSIDE a TEXT field.

    Parameter values (CN="...") and mailto: URIs cannot be backslash-escaped —
    a CR/LF smuggled through the booking form's name or email field would end
    the line early and let the attacker append their own ICS properties
    (ORGANIZER, ATTENDEE, anything). Names also lose the two characters that
    terminate a quoted parameter; emails lose everything that cannot appear in
    a mailto address.
    """
    return "".join(ch for ch in str(s or "") if ch >= " " and ch != "\x7f")


def _ics_cn(s: str) -> str:
    return _ics_ctrl(s).replace('"', "").replace(";", "").replace(":", "")


def _ics_mailto(s: str) -> str:
    return "".join(ch for ch in _ics_ctrl(s) if ch not in ' ";:<>()[]\\,')


def ics_for(slot_utc: str, client_name: str, booking_id: str,
            client_email: str = "", language: str = "de",
            cancel: bool = False) -> bytes:
    """A real calendar INVITE (METHOD:REQUEST): Gmail/Google Calendar show it as
    an event card with accept buttons and add it to team@'s calendar automatically.

    The client reads this invite too, so its wording follows the language they
    chose on the form — it is as customer-facing as the mail carrying it.
    """
    av = get_availability()
    start = _dt.datetime.fromisoformat(slot_utc)
    end = start + _dt.timedelta(minutes=int(av["slot_minutes"]))
    co = cfg.company()
    c = cfg.config()
    organizer = c.get("from_email", "team@auralisnatura.com")
    meet = co.get("meet_link", "")
    owner = co.get("owner", "Dr. rer. nat. Desiree Gruber")
    title, dtpl, join, online = _ICS_TEXT.get(language, _ICS_TEXT["de"])
    fmt = lambda t: t.strftime("%Y%m%dT%H%M%SZ")
    desc = _ics_esc(dtpl.format(owner=owner)) + (f"\\n{_ics_esc(join)}: {meet}" if meet else "")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Auralis Natura//Booking//DE",
        # Der CANCEL-Zwilling trägt DIESELBE UID mit höherer SEQUENCE — nur so
        # verschwindet das bereits angenommene Event wieder aus ihrem Kalender.
        "CALSCALE:GREGORIAN", ("METHOD:CANCEL" if cancel else "METHOD:REQUEST"),
        "BEGIN:VEVENT",
        f"UID:{booking_id}@auralisnatura.com",
        f"DTSTAMP:{fmt(_dt.datetime.now(_dt.timezone.utc))}",
        f"DTSTART:{fmt(start)}", f"DTEND:{fmt(end)}",
        f'ORGANIZER;CN="Auralis Natura":mailto:{organizer}',
        f'ATTENDEE;CN="Auralis Natura";ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED:mailto:{organizer}',
    ]
    if client_email:
        # CN quoted AND control-stripped: an unquoted comma/colon ends the
        # parameter early, and a smuggled CRLF would let the sender inject
        # whole ICS properties of their own.
        lines.append(f'ATTENDEE;CN="{_ics_cn(client_name)}";ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:{_ics_mailto(client_email)}')
    lines += [
        f"SUMMARY:Auralis Natura — {_ics_esc(title)}: {_ics_esc(client_name)}",
        f"DESCRIPTION:{desc}",
        (f"LOCATION:{_ics_esc(meet)}" if meet else f"LOCATION:{_ics_esc(online)}"),
        *( [f"URL:{meet}"] if meet else [] ),
        ("STATUS:CANCELLED" if cancel else "STATUS:CONFIRMED"),
        ("SEQUENCE:1" if cancel else "SEQUENCE:0"), "TRANSP:OPAQUE",
        "X-MICROSOFT-CDO-BUSYSTATUS:BUSY",
        "BEGIN:VALARM", "TRIGGER:-PT30M", "ACTION:DISPLAY", "DESCRIPTION:Auralis Natura Call", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR", "",
    ]
    return "\r\n".join(lines).encode("utf-8")


def _session_uid(s: dict, cid: str = "") -> str:
    """The CALENDAR identity of a session — stable across re-plans.

    The database row id changes every save (replace-not-append), but the
    client's calendar must recognise "Begleitgespräch 2" as the same event
    whenever it is moved. cid + session key + number is exactly that identity.
    """
    uid = s.get("uid")
    if not uid:
        key = s.get("key", s.get("session_key", "weekly"))
        n = int(s.get("n", s.get("session_n", 1)))
        uid = f"{cid or s.get('client_id', '')}-{key}{n}"
    return f"{uid}@auralisnatura.com"


def sessions_ics(sessions: list[dict], client_name: str, client_email: str,
                 language: str = "de", cid: str = "", cancel: bool = False) -> bytes:
    """ONE calendar carrying the whole programme — a VEVENT per session.

    One file, one accept: Google and Apple both add every event from a single
    METHOD:REQUEST calendar — the whole rhythm lands in her calendar at once.
    Each VEVENT's UID is the session's stable identity (cid + key + number,
    NOT the row id, which changes on every save), and SEQUENCE carries the
    session's revision — so a re-plan MOVES the events in the client's
    calendar instead of stacking duplicates, per RFC 5546.

    cancel=True builds the counterpart: METHOD:CANCEL with STATUS:CANCELLED
    and a bumped SEQUENCE, which removes the events from her calendar — sent
    when a session is dropped or cancelled outright.
    """
    co = cfg.company()
    c = cfg.config()
    organizer = _ics_mailto(c.get("from_email", "team@auralisnatura.com"))
    meet = co.get("meet_link", "")
    owner = co.get("owner", "Dr. rer. nat. Desiree Gruber")
    _t, dtpl, join, online = _ICS_TEXT.get(language, _ICS_TEXT["de"])
    fmt = lambda t: t.strftime("%Y%m%dT%H%M%SZ")
    stamp = fmt(_dt.datetime.now(_dt.timezone.utc))
    cn = _ics_cn(client_name)
    mailto = _ics_mailto(client_email)
    desc = _ics_esc(dtpl.format(owner=owner)) + (f"\\n{_ics_esc(join)}: {meet}" if meet else "")
    method = "CANCEL" if cancel else "REQUEST"
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Auralis Natura//Programme//DE",
             "CALSCALE:GREGORIAN", f"METHOD:{method}"]
    for s in sessions:
        start = _dt.datetime.fromisoformat(s.get("utc") or s["start_utc"])
        end = start + _dt.timedelta(minutes=int(s.get("minutes", 45)))
        title = session_label(s.get("key", s.get("session_key", "weekly")),
                              int(s.get("n", s.get("session_n", 1))), language)
        seq = int(s.get("seq", 0)) + (1 if cancel else 0)
        lines += [
            "BEGIN:VEVENT",
            f"UID:{_session_uid(s, cid)}",
            f"DTSTAMP:{stamp}", f"DTSTART:{fmt(start)}", f"DTEND:{fmt(end)}",
            f'ORGANIZER;CN="Auralis Natura":mailto:{organizer}',
            f'ATTENDEE;CN="Auralis Natura";ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED:mailto:{organizer}',
            f'ATTENDEE;CN="{cn}";ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:{mailto}',
            f"SUMMARY:Auralis Natura — {_ics_esc(title)}",
            f"DESCRIPTION:{desc}",
            (f"LOCATION:{_ics_esc(meet)}" if meet else f"LOCATION:{_ics_esc(online)}"),
            *( [f"URL:{meet}"] if meet else [] ),
            ("STATUS:CANCELLED" if cancel else "STATUS:CONFIRMED"),
            f"SEQUENCE:{seq}", "TRANSP:OPAQUE",
            "X-MICROSOFT-CDO-BUSYSTATUS:BUSY",
            *( [] if cancel else ["BEGIN:VALARM", "TRIGGER:-PT30M", "ACTION:DISPLAY",
                                  "DESCRIPTION:Auralis Natura", "END:VALARM"] ),
            "END:VEVENT",
        ]
    lines += ["END:VCALENDAR", ""]
    return "\r\n".join(lines).encode("utf-8")
