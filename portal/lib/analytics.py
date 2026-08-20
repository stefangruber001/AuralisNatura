"""The funnel: where people arrive, where they leave, and what that costs.

Two halves meet here.

The BOTTOM of the funnel already existed — bookings, wins, payments are logged
by the portal as anonymous events (store.log_event). What was missing is the
TOP: the website could not tell anyone how many people opened it, looked at a
programme, or reached for a call and changed their mind. Without that the first
and widest leak in the business was invisible.

Measurement is deliberately cookieless and aggregate-only: no cookie, no
identifier, no client-side state, no IP or user-agent stored — only "this
happened, at this hour, from this kind of referrer". That is the Plausible /
Fathom "privacy mode" shape, it needs no consent banner, and for a health
practice in the EU it is the only version worth having. The cost is honest and
must stay visible in the UI: we count PAGE OPENS, not people. Nothing here can
follow one visitor from the homepage to a purchase, and it should not be able to.

Everything is derived from the events table, which carries no personal data and
survives GDPR erasure, so the numbers stay truthful after a client exercises
Article 17.
"""
from __future__ import annotations

import datetime as _dt
from collections import Counter

from . import store

# ── what the website is allowed to report ────────────────────────────────────
# A whitelist, not a free-form name: a public endpoint that accepts arbitrary
# strings is a public endpoint that fills your database with someone else's junk.
WEB_EVENTS = {
    "view",         # a page was opened
    "programmes",   # the programmes section actually came into view
    "pkg_click",    # a programme's button was pressed
    "call_click",   # a free-introductory-call button was pressed
    "portal_click", # the client-portal sign-in link was pressed
    "faq_open",     # an FAQ question was opened
    "deep_read",    # scrolled past ~70 % of the page
}

# A programme button carries WHICH programme. The website's attribute uses the
# localised English names (clarity/change/balance) because those drive the Stripe
# links; everything else in this business — config, revenue, journey — uses the
# internal keys. Map here, once, so the funnel speaks the same language as the
# rest of the console and a package rename never has to touch two vocabularies.
PKG_ALIASES = {
    "clarity": "root", "change": "bloom", "balance": "flourish",
    "klarheit": "root", "wandel": "bloom", "equilibrio": "flourish",
    "claridad": "root", "cambio": "bloom",
    "root": "root", "bloom": "bloom", "flourish": "flourish", "flourishing": "flourish",
}

# Referrers are reduced to a channel before storage — never a full URL, which
# can carry a search term and with it a health question.
CHANNELS = {
    "instagram": ("instagram.", "l.instagram.", "ig."),
    "facebook": ("facebook.", "l.facebook.", "fb."),
    "google": ("google.", "www.google"),
    "linkedin": ("linkedin.", "lnkd."),
    "mail": ("mail.", "outlook.", "webmail."),
}


def channel_of(referrer: str) -> str:
    """A coarse bucket, so a search term can never be stored."""
    r = (referrer or "").strip().lower()
    if not r:
        return "direct"
    for host in ("http://", "https://"):
        if r.startswith(host):
            r = r[len(host):]
    r = r.split("/")[0]
    if "auralisnatura" in r:
        return "intern"
    for name, prefixes in CHANNELS.items():
        if any(r.startswith(p) or f".{p}" in f".{r}" for p in prefixes):
            return name
    return "andere"


def record(name: str, channel: str = "direct", lang: str = "", pkg: str = "") -> bool:
    """Store one website event. Returns False for anything not whitelisted."""
    if name not in WEB_EVENTS:
        return False
    meta = {"channel": channel if channel in ({"direct", "intern", "andere"} | set(CHANNELS))
            else "andere"}
    if lang in ("de", "en", "es"):
        meta["lang"] = lang
    # Only a programme click carries a programme, and only a known one: an
    # unrecognised value is dropped rather than stored, so a public endpoint can
    # never invent a fourth package in the console.
    if name == "pkg_click":
        key = PKG_ALIASES.get((pkg or "").strip().lower())
        if key:
            meta["pkg"] = key
    store.log_event("web_" + name, **meta)
    return True


