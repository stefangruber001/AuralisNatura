"""Payment comes BEFORE the programme starts, and the console must agree.

The console was built on a "deliver, then invoice" model: the 💶 button existed
only at the delivery stage and the unpaid alert waited fourteen days after that.
This business takes payment up front, so that ordering produced two real
failures — an unpaid programme could run to completion without a single warning,
and the Cockpit could show a client won with nothing paid, which under prepay is
an impossible state rather than a slow one.

Worse, recording a payment also jumped the client to "abgeschlossen". Under
prepay that fires right after the yes, so one click would have thrown away
intake, report and programme.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: F401,E402  — temp DB + config shield. MUST be first.

import os  # noqa: E402
os.environ["AURALIS_API_KEY"] = "test-key"

from server.app import app  # noqa: E402
from lib import cfg, store, analytics  # noqa: E402

KEY = {"X-Auralis-Key": "test-key"}
fails = []


def ck(n, c):
    print(("  PASS " if c else "  FAIL ") + n)
    (c or fails.append(n))


def _client(name, stage, pkg_key, paid, age_days=0):
    """Seed a client. upsert() stamps `updated` into the encrypted blob, so
    ageing a record means moving the clock, not the column."""
    cid = cfg.allocate_client(name=name, email=f"{name}@e.com".replace(" ", ""),
                              language="de", status="active")
    rec = store.ensure(cid)
    rec["stage"] = stage
    rec["paid"] = paid
    if pkg_key:
        p = next(x for x in cfg.config()["packages"] if x["key"] == pkg_key)
        rec["package"] = {"key": p["key"], "name": p["name"], "price": float(p["price"])}
    if age_days:
        import datetime as _dt
        old = (_dt.datetime.now(_dt.timezone.utc)
               - _dt.timedelta(days=age_days)).replace(microsecond=0).isoformat()
        real, store._now = store._now, (lambda: old)
        try:
            store.upsert(rec)
        finally:
            store._now = real
    else:
        store.upsert(rec)
    return cid


def run():
    c = app.test_client()

    print("· recording a payment does NOT move the client along")
    cid = _client("Marie", "won", "root", False)
    r = c.post(f"/api/client/{cid}/profile", headers=KEY, json={"paid": True})
    rec = store.get(cid)
    ck("payment accepted", r.status_code == 200 and rec["paid"] is True)
    ck("stage untouched — intake, report and programme still ahead", rec["stage"] == "won")
    ck("revenue is recorded from the flag, not from the stage",
       any(e["event"] == "paid" for e in store.list_events("")))

    print("· an unpaid programme that is RUNNING is an error, not a footnote")
    _client("Lena", "intake", "bloom", False, age_days=6)
    alerts = {a["key"]: a for a in c.get("/api/alerts", headers=KEY).get_json()["alerts"]}
    ck("running-unpaid raised", "unpaid" in alerts)
    ck("raised as an error", alerts.get("unpaid", {}).get("level") == "error")
    ck("names the client", any("Lena" in i["label"] for i in alerts["unpaid"]["items"]))
    ck("does not wait 14 days after delivery",
       "Programm läuft" in alerts["unpaid"]["items"][0]["label"])

    print("· a promise that has not been paid for is a warning after three days")
    _client("Sofia", "won", "flourish", False, age_days=6)
    _client("Nora", "won", "root", False, age_days=1)          # still fresh
    alerts = {a["key"]: a for a in c.get("/api/alerts", headers=KEY).get_json()["alerts"]}
    start = alerts.get("unpaid_start", {"items": [], "level": ""})
    labels = " ".join(i["label"] for i in start["items"])
    ck("pending payment raised", "unpaid_start" in alerts)
    ck("as a warning, not an error", start["level"] == "warn")
    ck("names the one that has waited", "Sofia" in labels)
    ck("leaves yesterday's promise alone", "Nora" not in labels)

    print("· a paid client raises nothing")
    _client("Ana", "prep", "flourish", True)
    alerts = c.get("/api/alerts", headers=KEY).get_json()["alerts"]
    paid_names = " ".join(i["label"] for a in alerts if a["key"].startswith("unpaid")
                          for i in a["items"])
    ck("no alert for a paid client", "Ana" not in paid_names)

    print("· the funnel puts payment before delivery, and says why")
    keys = [s["key"] for s in analytics.funnel(30)["stages"]]
    ck("won → paid → sent", keys.index("won") < keys.index("paid") < keys.index("sent"))
    paid_stage = next(s for s in analytics.funnel(30)["stages"] if s["key"] == "paid")
    ck("the hint calls it the start, not the invoice",
       "Vorkasse" in paid_stage["hint"] and "Startschuss" in paid_stage["hint"])

    print("· the console's own wiring matches")
    js = (ROOT / "web" / "staff.html").read_text(encoding="utf-8")
    mp = js[js.index("async function markPaid"):js.index("async function markPaid") + 700]
    ck("markPaid no longer forces the stage to 'done'", "stage:'done'" not in mp.replace(" ", ""))
    ck("payment is offered from 'won' onward, not only at delivery",
       "const owes=" in js and "'lead','call','lost'" in js.replace('"', "'"))
    ck("card 03 owns the payment", "Gewonnen · Zahlung & Zugang" in js)
    ck("card 06 no longer claims it", "Geliefert & Zahlung'" not in js)

    print("\n" + ("PAYMENT ORDER ALL PASSED ✓" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(run())
