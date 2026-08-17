#!/usr/bin/env python3
"""Build the programme photo imagesets from their masters.

Why this exists: the four programme photos were hand-committed portrait JPEGs
with no `scale` key, while the card hero is a 4:3 LANDSCAPE box filled with
`scaledToFill`. So iOS threw away 40–50 % of every image's height at render
time, decoded 6 MiB per card to paint it, and still fell short of 3x on the
largest iPhone. Every device also downloaded one bitmap sized for none of them.

This bakes the crop the app was already showing — full width, vertical centre —
and emits a real 1x/2x/3x ladder, so App Store thinning ships each device only
its own slice and the pixels line up with the points.

    python3 ios-app/scripts/build_photo_assets.py

Idempotent. Re-run after replacing a master.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("needs Pillow:  pip install Pillow --break-system-packages")

ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG = ROOT / "ios-app" / "AuralisApp" / "Assets.xcassets"

# The hero is 4:3 and at most 400 pt wide (iPhone 16 Pro Max: 440 pt screen −
# 40 pt padding). 400×300 pt is therefore the nominal size; @3x = 1200×900 px.
POINT_W, POINT_H = 400, 300
QUALITY = 82

# asset name → master. Keys come from CatalogStore.photo(for:) in Stores.swift.
PHOTOS = {
    "PhotoNourish": "images/nourish.jpg",              # root      · Klarheit
    "PhotoTea": "images/tea.jpg",                      # bloom     · Wandel
    "PhotoBowl": "brand/photos/programme-wandel-bowl.jpg",  # flourish · Balance
    "PhotoPortrait": "images/desiree-portrait.jpg",     # grove/default · Verbindung
}


def crop_4x3(im: Image.Image) -> Image.Image:
    """The region the app already displays: full width, vertical centre.

    `scaledToFill` into a wider-than-tall box is width-driven for a portrait
    source, so pre-cropping to this exact region changes nothing on screen — it
    only stops shipping pixels that were never visible.
    """
    w, h = im.size
    want_h = round(w * POINT_H / POINT_W)
    if want_h <= h:
        top = (h - want_h) // 2
        return im.crop((0, top, w, top + want_h))
    want_w = round(h * POINT_W / POINT_H)      # source already wide enough
    left = (w - want_w) // 2
    return im.crop((left, 0, left + want_w, h))


def build(name: str, master: Path) -> list[str]:
    im = Image.open(master).convert("RGB")
    src_size = im.size
    base = crop_4x3(im)
    out_dir = CATALOG / f"{name}.imageset"
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("*.jpg"):
        f.unlink()
    for f in out_dir.glob("*.png"):
        f.unlink()

    images, notes = [], []
    for scale in (1, 2, 3):
        w, h = POINT_W * scale, POINT_H * scale
        fn = f"{name.lower()}@{scale}x.jpg"
        # LANCZOS both ways; a source short of the 3x target is nudged up rather
        # than left inconsistent — iOS was already resampling it at render time.
        img = base.resize((w, h), Image.LANCZOS)
        img.save(out_dir / fn, "JPEG", quality=QUALITY, optimize=True, progressive=False)
        images.append({"filename": fn, "idiom": "universal", "scale": f"{scale}x"})
        if scale == 3 and base.size[0] < w:
            notes.append(f"upscaled {base.size[0]}→{w}px")
    (out_dir / "Contents.json").write_text(
        json.dumps({"images": images, "info": {"author": "xcode", "version": 1}},
                   indent=2) + "\n", encoding="utf-8")
    total = sum(f.stat().st_size for f in out_dir.iterdir())
    return [f"{name:14s} {src_size[0]}x{src_size[1]} → crop {base.size[0]}x{base.size[1]}"
            f" → ladder {total/1024:6.0f} KB" + (f"  ({', '.join(notes)})" if notes else "")]


def main() -> int:
    lines = []
    for name, rel in PHOTOS.items():
        master = ROOT / rel
        if not master.exists():
            print(f"missing master for {name}: {rel}")
            return 1
        lines += build(name, master)
    print("\n".join(lines))
    used = {f"{n}.imageset" for n in PHOTOS}
    stale = [d.name for d in CATALOG.iterdir()
             if d.name.endswith(".imageset") and d.name not in used
             and d.name.startswith("Photo")]
    if stale:
        print("\nno longer referenced (delete by hand if intended):", ", ".join(stale))
    return 0


if __name__ == "__main__":
    sys.exit(main())
