"""Social visuals — brand HTML templates rendered to PNG by headless Chromium.

The same Chromium that prints the client-report PDF takes the screenshots
(--headless --screenshot --window-size=WxH gives an exact-size PNG), so the
server needs no Playwright and no PIL. Fonts are the design system's own
woff2 files inlined as data: URIs — a template renders pixel-identically with
the network cable pulled, which is also what makes it testable.

Degrade contract copied from render.to_pdf(): no Chromium, or no PNG appears →
the HTML is written next to the target and returned instead, and the console
says so, loudly. Silent broken images are how brands die.

Design rules come from the printed corporate ID (brand/print/…, 2026-08-09):
square corners everywhere, hairline edges, clay only as accent, flat gold,
the seal as a quiet watermark bleeding off the edge, restraint as the premium
signal. The uploaded photo is never cropped server-side — CSS object-fit does
it inside the canvas.
"""
from __future__ import annotations
import base64
import html
import json
import re
import struct
import subprocess
import tempfile
import time
import zlib
from pathlib import Path

from . import cfg
from . import render as _render

SIZES = {"post": (1080, 1350), "square": (1080, 1080), "story": (1080, 1920)}

_FONT_DIR = cfg.ROOT.parent / "design-system" / "assets" / "fonts"

_e = html.escape


