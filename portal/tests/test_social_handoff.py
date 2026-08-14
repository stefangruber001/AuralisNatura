#!/usr/bin/env python3
"""S5: handoff — stacked caption assembly, the week ZIP, the package mail."""
from __future__ import annotations
import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: F401
import os
os.environ.setdefault("AURALIS_API_KEY", "test-key")

from lib import cfg, social, mailer  # noqa: E402
from server.app import app  # noqa: E402

KEY = {"X-Auralis-Key": "test-key"}
FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


def model(prompt, timeout):
    return {"strategy": {"theme": "T", "rationale": "R"}, "slots": [
        {"kind": "post", "day": "Montag", "time": "09:00", "hook": "h",
         "caption_de": "Deutsch zuerst.", "caption_en": "English second.",
         "caption_es": "Español tercero.", "hashtags": ["#eins", "#zwei"],
         "alt_text": "Alt", "cta": "", "visual": {"template": "quote", "headline": "H", "sub": "S"}},
        {"kind": "story", "day": "Dienstag", "time": "18:00", "hook": "h",
         "caption_de": "Story-DE.", "caption_en": "", "caption_es": "",
         "hashtags": [], "alt_text": "", "cta": "",
         "visual": {"template": "story", "question": "F?"}},
    ]}


def run() -> int:
    social.save_social({"cadence": {"posts": 1, "stories": 1, "reels": 0}})
    plan = social.run_strategy(claude=model)
    wk = plan["week"]
    c = app.test_client()

    print("· the stacked caption")
    cap = social.assemble_caption(plan["slots"][0])
    check("DE first", cap.startswith("Deutsch zuerst."))
    check("three languages separated", cap.count("\n\n·\n\n") == 2)
    check("hashtags at the end", cap.endswith("#eins #zwei"))
    cap2 = social.assemble_caption(plan["slots"][1])
    check("missing languages leave no empty separators", "·" not in cap2 and cap2 == "Story-DE.")

    print("\n· the ZIP wants approvals")
    r = c.get(f"/api/social/week/{wk}/package.zip", headers=KEY)
    check("no approved slots → 400 with a reason", r.status_code == 400
          and "freigegeben" in r.get_json()["error"])

    # approve both + render the first so the ZIP carries an asset
    for s in plan["slots"]:
        social.update_slot(wk, s["id"], {"approved": True})
    c.post(f"/api/social/week/{wk}/slot/{plan['slots'][0]['id']}/render", headers=KEY)

    r = c.get(f"/api/social/week/{wk}/package.zip", headers=KEY)
    check("package downloads", r.status_code == 200)
    z = zipfile.ZipFile(io.BytesIO(r.data))
    names = z.namelist()
    check("checklist inside", "README-Checkliste.txt" in names)
    check("captions per slot", sum(1 for n in names if n.endswith("captions.txt")) == 2)
    check("rendered asset inside", any(n.endswith("post.png") for n in names))
    cap_txt = z.read([n for n in names if n.endswith("captions.txt")][0]).decode()
    check("caption file carries the stacked text + alt-text",
          "Deutsch zuerst." in cap_txt and "ALT-TEXT" in cap_txt)
    check("checklist mentions Meta Business Suite planner",
          "business.facebook.com" in z.read("README-Checkliste.txt").decode())

    print("\n· the package mail")
    r = c.post(f"/api/social/week/{wk}/mail", headers=KEY)
    check("mail endpoint ok", r.status_code == 200, str(r.get_json()))
    eml = sorted((cfg.OUTPUT_DIR / "social" / "internal").glob("*.eml"))
    check("audit .eml written", len(eml) >= 1)
    raw = eml[-1].read_bytes().decode("utf-8", "replace")
    check("subject names week + count", f"Social-Wochenpaket · {wk} · 2 Posts" in raw.replace("=C2=B7", "·")
          or "Social-Wochenpaket" in raw)
    check("small ZIP attached", "application/zip" in raw)

    msg = mailer.build_social_package_email(wk, social.load_plan(wk))
    check("builder works without a zip too", msg["Subject"].startswith("Social-Wochenpaket"))

    print("\n" + ("SOCIAL HANDOFF ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
