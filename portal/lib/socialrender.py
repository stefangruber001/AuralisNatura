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
import subprocess
import tempfile
import time
from pathlib import Path

from . import cfg
from . import render as _render

SIZES = {"post": (1080, 1350), "square": (1080, 1080), "story": (1080, 1920)}

_FONT_DIR = cfg.ROOT.parent / "design-system" / "assets" / "fonts"
_SEAL = cfg.ASSETS_DIR / "seal.png"                       # 193 KB, clean alpha
_WATERMARK = cfg.ROOT.parent / "brand" / "masters" / "seal-gold-watermark-1200.png"

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


def _frame(w: int, h: int, body: str, dark: bool = False, watermark: bool = False) -> str:
    """The shared canvas: paper (or dark band), hairline inner frame, kicker,
    seal footer, optional watermark bleeding off the bottom-right edge."""
    wm = ""
    if watermark and _WATERMARK.exists():
        wm = (f'<img src="{_durl(_WATERMARK, "image/png")}" style="position:absolute;'
              f'right:-{int(w * .28)}px;bottom:-{int(w * .28)}px;width:{int(w * .78)}px;'
              f'opacity:.10;pointer-events:none">')
    seal = f'<img src="{_durl(_SEAL, "image/png")}" style="width:76px;height:76px">' \
        if _SEAL.exists() else ""
    fg = "#F6EFE3" if dark else "var(--ink)"
    sub = "rgba(246,239,227,.72)" if dark else "var(--ink-soft)"
    bg = ("background:linear-gradient(165deg,#5A3A22 0%,#3D2719 55%,#221305 100%)"
          if dark else "background:var(--paper)")
    hair = "rgba(214,168,78,.35)" if dark else "var(--gold-hair)"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{_font_css()}
{_TOKENS}
html,body{{width:{w}px;height:{h}px;overflow:hidden}}
body{{{bg};font-family:var(--fb);color:{fg};position:relative}}
.inner{{position:absolute;inset:44px;border:1px solid {hair};padding:64px 58px;
  display:flex;flex-direction:column}}
.kick{{font-family:var(--fb);font-weight:600;font-size:24px;letter-spacing:.32em;
  text-transform:uppercase;color:{'#D6A84E' if dark else 'var(--clay)'}}}
.kick::after{{content:"";display:block;width:64px;height:2px;margin-top:20px;
  background:{'#D6A84E' if dark else 'var(--gold)'}}}
.grow{{flex:1;display:flex;flex-direction:column;justify-content:center}}
.foot{{display:flex;align-items:center;gap:22px;font-size:24px;letter-spacing:.14em;
  text-transform:uppercase;color:{sub}}}
.foot .h{{flex:1;height:1px;background:{hair}}}
h1{{font-family:var(--fd);font-weight:420;line-height:1.12;letter-spacing:-.015em;
  hyphens:none;overflow-wrap:break-word}}
.sub{{color:{sub};line-height:1.5}}
</style></head><body>{wm}<div class="inner">{body}</div></body></html>"""


def _foot(handle: str = "@auralis_natura") -> str:
    seal = f'<img src="{_durl(_SEAL, "image/png")}" style="width:72px;height:72px">' \
        if _SEAL.exists() else ""
    return f'<div class="foot">{seal}<span>Auralis Natura</span><span class="h"></span><span>{_e(handle)}</span></div>'


# ─────────────────────────────────────────────────────────── the templates ──
def tpl_quote(v: dict, w: int, h: int) -> str:
    return _frame(w, h, f"""
<div class="kick">Impuls der Woche</div>
<div class="grow">
  <h1 style="font-size:88px;max-width:12ch">{_e(v.get('headline', ''))}</h1>
  <p class="sub" style="font-size:38px;margin-top:36px;max-width:26ch">{_e(v.get('sub', ''))}</p>
</div>
{_foot()}""", watermark=True)


def tpl_mythfact(v: dict, w: int, h: int) -> str:
    return _frame(w, h, f"""
<div class="kick">Mythos &nbsp;·&nbsp; Fakt</div>
<div class="grow" style="gap:44px">
  <div style="border-left:3px solid var(--clay);padding:8px 0 8px 34px">
    <div style="font-size:26px;letter-spacing:.24em;text-transform:uppercase;color:var(--clay);font-weight:600">Mythos</div>
    <h1 style="font-size:56px;margin-top:14px;color:var(--ink-soft)">{_e(v.get('myth', ''))}</h1>
  </div>
  <div style="border-left:3px solid var(--gold);padding:8px 0 8px 34px">
    <div style="font-size:26px;letter-spacing:.24em;text-transform:uppercase;color:var(--gold);font-weight:600">Fakt</div>
    <h1 style="font-size:60px;margin-top:14px">{_e(v.get('fact', ''))}</h1>
  </div>
