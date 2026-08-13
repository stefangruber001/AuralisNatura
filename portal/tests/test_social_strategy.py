#!/usr/bin/env python3
"""S3: strategy + drafts — schema, three languages, lint, edit/approve, regen.

Offline throughout: the model is injected (or absent → stub), exactly the
repo's established provider pattern.
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


def model(prompt: str, timeout: int) -> dict:
    assert "<<<UNTRUSTED CONTEXT>>>" in prompt
    assert "Sichtbarkeit für Klarheit" in prompt          # objective reached the prompt
    assert "retreat.jpg" in prompt                        # photo inventory reached it
    assert "GERMAN FIRST" in prompt
    return {"strategy": {"theme": "Energie verstehen", "rationale": "Passt zu Ziel und Digest."},
            "slots": [
                {"kind": "post", "day": "Montag", "time": "09:00", "hook": "Müdigkeit ist ein Signal.",
                 "caption_de": "Anhaltende Müdigkeit heilt niemand mit Kaffee — aber verstehen kann man sie.",
                 "caption_en": "No one cures lasting tiredness with coffee — but you can understand it.",
                 "caption_es": "El café no cura el cansancio — pero se puede entender.",
                 "hashtags": ["#frauengesundheit", "#energie", "kaputt-ohne-#"],
                 "alt_text": "Zitatkarte", "cta": "Link im Profil.",
                 "visual": {"template": "quote", "headline": "Müdigkeit ist ein Signal",
                            "sub": "Wissenschaft, warm erklärt", "photo_id": ""}},
                {"kind": "carousel", "day": "Mittwoch", "time": "12:30", "hook": "5 Mythen.",
                 "caption_de": "Fünf Mythen über Eisen.", "caption_en": "Five iron myths.",
                 "caption_es": "Cinco mitos del hierro.", "hashtags": ["#eisen"],
                 "alt_text": "Karussell", "cta": "Speichern!",
                 "visual": {"template": "carousel",
                            "slides": [{"title": f"Mythos {n}", "body": "…"} for n in range(1, 6)],
                            "photo_id": ""}},
                {"kind": "story", "day": "Donnerstag", "time": "18:00", "hook": "Frage an dich.",
                 "caption_de": "Story.", "caption_en": "Story.", "caption_es": "Story.",
                 "hashtags": [], "alt_text": "Story-Frage", "cta": "",
                 "visual": {"template": "story", "question": "Was raubt dir Energie?", "photo_id": ""}},
                {"kind": "reel", "day": "Samstag", "time": "11:00", "hook": "Reel-Hook.",
                 "caption_de": "Reel-Caption.", "caption_en": "Reel caption.", "caption_es": "Reel.",
                 "hashtags": ["#reel"], "alt_text": "Reel", "cta": "",
                 "visual": {"template": "reel", "title": "3 Energie-Impulse",
                            "outro": "Folge @auralis_natura", "photo_id": "abc123"}},
                {"kind": "post", "day": "Kaputt-Tag", "time": "9:00", "hook": "x",
                 "caption_de": "ok", "caption_en": "ok", "caption_es": "ok",
                 "hashtags": [], "alt_text": "", "cta": "",
                 "visual": {"template": "nonsense"}},
            ]}


def run() -> int:
    social.save_social({"objective_week": "Sichtbarkeit für Klarheit",
                        "cadence": {"posts": 2, "stories": 1, "reels": 1}})
    social.add_material("retreat.jpg", bytes.fromhex("ffd8ff") + b"\x00" * 100, "Retreat, Querformat")

    print("· the plan: schema, languages, lint, normalisation")
    plan = social.run_strategy(claude=model)
    check("plan saved for this week", social.load_plan(plan["week"])["strategy"]["theme"] == "Energie verstehen")
    check("five slots normalised", len(plan["slots"]) == 5)
    s1 = plan["slots"][0]
    check("stacked languages present",
          s1["caption_de"] and s1["caption_en"] and s1["caption_es"])
    check("compliance lint flags 'heilt'/'cures'/'cura' on slot 1",
          "heilt" in s1["warnings"] and "cura" in s1["warnings"], str(s1["warnings"]))
    check("clean slot has no warnings", plan["slots"][1]["warnings"] == [])
    check("non-# hashtag dropped", s1["hashtags"] == ["#frauengesundheit", "#energie"])
    check("bad day replaced by a valid one", plan["slots"][4]["day"] in social._SLOT_DAYS)
    check("bad template mapped to the kind's default",
          plan["slots"][4]["visual"]["template"] == "quote")
    check("photo reference survives", plan["slots"][3]["visual"]["photo_id"] == "abc123")
    check("nothing pre-approved", all(not s["approved"] for s in plan["slots"]))

    print("\n· stub path: model failure, still a full reviewable week")
    def broken(prompt, timeout):
        raise RuntimeError("model offline")
    stub = social.run_strategy(claude=broken)
    check("stub provider labelled", stub["provider"].startswith("stub"), stub["provider"])
    check("stub honours cadence (2+1+1)", len(stub["slots"]) == 4, str(len(stub["slots"])))
    check("stub slots carry all three languages",
          all(s["caption_de"] and s["caption_en"] and s["caption_es"] for s in stub["slots"]))

    print("\n· review: edit, approve, warnings recomputed")
    wk = stub["week"]
    sid = stub["slots"][0]["id"]
    upd = social.update_slot(wk, sid, {"caption_de": "Dieses Programm heilt dich garantiert!",
                                       "approved": True, "hashtags": "energie #zyklus",
                                       "secret": "evil"})
    check("edit persisted + approved", upd["approved"] is True)
    check("warnings recomputed on edit", "heilt" in upd["warnings"] and "garantiert" in upd["warnings"])
    check("hashtags normalised from a plain string", upd["hashtags"] == ["#energie", "#zyklus"])
    check("unknown field ignored", "secret" not in upd)
    check("persisted to disk", social.load_plan(wk)["slots"][0]["approved"] is True)

    print("\n· regenerate one slot, others untouched")
    other_before = json.dumps(social.load_plan(wk)["slots"][1], sort_keys=True)
    new = social.regenerate_slot(wk, sid, claude=model)
    check("slot replaced under the same id", new["id"] == sid)
    check("regenerated slot is not pre-approved", new["approved"] is False)
    check("neighbour slot untouched",
          json.dumps(social.load_plan(wk)["slots"][1], sort_keys=True) == other_before)

    print("\n· the API surface")
    c = app.test_client()
    r = c.get("/api/social/weeks", headers=KEY)
    check("weeks listed", r.status_code == 200 and wk in r.get_json()["weeks"])
    r = c.get(f"/api/social/week/{wk}", headers=KEY)
    check("plan served", r.status_code == 200 and len(r.get_json()["slots"]) == 4)
    r = c.post(f"/api/social/week/{wk}/slot/{sid}", headers=KEY, json={"approved": False})
    check("slot update via API", r.status_code == 200 and r.get_json()["slot"]["approved"] is False)
    check("unknown week 404", c.get("/api/social/week/2020-W99", headers=KEY).status_code == 404)
    check("no auth 401", c.get(f"/api/social/week/{wk}").status_code == 401)

    print("\n" + ("SOCIAL STRATEGY ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
