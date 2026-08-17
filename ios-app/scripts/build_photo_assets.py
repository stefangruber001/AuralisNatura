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

# asset name → master, nominal point size, and where the crop window sits.
#
# `bias` is the vertical position of the window in the source: 0.0 hugs the top,
# 0.5 is centred, 1.0 hugs the bottom. It exists because a centred 4:3 window on
# a portrait photo of a person cuts their head off — which is exactly what
# happened to Desiree on the Verbindung card.
PHOTOS = {
    "PhotoNourish":  {"src": "images/nourish.jpg"},                      # root · Klarheit
    "PhotoTea":      {"src": "images/tea.jpg"},                          # bloom · Wandel
    "PhotoBowl":     {"src": "brand/photos/programme-wandel-bowl.jpg"},  # flourish · Balance
    # near the top so there is headroom above her scarf, not a cut forehead
    "PhotoPortrait": {"src": "images/desiree-portrait.jpg", "bias": 0.10},  # grove · Verbindung
    # The small square avatar beside her credential line on the welcome screen.
    # Measured, not eyeballed: in desiree-portrait.jpg the top of her headscarf is
    # at y≈115 and her face centres on x≈690, so the window starts at y=90 to keep
    # margin above the scarf. A first attempt started at y=255 and sliced the hat
    # off — if you move this box, check the TOP edge against the scarf first.
    "PhotoDesiree":  {"src": "images/desiree-portrait.jpg", "pt": (56, 56),
                      "crop": (470, 90, 910, 530)},
}


def crop_to(im: Image.Image, pt_w: int, pt_h: int, bias: float) -> Image.Image:
    """Largest window of the target aspect, positioned by `bias`.

    For a portrait source in a landscape box this is width-driven and the window
    slides vertically; for the reverse it slides horizontally (bias then reads
    left→right). bias 0.5 reproduces what `scaledToFill` shows today.
    """
    w, h = im.size
    want_h = round(w * pt_h / pt_w)
    if want_h <= h:
        top = round((h - want_h) * min(max(bias, 0.0), 1.0))
        return im.crop((0, top, w, top + want_h))
    want_w = round(h * pt_w / pt_h)
    left = round((w - want_w) * min(max(bias, 0.0), 1.0))
    return im.crop((left, 0, left + want_w, h))


def build(name: str, spec: dict) -> list[str]:
    master = ROOT / spec["src"]
    pt_w, pt_h = spec.get("pt", (POINT_W, POINT_H))
    im = Image.open(master).convert("RGB")
    src_size = im.size
    if spec.get("crop"):
        base = crop_to(im.crop(spec["crop"]), pt_w, pt_h, 0.5)
    else:
        base = crop_to(im, pt_w, pt_h, spec.get("bias", 0.5))
    out_dir = CATALOG / f"{name}.imageset"
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("*.jpg"):
        f.unlink()
    for f in out_dir.glob("*.png"):
        f.unlink()

    images, notes = [], []
    for scale in (1, 2, 3):
        w, h = pt_w * scale, pt_h * scale
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
    for name, spec in PHOTOS.items():
        if not (ROOT / spec["src"]).exists():
            print(f"missing master for {name}: {spec['src']}")
            return 1
        lines += build(name, spec)
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
