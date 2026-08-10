#!/usr/bin/env python3
"""max_per_day caps BOOKINGS per day, not how many slots are offered.

The old code did `slots[:max_per_day]`, so a Monday with six hours of
availability showed six times and hid the rest even with nothing booked.

  python3 portal/tests/test_booking_cap.py
"""
import datetime as dt, json, os, pathlib, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = pathlib.Path(tempfile.mkdtemp())
os.environ.setdefault("AURALIS_DATA_KEY", "1FRxAvB2n0oPzDLcbnQOGTr9r2wSPqUwqbrJ4kIH9dQ=")
os.environ.update(AURALIS_DATA_DIR=str(TMP), AURALIS_ENV="test")

# booking._conn() opens store._DB — a module constant, NOT an env var. Setting
# AURALIS_DB does nothing, so a test that only sets env vars books into the REAL
# client database. This one did, before the redirect below was added: four test
# appointments landed in portal/auralis.db and had to be deleted by hand.
# Redirect the constant itself, and refuse to run if it still points at the
# live file.
from lib import store  # noqa: E402
store._DB = str(TMP / "test.db")
from lib import booking  # noqa: E402
booking._INIT = False
assert "portal/auralis.db" not in store._DB, "refusing to run against the live database"

# availability.json is read from the config dir, which AURALIS_DATA_DIR does not
# move either — so keep a copy of the real one and restore it at exit.
_AV_PATH = booking._avail_path()
_AV_BACKUP = _AV_PATH.read_text(encoding="utf-8") if _AV_PATH.exists() else None
import atexit  # noqa: E402
@atexit.register
def _restore():
    if _AV_BACKUP is not None:
        _AV_PATH.write_text(_AV_BACKUP, encoding="utf-8")

FAIL = []
def check(name, got, want):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + name + ("" if ok else f"\n         got {got!r}\n        want {want!r}"))
    if not ok:
        FAIL.append(name)

# A wide open week: 09:00-17:00 every day, 25-min slots, no buffer, no lead time.
# That is ~19 slots a day — far more than any sane max_per_day.
AV = dict(booking.get_availability())
AV.update(timezone="Europe/Madrid", slot_minutes=25, buffer_minutes=0, lead_hours=0,
          horizon_days=3, max_per_day=2,
          windows={k: ["09:00-17:00"] for k in
                   ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
          blocked_dates=[], overrides={})
booking.save_availability(AV)

days = booking.compute_slots()["days"]
assert days, "no days computed"
# NOT days[0]: run this in the afternoon and day 0 is today, already partly in
# the past, with a handful of slots left. Take the first day that starts whole.
today = dt.datetime.now(booking._tz()).date().isoformat()
full = [d for d in days if d["date"] > today]
assert full, "no fully future day in the horizon"
day0 = full[0]
n_first = len(day0["slots"])
check("all slots offered, not truncated to max_per_day", n_first > 2, True)
check("a full 09:00-17:00 window yields ~19 slots at 25 min", n_first >= 18, True)
for i in range(2):
    fresh = [d for d in booking.compute_slots()["days"] if d["date"] == day0["date"]]
    assert fresh, f"day {day0['date']} vanished after {i} bookings"
    booking.book(fresh[0]["slots"][0]["utc"], f"T{i}", f"t{i}@x.de", "de", "")

after = {d["date"]: len(d["slots"]) for d in booking.compute_slots()["days"]}
check("day disappears once the booking cap is reached", day0["date"] in after, False)
other = [d for d in booking.compute_slots()["days"] if d["date"] != day0["date"]]
other_full = [d for d in other if d["date"] > today]
check("other days keep every slot", len(other_full[0]["slots"]) >= 18, True)

# The cap must also hold at the booking endpoint, not only in the offer list.
try:
    booking.book(day0["slots"][-1]["utc"], "X", "x@x.de", "de", "")
    check("booking into a full day is refused", "accepted", "refused")
except ValueError as e:
    check("booking into a full day is refused", "refused", "refused")
    print(f"         ({e})")

# Raising the cap reopens the day without any other change.
AV["max_per_day"] = 5
booking.save_availability(AV)
reopened = [d for d in booking.compute_slots()["days"] if d["date"] == day0["date"]]
check("raising the cap reopens the day", bool(reopened), True)
if reopened:
    check("reopened day still hides the two taken times", len(reopened[0]["slots"]) >= 16, True)

print()
if FAIL:
    print(f"{len(FAIL)} FAILED: {', '.join(FAIL)}"); sys.exit(1)
print("all booking-cap checks passed")