def _durl(path: Path, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


_FONT_CACHE: dict = {}


def _font_css() -> str:
    """@font-face for Fraunces + Hanken Grotesk from the repo's own woff2.
    latin-ext included: German umlauts sit in latin, but ő/ș-style guests in
    quoted studies should not fall back to a system font mid-line."""
    if "css" in _FONT_CACHE:
        return _FONT_CACHE["css"]
    faces = []
    spec = [
        ("Fraunces", "normal", "300 600", "fraunces-normal-300_600-latin.woff2"),
        ("Fraunces", "italic", "300 500", "fraunces-italic-300_500-latin.woff2"),
        ("Hanken Grotesk", "normal", "300 700", "hanken-grotesk-normal-300_700-latin.woff2"),
        ("Hanken Grotesk", "normal", "300 700", "hanken-grotesk-normal-300_700-latin-ext.woff2"),
    ]
    for fam, style, weight, fname in spec:
        p = _FONT_DIR / fname
        if not p.exists():
            continue
        faces.append(
            f"@font-face{{font-family:'{fam}';font-style:{style};font-weight:{weight};"
            f"src:url({_durl(p, 'font/woff2')}) format('woff2');font-display:block}}")
    _FONT_CACHE["css"] = "\n".join(faces)
    return _FONT_CACHE["css"]


# Tokens verbatim from design-system/dist/auralis.css — the declared single
# source of truth. Square corners are the system's defining decision.
_TOKENS = """
:root{--ink:#281F16;--ink-soft:#5C4A3A;--ink-faint:#75685A;
--forest:#3D2719;--forest-soft:#5A3A22;--forest-deep:#221305;--forest-2:#8A4A2A;
--sage:#927B4A;--sage-soft:#DAC79E;--clay:#A8492A;--clay-deep:#8F3D22;--clay-soft:#C47A52;
--gold:#AD7A32;--gold-bright:#D6A84E;--paper:#F5EEE0;--paper-2:#ECE2CE;--paper-3:#E3D6BC;
--cream:#FBF6EB;--line:rgba(61,39,25,.14);--line-strong:rgba(61,39,25,.26);
--gold-hair:rgba(173,122,50,.42);
--fd:'Fraunces',Georgia,serif;--fb:'Hanken Grotesk',system-ui,sans-serif}
*{margin:0;padding:0;box-sizing:border-box;border-radius:0!important}
"""


# ─────────────────────────────────────────────────────────── the templates ──
# ─────────────────────────────── v2 frames ────────────────────────────────
# The v2 social designs ship as complete HTML frames (lib/social_v2/), with the
# fonts and the emblem stored once beside them and inlined at load. Each tpl_*
# swaps the frame's worked sample for the slot's own fields — strict, so a
# drifted frame raises instead of posting the sample copy to Instagram.

_V2_DIR = Path(__file__).resolve().parent / "social_v2"
_V2_CACHE: dict[str, str] = {}


def _v2(name: str) -> str:
    if name not in _V2_CACHE:
        import base64 as _b64
        doc = (_V2_DIR / f"{name}.html").read_text(encoding="utf-8")
        fonts = (_V2_DIR / "_assets" / "fonts" / "fonts.css").read_text()
        for wf in sorted((_V2_DIR / "_assets" / "fonts").glob("*.woff2")):
            fonts = fonts.replace(
                wf.name, "data:font/woff2;base64," + _b64.b64encode(wf.read_bytes()).decode())
        doc = re.sub(r'<link[^>]+fonts\.css[^>]*>', "<style>" + fonts + "</style>", doc)
        emblem = ("data:image/png;base64," + _b64.b64encode(
            (_V2_DIR / "_assets" / "emblem-320.png").read_bytes()).decode())
        doc = doc.replace("../_assets/emblem-320.png", emblem)
        # the frames carry browser-preview chrome (centering, page background,
        # a soft shadow). Pin the artboard to the top-left at its NATURAL size —
        # to_png() renders an over-tall window and crops to the exact canvas, so
        # the art must never be stretched to the viewport (headless Chromium's
        # viewport is ~87px shorter than --window-size; see to_png).
        doc = doc.replace("</head>",
            "<style>html,body{margin:0!important;padding:0!important;"
            "background:transparent!important}"
            ".art{position:absolute!important;top:0!important;left:0!important;"
            "margin:0!important;box-shadow:none!important}"
            "</style></head>", 1)
        _V2_CACHE[name] = doc
    return _V2_CACHE[name]


def _v2_form(doc: str, old: str) -> str:
    """Whichever encoding of `old` the frame actually uses."""
    from html.entities import codepoint2name
    ent = "".join(f"&{codepoint2name[ord(c)]};" if ord(c) > 127 and ord(c) in codepoint2name
                  else c for c in old)
    return old if old in doc else ent


def _v2sub(doc: str, old: str, new: str, required: bool = True) -> str:
    from html.entities import codepoint2name
    ent = "".join(f"&{codepoint2name[ord(c)]};" if ord(c) > 127 and ord(c) in codepoint2name
                  else c for c in old)
    for form in (old, ent):
        if form in doc:
            return doc.replace(form, new)
    if required:
        raise KeyError(f"social frame drift: {old[:50]!r}")
    return doc


def _v2h1(doc: str, text: str) -> str:
    """The headline, keeping the frame's <em> flourish on the tail when the
    text carries an em-dash — the v2 designs italicise the turn of phrase."""
    m = re.search(r"<h1[^>]*>.*?</h1>", doc, re.S)
    if " — " in text:
        head, _, tail = text.rpartition(" — ")
        inner_em = re.search(r"<em[^>]*>", m.group(0))
        em_open = inner_em.group(0) if inner_em else "<em>"
        inner = _e(head) + " &mdash; " + em_open + _e(tail) + "</em>"
    else:
        inner = _e(text)
    h1_open = re.match(r"<h1[^>]*>", m.group(0)).group(0)
    return doc[:m.start()] + h1_open + inner + "</h1>" + doc[m.end():]


def tpl_quote(v: dict, w: int, h: int) -> str:
    doc = _v2("post-zitat")
    doc = _v2h1(doc, v.get("headline", ""))
    doc = _v2sub(doc, "Was anhaltende Erschöpfung über Eisen, Schlaf und Stress verraten kann.",
                 _e(v.get("sub", "")))
    return doc


def tpl_mythfact(v: dict, w: int, h: int) -> str:
    doc = _v2("post-mythos-fakt")
    doc = _v2sub(doc, "Müdigkeit nach 40 ist einfach normal.", _e(v.get("myth", "")))
    doc = _v2sub(doc, "Anhaltende Erschöpfung hat messbare Ursachen — hinschauen lohnt sich.",
                 _e(v.get("fact", "")))
    return doc


def tpl_tips(v: dict, w: int, h: int) -> str:
    doc = _v2("post-tipps")
    doc = _v2h1(doc, v.get("headline", ""))
    samples = ["Morgens zehn Minuten Tageslicht", "Protein zum Frühstück",
               "Koffein nach 14 Uhr weglassen", "Abends den Bildschirm dimmen"]
    items = [str(x) for x in (v.get("items") or v.get("tips") or [])][:4]
    for i, sample in enumerate(samples):
        if i < len(items):
            doc = _v2sub(doc, sample, _e(items[i]))
        else:
            # drop the whole numbered row, not just its text
            doc = re.sub(r'<div[^>]*>\s*<span[^>]*>0' + str(i + 1)
                         + r'</span>\s*<span[^>]*>' + re.escape(_v2_form(doc, sample))
                         + r'</span>\s*</div>', "", doc, count=1)
    return doc


def tpl_carousel_slide(v: dict, idx: int, total: int, w: int, h: int) -> str:
    sl = (v.get("slides") or [])[idx] if idx < len(v.get("slides") or []) else {}
    title, body = str(sl.get("title", "")), str(sl.get("body", ""))
    if idx == 0:
        doc = _v2("karussell-1")
        doc = _v2sub(doc, "Eisen &amp; Energie", _e(title))
        doc = _v2sub(doc, "Warum Ferritin mehr sagt als Hämoglobin — und wann Werte täuschen.",
                     _e(body))
    else:
        doc = _v2("karussell-2")
        doc = _v2sub(doc, "Was Ferritin misst", _e(title))
        doc = _v2sub(doc, "Den Speicher, nicht den Transport. Deshalb kann Hämoglobin normal sein.",
                     _e(body))
        n = f"{idx:02d}"
        doc = re.sub(r'(class="ghost"[^>]*>)[^<]*', lambda m: m.group(1) + n, doc, count=1)
        doc = re.sub(r'(class="count"[^>]*>)\d+\s*<small[^>]*>/ \d+',
                     lambda m: m.group(1) + f"{idx} <small>/ {max(total - 1, 1)}", doc, count=1)
    # progress dots: one per slide, the current one lit
    dots = "".join('<i class="on"></i>' if k == idx else "<i></i>" for k in range(total))
    doc = re.sub(r'(<div class="prog"[^>]*>).*?(</div>)',
                 lambda m: m.group(1) + dots + m.group(2), doc, count=1, flags=re.S)
    return doc


def tpl_story(v: dict, w: int, h: int) -> str:
    doc = _v2("story")
    doc = _v2h1(doc, v.get("question", ""))
    return doc


def tpl_photo(v: dict, w: int, h: int, photo: Path | None) -> str:
    img = (f'<img src="{_durl(photo, "image/jpeg")}" style="position:absolute;inset:0;'
           f'width:100%;height:100%;object-fit:cover">') if photo and photo.exists() else \
        '<div style="position:absolute;inset:0;background:var(--paper-2)"></div>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{_font_css()}
{_TOKENS}
html,body{{width:{w}px;height:{h}px;overflow:hidden}}
body{{position:relative;font-family:var(--fb)}}
</style></head><body>
{img}
<div style="position:absolute;inset:0;background:linear-gradient(180deg,transparent 46%,rgba(34,19,5,.82) 100%)"></div>
<div style="position:absolute;left:44px;right:44px;bottom:44px;border:1px solid rgba(214,168,78,.4);padding:46px 50px;color:#F6EFE3">
  <div style="font-size:24px;letter-spacing:.32em;text-transform:uppercase;color:#D6A84E;font-weight:600;margin-bottom:22px">Auralis Natura</div>
  <div style="font-family:var(--fd);font-size:62px;line-height:1.14;hyphens:none">{_e(v.get('headline', ''))}</div>
  <div style="display:flex;align-items:center;gap:20px;margin-top:30px;font-size:23px;letter-spacing:.14em;text-transform:uppercase;color:rgba(246,239,227,.75)">
    <span style="flex:1;height:1px;background:rgba(214,168,78,.4)"></span><span>@auralis_natura</span></div>
</div></body></html>"""


def tpl_reel_card(v: dict, which: str, w: int, h: int) -> str:
    if which == "title":
        doc = _v2("reel-titel")
        return _v2sub(doc, "Drei Energie-Impulse für deine Woche",
                      _e(v.get("title", v.get("headline", ""))))
    doc = _v2("reel-outro")
    outro = (v.get("outro") or "").strip()
    if outro:
        doc = _v2h1(doc, outro)
    return doc


# ───────────────────────────────────────────────────────────── the renderer ──
# Headless Chromium's screenshot PNG is --window-size sized, but the page only
# gets a viewport ~87px SHORTER (the new headless mode reserves window chrome),
# and content below the viewport is clipped, never scrolled in. So an exact-size
# window always yields a dead band at the bottom. The fix: render into a window
# taller than the canvas, keep the artboard pinned top-left at natural size
# (see _v2), and crop the PNG to the exact canvas here — pure stdlib, no PIL.
_CHROME_SLACK = 200  # > any observed viewport shortfall, version-proof headroom


def _crop_png(path: Path, w: int, h: int) -> None:
    """Crop an RGBA8 PNG in place to its top-left w×h region (stdlib only)."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    sw, sh = struct.unpack(">II", data[16:24])
    bitdepth, ctype = data[24], data[25]
    if (sw, sh) == (w, h):
        return
    if sw < w or sh < h or bitdepth != 8 or ctype != 6:
        raise ValueError(f"cannot crop {sw}x{sh}/{bitdepth}/{ctype} to {w}x{h}")
    idat, i = b"", 8
    while i < len(data):
        ln, typ = struct.unpack(">I4s", data[i:i + 8])
        if typ == b"IDAT":
            idat += data[i + 8:i + 8 + ln]
        i += 12 + ln
    raw = zlib.decompress(idat)
    ch, stride = 4, sw * 4 + 1
    # unfilter only the rows we keep, re-filter each as Up (type 2)
    out = bytearray()
    prev_keep = bytearray(w * ch)
    prev = bytearray(sw * ch)
    for y in range(h):
        f = raw[y * stride]
        line = bytearray(raw[y * stride + 1:(y + 1) * stride])
        if f == 1:
            for x in range(ch, len(line)):
                line[x] = (line[x] + line[x - ch]) & 255
        elif f == 2:
            for x in range(len(line)):
                line[x] = (line[x] + prev[x]) & 255
        elif f == 3:
            for x in range(len(line)):
                a = line[x - ch] if x >= ch else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 255
        elif f == 4:
            for x in range(len(line)):
                a = line[x - ch] if x >= ch else 0
                b = prev[x]
                c = prev[x - ch] if x >= ch else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        prev = line
        keep = line[:w * ch]
        out += b"\x02" + bytes((keep[x] - prev_keep[x]) & 255
                               for x in range(w * ch))
        prev_keep = keep

    def chunk(typ: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + typ + body
                + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                     + chunk(b"IDAT", zlib.compress(bytes(out), 9))
                     + chunk(b"IEND", b""))


def to_png(html_text: str, out_path: Path, w: int, h: int) -> Path:
    """Exact-size PNG via chromium --screenshot; render.to_pdf's degrade
    contract: any failure writes the .html next to the target and returns it."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    chrome = _render._chrome()
    src = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                         encoding="utf-8") as f:
            f.write(html_text)
            src = Path(f.name)
        if chrome:
            cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox",
                   "--hide-scrollbars", "--force-device-scale-factor=1",
                   f"--window-size={w},{h + _CHROME_SLACK}",
                   "--default-background-color=00000000",
                   "--virtual-time-budget=5000",
                   f"--screenshot={out_path}", f"file://{src}"]
            subprocess.run(cmd, capture_output=True, timeout=60)
        if not chrome or not out_path.exists() or out_path.stat().st_size == 0:
            fb = out_path.with_suffix(".html")
            fb.write_text(html_text, encoding="utf-8")
            return fb
        try:
            _crop_png(out_path, w, h)
        except Exception:
            fb = out_path.with_suffix(".html")
            fb.write_text(html_text, encoding="utf-8")
            return fb
        return out_path
    finally:
        if src is not None:
            src.unlink(missing_ok=True)


def render_reel(slot: dict, out_dir: Path) -> Path | None:
    """The mp4 alone: title card → (her photo) → outro card.

    Split out of render_slot because it is the one genuinely slow step here —
    zoompan renders at high internal resolution, so a 1080×1920 reel takes
    minutes where the still cards take seconds. Callers serving an HTTP request
    run this on a thread; nothing else in the pipeline needs to wait for it.
    """
    v = slot.get("visual") or {}
    cards = [out_dir / "reel-title.png", out_dir / "reel-outro.png"]
    if not all(p.exists() for p in cards) or not ffmpeg_available():
        return None
    seq = [cards[0]]
    if v.get("photo_id"):
        from . import social as _social
        photo = _social.material_path(v["photo_id"])
        if photo:
            seq.append(photo)
    seq.append(cards[1])
    return build_reel(seq, out_dir / "reel.mp4")


def render_slot(week: str, slot: dict, materials_dir: Path,
                out_dir: Path, video: bool = True) -> list[str]:
    """All assets for one slot. Returns produced file names (PNG, or the .html
    fallbacks when Chromium is absent — the caller surfaces which).

    video=False renders the still cards only and leaves the mp4 to the caller,
    which is what request handlers want."""
    v = slot.get("visual") or {}
    kind = slot.get("kind", "post")
    tpl = v.get("template", "quote")
    out_dir.mkdir(parents=True, exist_ok=True)
    produced: list[Path] = []

    def emit(name: str, html_text: str, size: tuple[int, int]):
        produced.append(to_png(html_text, out_dir / name, *size))

    if kind == "story":
        w, h = SIZES["story"]
        emit("story.png", tpl_story(v, w, h), (w, h))
    elif kind == "reel":
        w, h = SIZES["story"]
        emit("reel-title.png", tpl_reel_card(v, "title", w, h), (w, h))
        emit("reel-outro.png", tpl_reel_card(v, "outro", w, h), (w, h))
        if video:
            reel = render_reel(slot, out_dir)
            if reel:
                produced.append(reel)
    elif kind == "carousel" or tpl == "carousel":
        w, h = SIZES["post"]
        total = min(len(v.get("slides") or []), 7) or 5
        for i in range(total):
            emit(f"slide-{i + 1}.png", tpl_carousel_slide(v, i, total, w, h), (w, h))
    else:
        w, h = SIZES["post"]
        photo = None
        if tpl == "photo" and v.get("photo_id"):
            from . import social as _social
            photo = _social.material_path(v["photo_id"])
        html_text = {"quote": tpl_quote, "mythfact": tpl_mythfact,
                     "tips": tpl_tips}.get(tpl, tpl_quote)(v, w, h) \
            if tpl != "photo" else tpl_photo(v, w, h, photo)
        emit("post.png", html_text, (w, h))
    return [p.name for p in produced]


# ══════════════════════════════════════════════════════ S5 · reels (ffmpeg) ══
import shutil as _shutil


def ffmpeg_available() -> bool:
    return _shutil.which("ffmpeg") is not None


def build_reel(images: list[Path], out_path: Path, seconds_per: float = 4.0,
               fps: int = 30, encoder: str = "libx264",
               ffmpeg_bin: str | None = None) -> Path | None:
    """A quiet 1080x1920 slideshow reel: slow zoom on every card, crossfades
    between them. No audio ON PURPOSE — Instagram's licensed trending audio
    exists only inside the app, and that is also what the algorithm rewards.

    Missing ffmpeg or a failed encode returns None; the caller keeps the PNG
    cards and tells the founder to post those (or install ffmpeg). Encoding is
    niced and thread-capped: this box also runs someone's ERP.
    """
    bin_ = ffmpeg_bin or _shutil.which("ffmpeg")
    if not bin_ or not images:
        return None
    imgs = [p for p in images if p.exists()]
    if not imgs:
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(seconds_per * fps)
    inputs, filters = [], []
    for i, p in enumerate(imgs):
        inputs += ["-loop", "1", "-t", str(seconds_per), "-i", str(p)]
        # cover-scale into the canvas, then a slow push-in (1.00 -> 1.06)
        filters.append(
            f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,zoompan=z='min(1+0.06*on/{frames},1.06)':d={frames}"
            f":s=1080x1920:fps={fps}[v{i}]")
    last, fade = "v0", 0.6
    for i in range(1, len(imgs)):
        nxt = f"vx{i}"
        off = i * seconds_per - i * fade
        filters.append(f"[{last}][v{i}]xfade=transition=fade:duration={fade}:offset={off:.2f}[{nxt}]")
        last = nxt
    enc_opts = (["-pix_fmt", "yuv420p", "-movflags", "+faststart"]
                if encoder == "libx264" else [])

    def _run(cmd) -> Path | None:
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=300)
            if proc.returncode == 0 and out_path.exists() and out_path.stat().st_size >= 10_000:
                return out_path
        except Exception:
            pass
        out_path.unlink(missing_ok=True)
        return None

    got = _run(["nice", "-n", "10", bin_, "-y", *inputs,
                "-filter_complex", ";".join(filters), "-map", f"[{last}]",
                "-r", str(fps), "-c:v", encoder, *enc_opts,
                "-threads", "2", "-an", str(out_path)])
    if got:
        return got

    # Fallback cut — concat demuxer, hard cuts, scale/crop only. Worse-looking
    # but posts fine, and it survives ffmpeg builds stripped of zoompan/xfade.
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as f:
        for p in imgs:
            f.write(f"file '{p}'\nduration {seconds_per}\n")
        f.write(f"file '{imgs[-1]}'\n")          # concat quirk: repeat the last
        lst = Path(f.name)
    try:
        return _run(["nice", "-n", "10", bin_, "-y", "-f", "concat", "-safe", "0",
                     "-i", str(lst),
                     "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                     "-r", str(fps), "-c:v", encoder, *enc_opts,
                     "-threads", "2", "-an", str(out_path)])
    finally:
        lst.unlink(missing_ok=True)
