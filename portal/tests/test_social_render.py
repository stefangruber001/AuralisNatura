#!/usr/bin/env python3
"""S4: the visual factory — exact sizes, offline templates, honest fallback.

With Chromium (the dev sandbox has one) every asset must be a REAL PNG at the
EXACT Instagram size — read straight from the IHDR. Templates must be fully
self-contained (data: fonts and images only): a template that phones home
renders differently on the server than in review, which is a brand bug.
"""
from __future__ import annotations
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import _sandbox  # noqa: F401
import os
os.environ.setdefault("AURALIS_API_KEY", "test-key")

from lib import cfg, social, socialrender, render  # noqa: E402
from server.app import app  # noqa: E402

KEY = {"X-Auralis-Key": "test-key"}
FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


def png_size(p: Path) -> tuple[int, int]:
    d = p.read_bytes()
    assert d.startswith(b"\x89PNG"), "not a png"
    return struct.unpack(">II", d[16:24])


_JPG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")


def run() -> int:
    have_chrome = render._chrome() is not None
    print(f"· chromium present: {have_chrome}")

    print("\n· every template is self-contained (no external URLs)")
    v = {"headline": "Müdigkeit ist ein Signal", "sub": "Wissenschaft, warm erklärt",
         "myth": "Mythos", "fact": "Fakt", "question": "Was raubt dir Energie?",
         "items": ["Licht am Morgen", "Protein zum Frühstück", "Abends dimmen"],
         "slides": [{"title": f"S{i}", "body": "Text"} for i in range(5)],
         "title": "3 Impulse", "outro": "Folge uns"}
    pages = [socialrender.tpl_quote(v, 1080, 1350),
             socialrender.tpl_mythfact(v, 1080, 1350),
             socialrender.tpl_tips(v, 1080, 1350),
             socialrender.tpl_carousel_slide(v, 0, 5, 1080, 1350),
             socialrender.tpl_story(v, 1080, 1920),
             socialrender.tpl_reel_card(v, "title", 1080, 1920),
             socialrender.tpl_photo(v, 1080, 1350, None)]
    ext = [u for pg in pages for u in re.findall(r'(?:src|href)="(https?:[^"]+)"', pg)]
    check("zero external references across all templates", ext == [], str(ext[:3]))
    check("brand fonts embedded as data:font", all("data:font/woff2" in pg for pg in pages[:6]))
    check("umlauts survive escaping", "Müdigkeit ist ein Signal" in pages[0])

    print("\n· a full week renders at exact Instagram sizes")
    social.save_social({"objective_week": "Test", "cadence": {"posts": 2, "stories": 1, "reels": 1}})
    mat = social.add_material("foto.jpg", _JPG + b"\x00" * 500, "Testfoto")

    def model(prompt, timeout):
        return {"strategy": {"theme": "T", "rationale": "R"}, "slots": [
            {"kind": "post", "day": "Montag", "time": "09:00", "hook": "h",
             "caption_de": "de", "caption_en": "en", "caption_es": "es",
             "hashtags": ["#x"], "alt_text": "a", "cta": "c",
             "visual": {"template": "photo", "headline": "Echtes Foto, echter Moment",
                        "photo_id": mat["id"]}},
            {"kind": "carousel", "day": "Dienstag", "time": "10:00", "hook": "h",
             "caption_de": "de", "caption_en": "en", "caption_es": "es",
             "hashtags": [], "alt_text": "a", "cta": "",
             "visual": {"template": "carousel", "slides": v["slides"]}},
            {"kind": "story", "day": "Mittwoch", "time": "18:00", "hook": "h",
             "caption_de": "de", "caption_en": "en", "caption_es": "es",
             "hashtags": [], "alt_text": "a", "cta": "",
             "visual": {"template": "story", "question": "Frage?"}},
            {"kind": "reel", "day": "Freitag", "time": "11:00", "hook": "h",
             "caption_de": "de", "caption_en": "en", "caption_es": "es",
             "hashtags": [], "alt_text": "a", "cta": "",
             "visual": {"template": "reel", "title": "Titel", "outro": "Outro"}},
        ]}

    plan = social.run_strategy(claude=model)
    wk = plan["week"]
    c = app.test_client()
    sizes = {}
    for s in plan["slots"]:
        r = c.post(f"/api/social/week/{wk}/slot/{s['id']}/render", headers=KEY)
        check(f"{s['kind']} renders", r.status_code == 200, str(r.get_json()))
        body = r.get_json()
        if have_chrome:
            check(f"{s['kind']}: real PNGs, no fallback", body["fallback"] is False, str(body))
        base = cfg.OUTPUT_DIR / "social" / "weeks" / wk / "assets" / s["id"]
        for f in body["files"]:
            if f.endswith(".png"):
                sizes[f"{s['kind']}/{f}"] = png_size(base / f)

    if have_chrome:
        check("post is 1080x1350", sizes.get("post/post.png") == (1080, 1350), str(sizes))
        check("carousel has 5 slides at 1080x1350",
              all(sizes.get(f"carousel/slide-{i}.png") == (1080, 1350) for i in range(1, 6)))
        check("story is 1080x1920", sizes.get("story/story.png") == (1080, 1920))
        check("reel cards are 1080x1920",
              sizes.get("reel/reel-title.png") == (1080, 1920)
              and sizes.get("reel/reel-outro.png") == (1080, 1920))

    print("\n· asset serving is listed, downloadable and traversal-safe")
    sid = plan["slots"][0]["id"]
    r = c.get(f"/api/social/week/{wk}/assets/{sid}", headers=KEY)
    check("asset list", r.status_code == 200 and len(r.get_json()["files"]) >= 1)
    name = r.get_json()["files"][0]
    r = c.get(f"/api/social/week/{wk}/asset/{sid}/{name}", headers=KEY)
    check("asset downloads", r.status_code == 200 and len(r.data) > 100)
    check("unknown asset 404",
          c.get(f"/api/social/week/{wk}/asset/{sid}/nope.png", headers=KEY).status_code == 404)

    print("\n· the fallback contract (no chromium → .html beside the target)")
    real = render._CHROME_CANDIDATES[:]
    env = os.environ.pop("AURALIS_CHROME", None)
    try:
        render._CHROME_CANDIDATES.clear()
        out = cfg.OUTPUT_DIR / "social" / "probe" / "x.png"
        got = socialrender.to_png("<body>x</body>", out, 100, 100)
        check("fallback writes .html and returns it",
              got.suffix == ".html" and got.exists() and not out.exists())
    finally:
        render._CHROME_CANDIDATES.extend(real)
        if env:
            os.environ["AURALIS_CHROME"] = env

    print("\n" + ("SOCIAL RENDER ALL PASSED ✓" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(run())