# ── reading it back ──────────────────────────────────────────────────────────
def _since(days: int) -> str:
    return (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)).isoformat()


def _counts(events: list[dict]) -> Counter:
    return Counter(e.get("event", "") for e in events)


# The funnel as the business actually works: strangers → interest → intent →
# a conversation → a client → money → a delivered report. `measured` says
# whether a stage has a real source; a stage nobody has instrumented must never
# be drawn as a confident zero.
STAGES = [
    {"key": "view", "label": "Website geöffnet",
     "hint": "Seitenaufrufe — nicht Personen (wir setzen keine Cookies).",
     "src": "web_view"},
    {"key": "programmes", "label": "Programme angesehen",
     "hint": "Der Programm-Bereich kam wirklich ins Bild.",
     "src": "web_programmes"},
    {"key": "intent", "label": "Auf einen Button geklickt",
     "hint": "Kennenlerngespräch, Paket oder Portal-Login.",
     "src": ("web_call_click", "web_pkg_click", "web_portal_click")},
    {"key": "booking", "label": "Gespräch gebucht",
     "hint": "Der Termin steht im Kalender.", "src": "booking"},
    {"key": "won", "label": "Kundin geworden",
     "hint": "Nach dem Gespräch gewonnen.", "src": "won"},
    # Bezahlt wird VOR dem Programmstart — diese Stufe ist der Start, nicht die
    # Schlussrechnung. Beim Direktkauf über die Website fallen "gewonnen" und
    # "bezahlt" auf denselben Moment, dann sind beide Zahlen gleich.
    {"key": "paid", "label": "Bezahlt — Programm startet",
     "hint": "Vorkasse: die Zahlung ist der Startschuss, nicht die Schlussrechnung.",
     "src": "paid"},
    {"key": "sent", "label": "Bericht geliefert",
     "hint": "Der persönliche Bericht ist raus.", "src": "sent"},
]


def last_web_event() -> str:
    """When the website last reported anything, at ANY age.

    Without this the console cannot tell "nobody has opened the site since the
    counter went in" from "the counter is broken" — both look like an empty
    funnel, and one of them is an emergency while the other is a Tuesday. The
    window-limited counts cannot answer it, so this deliberately ignores the
    window.
    """
    for e in reversed(store.list_events("")):
        if str(e.get("event", "")).startswith("web_"):
            return str(e.get("ts", ""))
    return ""


def _pkg_names() -> dict:
    """German package names from config, so a rename lands here automatically."""
    try:
        from . import cfg
        return {p.get("key", ""): p.get("name", "") for p in cfg.config().get("packages", [])}
    except Exception:
        return {}


def intent_split(events: list[dict]) -> list[dict]:
    """WHICH button, not just "a button".

    One number for "reached for something" says the offer works; it cannot say
    whether the €899 draws the eye while the €199 gets the clicks, and those two
    findings lead to opposite decisions. The rows below always sum to the intent
    stage above them — the console prints both, so they must agree.
    """
    names = _pkg_names()
    rows = {"call": {"key": "call", "label": "Kostenloses Kennenlerngespräch", "count": 0},
            "portal": {"key": "portal", "label": "Portal-Login (bestehende Kundin)", "count": 0}}
    for key in ("root", "bloom", "flourish"):
        rows["pkg:" + key] = {"key": "pkg:" + key, "label": names.get(key) or key, "count": 0}
    unknown = {"key": "pkg:?", "label": "Programm (nicht zugeordnet)", "count": 0}

    for e in events:
        ev = e.get("event", "")
        if ev == "web_call_click":
            rows["call"]["count"] += 1
        elif ev == "web_portal_click":
            rows["portal"]["count"] += 1
        elif ev == "web_pkg_click":
            k = "pkg:" + str(e.get("pkg", ""))
            (rows.get(k) or unknown)["count"] += 1

    out = list(rows.values())
    if unknown["count"]:
        out.append(unknown)
    total = sum(r["count"] for r in out)
    for r in out:
        r["share"] = round(r["count"] / total * 100, 1) if total else 0.0
    # by size, so the strongest interest reads first — but keep a zero row: an
    # offer nobody reaches for is a finding, not something to hide
    out.sort(key=lambda r: -r["count"])
    return out


