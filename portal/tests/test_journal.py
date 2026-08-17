#!/usr/bin/env python3
"""Impulse — the console-to-app content channel.

Covers the three things that would hurt if wrong: that guest mode leaks nothing
it should not, that the claim lint blocks real claims without blocking the
refer-out sentence the guardrails require, and that a client only ever sees her
own language.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: E402,F401
import os  # noqa: E402
os.environ.setdefault("AURALIS_API_KEY", "test-key")

from lib import cfg, journal, auth  # noqa: E402
cfg.reset_caches()
from server.app import app  # noqa: E402

KEY = {"X-Auralis-Key": "test-key"}
FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


def run() -> int:
    c = app.test_client()

    print("· the claim lint blocks claims but never the refer-out sentence")
    check("a cure claim is caught", journal.lint("Das heilt Hashimoto.") != [])
    check("'garantiert' is caught", journal.lint("Garantiert mehr Energie.") != [])
    # The guardrails REQUIRE this sentence. A bare substring matcher blocks it.
    check("the required refer-out sentence passes",
          journal.lint("Falls du eine Diagnose bekommen hast, sprich mit deiner Ärztin.") == [],
          str(journal.lint("Falls du eine Diagnose bekommen hast, sprich mit deiner Ärztin.")))
    check("'keine medizinische Diagnose' passes",
          journal.lint("Coaching ist keine medizinische Diagnose.") == [])
    check("English refer-out passes",
          journal.lint("This is not a diagnosis and does not replace medical care.") == [])
    check("Spanish refer-out passes",
          journal.lint("No sustituye la atención médica.") == [])

    print("\n· authoring, seeded from a slot so she writes once")
    slot = {"id": "slot-01", "hook": "Schlaf",
            "caption_de": "Deutscher Text.", "caption_en": "English text.",
            "caption_es": "Texto español."}
    art = journal.from_slot(slot)
    journal.upsert(art)
    check("all three captions carried over",
          all(art["body"][l] for l in ("de", "en", "es")))
    check("the rendered image is NOT auto-adopted as a cover", art["cover"] == "",
          "her typography is baked into the 1080×1350 canvas; cropping cuts her words")
    check("linked back to the slot", art["source_slot"] == "slot-01")

    print("\n· publishing is blocked by default, overridable with a logged reason")
    bad = journal.new_article(body={"de": "Das heilt deine Schilddrüse."})
    journal.upsert(bad)
    got, err = journal.publish(bad["id"])
    check("a claim blocks publication", got is None and err.get("error") == "claim_language",
          str(err))
    got, err = journal.publish(bad["id"], override_reason="Zitat aus einer Studie, geprüft")
    check("an override needs a reason and is recorded",
          got is not None and got["override"]["reason"].startswith("Zitat"), str(err))
    empty = journal.new_article()
    journal.upsert(empty)
    check("an empty article cannot be published", journal.publish(empty["id"])[0] is None)

    print("\n· the client feed is one language and nothing else")
    journal.publish(art["id"])
    de = journal.feed("de")
    check("feed carries the client's language only",
          de and de[0]["body"] == "Deutscher Text." and "title" in de[0], str(de[:1]))
    check("no other language leaks", all("caption_en" not in a for a in de))
    check("the override note never reaches the app",
          all("override" not in a and "source_slot" not in a for a in journal.feed("de")))
    check("an article not written in a language is skipped there",
          all(a["body"] for a in journal.feed("es")))

    print("\n· guest mode leaks only what she marked public")
    pub = journal.new_article(body={"de": "Öffentlich."}, audience="public")
    journal.upsert(pub)
    journal.publish(pub["id"])
    ids_pub = {a["id"] for a in journal.feed("de", public_only=True)}
    check("public feed contains the public article", pub["id"] in ids_pub)
    check("public feed excludes clients-only articles", art["id"] not in ids_pub)
    r = c.get("/api/public/journal?lang=de")
    check("guest endpoint needs no auth", r.status_code == 200, str(r.status_code))
    got_ids = {a["id"] for a in r.get_json()["articles"]}
    check("guest endpoint serves only public", got_ids == ids_pub, str(got_ids))
    r = c.get("/api/app/journal")
    check("the client feed still requires a login", r.status_code == 401)

    print("\n· the console endpoints are staff-only")
    check("listing without the staff key is refused",
          c.get("/api/social/journal").status_code in (401, 403))
    r = c.post("/api/social/journal", headers=KEY, json={"body": {"de": "Neu."}})
    check("staff can create", r.status_code == 200 and r.get_json()["ok"])
    nid = r.get_json()["article"]["id"]
    r = c.post(f"/api/social/journal/{nid}/publish", headers=KEY, json={})
    check("staff can publish a clean article", r.status_code == 200, str(r.get_json()))
    r = c.post("/api/social/journal/does-not-exist/publish", headers=KEY, json={})
    check("unknown id is 404, not 500", r.status_code == 404)
    r = c.delete(f"/api/social/journal/{nid}", headers=KEY)
    check("staff can delete", r.status_code == 200 and journal.get(nid) is None)

    print("\n· the feed has an end")
    for i in range(journal.FEED_CAP + 6):
        a = journal.new_article(body={"de": f"Text {i}."})
        journal.upsert(a)
        journal.publish(a["id"])
    check(f"feed is capped at {journal.FEED_CAP}", len(journal.feed("de")) == journal.FEED_CAP,
          str(len(journal.feed("de"))))

    print("\n" + ("JOURNAL ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