</div>
{_foot()}""")


def tpl_tips(v: dict, w: int, h: int) -> str:
    items = "".join(
        f'<div style="display:flex;gap:26px;align-items:baseline;padding:26px 0;'
        f'border-bottom:1px solid var(--line)">'
        f'<span style="font-family:var(--fd);font-size:44px;color:var(--gold)">{i + 1:02d}</span>'
        f'<span style="font-size:38px;line-height:1.35">{_e(str(t))}</span></div>'
        for i, t in enumerate((v.get("items") or [])[:5]))
    return _frame(w, h, f"""
<div class="kick">Diese Woche</div>
<div class="grow">
  <h1 style="font-size:64px;max-width:16ch;margin-bottom:30px">{_e(v.get('headline', ''))}</h1>
  {items}
</div>
{_foot()}""")


def tpl_carousel_slide(v: dict, idx: int, total: int, w: int, h: int) -> str:
    s = (v.get("slides") or [])[idx] if idx < len(v.get("slides") or []) else {}
    dark = idx == 0
    dots = "".join(
        f'<span style="width:14px;height:14px;display:inline-block;margin-right:10px;'
        f'background:{"#D6A84E" if dark else "var(--gold)"};'
        f'opacity:{1 if i == idx else .3}"></span>' for i in range(total))
    body = f"""
<div class="kick">{_e(str(s.get('kicker', 'Auralis Natura')) if idx == 0 else f'{idx}/{total - 1}')}</div>
<div class="grow">
  <h1 style="font-size:{78 if dark else 66}px;max-width:13ch">{_e(str(s.get('title', '')))}</h1>
  <p class="sub" style="font-size:36px;margin-top:32px;max-width:28ch">{_e(str(s.get('body', '')))}</p>
</div>
<div style="margin-bottom:28px">{dots}</div>
{_foot()}"""
    return _frame(w, h, body, dark=dark, watermark=dark)


def tpl_story(v: dict, w: int, h: int) -> str:
    return _frame(w, h, f"""
<div class="kick">Frage an dich</div>
<div class="grow">
  <h1 style="font-size:84px;max-width:12ch">{_e(v.get('question', ''))}</h1>
  <div style="margin-top:70px;border:1px solid var(--line-strong);padding:34px 40px;
    font-size:32px;color:var(--ink-faint);max-width:80%">Antwort hier eintippen …
    <span style="font-size:24px;display:block;margin-top:8px;color:var(--ink-faint)">
    (Platz für den Instagram-Frage-Sticker)</span></div>
</div>
{_foot()}""", watermark=True)


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
        return _frame(w, h, f"""
<div class="kick">Reel</div>
<div class="grow">
  <h1 style="font-size:96px;max-width:11ch">{_e(v.get('title', ''))}</h1>
</div>
{_foot()}""", dark=True, watermark=True)
    return _frame(w, h, f"""
<div class="kick">Mehr davon</div>
<div class="grow">
  <h1 style="font-size:72px;max-width:13ch">{_e(v.get('outro', ''))}</h1>
  <p class="sub" style="font-size:36px;margin-top:36px">Wissenschaft, warm erklärt — Bildung, keine medizinische Beratung.</p>
</div>
{_foot()}""", dark=True)


# ───────────────────────────────────────────────────────────── the renderer ──
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
                   f"--window-size={w},{h}", "--default-background-color=00000000",
                   "--virtual-time-budget=5000",
                   f"--screenshot={out_path}", f"file://{src}"]
            subprocess.run(cmd, capture_output=True, timeout=60)
        if not chrome or not out_path.exists() or out_path.stat().st_size == 0:
            fb = out_path.with_suffix(".html")
            fb.write_text(html_text, encoding="utf-8")
            return fb
        return out_path
    finally:
        if src is not None:
            src.unlink(missing_ok=True)


def render_slot(week: str, slot: dict, materials_dir: Path,
                out_dir: Path) -> list[str]:
    """All assets for one slot. Returns produced file names (PNG, or the .html
    fallbacks when Chromium is absent — the caller surfaces which)."""
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
        # the mp4 itself, when ffmpeg exists: title → (her photo) → outro
        cards = [p for p in produced if p.suffix == ".png"]
        if len(cards) == 2 and ffmpeg_available():
            seq = [cards[0]]
            if v.get("photo_id"):
                from . import social as _social
                photo = _social.material_path(v["photo_id"])
                if photo:
                    seq.append(photo)
            seq.append(cards[1])
            reel = build_reel(seq, out_dir / "reel.mp4")
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
