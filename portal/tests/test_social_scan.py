#!/usr/bin/env python3
"""S2: the screening engine — fetch, dedupe, digest, and every failure mode.

Runs fully offline: the fetcher is injected, the Claude call is injected. The
one thing that must NEVER depend on the network or the model is that a scan
lands a digest file with the raw harvest in it.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: F401
import os
os.environ.setdefault("AURALIS_API_KEY", "test-key")

from lib import social  # noqa: E402
from server.app import app  # noqa: E402

KEY = {"X-Auralis-Key": "test-key"}
FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


_RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Journal</title>
<item><title>Eisenmangel und Erschöpfung: neue Übersichtsarbeit</title>
<link>https://example.org/eisen</link>
<description>&lt;p&gt;Eine Meta-Analyse zu Ferritin und Müdigkeit.&lt;/p&gt;</description>
<pubDate>Mon, 10 Aug 2026 06:00:00 GMT</pubDate></item>
<item><title>Schlaf und Zyklus — was die Forschung sagt</title>
<link>https://example.org/schlaf</link><description>Kurzreview.</description></item>
</channel></rss>"""

_ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<title>Health Atom</title>
<entry><title>Perimenopause: Ernährung als Hebel im Alltag</title>
<link href="https://example.net/peri"/><summary>Longread.</summary>
<updated>2026-08-09T10:00:00Z</updated></entry></feed>"""

_PAGE = """<html><body><nav><a href="/impressum">Impressum</a></nav>
<main><a href="/artikel/omega-3-in-der-stillzeit-worauf-achten">Omega-3 in der Stillzeit: worauf Frauen wirklich achten sollten</a>
<a href="/artikel/kurz">Kurz</a>
<a href="https://competitor.example/blog/darmgesundheit-mythen-2026">Darmgesundheit: die fünf hartnäckigsten Mythen 2026 im Check</a>
</main></body></html>"""


def fake_fetch(url: str) -> str:
    if "journal" in url:
        return _RSS
    if "atomfeed" in url:
        return _ATOM
    if "broken" in url:
        raise OSError("connection refused")
    return _PAGE


def fake_claude(prompt: str, timeout: int) -> dict:
    assert "<<<UNTRUSTED HARVEST>>>" in prompt and "<<<END HARVEST>>>" in prompt
    return {"themes": ["Energie & Zyklus"],
            "findings": [{"title": "Eisen & Müdigkeit", "why": "Kernthema", "source": "https://example.org/eisen"}],
            "angles": ["Mythos/Fakt: Eisen und Müdigkeit"],
            "competitor_topics": ["Darmgesundheit"]}


def broken_claude(prompt: str, timeout: int) -> dict:
    raise RuntimeError("model unavailable")


def run() -> int:
    social.save_social({"agents": [
        {"id": "journal", "name": "Journal", "type": "rss",
         "urls": ["https://journal.example/feed"], "enabled": True},
        {"id": "atom", "name": "Atom", "type": "rss",
         "urls": ["https://atomfeed.example/atom"], "enabled": True},
        {"id": "blog", "name": "Wettbewerberin", "type": "web",
         "urls": ["https://blog.example/"], "keywords": "Stillzeit", "enabled": True},
        {"id": "dead", "name": "Kaputt", "type": "rss",
         "urls": ["https://broken.example/feed"], "enabled": True},
        {"id": "off", "name": "Aus", "type": "rss",
         "urls": ["https://journal.example/feed"], "enabled": False},
    ]})

    print("· parsers: RSS, Atom, plain page")
    check("RSS items", len(social._parse_feed(_RSS)) == 2)
    check("RSS strips tags from description",
          "<p>" not in social._parse_feed(_RSS)[0]["summary"])
    check("Atom items via href", social._parse_feed(_ATOM)[0]["link"] == "https://example.net/peri")
    page = social._parse_page(_PAGE, "https://blog.example/")
    check("page: headline-length links only, absolute URLs",
          len(page) == 2 and page[0]["link"].startswith("https://blog.example/artikel/"))

    print("\n· a full scan: harvest, dedupe, one dead source, digest")
    d = social.run_scan(fetch=fake_fetch, claude=fake_claude)
    check("digest written for this ISO week", d["week"] == social.week_key())
    check("items from all live agents", d["items_total"] == 5, str(d["items_total"]))
    check("dead source recorded, not fatal",
          d["agents"]["dead"]["error"] != "" and d["agents"]["journal"]["error"] == "")
    check("disabled agent not scanned", "off" not in d["agents"])
    check("keyword hit ranked first for the blog agent",
          next(i for i in d["raw"] if i["agent"] == "blog")["matched"] is True)
    check("summary present", (d["summary"] or {}).get("themes") == ["Energie & Zyklus"])
    check("digest file on disk", social.load_digest(d["week"])["items_total"] == 5)

    print("\n· the second scan finds nothing new (seen-state dedupe)")
    d2 = social.run_scan(fetch=fake_fetch, claude=fake_claude)
    check("zero new items on rescan", d2["items_total"] == 0, str(d2["items_total"]))

    print("\n· a model failure never loses the harvest")
    st = social.state()
    st["seen"] = []
    social.save_state(st)
    d3 = social.run_scan(fetch=fake_fetch, claude=broken_claude)
    check("summary is null, provider says why",
          d3["summary"] is None and "model unavailable" in d3["provider"])
    check("raw harvest preserved", d3["items_total"] == 5)
    d4 = social.summarise_digest(d3["week"], claude=fake_claude)
    check("'Digest nachholen' repairs it from the stored raw items",
          (d4["summary"] or {}).get("themes") == ["Energie & Zyklus"])

    print("\n· the console API")
    c = app.test_client()
    r = c.get("/api/social/digests", headers=KEY)
    check("digest list", r.status_code == 200 and d3["week"] in r.get_json()["weeks"])
    r = c.get(f"/api/social/digest/{d3['week']}", headers=KEY)
    check("digest detail", r.status_code == 200 and r.get_json()["items_total"] == 5)
    check("bad week rejected", c.get("/api/social/digest/evil", headers=KEY).status_code == 404)
    r = c.get("/api/social/scan/status", headers=KEY)
    check("status route", r.status_code == 200 and "journal" in r.get_json()["agents"])
    check("agent test knows a URL-less agent",
          "keine URL" in (social.test_agent("nope") or {}).get("error", "agent not found")
          or social.test_agent("nope").get("error") == "agent not found")

    print("\n· 'Jetzt prüfen' does not eat the Monday scan's findings")
    st = social.state()
    st["seen"] = []
    social.save_state(st)
    t = social.test_agent("journal", fetch=fake_fetch)
    check("live test sees items", t["count"] == 2, str(t))
    d5 = social.run_scan(fetch=fake_fetch, claude=fake_claude)
    check("scan after test still harvests them", d5["items_total"] == 5, str(d5["items_total"]))

    print("\n" + ("SOCIAL SCAN ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
