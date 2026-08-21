#!/usr/bin/env python3
"""The go-live self-test must never lie about mail, and must never bill the data.

Two failure modes are worse than the bug they are meant to find:

  · reporting success when nothing was actually sent — the founder would go live
    believing a buyer receives her access, and only a real customer would find
    out otherwise;
  · leaving a client record, a booked slot or a journey entry behind — a
    diagnostic that pollutes production data is one nobody dares run twice.

These pin both, plus the fact that the endpoint is staff-only: it sends mail, so
an open one would be a spam cannon aimed at Desiree's own domain reputation.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: E402,F401
import os  # noqa: E402
os.environ.setdefault("AURALIS_API_KEY", "test-key")

from lib import cfg  # noqa: E402
cfg.reset_caches()

FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


def run() -> int:
    from server.app import app
    c = app.test_client()
    K = {"X-Auralis-Key": os.environ["AURALIS_API_KEY"]}

    print("· the mail self-test is staff-only — it sends real mail")
    check("no key is refused", c.post("/api/selftest/mail").status_code in (401, 403))

    print("\n· with no SMTP password it must report failure, not success")
    # _sandbox pins email_mode=off and there is no AURALIS_SMTP_PASSWORD here,
    # which is exactly the state a half-configured host is in.
    os.environ.pop("AURALIS_SMTP_PASSWORD", None)
    cfg.config()["smtp_password"] = ""
    r = c.post("/api/selftest/mail", json={"to": "selftest@example.com"}, headers=K)
    check("the endpoint answers", r.status_code in (200, 409), str(r.status_code))
    if r.status_code == 200:
        d = r.get_json()
        check("it does NOT claim success", d.get("ok") is False, str(d))
        check("it names the instant path honestly",
              "not sent" in str((d.get("instant") or {}).get("ack", "")),
              str(d.get("instant")))
        check("it reports the mode that produced no draft",
              d.get("email_mode") == "off", str(d.get("email_mode")))

    print("\n· it must leave no trace in the business data")
    before_clients = len(cfg.clients().get("clients", {}))
    from lib import booking
    before_bookings = len(booking.list_bookings()) if hasattr(booking, "list_bookings") else None
    c.post("/api/selftest/mail", json={"to": "selftest@example.com"}, headers=K)
    check("no client was created",
          len(cfg.clients().get("clients", {})) == before_clients)
    if before_bookings is not None:
        check("no slot was booked", len(booking.list_bookings()) == before_bookings)

    print("\n· the recipient defaults to the practice's own address, never a client")
    cfg.config()["from_email"] = "team@auralisnatura.com"
    r = c.post("/api/selftest/mail", json={}, headers=K)
    if r.status_code == 200:
        check("defaults to from_email",
              r.get_json().get("to") == "team@auralisnatura.com",
              str(r.get_json().get("to")))

    print("\n· the go-live tool itself imports and parses")
    import py_compile
    for t in ("golive_test.py", "stripe_rehearsal.py", "console_check.py"):
        try:
            py_compile.compile(str(ROOT / "tools" / t), doraise=True)
            check(f"tools/{t} compiles", True)
        except Exception as e:
            check(f"tools/{t} compiles", False, str(e))

    print()
    if FAILS:
        print(f"{len(FAILS)} failure(s):")
        for f in FAILS:
            print("  ·", f)
        return 1
    print("go-live self-test: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