def funnel(days: int = 30) -> dict:
    """Stage counts, step conversion, and the single biggest leak.

    Conversion is measured step-to-step, not against the top: the number that
    tells you what to fix is "of those who got here, how many went on", and a
    percentage of all traffic hides which step is actually broken.
    """
    events = store.list_events(_since(days))
    c = _counts(events)

    rows, prev = [], None
    for st in STAGES:
        src = st["src"]
        n = sum(c.get(s, 0) for s in src) if isinstance(src, tuple) else c.get(src, 0)
        row = {"key": st["key"], "label": st["label"], "hint": st["hint"], "count": n,
               "measured": True}
        if st["key"] == "intent":
            row["split"] = intent_split(events)
        if prev is not None:
            row["from_prev"] = round(n / prev * 100, 1) if prev else None
            row["lost"] = max(0, prev - n)
        rows.append(row)
        prev = n

    # The worst step is the one that loses the most PEOPLE, not the one with the
    # ugliest percentage — a 90 % drop from 10 visitors is noise next to a 40 %
    # drop from 400.
    leak = None
    for i, r in enumerate(rows[1:], start=1):
        if r.get("lost") and (leak is None or r["lost"] > rows[leak]["lost"]):
            leak = i
    top = rows[0]["count"] or 0
    end = rows[-1]["count"] or 0
    return {
        "days": days,
        "stages": rows,
        "leak": rows[leak]["key"] if leak is not None else None,
        "overall": round(end / top * 100, 2) if top else None,
        "has_web_data": any(r["count"] for r in rows[:3]),
        "web_last_seen": last_web_event(),
    }


def channels(days: int = 30) -> list[dict]:
    """Where arrivals come from, and how far each source gets.

    Channel is attached to every website event, so a source can be followed as
    far as the last anonymous step — a click. It cannot be followed into a
    booking, because that would need an identifier we deliberately do not set.
    """
    events = store.list_events(_since(days))
    views: Counter = Counter()
    intent: Counter = Counter()
    for e in events:
        ev = e.get("event", "")
        if not ev.startswith("web_"):
            continue
        ch = e.get("channel", "direct")
        if ev == "web_view":
            views[ch] += 1
        elif ev in ("web_call_click", "web_pkg_click", "web_portal_click"):
            intent[ch] += 1
    out = []
    for ch, n in views.most_common():
        out.append({"channel": ch, "views": n, "intent": intent.get(ch, 0),
                    "rate": round(intent.get(ch, 0) / n * 100, 1) if n else 0.0})
    return out


def daily(days: int = 30) -> list[dict]:
    """One row per day: arrivals, intent, bookings — for the trend line."""
    events = store.list_events(_since(days))
    buckets: dict[str, dict] = {}
    for e in events:
        day = (e.get("ts") or "")[:10]
        if not day:
            continue
        b = buckets.setdefault(day, {"date": day, "views": 0, "intent": 0, "bookings": 0})
        ev = e.get("event", "")
        if ev == "web_view":
            b["views"] += 1
        elif ev in ("web_call_click", "web_pkg_click", "web_portal_click"):
            b["intent"] += 1
        elif ev == "booking":
            b["bookings"] += 1
    return [buckets[k] for k in sorted(buckets)]


def summary(days: int = 30) -> dict:
    f = funnel(days)
    return {"funnel": f, "channels": channels(days), "daily": daily(days)}
