#!/usr/bin/env python3
"""Cover / banner images for the social profiles, at each platform's real size.

Every platform crops its cover differently on desktop and mobile, and each one
crops it *from a different part of the image*. So these are not one image
resized: each is composed for its own safe area, and the script writes a
`-guides` copy of each showing where that safe area is, so the crop can be
checked rather than hoped for.

  python3 brand/make_covers.py      -> brand/social/
"""
from __future__ import annotations
import pathlib
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "brand" / "social"
FONTS = ROOT / "ios-app" / "AuralisApp" / "Fonts"

PAPER = (0xF5, 0xEE, 0xE0)
FOREST = (0x3D, 0x27, 0x19)
FOREST_SOFT = (0x5A, 0x3A, 0x22)
FOREST_DEEP = (0x22, 0x13, 0x05)
GOLD = (0xAD, 0x7A, 0x32)
GOLD_BRIGHT = (0xD6, 0xA8, 0x4E)
SAND = (0xDA, 0xC7, 0x9E)
CREAM = (0xF2, 0xE8, 0xD8)

# Each entry: (width, height, safe-area box as fractions l,t,r,b)
# The safe area is the part every client shows. Outside it, content is cropped
# on at least one surface.
SPECS = {
    # Facebook page cover: 820x312 desktop, 640x360 mobile, from a 1640x856 upload.
    # The intersection of those two crops is a band in the middle.
    "facebook-cover":  (1640, 856, (0.11, 0.10, 0.89, 0.90)),
    # LinkedIn personal banner. The avatar sits over the lower LEFT on desktop,
    # so nothing important goes there.
    "linkedin-banner": (1584, 396, (0.22, 0.08, 0.97, 0.72)),
    # LinkedIn company page cover.
    "linkedin-company-cover": (1128, 191, (0.02, 0.10, 0.98, 0.90)),
    # Google Business Profile cover.
    "google-cover":    (1024, 576, (0.08, 0.12, 0.92, 0.88)),
}


