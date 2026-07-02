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
    booked = _booked_starts()
    days = []
    today_local = _dt.datetime.now(tz).date()
    for d in range(int(av["horizon_days"])):
        day = today_local + _dt.timedelta(days=d)
        if day.isoformat() in av.get("blocked_dates", []):
            continue
        iso_day = day.isoformat()
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
                iso = utc.isoformat()
                if utc >= earliest and iso not in booked:
                    slots.append({"utc": iso, "local": t.strftime("%H:%M")})
                t += _dt.timedelta(minutes=step)
        if slots:
            days.append({"date": day.isoformat(),
                         "label": day.strftime("%a %d %b"),
                         "slots": slots[: int(av.get("max_per_day", 6))]})
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
    with _LOCK, closing(_conn()) as c, c:
        try:
            c.execute("INSERT INTO bookings(id,start_utc,status,created,blob) VALUES(?,?,?,?,?)",
                      (bid, slot_utc, "confirmed", store._now(), blob))
        except sqlite3.IntegrityError:
            raise ValueError("slot was just taken — please pick another")
    return {"id": bid, "start_utc": slot_utc}


def ics_for(slot_utc: str, client_name: str, booking_id: str,
            client_email: str = "") -> bytes:
    """A real calendar INVITE (METHOD:REQUEST): Gmail/Google Calendar show it as
    an event card with accept buttons and add it to team@'s calendar automatically."""
    av = get_availability()
    start = _dt.datetime.fromisoformat(slot_utc)
    end = start + _dt.timedelta(minutes=int(av["slot_minutes"]))
    co = cfg.company()
    c = cfg.config()
    organizer = c.get("from_email", "team@auralisnatura.com")
    meet = co.get("meet_link", "")
    fmt = lambda t: t.strftime("%Y%m%dT%H%M%SZ")
    desc = f"Dein Gespräch mit {co.get('owner','Dr. rer. nat. Desiree Gruber')} · Auralis Natura." \
           + (f"\\nTeilnehmen: {meet}" if meet else "")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Auralis Natura//Booking//DE",
        "METHOD:REQUEST", "BEGIN:VEVENT",
        f"UID:{booking_id}@auralisnatura.com",
        f"DTSTAMP:{fmt(_dt.datetime.now(_dt.timezone.utc))}",
        f"DTSTART:{fmt(start)}", f"DTEND:{fmt(end)}",
        f"ORGANIZER;CN=Auralis Natura:mailto:{organizer}",
        f"ATTENDEE;CN=Auralis Natura;ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED:mailto:{organizer}",
    ]
    if client_email:
        lines.append(f"ATTENDEE;CN={client_name};ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:{client_email}")
    lines += [
        f"SUMMARY:Auralis Natura — Gespräch mit {co.get('owner','Dr. rer. nat. Desiree Gruber')}",
        f"DESCRIPTION:{desc}",
        (f"LOCATION:{meet}" if meet else "LOCATION:Online"),
        *( [f"URL:{meet}"] if meet else [] ),
        "STATUS:CONFIRMED", "SEQUENCE:0",
        "BEGIN:VALARM", "TRIGGER:-PT30M", "ACTION:DISPLAY", "DESCRIPTION:Auralis Natura Call", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR", "",
    ]
    return "\r\n".join(lines).encode("utf-8")
