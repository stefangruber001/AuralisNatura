#!/usr/bin/env python3
"""Build the square profile pictures for WhatsApp Business and the other socials.

Run:  python3 brand/make_social_avatars.py         (writes into brand/social/)

Why this exists rather than "just crop the logo":

* WhatsApp shows a profile photo as a CIRCLE inscribed in the square, so the
  four corners are always discarded and anything close to the circle's edge is
  clipped on some renderings. images/logo-ig-profile.png puts its outer ring
  almost exactly on that boundary — as a WhatsApp avatar it loses its frame.
* The avatar is read at ~48px in a chat list. At that size a wordmark and a
  "HOLISTIC HEALTH" kicker are grey mush; only the seal survives. So the
  WhatsApp variants carry the seal alone.
* logo-ig-profile.png is also on the OLD identity — a deep-forest-green outer
  ring, from before the 2026-06 move to the warm-earth palette. Everything here
  uses the tokens the live site uses today.

The seal itself is NOT redrawn. images/logo-emblem.png is the mark on the live
site, and an avatar that does not match the website is worse than a slightly
imperfect one. It is a clean circular medallion (opaque interior, transparent
corners), so it composites onto any background.
"""
from __future__ import annotations
import pathlib
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "brand" / "social"

# The live palette (index.html :root). Kept as literals with their token names
# so a future palette change is a visible, deliberate edit here too.
PAPER = (0xF5, 0xEE, 0xE0)   # --paper
CREAM = (0xFB, 0xF6, 0xEB)   # --cream
FOREST = (0x3D, 0x27, 0x19)  # --forest       dark cinnamon-brown (primary)
FOREST_DEEP = (0x22, 0x13, 0x05)
GOLD = (0xAD, 0x7A, 0x32)    # --gold
SAND = (0xDA, 0xC7, 0x9E)    # --sage-soft

# Where the mark comes from.
#
# brand/masters/seal-1600.png is the real master, supplied with the printed
# flyer handoff: 1600px, clean alpha, the same emblem as the website. Everything
# here downsamples from it, which is always better than upsampling.
#
# The fallbacks are what this script used before that master existed, kept so it
# still runs against an older checkout: images/logo-lockup.png carries the mark
# at 426px inside a 2172x724 canvas (cropped and alpha-masked below), and
# images/logo-emblem.png is the same thing at 300px. handover/assets/
# emblem_seal_360.png is deliberately never used — it is a DIFFERENT, far busier
# seal, and an avatar that does not match the website is worse than a soft one.
MASTER = ROOT / "brand" / "masters" / "seal-1600.png"
LOCKUP = ROOT / "images" / "logo-lockup.png"
EMBLEM = ROOT / "images" / "logo-emblem.png"

SEAL_FRAC = 0.78   # seal diameter as a fraction of the canvas
RING_FRAC = 0.90   # hairline ring diameter — inside the circular crop (1.00)


