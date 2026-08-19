"""The funnel: does it count the right things, and does it refuse the wrong ones.

Two properties are load-bearing and are pinned here rather than trusted:

1. **A referrer never reaches the database.** The bucket is computed before the
   write. For this business a Google referrer can carry a health question in its
   query string, so "we only store the channel" has to be a fact, not an
   intention — the assertion below reads the raw event rows back and fails if any
   URL, query or search term survived.

2. **The leak is the step that loses the most PEOPLE.** A funnel that reports the
   ugliest percentage sends the founder to fix a step where ten people were lost
   while four hundred walk out of a different one.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: F401,E402  — temp DB + config shield. MUST be first.

import os  # noqa: E402
os.environ["AURALIS_API_KEY"] = "test-key"

from server.app import app  # noqa: E402
from lib import analytics, store  # noqa: E402

KEY = {"X-Auralis-Key": "test-key"}
fails = []


def ck(n, c):
    print(("  PASS " if c else "  FAIL ") + n)
    (c or fails.append(n))


def run():
    c = app.test_client()

    print("· only whitelisted event names are stored")
    ck("known name accepted", analytics.record("view", "direct", "de") is True)
    ck("unknown name refused", analytics.record("buy_now_hack", "direct") is False)
    ck("sql-ish name refused", analytics.record("view'; DROP TABLE events;--") is False)
    names = {e["event"] for e in store.list_events("")}
    ck("nothing outside the whitelist landed", all(
        n.startswith("web_") is False or n[4:] in analytics.WEB_EVENTS for n in names))

    print("· a referrer is reduced to a channel BEFORE it is written")
    ck("instagram", analytics.channel_of("https://l.instagram.com/?u=x") == "instagram")
    ck("google", analytics.channel_of("https://www.google.com/search?q=schilddr%C3%BCse+m%C3%BCde") == "google")
    ck("own site is internal", analytics.channel_of("https://www.auralisnatura.com/impressum.html") == "intern")
    ck("empty is direct", analytics.channel_of("") == "direct")
    ck("unknown host is 'andere'", analytics.channel_of("https://forum.example.org/t/42") == "andere")

    analytics.record("view", analytics.channel_of(
        "https://www.google.com/search?q=hashimoto+ernaehrung+barcelona"), "de")
    blob = " ".join(str(e) for e in store.list_events(""))
    for leak in ("hashimoto", "search?q", "google.com/", "schilddr", "u=x"):
        ck(f"no '{leak}' in any stored event", leak not in blob)

    print("· the funnel counts step to step")
    for _ in range(100):
        analytics.record("view", "instagram")
    for _ in range(40):
        analytics.record("programmes", "instagram")
    for _ in range(10):
        analytics.record("call_click", "instagram")
    f = analytics.funnel(30)
    by = {s["key"]: s for s in f["stages"]}
    ck("views counted", by["view"]["count"] == 102)          # +2 from the checks above
    ck("programmes counted", by["programmes"]["count"] == 40)
    ck("intent merges the three click kinds", by["intent"]["count"] == 10)
    ck("conversion is from the PREVIOUS step", by["intent"]["from_prev"] == 25.0)
    ck("lost is an absolute count", by["programmes"]["lost"] == 62)
    ck("has_web_data true once the site reports", f["has_web_data"] is True)

    print("· a programme click says WHICH programme")
    # the website attribute uses the localised English names; the business uses
    # the internal keys, and only the internal keys may reach the console
    ck("clarity → root", analytics.PKG_ALIASES["clarity"] == "root")
    ck("change → bloom", analytics.PKG_ALIASES["change"] == "bloom")
    ck("balance → flourish", analytics.PKG_ALIASES["balance"] == "flourish")
    for _ in range(4):
        analytics.record("pkg_click", "instagram", "de", "clarity")
    for _ in range(6):
        analytics.record("pkg_click", "instagram", "de", "balance")
    analytics.record("pkg_click", "instagram", "de", "made-up-package")
    analytics.record("portal_click", "direct")
    pk = [e.get("pkg") for e in store.list_events("") if e["event"] == "web_pkg_click"]
    ck("stored as internal keys", pk.count("root") == 4 and pk.count("flourish") == 6)
    ck("an invented package is not stored", "made-up-package" not in pk and pk.count(None) == 1)
    ck("only pkg_click carries a package",
       all("pkg" not in e for e in store.list_events("") if e["event"] == "web_call_click"))

    sp = next(x for x in analytics.funnel(30)["stages"] if x["key"] == "intent")["split"]
    by = {r["key"]: r for r in sp}
    ck("rows are ordered by interest", sp == sorted(sp, key=lambda r: -r["count"]))
    ck("the free call still leads overall", sp[0]["key"] == "call")
    ck("Balance leads among the programmes",
       max((r for r in sp if r["key"].startswith("pkg:")), key=lambda r: r["count"])["key"]
       == "pkg:flourish")
    ck("Klarheit counted", by["pkg:root"]["count"] == 4)
    ck("a programme nobody clicked still has a row", by["pkg:bloom"]["count"] == 0)
    ck("unattributed clicks are shown, not dropped", by["pkg:?"]["count"] == 1)
    ck("labels come from config", by["pkg:root"]["label"] == "Klarheit")
    ck("free call is its own row", by["call"]["count"] == 10)
    ck("portal login is its own row", by["portal"]["count"] == 1)
    # the console prints the stage total and the split on one screen
    intent = next(x for x in analytics.funnel(30)["stages"] if x["key"] == "intent")
    ck("split sums to the intent stage", sum(r["count"] for r in sp) == intent["count"])
    ck("shares sum to 100", abs(sum(r["share"] for r in sp) - 100) < 0.5)

    print("· the leak is the step losing the most people, not the worst rate")
    # booking → won loses 8 of 10 (80 %); view → programmes loses 62 (62 %).
    for _ in range(10):
        store.log_event("booking")
    for _ in range(2):
        store.log_event("won")
    f = analytics.funnel(30)
    by = {s["key"]: s for s in f["stages"]}
    ck("won has the uglier rate", by["won"]["from_prev"] < by["programmes"]["from_prev"])
    ck("leak is still the step costing 62 people", f["leak"] == "programmes")

    print("· channels are aggregated, and only as far as a click")
    for _ in range(20):
        analytics.record("view", "google")
    analytics.record("pkg_click", "google")
    ch = {r["channel"]: r for r in analytics.channels(30)}
    ck("instagram views", ch["instagram"]["views"] == 100)
    ck("instagram intent counts calls AND programme clicks", ch["instagram"]["intent"] == 21)
    ck("instagram rate", ch["instagram"]["rate"] == 21.0)
    ck("google views incl. the one from the referrer check", ch["google"]["views"] == 21)
    ck("google rate is intent/views", ch["google"]["rate"] == 4.8)
    ck("channel rows carry no client identifier",
       all(set(r) == {"channel", "views", "intent", "rate"} for r in analytics.channels(30)))

    print("· /api/pulse is public, silent and rate-limited")
    r = c.post("/api/pulse", json={"e": "view", "r": "https://instagram.com/", "l": "de"})
    ck("good beacon → 204 and no body", r.status_code == 204 and not r.data)

    # The browser sends the body as text/plain so the request stays CORS-simple
    # and no preflight can drop it. If the server ever stops parsing that, the
    # Cockpit goes quietly empty and nothing anywhere reports an error.
    n0 = sum(1 for e in store.list_events("") if e["event"] == "web_deep_read")
    r = c.post("/api/pulse", data='{"e":"deep_read","r":"","l":"de"}',
               content_type="text/plain;charset=UTF-8")
    n1 = sum(1 for e in store.list_events("") if e["event"] == "web_deep_read")
    ck("text/plain beacon body is parsed", r.status_code == 204 and n1 == n0 + 1)
    ck("a garbled body is survivable",
       c.post("/api/pulse", data="not json at all", content_type="text/plain").status_code == 204)
    r = c.post("/api/pulse", json={"e": "nonsense"})
    ck("junk beacon → 204 too (never argue with a beacon)", r.status_code == 204)
    ck("no cookie is ever set", not r.headers.getlist("Set-Cookie"))
    before = len(store.list_events(""))
    for _ in range(30):
        c.post("/api/pulse", json={"e": "nonsense"})
    grew = len(store.list_events("")) - before
    ck("junk cannot fill the events table", grew == 0)

    print("· /api/funnel is staff-only and bounded")
    ck("no key → 401", c.get("/api/funnel").status_code == 401)
    body = c.get("/api/funnel?days=30", headers=KEY).get_json()
    ck("returns funnel, channels, daily", set(body) == {"funnel", "channels", "daily"})
    ck("days clamped low", c.get("/api/funnel?days=1", headers=KEY).get_json()["funnel"]["days"] == 7)
    ck("days clamped high", c.get("/api/funnel?days=99999", headers=KEY).get_json()["funnel"]["days"] == 365)
    ck("junk days falls back to 30",
       c.get("/api/funnel?days=abc", headers=KEY).get_json()["funnel"]["days"] == 30)

    print("· the daily rows reproduce the funnel totals exactly")
    # The Cockpit prints both on one screen; if they can disagree, one of them
    # is wrong and the founder cannot tell which.
    s = c.get("/api/funnel?days=30", headers=KEY).get_json()
    ck("daily views sum == funnel views",
       sum(d["views"] for d in s["daily"]) == s["funnel"]["stages"][0]["count"])
    ck("daily intent sum == funnel intent",
       sum(d["intent"] for d in s["daily"]) ==
       next(x for x in s["funnel"]["stages"] if x["key"] == "intent")["count"])

    print("\n" + ("ALL ANALYTICS TESTS PASSED ✓" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(run())