def font(name: str, size: int):
    p = FONTS / name
    if p.exists():
        return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def seal(px: int) -> Image.Image:
    """Same mark, same extraction, as the avatars — imported so the two cannot
    diverge."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "av", ROOT / "brand" / "make_social_avatars.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.seal(px)


def gradient(w: int, h: int) -> Image.Image:
    """The website's warm-brown band: forest-soft -> forest -> forest-deep,
    left to right. Built per-column, so it costs nothing at these sizes."""
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for x in range(w):
        t = x / max(1, w - 1)
        if t < 0.5:
            u = t / 0.5
            a, b = FOREST_SOFT, FOREST
        else:
            u = (t - 0.5) / 0.5
            a, b = FOREST, FOREST_DEEP
        d.line([(x, 0), (x, h)], fill=tuple(round(a[i] + (b[i] - a[i]) * u) for i in range(3)))
    return im


def _fit(d, text, path, target_px, max_w):
    """Largest size at or below target_px whose rendered width fits max_w.

    Sizing type off the safe-area HEIGHT alone works for a wide, short banner
    and breaks badly on a tall one: the Facebook cover is 856px high, so a
    height-derived title came out 205px and ran clean off the right edge. Fit
    to the available WIDTH as well, always.
    """
    size = max(10, target_px)
    while size > 10:
        f = font(path, size)
        if d.textbbox((0, 0), text, font=f)[2] <= max_w:
            return f
        size -= 2
    return font(path, 10)


def cover(name: str, wordmark: str, tagline: str) -> Image.Image:
    w, h, (sl, st, sr, sb) = SPECS[name]
    im = gradient(w, h)
    d = ImageDraw.Draw(im)
    safe = (sl * w, st * h, sr * w, sb * h)
    safe_w, safe_h = safe[2] - safe[0], safe[3] - safe[1]

    # A wide, short safe area reads best as seal-beside-type; a squarer one as
    # seal-above-type. Choosing by aspect ratio keeps one code path honest for
    # banners from 1128x191 through 1024x576.
    horizontal = (safe_w / safe_h) > 3.2

    if horizontal:
        sp = round(safe_h * 0.62)
        gap_x = round(safe_h * 0.16)
        text_w = safe_w - sp - gap_x
        f_title = _fit(d, wordmark, "Fraunces-Regular.ttf", round(safe_h * 0.30), text_w)
        f_sub = _fit(d, tagline, "HankenGrotesk-Regular.ttf", round(safe_h * 0.105), text_w)
    else:
        sp = round(min(safe_h * 0.42, safe_w * 0.30))
        gap_x = 0
        f_title = _fit(d, wordmark, "Fraunces-Regular.ttf", round(safe_h * 0.17), safe_w)
        f_sub = _fit(d, tagline, "HankenGrotesk-Regular.ttf", round(safe_h * 0.062), safe_w)

    tb = d.textbbox((0, 0), wordmark, font=f_title)
    sbx = d.textbbox((0, 0), tagline, font=f_sub)
    # Fraunces sits high in its box, so the optical gap is smaller than the
    # metric one — 0.10 of the height looked like a collision.
    gap = round((tb[3] - tb[1]) * 0.55)
    dot_r = max(2, round((tb[3] - tb[1]) * 0.055))
    dot_gap = round((tb[3] - tb[1]) * 0.5)

    if horizontal:
        sm = seal(sp)
        im.paste(sm, (round(safe[0]), round(safe[1] + (safe_h - sp) / 2)), sm)
        tx = round(safe[0]) + sp + gap_x
        block_h = (tb[3] - tb[1]) + gap + (sbx[3] - sbx[1])
        ty = round(safe[1] + (safe_h - block_h) / 2 - tb[1])
        d.text((tx, ty), wordmark, font=f_title, fill=CREAM)
        d.text((tx, ty + (tb[3] - tb[1]) + gap - sbx[1]), tagline, font=f_sub, fill=SAND)
        dy = ty + (tb[3] - tb[1]) + gap + (sbx[3] - sbx[1]) + dot_gap
        dx = tx
    else:
        block_h = sp + gap + (tb[3] - tb[1]) + gap + (sbx[3] - sbx[1])
        top = safe[1] + (safe_h - block_h) / 2
        sm = seal(sp)
        im.paste(sm, (round(safe[0] + (safe_w - sp) / 2), round(top)), sm)
        cx = safe[0] + safe_w / 2
        ty = round(top + sp + gap - tb[1])
        d.text((cx - (tb[2] - tb[0]) / 2, ty), wordmark, font=f_title, fill=CREAM)
        sy = ty + (tb[3] - tb[1]) + gap - sbx[1]
        d.text((cx - (sbx[2] - sbx[0]) / 2, sy), tagline, font=f_sub, fill=SAND)
        dy = sy + (sbx[3] - sbx[1]) + dot_gap
        dx = cx - dot_r * 4

    for i, c in enumerate((GOLD_BRIGHT, SAND, GOLD)):
        x = dx + i * dot_r * 4
        d.ellipse((x - dot_r, dy - dot_r, x + dot_r, dy + dot_r), fill=c)
    return im


def with_guides(im: Image.Image, name: str) -> Image.Image:
    """A throwaway copy showing the safe area — for checking the crop, never
    for uploading."""
    w, h, (sl, st, sr, sb) = SPECS[name]
    g = im.copy()
    d = ImageDraw.Draw(g, "RGBA")
    d.rectangle((0, 0, w - 1, h - 1), outline=(255, 255, 255, 90), width=2)
    d.rectangle((sl * w, st * h, sr * w, sb * h), outline=(214, 168, 78, 220), width=3)
    d.text((10, 8), f"{name}  {w}x{h}   gold = safe area",
           font=font("HankenGrotesk-Regular.ttf", max(12, h // 30)),
           fill=(255, 255, 255, 220))
    return g


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    made = [
        ("facebook-cover", "Auralis Natura", "Wissenschaftlich fundiertes Gesundheitscoaching"),
        ("linkedin-banner", "Auralis Natura", "Wissenschaft trifft ganzheitliche Gesundheit"),
        ("linkedin-company-cover", "Auralis Natura", "Holistic Health · Barcelona"),
        ("google-cover", "Auralis Natura", "Gesundheitscoaching · Barcelona"),
    ]
    for name, wm, tag in made:
        im = cover(name, wm, tag)
        p = OUT / f"auralis-{name}.jpg"
        im.save(p, "JPEG", quality=92, optimize=True, progressive=True)
        gp = OUT / f"_guide-{name}.jpg"
        with_guides(im, name).save(gp, "JPEG", quality=80, optimize=True)
        print(f"  {p.name:38} {im.size[0]}x{im.size[1]:<5} {p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