def _seal_master() -> Image.Image:
    """The mark, square, with a real circular alpha — as large as we have it.

    Prefers brand/masters/seal-1600.png, which already has a clean alpha and
    needs no extraction at all.

    The lockup copy sits on opaque near-white. Left as-is it would show as a
    pale square halo behind the medallion on the cinnamon background, so the
    alpha is cut to the medallion's own circle: located by thresholding the
    lockup against its background colour, then masked one pixel inside the
    measured radius so no rim of that near-white survives.
    """
    if MASTER.exists():
        return Image.open(MASTER).convert("RGBA")
    if LOCKUP.exists():
        im = Image.open(LOCKUP).convert("RGB")
        w, h = im.size
        bgc = im.getpixel((2, 2))
        # Column/row extents of the leftmost ink cluster = the seal.
        px = im.load()
        def inky(x, y):
            p = px[x, y]
            return abs(p[0] - bgc[0]) + abs(p[1] - bgc[1]) + abs(p[2] - bgc[2]) > 28
        cols = [x for x in range(w // 2) if any(inky(x, y) for y in range(0, h, 3))]
        if cols:
            # stop at the gap between the seal and the wordmark
            x0 = cols[0]
            x1 = x0
            for x in cols:
                if x - x1 > 20:
                    break
                x1 = x
            rows = [y for y in range(h) if any(inky(x, y) for x in range(x0, x1 + 1, 3))]
            if rows and (x1 - x0) > 100:
                cx, cy = (x0 + x1) / 2, (rows[0] + rows[-1]) / 2
                r = max(x1 - x0, rows[-1] - rows[0]) / 2
                side = int(2 * r) + 2
                crop = im.crop((round(cx - side / 2), round(cy - side / 2),
                                round(cx + side / 2), round(cy + side / 2))).convert("RGBA")
                mask = Image.new("L", (side * 4, side * 4), 0)
                inset = (side / 2 - (r - 1)) * 4
                ImageDraw.Draw(mask).ellipse(
                    (inset, inset, side * 4 - inset, side * 4 - inset), fill=255)
                crop.putalpha(mask.resize((side, side), Image.LANCZOS))
                return crop
    return Image.open(EMBLEM).convert("RGBA")


_MASTER: Image.Image | None = None


def seal(size: int) -> Image.Image:
    global _MASTER
    if _MASTER is None:
        _MASTER = _seal_master()
    return _MASTER.resize((size, size), Image.LANCZOS)


def avatar(px: int, bg, ring=None, ring_w_frac: float = 0.006) -> Image.Image:
    """One square avatar: flat background, centred seal, optional hairline ring."""
    im = Image.new("RGB", (px, px), bg)
    if ring is not None:
        d = ImageDraw.Draw(im)
        r = RING_FRAC * px / 2
        w = max(1, round(ring_w_frac * px))
        box = (px / 2 - r, px / 2 - r, px / 2 + r, px / 2 + r)
        # Drawn on a 4x canvas and downsampled: PIL's ellipse has no antialiasing
        # and a 1-2px hard-edged circle at this diameter looks like a sawtooth.
        ov = Image.new("RGBA", (px * 4, px * 4), (0, 0, 0, 0))
        ImageDraw.Draw(ov).ellipse([c * 4 for c in box], outline=ring + (255,), width=w * 4)
        im.paste(ov.resize((px, px), Image.LANCZOS), (0, 0),
                 ov.resize((px, px), Image.LANCZOS))
    s = round(SEAL_FRAC * px)
    sm = seal(s)
    im.paste(sm, ((px - s) // 2, (px - s) // 2), sm)
    return im


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    # 640 is what WhatsApp stores; 1000 for everything else (Meta Business,
    # Instagram, LinkedIn, Google Business Profile all take a larger square).
    for px in (640, 1000):
        for name, bg, ring in (
            # THE ONE TO USE. A chat list is a light surface, so the avatar needs
            # its own dark silhouette or it dissolves into the background — see
            # the contact sheet: the cream variants are unreadable at 32px, the
            # cinnamon one still is at 32px.
            ("cinnamon", FOREST, GOLD),
            # Light alternative, for placing ON something dark.
            ("cream", PAPER, GOLD),
        ):
            p = OUT / f"auralis-avatar-{name}-{px}.png"
            avatar(px, bg, ring).save(p, optimize=True)
            written.append(p)

    # A legibility contact sheet: every variant at the size a chat list actually
    # renders it, circle-cropped the way WhatsApp will crop it. If a variant
    # does not read here, it does not work — whatever it looks like at 640.
    variants = [p for p in written if p.name.endswith("-640.png")]
    SIZES = (128, 64, 48, 32)
    pad, cell = 20, 132
    sheet = Image.new("RGB",
                      (pad + len(variants) * (cell + pad),
                       2 * pad + sum(SIZES) + 10 * len(SIZES)),
                      CREAM)
    for i, p in enumerate(variants):
        im = Image.open(p).convert("RGB")
        x, y = pad + i * (cell + pad), pad
        for s in SIZES:
            thumb = im.resize((s, s), Image.LANCZOS)
            mask = Image.new("L", (s * 4, s * 4), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, s * 4 - 1, s * 4 - 1), fill=255)
            sheet.paste(thumb, (x + (cell - s) // 2, y), mask.resize((s, s), Image.LANCZOS))
            y += s + 10
    sheet.save(OUT / "_contact-sheet.png")
    written.append(OUT / "_contact-sheet.png")

    for p in written:
        im = Image.open(p)
        print(f"  {p.relative_to(ROOT)!s:46} {im.size[0]}x{im.size[1]:<5} {p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
