#!/usr/bin/env python3
"""Build the Auralis Natura Design Handbook — the reference a designer or web
developer works from when building anything on this brand.

Everything that can be derived from the repo IS derived from the repo: the colour
swatches come from `design-system/src/styles/tokens.css`, the component roster and
its one-line briefs come from `design-system/docs/*.md` frontmatter, the fonts are
the same self-hosted woff2 the design system ships. A handbook that restates the
values by hand is a handbook that goes stale the first time a token moves.

Fonts and imagery are inlined as data URIs so the file renders identically offline
— the same lesson `lib/render.py` learned when the report PDF silently lost its
brand faces without a network.

  python3 brand/build_design_handbook.py          # HTML + PDF
"""
from __future__ import annotations

import base64
import html
import pathlib
import re
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONTS = ROOT / "design-system" / "assets" / "fonts"
DOCS = ROOT / "design-system" / "docs"
MASTERS = ROOT / "brand" / "masters"
IMAGES = ROOT / "images"
OUT_DIR = ROOT / "brand" / "handbook"
OUT_HTML = OUT_DIR / "Auralis-Natura-Design-Handbook.html"
OUT_PDF = OUT_DIR / "Auralis-Natura-Design-Handbook.pdf"

CHROME_CANDIDATES = [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
]


# ---------------------------------------------------------------- inlining

def durl(p: pathlib.Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def font_face(family: str, path: pathlib.Path, weight: str, style: str = "normal") -> str:
    return (f"@font-face{{font-family:'{family}';font-style:{style};"
            f"font-weight:{weight};font-display:swap;"
            f"src:url({durl(path, 'font/woff2')}) format('woff2')}}")


FACES = "".join([
    font_face("Fraunces", FONTS / "fraunces-normal-300_600-latin.woff2", "300 600"),
    font_face("Fraunces", FONTS / "fraunces-italic-300_500-latin.woff2", "300 500", "italic"),
    font_face("Hanken Grotesk", FONTS / "hanken-grotesk-normal-300_700-latin.woff2", "300 700"),
])


def thumb(src: pathlib.Path, w: int) -> str:
    """Downscaled data URI. Embedding a 2.8 MB master six times would make the
    handbook unopenable; the browser scaling it to 5% would also look wrong."""
    from PIL import Image
    import io
    im = Image.open(src)
    im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
    h = max(1, round(im.height * w / im.width))
    im = im.resize((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    if im.mode == "RGBA":
        im.save(buf, "PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    im.save(buf, "JPEG", quality=86, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------- derived data

def read_tokens() -> dict[str, str]:
    """Parse the real token file — never a hand-copied palette."""
    txt = (ROOT / "design-system" / "src" / "styles" / "tokens.css").read_text()
    body = re.search(r":root\{(.*?)\n\}", txt, re.S).group(1)
    out: dict[str, str] = {}
    for m in re.finditer(r"--([a-z0-9-]+)\s*:\s*([^;]+);", body):
        out[m.group(1)] = m.group(2).strip()
    return out


TOK = read_tokens()


def components() -> list[dict]:
    """Roster + one-line brief straight from each component's own doc."""
    out = []
    for p in sorted(DOCS.glob("*.md")):
        txt = p.read_text()
        fm = re.match(r"---\n(.*?)\n---\n", txt, re.S)
        cat = "Other"
        if fm:
            cm = re.search(r"^category:\s*(.+)$", fm.group(1), re.M)
            if cm:
                cat = cm.group(1).strip()
            txt = txt[fm.end():]
        # the paragraph after the H1 is the component's brief
        pm = re.search(r"^#\s+\w[^\n]*\n+(.+?)(?=\n\n)", txt, re.S | re.M)
        brief = " ".join(pm.group(1).split()) if pm else ""
        out.append({"name": p.stem, "cat": cat, "brief": brief})
    return out


COMPS = components()
GROUP_ORDER = ["Foundations", "Typography", "Layout", "Media", "Content", "Commerce"]


# ---------------------------------------------------------------- fragments

def swatch(token: str, role: str, *, dark: bool = False) -> str:
    val = TOK.get(token, "")
    cls = " sw--dark" if dark else ""
    return (f'<div class="sw{cls}"><div class="sw-chip" style="background:{val}"></div>'
            f'<div class="sw-meta"><code>--{token}</code><b>{val.upper()}</b>'
            f'<span>{html.escape(role)}</span></div></div>')


def rule(n: str, title: str, body: str) -> str:
    return (f'<div class="rule"><div class="rule-n">{n}</div>'
            f'<div class="rule-b"><h4>{html.escape(title)}</h4><p>{body}</p></div></div>')


def comp_group(cat: str) -> str:
    rows = "".join(
        f'<tr><td><code>{c["name"]}</code></td><td>{html.escape(c["brief"])}</td></tr>'
        for c in COMPS if c["cat"] == cat)
    n = sum(1 for c in COMPS if c["cat"] == cat)
    return (f'<h4 class="cg">{html.escape(cat)} <span>{n}</span></h4>'
            f'<table class="ct"><tbody>{rows}</tbody></table>')


SEAL_BROWN = thumb(MASTERS / "seal-brown-1200.png", 340)
SEAL_GOLD = thumb(MASTERS / "seal-gold-1200.png", 340)
SEAL_WM = thumb(MASTERS / "seal-gold-watermark-1200.png", 900)
SEAL_MARK = thumb(MASTERS / "seal-1600.png", 260)
QR = thumb(MASTERS / "qr-website-1480.png", 300)
LOCKUP = thumb(IMAGES / "logo-lockup.png", 520)
PHOTO_PORTRAIT = thumb(IMAGES / "desiree-portrait.jpg", 460)
PHOTO_CONSULT = thumb(IMAGES / "desiree-consult.jpg", 460)
PHOTO_NOURISH = thumb(IMAGES / "nourish.jpg", 460)


# ---------------------------------------------------------------- the document

CSS = f"""
{FACES}
*{{box-sizing:border-box}}
:root{{
  --ink:{TOK['ink']}; --ink-soft:{TOK['ink-soft']}; --ink-faint:{TOK['ink-faint']};
  --forest:{TOK['forest']}; --forest-soft:{TOK['forest-soft']}; --forest-deep:{TOK['forest-deep']};
  --forest-2:{TOK['forest-2']}; --sage:{TOK['sage']}; --sage-soft:{TOK['sage-soft']};
  --clay:{TOK['clay']}; --clay-deep:{TOK['clay-deep']}; --clay-soft:{TOK['clay-soft']};
  --gold:{TOK['gold']}; --gold-bright:{TOK['gold-bright']};
  --paper:{TOK['paper']}; --paper-2:{TOK['paper-2']}; --paper-3:{TOK['paper-3']};
  --cream:{TOK['cream']};
  --line:{TOK['line']}; --line-strong:{TOK['line-strong']}; --gold-hair:{TOK['gold-hair']};
  --fd:'Fraunces',Georgia,serif; --fb:'Hanken Grotesk',system-ui,sans-serif;
}}
html{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
body{{margin:0;background:#8d8577;font-family:var(--fb);color:var(--ink);
  font-size:9.8pt;line-height:1.56;hyphens:none;-webkit-hyphens:none}}

/* one A4 sheet per .page — geometry never depends on content */
.page{{position:relative;width:210mm;min-height:297mm;padding:17mm 19mm 15mm;
  margin:0 auto 8mm;background:var(--cream);overflow:hidden;page-break-after:always}}
.page:last-child{{page-break-after:auto}}
@page{{size:A4;margin:0}}
@media print{{body{{background:#fff}} .page{{margin:0;box-shadow:none}}}}

/* ---- running heads ---- */
.rh{{position:absolute;top:9mm;left:19mm;right:19mm;display:flex;
  justify-content:space-between;font-size:6.6pt;letter-spacing:.16em;
  text-transform:uppercase;color:var(--ink-faint);
  border-bottom:1px solid var(--line);padding-bottom:2.5mm}}
.rf{{position:absolute;bottom:9mm;left:19mm;right:19mm;display:flex;
  justify-content:space-between;font-size:6.6pt;letter-spacing:.14em;
  text-transform:uppercase;color:var(--ink-faint);
  border-top:1px solid var(--line);padding-top:2.5mm}}

/* ---- cover ---- */
.cover{{background:linear-gradient(158deg,var(--forest-soft) 0%,var(--forest) 55%,var(--forest-deep) 100%);
  color:#EDE7D6;display:flex;flex-direction:column;justify-content:space-between;
  padding:26mm 22mm 20mm}}
.cover::after{{content:"";position:absolute;right:-52mm;bottom:-46mm;width:170mm;height:170mm;
  background:url({SEAL_WM}) center/contain no-repeat;opacity:.10}}
.cover-in{{position:relative;z-index:2}}
.cv-seal{{width:26mm;height:26mm;background:url({SEAL_GOLD}) center/contain no-repeat;
  margin-bottom:12mm}}
.cv-kick{{font-size:7.4pt;letter-spacing:.3em;text-transform:uppercase;
  color:var(--gold-bright);margin-bottom:7mm}}
.cover h1{{font-family:var(--fd);font-weight:300;font-size:40pt;line-height:1.06;
  letter-spacing:-.022em;margin:0 0 7mm}}
.cover h1 i{{font-style:italic;color:var(--gold-bright)}}
.cv-lede{{font-size:11.4pt;line-height:1.66;color:#DED6C4;max-width:112mm;margin:0}}
.cv-rule{{width:22mm;height:.25mm;background:var(--gold);margin:9mm 0}}
.cv-meta{{position:relative;z-index:2;display:flex;justify-content:space-between;
  align-items:flex-end;font-size:8pt;color:#C9BFAC;
  border-top:1px solid rgba(214,168,78,.42);padding-top:5mm}}
.cv-meta b{{display:block;color:#EDE7D6;font-weight:500;letter-spacing:.02em}}

/* ---- type ---- */
h2.ch{{font-family:var(--fd);font-weight:300;font-size:25pt;line-height:1.12;
  letter-spacing:-.02em;margin:0 0 4mm}}
h2.ch i{{font-style:italic;color:var(--forest-2)}}
.ch-n{{font-family:var(--fd);font-size:36pt;font-weight:300;color:var(--paper-3);
  line-height:.8;margin:0 0 2.5mm}}
.kick{{font-size:6.8pt;letter-spacing:.24em;text-transform:uppercase;
  color:var(--clay);margin:0 0 2.5mm}}
.lede{{font-size:10.6pt;line-height:1.56;color:var(--ink-soft);max-width:150mm;margin:0 0 6mm}}
h3{{font-family:var(--fd);font-weight:400;font-size:13pt;letter-spacing:-.01em;
  margin:7mm 0 2.5mm}}
h4{{font-size:9pt;font-weight:600;letter-spacing:.01em;margin:5mm 0 1.8mm}}
p{{margin:0 0 3mm;max-width:158mm}}
strong{{font-weight:600;color:var(--ink)}}
em.a{{font-family:var(--fd);font-style:italic;color:var(--forest-2);font-size:1.06em}}
code{{font-family:var(--fb);font-size:.9em;background:var(--paper-2);
  padding:.5mm 1.4mm;border:1px solid var(--line);white-space:nowrap}}
ul{{margin:0 0 4mm;padding-left:5mm}} li{{margin-bottom:1.6mm}}
a{{color:var(--clay-deep);text-decoration:none;border-bottom:1px solid var(--gold-hair)}}

/* ---- structures ---- */
.hair{{height:1px;background:var(--line);margin:5.5mm 0}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:8mm}}
.three{{display:grid;grid-template-columns:repeat(3,1fr);gap:6mm}}

.card{{background:var(--paper);border:1px solid var(--line);padding:5mm 5.5mm}}
.card h4{{margin-top:0}}
.card p:last-child{{margin-bottom:0}}

.dark{{background:linear-gradient(158deg,var(--forest-soft),var(--forest) 60%,var(--forest-deep));
  color:#E6DECC;padding:7mm 7.5mm;position:relative;overflow:hidden;
  border-top:1px solid var(--gold-hair)}}
.dark h3,.dark h4{{color:#F3EDDF;margin-top:0}}
.dark strong{{color:var(--gold-bright)}}
.dark::after{{content:"";position:absolute;right:-26mm;top:-26mm;width:86mm;height:86mm;
  background:url({SEAL_WM}) center/contain no-repeat;opacity:.10}}
.dark>*{{position:relative;z-index:2}}

.note{{border-left:2px solid var(--clay);background:var(--paper-2);
  padding:3.4mm 4.5mm;margin:4mm 0}}
.note p:last-child{{margin-bottom:0}}
.warn{{border-left:2px solid var(--gold);background:#F7F0DE;
  padding:3.4mm 4.5mm;margin:4mm 0}}
.warn p:last-child{{margin-bottom:0}}

/* ---- numbered rules ---- */
.rule{{display:flex;gap:4mm;padding:2.8mm 0;border-bottom:1px solid var(--line)}}
.rule:last-child{{border-bottom:0}}
.rule-n{{font-family:var(--fd);font-size:15pt;font-weight:300;color:var(--clay);
  line-height:1;min-width:9mm;padding-top:.6mm}}
.rule-b h4{{margin:0 0 1.2mm}}
.rule-b p{{margin:0;color:var(--ink-soft)}}

/* ---- swatches ---- */
.sw-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:3.4mm;margin-bottom:4mm}}
.sw-chip{{height:12mm;border:1px solid var(--line-strong)}}
.sw-meta{{padding-top:1.6mm}}
.sw-meta code{{display:block;background:none;border:0;padding:0;font-size:7.4pt;
  color:var(--clay-deep);letter-spacing:.02em}}
.sw-meta b{{display:block;font-size:7.6pt;font-weight:600;letter-spacing:.06em;
  margin:.6mm 0}}
.sw-meta span{{display:block;font-size:7.4pt;color:var(--ink-faint);line-height:1.45}}

/* ---- tables ---- */
table{{width:100%;border-collapse:collapse;font-size:8.4pt;margin-bottom:4mm}}
th{{text-align:left;font-size:6.8pt;letter-spacing:.16em;text-transform:uppercase;
  color:var(--ink-faint);font-weight:600;padding:0 3mm 2mm 0;
  border-bottom:1px solid var(--line-strong)}}
td{{padding:1.8mm 3mm 1.8mm 0;border-bottom:1px solid var(--line);
  vertical-align:top;color:var(--ink-soft)}}
td:first-child{{color:var(--ink);white-space:nowrap}}
.ct td:first-child{{width:34mm}}
.cg{{font-family:var(--fd);font-weight:400;font-size:12pt;margin:6mm 0 2mm;
  display:flex;align-items:baseline;gap:2.5mm}}
.cg span{{font-size:7.4pt;font-family:var(--fb);letter-spacing:.14em;
  color:var(--ink-faint)}}

/* ---- type specimens ---- */
.spec{{border:1px solid var(--line);padding:5mm 5.5mm;margin-bottom:4mm;
  background:var(--paper)}}
.spec-l{{font-size:6.6pt;letter-spacing:.18em;text-transform:uppercase;
  color:var(--ink-faint);margin-bottom:2.5mm}}
.sp-display{{font-family:var(--fd);font-weight:300;font-size:26pt;line-height:1.1;
  letter-spacing:-.022em;margin:0}}
.sp-display i{{font-style:italic;color:var(--forest-2)}}
.sp-h{{font-family:var(--fd);font-weight:400;font-size:16pt;line-height:1.2;margin:0}}
.sp-body{{font-size:10.4pt;line-height:1.72;color:var(--ink-soft);margin:0;max-width:140mm}}
.sp-label{{font-size:7.4pt;letter-spacing:.2em;text-transform:uppercase;
  color:var(--clay);margin:0}}

/* ---- imagery ---- */
.shot{{border:1px solid var(--line);background:var(--paper)}}
.shot img{{display:block;width:100%;height:auto}}
.cap{{font-size:7.4pt;color:var(--ink-faint);line-height:1.5;padding:2.5mm 0 0}}
.seal-row{{display:grid;grid-template-columns:repeat(3,1fr);gap:6mm;margin-bottom:5mm}}
.seal-cell{{text-align:center;padding:6mm 4mm;border:1px solid var(--line)}}
.seal-cell img{{width:26mm;height:26mm;object-fit:contain}}
.seal-cell.on-dark{{background:var(--forest);border-color:var(--gold-hair)}}
.seal-cell.on-paper{{background:var(--paper-2)}}
.seal-lab{{font-size:7.2pt;letter-spacing:.12em;text-transform:uppercase;
  margin-top:3mm;color:var(--ink-faint)}}
.seal-cell.on-dark .seal-lab{{color:#C9BFAC}}

/* ---- do / don't ---- */
.dd{{display:grid;grid-template-columns:1fr 1fr;gap:5mm;margin:4mm 0 6mm}}
.dd>div{{border:1px solid var(--line);padding:4mm 4.5mm;background:var(--paper)}}
.dd h4{{margin:0 0 2mm;font-size:8pt;letter-spacing:.14em;text-transform:uppercase}}
.dd .do h4{{color:#4E6B3E}} .dd .dont h4{{color:var(--clay-deep)}}
.dd ul{{margin:0;padding-left:4mm;font-size:8.8pt;color:var(--ink-soft)}}

/* ---- closing ---- */
.qr{{width:23mm;height:23mm}}
.toc td:first-child{{width:12mm;font-family:var(--fd);font-size:11pt;color:var(--clay)}}
.toc td:last-child{{text-align:right;white-space:nowrap;color:var(--ink-faint);width:16mm}}
"""


def page(n: str, chapter: str, body: str, *, klass: str = "") -> str:
    return (f'<section class="page {klass}">'
            f'<div class="rh"><span>Auralis Natura · Design Handbook</span>'
            f'<span>{html.escape(chapter)}</span></div>'
            f'{body}'
            f'<div class="rf"><span>Modern Materia Medica</span><span>{n}</span></div>'
            f'</section>')


def chapter_head(num: str, title_html: str, kick: str, lede: str) -> str:
    return (f'<div class="ch-n">{num}</div><p class="kick">{html.escape(kick)}</p>'
            f'<h2 class="ch">{title_html}</h2><p class="lede">{lede}</p>')


PAGES: list[str] = []

# ------------------------------------------------------------------ cover
PAGES.append(f"""
<section class="page cover">
  <div class="cover-in">
    <div class="cv-seal"></div>
    <p class="cv-kick">Design Handbook · Edition 2026</p>
    <h1>Auralis Natura.<br><i>Modern Materia Medica.</i></h1>
    <div class="cv-rule"></div>
    <p class="cv-lede">The complete visual reference for this brand — the marks, the
    palette, the type, the components, the printed work and the rules that hold it
    together. Everything a designer or developer needs to build something new that
    belongs.</p>
  </div>
  <div class="cv-meta">
    <div><b>Dr. rer. nat. Desiree Gruber</b>Holistic Health · Barcelona</div>
    <div><b>auralisnatura.com</b>office@auralisnatura.com</div>
  </div>
</section>""")

# ------------------------------------------------------------------ 01 contents + brand
toc_rows = "".join(
    f'<tr><td>{n}</td><td>{t}</td><td>{p}</td></tr>' for n, t, p in [
        ("01", "The brand in one page", "3"),
        ("02", "Eight decisions that define the look", "4"),
        ("03", "The mark — seal, lockup, watermark", "5"),
        ("04", "Colour", "6"),
        ("05", "Typography", "8"),
        ("06", "Layout, rhythm and tone", "10"),
        ("07", "The component library — 22 parts", "11"),
        ("08", "Composing a page", "14"),
        ("09", "Writing the copy", "15"),
        ("10", "Print production", "16"),
        ("11", "Photography", "18"),
        ("12", "Content guardrails — legal, not stylistic", "19"),
        ("13", "What ships in this package", "20"),
    ])
PAGES.append(page("2", "Contents", f"""
<div class="ch-n">—</div>
<p class="kick">Contents</p>
<h2 class="ch">What is <i>in here.</i></h2>
<p class="lede">This handbook is written to be used, not admired. Chapters 02–06 are the
rules; 07–09 are how to build with them; 10–13 are production, imagery, law and the
asset inventory.</p>
<table class="toc"><tbody>{toc_rows}</tbody></table>
<div class="hair"></div>
<div class="note"><p><strong>How to read a rule in this book.</strong> Anything stated as a
number — a millimetre, a hex value, a weight — is binding and reproducible from the
repository. Anything describing tone or intent is guidance you are expected to apply
with judgement. Where the two conflict, the number wins.</p></div>
"""))

# ------------------------------------------------------------------ 02 brand
PAGES.append(page("3", "01 · The brand", chapter_head(
    "01", "PhD rigour meeting <i>botanical warmth.</i>", "The brand in one page",
    "Auralis Natura is the holistic health coaching practice of Dr. rer. nat. Desiree "
    "Gruber in Barcelona. The brand's whole job is to make rigorous science feel warm "
    "and human — and to be unmistakably honest about what it is.") + f"""
<div class="two">
  <div>
    <h4>The positioning</h4>
    <p>A chemist's precision applied to everyday wellbeing. The competitive gap this brand
    occupies is the quadrant nobody else holds: <strong>high scientific rigour and high
    human warmth at once</strong>. Most wellness brands pick one.</p>
    <h4>The voice</h4>
    <p><em class="a">A brilliant friend who happens to be a scientist.</em> Warm,
    intelligent, calm, precise. Never breathless, never mystical, never hedging behind
    jargon. Where evidence is weak, the copy says so — that honesty is a brand asset,
    not a liability.</p>
  </div>
  <div>
    <h4>The emotional job</h4>
    <p>Clients arrive depleted and want to <strong>feel like themselves again</strong>.
    Every page, card and report should answer that, not a feature list.</p>
    <h4>What it is never</h4>
    <p>Not medicine. Not diagnosis. Not "cream + terracotta + serif" wellness pastiche —
    the palette deliberately moved to warm earth tones, and the geometry to square
    corners, to sit outside that cliché. See chapter 12 for the guardrails that are
    legal rather than aesthetic.</p>
  </div>
</div>
<div class="hair"></div>
<div class="dark">
  <h3>The one-line test</h3>
  <p>Before shipping anything on this brand, read it back and ask: <strong>would a
  thoughtful scientist put their name on this, and would a tired woman at the end of a
  long week feel welcomed by it?</strong> It has to be both. Something that passes only
  the first reads cold; only the second reads like everyone else.</p>
</div>
"""))

# ------------------------------------------------------------------ 03 eight decisions
eight = "".join([
    rule("1", "Corners are square", f'<code>--r</code> and <code>--r-lg</code> are '
         f'<code>0px</code>. Never add a <code>border-radius</code> anywhere — this is the '
         f'single most defining structural decision in the system, and one rounded card '
         f'undoes it.'),
    rule("2", "The seal is the recurring mark", 'Its signature move is the seal at '
         '<strong>10 % opacity, bleeding off the edge</strong> as a watermark on large quiet '
         'surfaces — hero, dark bands, the CTA card. Never as loud decoration.'),
    rule("3", "Clay is the accent, never a field", 'Role lines, small marks, and '
         '<strong>one primary clay button per view</strong>. Large surfaces are paper, cream '
         'or the dark brown band.'),
    rule("4", "Gold is structural, not shiny", 'Hairlines, small caps, the seal — flat '
         '<code>--gold</code> / <code>--gold-bright</code>. Mirrored or gradient "chrome" gold '
         'was reviewed and rejected as dated.'),
    rule("5", "Edges are hairlines; shadows are wide and soft", 'The printed card\'s frame '
         'is a 0.2 mm hairline. Never tight, dark drop shadows.'),
    rule("6", "Restraint is the premium signal", 'The business card prints at roughly '
         '<strong>4 % ink coverage</strong> — the paper does the work. The screen equivalent '
         'is generous whitespace and few elements per viewport. Resist filling space.'),
    rule("7", "“Desiree Gruber” never breaks across lines", 'At any breakpoint, in any '
         'language. Check it at 360 px.'),
    rule("8", "Never hyphenate", '<code>hyphens: none</code> throughout. German compounds are '
         'handled by <strong>reducing type size</strong>, never by splitting the word. '
         '“GE-SUNDHEITSCOACHING” is the failure this rule exists to prevent.'),
])
PAGES.append(page("4", "02 · Structural decisions", chapter_head(
    "02", "Eight decisions that <i>define the look.</i>", "Non-negotiables",
    "These were settled by a real print run — the approved business card, design 5B "
    "“Reine Fläche”. They are not open questions, and a proposal that breaks one is a "
    "proposal to leave the brand.") + f"""
<div class="card" style="padding:2mm 5.5mm">{eight}</div>
<div class="warn"><p><strong>Where these came from.</strong> The card handoff describes itself
as “the most refined expression of this brand that exists.” Where any older brand note
disagrees with these eight, these win — they were measured against ink on paper.</p></div>
"""))

# ------------------------------------------------------------------ 04 the mark
PAGES.append(page("5", "03 · The mark", chapter_head(
    "03", "The botanical <i>seal.</i>", "Logo, lockup and watermark",
    "A circular line-drawn botanical crest — the only illustrative element in the whole "
    "system, and the thing that makes a surface recognisably Auralis.") + f"""
<div class="seal-row">
  <div class="seal-cell on-paper"><img src="{SEAL_MARK}" alt="Seal, full colour">
    <div class="seal-lab">Primary · on paper</div></div>
  <div class="seal-cell on-dark"><img src="{SEAL_GOLD}" alt="Seal in gold on dark">
    <div class="seal-lab">Gold · on dark bands</div></div>
  <div class="seal-cell on-paper"><img src="{SEAL_BROWN}" alt="Seal in brown">
    <div class="seal-lab">Brown · single-colour</div></div>
</div>
<div class="two">
  <div>
    <h4>The lockup</h4>
    <div class="shot"><img src="{LOCKUP}" alt="Auralis Natura logo lockup"></div>
    <p class="cap">Seal plus wordmark. Use where the brand has to introduce itself —
    letterheads, profile headers, the top of a document. On the website the seal alone
    is usually enough.</p>
  </div>
  <div>
    <h4>The watermark move</h4>
    <p>The brand's signature treatment: the seal scaled large, set to <strong>10 %
    opacity</strong>, and positioned so it <strong>bleeds off the edge</strong> of the
    surface. It reads as texture, not as a logo. Both the cover and the dark band of this
    handbook use it.</p>
    <h4>Clear space</h4>
    <p>Keep free space around the seal equal to at least <strong>half its
    diameter</strong>. It never sits inside a box, never gets a keyline, and never
    appears on a busy photograph.</p>
    <h4>Minimum size</h4>
    <p>16 mm in print, 48 px on screen. Below that the botanical linework fills in and it
    reads as a smudge — use the wordmark alone instead.</p>
  </div>
</div>
<div class="dd">
  <div class="do"><h4>Do</h4><ul>
    <li>Use the supplied masters — they have clean alpha channels.</li>
    <li>Match the variant to the ground: gold on dark, full colour on paper.</li>
    <li>Let it bleed off the edge when used as a watermark.</li>
  </ul></div>
  <div class="dont"><h4>Never</h4><ul>
    <li>Recolour, outline, rotate or add effects to the seal.</li>
    <li>Stretch it — it is circular and stays circular.</li>
    <li>Use <code>handover/assets/emblem_seal_360.png</code>: a different, busier
    seal that must never appear on anything customer-facing.</li>
  </ul></div>
</div>
"""))

# ------------------------------------------------------------------ 05 colour (2pp)
PAGES.append(page("6", "04 · Colour", chapter_head(
    "04", "A warm-earth <i>palette.</i>", "Colour",
    "Cinnamon brown carries the brand; ember clay accents it; amber gold structures it. "
    "Every value below is read directly from the design system's token file — these are "
    "the live values, not a transcription.") + f"""
<h4>Primary — the dark ground</h4>
<div class="sw-grid">
  {swatch('forest', 'Primary. Dark cinnamon brown — the brand colour.')}
  {swatch('forest-soft', 'Top of the dark-band gradient.')}
  {swatch('forest-deep', 'Bottom of the dark-band gradient.')}
  {swatch('forest-2', 'Cinnamon rust. Italic accents on LIGHT grounds only.')}
</div>
<h4>Accent — used sparingly, never as a field</h4>
<div class="sw-grid">
  {swatch('clay', 'THE action colour. Primary buttons, role lines, small marks.')}
  {swatch('clay-deep', 'Pressed and hover state; links on paper.')}
  {swatch('clay-soft', 'Caramel. Rare — soft accents only.')}
  {swatch('gold', 'Structural gold: hairlines, small caps, rules. Flat, never shiny.')}
</div>
<h4>Gold, sage and ink</h4>
<div class="sw-grid">
  {swatch('gold-bright', 'Amber. Emphasis text on the dark bands.')}
  {swatch('sage', 'Warm olive-taupe. Quiet supporting text.')}
  {swatch('sage-soft', 'Warm sand. Secondary text on dark grounds.')}
  {swatch('ink', 'Body copy and headlines on light grounds.')}
</div>
<h4>Ink tones and papers</h4>
<div class="sw-grid">
  {swatch('ink-soft', 'Long-form body copy — softer than full ink.')}
  {swatch('ink-faint', 'Captions, labels, metadata.')}
  {swatch('paper', 'The default page ground.')}
  {swatch('cream', 'The lighter ground — alternate with paper for rhythm.')}
</div>
<div class="sw-grid">
  {swatch('paper-2', 'Cards and inset panels on a paper ground.')}
  {swatch('paper-3', 'The deepest paper tone — quiet fills, oversized numerals.')}
</div>
"""))

PAGES.append(page("7", "04 · Colour", f"""
<h3 style="margin-top:0">Using the palette</h3>
<div class="two">
  <div>
    <h4>The dark band recipe</h4>
    <p>Dark sections are not a flat fill. They are a three-stop gradient at 158°:</p>
    <p><code>--forest-soft</code> → <code>--forest</code> at 55 % →
    <code>--forest-deep</code>, with a <code>--gold-hair</code> hairline on the top
    edge and the seal watermark bleeding from one corner.</p>
    <h4>Emphasis, by ground</h4>
    <p>On light sections, emphasis is <strong>ink at weight 600</strong>. On dark bands
    it is <strong>amber <code>--gold-bright</code></strong>. Never clay for emphasis
    text — clay belongs to actions.</p>
  </div>
  <div>
    <h4>The clay discipline</h4>
    <p>Clay is the most misused token in any system like this. The rule is simple:
    <strong>one primary clay button per view</strong>, and clay never fills an area
    larger than a button or a hairline rule. If a design has two clay buttons competing,
    one of them is not the primary action.</p>
    <h4>Structure lines</h4>
    <p><code>--line</code> for ordinary hairlines, <code>--line-strong</code> where a
    table header or a swatch edge needs to hold, and <code>--gold-hair</code> where the
    hairline is doing brand work rather than layout work.</p>
  </div>
</div>
<div class="hair"></div>
<h3>Contrast and accessibility</h3>
<p>Body copy on paper uses <code>--ink-soft</code>, which clears WCAG AA comfortably at
body sizes. Two combinations need care and are called out because they have caused real
bugs:</p>
<table><thead><tr><th>Combination</th><th>Rule</th></tr></thead><tbody>
<tr><td>Faint ink on dark</td><td>Never. <code>--ink-faint</code> is a light-ground token;
on the dark band use <code>--sage-soft</code>. A featured package card once shipped with
an illegible price label from exactly this mistake.</td></tr>
<tr><td>Clay on forest</td><td>Insufficient contrast. On dark grounds an action button
inverts to a paper or cream fill instead.</td></tr>
<tr><td>Gold as body text</td><td>Never. Gold is for hairlines, small caps and emphasis
at weight 600 — not for paragraphs.</td></tr>
</tbody></table>
<div class="note"><p><strong>Print note.</strong> These are screen values. The printed work
was produced from the same hex values with the printer converting to CMYK; the dark band
on the flyer is specified as <code>#4A3020</code> rather than <code>--forest</code>,
because the gradient does not survive a flat print well. See chapter 10.</p></div>
"""))

# ------------------------------------------------------------------ 06 typography (2pp)
PAGES.append(page("8", "05 · Typography", chapter_head(
    "05", "Two faces, <i>used with discipline.</i>", "Typography",
    "Fraunces carries every display and heading; Hanken Grotesk carries everything else. "
    "Both are self-hosted as woff2 and ship inside the stylesheet — nothing is fetched "
    "from a font host at runtime.") + f"""
<div class="spec">
  <div class="spec-l">Fraunces · display · weight 300 · tracking −0.022em</div>
  <p class="sp-display">Verstehe deinen Körper. <i>Verbessere deine Gesundheit
  nachhaltig.</i></p>
</div>
<div class="spec">
  <div class="spec-l">Fraunces · heading · weight 400</div>
  <p class="sp-h">Dein Körper sendet Signale.</p>
</div>
<div class="spec">
  <div class="spec-l">Hanken Grotesk · body · weight 300–400 · line-height 1.72</div>
  <p class="sp-body">Auralis Natura bietet ganzheitliches Gesundheits- und
  Ernährungscoaching. Wir arbeiten mit dem, was messbar ist, und mit dem, was du
  tatsächlich in deinen Alltag einbauen kannst.</p>
</div>
<div class="spec">
  <div class="spec-l">Hanken Grotesk · label · weight 600 · tracking 0.2em · uppercase</div>
  <p class="sp-label">Fundierte Wissenschaft · Persönliche Begleitung</p>
</div>
<table><thead><tr><th>Role</th><th>Family</th><th>Weight</th><th>Notes</th></tr></thead>
<tbody>
<tr><td>Display</td><td>Fraunces</td><td>300</td><td>Hero and section openers. Italic sets
the accent clause in <code>--forest-2</code> (light) or <code>--gold-bright</code> (dark).</td></tr>
<tr><td>Heading</td><td>Fraunces</td><td>400</td><td>Card and chapter titles.</td></tr>
<tr><td>Body</td><td>Hanken Grotesk</td><td>300–400</td><td>Everything readable. Max
measure ~60 characters.</td></tr>
<tr><td>Label</td><td>Hanken Grotesk</td><td>600</td><td>Kickers and small caps. The
<code>--font-mono</code> token deliberately resolves to Hanken, not a monospace — the
mono read as cold and robotic.</td></tr>
</tbody></table>
"""))

PAGES.append(page("9", "05 · Typography", f"""
<h3 style="margin-top:0">The typographic rules that matter most</h3>
<div class="card" style="padding:2mm 5.5mm">
{rule("1", "Never hyphenate", 'Set <code>hyphens: none</code> and leave it. German '
      'compounds — <em class="a">Gesundheitscoaching</em>, <em class="a">Frauengesundheit</em> '
      '— are handled by reducing the type size until the word fits, never by breaking it.')}
{rule("2", "The founder's name never breaks", '“Desiree Gruber” stays on one line at every '
      'breakpoint. Wrap it in a non-breaking span wherever it appears near a fold.')}
{rule("3", "Fluid sizes, not breakpoint jumps", 'Display type uses <code>clamp()</code> so it '
      'scales continuously. Check every headline at <strong>360 px</strong> — that is where '
      'German breaks first.')}
{rule("4", "Italic is an accent, not a voice", 'Fraunces italic marks the second clause of a '
      'headline or a single pulled phrase. A whole italic paragraph reads as a mistake.')}
{rule("5", "Measure over size", 'Body copy caps at roughly 60 characters. Widening the '
      'column is never the fix for too much text — cutting the text is.')}
</div>
<div class="hair"></div>
<h3>Multilingual setting</h3>
<p>Every customer-facing surface exists in <strong>German, English and Spanish</strong>.
German is the master language and is always the longest — which makes it the layout
constraint. Two consequences for design:</p>
<ul>
  <li><strong>Design in German first.</strong> A layout that holds in German holds in the
  other two. The reverse is not true, and English-first layouts routinely break when the
  German copy lands.</li>
  <li><strong>Headline sizes are per-language where needed.</strong> The printed flyer sets
  its A6 headline at 20.5 pt in English and Spanish but <strong>17 pt in German</strong>.
  That is the rule 1 escape hatch in practice.</li>
</ul>
<div class="note"><p><strong>Where the faces come from.</strong> Both families are
open-source and self-hosted in <code>design-system/assets/fonts/</code> as latin and
latin-ext woff2 subsets. Hanken Grotesk is a single variable file per subset covering
weights 300–700 — if you ever re-download it, dedupe the <code>@font-face</code> rules or
the bundle carries the same file five times.</p></div>
"""))

# ------------------------------------------------------------------ 07 layout
PAGES.append(page("10", "06 · Layout", chapter_head(
    "06", "Rhythm, width <i>and tone.</i>", "Layout",
    "The system has very little layout machinery on purpose: one container width, one "
    "vertical rhythm, and an alternation of grounds that paces a long page.") + f"""
<div class="two">
  <div>
    <h4>The container</h4>
    <p><code>--maxw</code> is <strong>{TOK['maxw']}</strong>, with a fluid gutter
    <code>--gut</code> of <strong>{TOK['gut']}</strong>. Everything centres inside it. Full-bleed
    surfaces — image bands, dark sections — break the container but their content does not.</p>
    <h4>Vertical rhythm</h4>
    <p>Sections carry one of two paddings: the standard <code>sec-pad</code> or the tighter
    <code>sec-pad-sm</code> where two related sections should read as one movement. Do not
    invent intermediate values.</p>
  </div>
  <div>
    <h4>Tone alternation</h4>
    <p>Grounds cycle <strong>paper → cream → paper</strong> to pace the scroll, with a
    <strong>dark band</strong> placed deliberately — <strong>three or four times on a long
    page at most</strong>. The dark band is the page's punctuation; used more often it stops
    landing.</p>
    <h4>Grid</h4>
    <p>Two-column splits are asymmetric (roughly 0.95 / 1.05) rather than an even half —
    it reads as composed rather than divided. Package cards are a fixed three columns and
    collapse to one below 1024 px.</p>
  </div>
</div>
<div class="hair"></div>
<div class="dark">
  <h3>The whitespace budget</h3>
  <p>The single most common way to break this brand is to fill the space. The printed card
  is the calibration: <strong>roughly 4 % ink coverage</strong>. On screen that means few
  elements per viewport, one idea per section, and a willingness to let a headline sit
  alone above a large quiet area. If a design feels sparse next to a competitor's, it is
  probably correct.</p>
</div>
<div class="note"><p><strong>Utility classes that exist</strong> and are safe to reuse:
<code>wrap</code> (the max-width container), <code>sec-pad</code> / <code>sec-pad-sm</code>
(vertical rhythm), <code>u-kick</code> (the kicker rule), <code>em</code> (the italic
accent). Never invent a class name — nothing outside the shipped stylesheet resolves.</p></div>
"""))

# ------------------------------------------------------------------ 08 components (2pp)
g1 = "".join(comp_group(c) for c in ["Foundations", "Typography", "Layout"])
g2 = "".join(comp_group(c) for c in ["Media", "Content", "Commerce"])
extra = [c for c in COMPS if c["cat"] not in GROUP_ORDER]
if extra:
    g2 += "".join(comp_group(c) for c in sorted({c["cat"] for c in extra}))

PAGES.append(page("11", "07 · Components", chapter_head(
    "07", "Twenty-two <i>parts.</i>", "The component library",
    f"The real, shipped library — <code>@auralis/design-system</code>. Every component "
    f"below is compiled code with a typed props contract and a written usage doc. This "
    f"roster is generated from those docs, so it cannot drift from the code.") + f"""
{g1}
"""))

PAGES.append(page("12", "07 · Components", f"""
{g2}
"""))

PAGES.append(page("13", "07 · Components", f"""
<h3 style="margin-top:0">Working with the library</h3>
<p>Import the stylesheet <strong>once</strong> at the app root — every component styles
itself through plain CSS classes, so without it everything renders unstyled:</p>
<div class="card"><p style="margin:0"><code>import '@auralis/design-system/styles.css';</code><br>
<code>import {{ Section, Display, Em, Button }} from '@auralis/design-system';</code></p></div>
<p>No provider and no context are needed. For your own layout glue, reach for the tokens
via <code>var(--*)</code> rather than raw hex values.</p>
<table><thead><tr><th>If you need</th><th>Use</th></tr></thead><tbody>
<tr><td>A primary action</td><td><code>Button variant="clay"</code> — exactly one per view.</td></tr>
<tr><td>A dark band</td><td><code>Section tone="dark"</code> — three or four per page at most.</td></tr>
<tr><td>The pricing row</td><td><code>PackageGrid</code> with exactly three
<code>PackageCard</code>s; <code>featured</code> inverts the middle one to the dark band.</td></tr>
<tr><td>A quiet brand moment</td><td><code>Emblem</code> in its watermark treatment.</td></tr>
<tr><td>Small caps above a heading</td><td><code>Label</code>, or <code>SectionHead</code>
when it also carries the heading. Both take <code>onDark</code>.</td></tr>
</tbody></table>
<div class="warn"><p><strong>The stylesheet is shared with the live site.</strong>
<code>src/styles/components.css</code> is the production homepage stylesheet, kept
byte-identical apart from the token block. A fix made in one must be mirrored into the
other in the same change, or the design system starts rendering against a stale sheet.</p></div>
"""))

# ------------------------------------------------------------------ 09 page composition
PAGES.append(page("14", "08 · Composing a page", chapter_head(
    "08", "How a page <i>is built.</i>", "Composition",
    "The homepage is the reference composition. Its order is not arbitrary — it moves a "
    "stranger from recognition, through credibility, to a single free action.") + f"""
<table><thead><tr><th>#</th><th>Movement</th><th>Built from</th></tr></thead><tbody>
<tr><td>1</td><td>Hero — the promise, in the reader's own words</td><td><code>Section</code> ·
<code>Display</code> · <code>Em</code> · <code>Button</code> · seal watermark</td></tr>
<tr><td>2</td><td>Credential ribbon — earn the right to be believed, immediately</td>
<td><code>CredentialRibbon</code> · <code>CredentialChip</code></td></tr>
<tr><td>3</td><td>The problem — name what she is feeling</td><td><code>Section tone="dark"</code>
· <code>Heading</code> · <code>Text</code></td></tr>
<tr><td>4</td><td>The method — four movements, plainly explained</td><td><code>Section</code> ·
<code>SectionHead</code> · <code>MetaList</code></td></tr>
<tr><td>5</td><td>An image band — let the page breathe</td><td><code>ImageBand</code></td></tr>
<tr><td>6</td><td>Services and pricing — three programmes, one featured</td>
<td><code>PackageGrid</code> · <code>PackageCard</code></td></tr>
<tr><td>7</td><td>The founder — a face, a voice, a signature</td><td><code>PhotoFrame</code> ·
<code>Signature</code> · <code>Emblem</code></td></tr>
<tr><td>8</td><td>Testimonials — real ones only</td><td><code>Testimonial</code></td></tr>
<tr><td>9</td><td>FAQ — answer the objections before they harden</td><td><code>FaqList</code> ·
<code>FaqItem</code></td></tr>
<tr><td>10</td><td>The close — one free, no-obligation call</td><td><code>CtaCard</code></td></tr>
</tbody></table>
<div class="hair"></div>
<div class="two">
  <div>
    <h4>Pacing rules</h4>
    <ul>
      <li>Alternate paper and cream between sections.</li>
      <li>Never place two dark surfaces back to back.</li>
      <li>One idea per section. If a section needs a sub-heading to hold together, it is
      two sections.</li>
      <li>The primary CTA repeats — hero, mid-page, close — but only one is clay per
      viewport.</li>
    </ul>
  </div>
  <div>
    <h4>Adapting the pattern</h4>
    <p>A landing page for a single programme collapses movements 4–6 into one and keeps
    everything else. A corporate page swaps the pricing grid for a bespoke enquiry band.
    What never changes is the arc: <strong>promise → credibility → problem → method →
    proof → one action</strong>.</p>
  </div>
</div>
"""))

# ------------------------------------------------------------------ 10 copy
PAGES.append(page("15", "09 · Writing the copy", chapter_head(
    "09", "German first, <i>always.</i>", "Copy",
    "Copy on this brand is not translated. It is written in German by the founder and "
    "then re-derived into English and Spanish — a change that lands in only one language "
    "is an unfinished change.") + f"""
<div class="two">
  <div>
    <h4>The workflow</h4>
    <p>German is the master. English and Spanish are re-derived from it in the same
    change, capturing the meaning and the register rather than the sentence structure. A
    literal translation of German marketing copy reads stiff in both.</p>
    <h4>Register</h4>
    <p>German uses the informal <em class="a">du</em> throughout — this is a personal
    practice, not an institution. Keep sentences short enough to read aloud.</p>
  </div>
  <div>
    <h4>Words to use</h4>
    <p>Coaching. Begleitung. Bildung. Gesundheitscoaching. <em class="a">May support</em>
    rather than <em class="a">will fix</em>.</p>
    <h4>Words that are legally unavailable</h4>
    <p><strong>Never</strong> “Ernährungsberaterin”, “Nutritionist” or
    “dietista-nutricionista” — a protected profession in Spain under Ley 44/2003. Never
    “heilt”, “cures”, “diagnose”, “treats” or “garantiert”.</p>
  </div>
</div>
<div class="hair"></div>
<h3>Naming</h3>
<p>The three programmes are localised, and the internal keys never change:</p>
<table><thead><tr><th>Key</th><th>German</th><th>English</th><th>Spanish</th><th>Price</th></tr></thead>
<tbody>
<tr><td><code>root</code></td><td>Klarheit</td><td>Clarity</td><td>Claridad</td><td>€199</td></tr>
<tr><td><code>bloom</code></td><td>Wandel</td><td>Change</td><td>Cambio</td><td>€399 · 4 weeks</td></tr>
<tr><td><code>flourish</code></td><td>Balance</td><td>Balance</td><td>Equilibrio</td><td>€899 · 12 weeks</td></tr>
<tr><td><code>corp</code></td><td>Verbindung</td><td>Connection</td><td>Conexión</td><td>Tailored</td></tr>
</tbody></table>
<div class="warn"><p><strong>Never state a duration for the free call.</strong> It is a
<em class="a">Kennenlerngespräch</em> / introductory call / <em class="a">llamada de
presentación</em> — free and no-obligation, with <strong>no minutes named anywhere</strong>
on a customer-facing surface. This is a standing founder decision.</p></div>
"""))

# ------------------------------------------------------------------ 11 print (2pp)
PAGES.append(page("16", "10 · Print production", chapter_head(
    "10", "Ink on <i>paper.</i>", "Print",
    "Two finished pieces define the printed brand: the business card (design 5B “Reine "
    "Fläche”) and the A5/A6 flyer in three languages. Their geometry is load-bearing and "
    "must not be “corrected”.") + f"""
<h3 style="margin-top:0">Flyer formats</h3>
<table><thead><tr><th>Format</th><th>Trim</th><th>Bleed box</th><th>Page box</th><th>Languages</th></tr></thead>
<tbody>
<tr><td>A6 (narrowed)</td><td>95 × 148 mm</td><td>101 × 154 mm</td><td>111 × 164 mm</td><td>EN · DE · ES</td></tr>
<tr><td>A5 (narrowed)</td><td>138 × 210 mm</td><td>144 × 216 mm</td><td>154 × 226 mm</td><td>EN · DE · ES</td></tr>
</tbody></table>
<div class="note"><p><strong>Both formats are 10 mm narrower than the DIN standard at
unchanged height.</strong> This is deliberate — it moves the proportion nearer the golden
ratio. It is not an error, and a printer or designer who “fixes” it back to DIN has broken
the piece.</p></div>
<h4>Page construction</h4>
<ul>
  <li><strong>Page box</strong> — the sheet the browser prints: trim, plus 3 mm bleed on
  every side, plus 5 mm of margin for the crop marks.</li>
  <li><strong>Artboard</strong> — an absolutely positioned div at <code>left:5mm;
  top:5mm</code>, sized to the bleed box. All artwork lives here; <code>overflow:hidden</code>
  clips the bleed.</li>
  <li><strong>Crop marks</strong> — eight 0.15 mm hairlines in <code>#aaa39a</code>, drawn
  1 mm outside the trim edge and 4 mm long, plus a caption strip naming language, side,
  trim and bleed.</li>
</ul>
<div class="warn"><p><strong>The registration rule — learned the hard way.</strong> No page's
geometry may depend on its content. An early version let the artboard flow, and the back
side printed roughly <strong>20 mm higher on the sheet than the front</strong>. Every page
is now a fixed page box with the artboard at a fixed offset, and the repository's CI print
check (<code>ci/check-print.mjs</code>) asserts it. Keep that check in any new print
piece.</p></div>
"""))

PAGES.append(page("17", "10 · Print production", f"""
<h3 style="margin-top:0">Specifying a new piece</h3>
<div class="two">
  <div>
    <h4>Units</h4>
    <p>Everything is specified in <strong>millimetres and points</strong>, never CSS
    pixels. Reproduce values exactly — a measure that looks “roughly 6 mm” is 6 mm.</p>
    <h4>Vertical rhythm</h4>
    <p>Built from explicit <code>height:*mm; flex:none</code> spacer divs rather than
    margins, so the stack cannot collapse or drift between browsers.</p>
    <h4>The dark band</h4>
    <p>Print uses a flat <code>#4A3020</code>, not the screen gradient — 46 mm tall on
    A6, 58 mm on A5, anchored with <code>margin-top:auto</code>.</p>
  </div>
  <div>
    <h4>Front-face proportions (A6 → A5)</h4>
    <table style="font-size:8.2pt">
      <thead><tr><th>Element</th><th>A6</th><th>A5</th></tr></thead>
      <tbody>
        <tr><td>Top spacer</td><td>10 mm</td><td>19 mm</td></tr>
        <tr><td>Seal</td><td>16 × 16 mm</td><td>24 × 24 mm</td></tr>
        <tr><td>Gold rule</td><td>14 × 0.25 mm</td><td>20 × 0.25 mm</td></tr>
        <tr><td>Headline</td><td>20.5 pt<br>(DE 17 pt)</td><td>29 pt<br>(DE 24 pt)</td></tr>
        <tr><td>Lede</td><td>8.6 pt / 80 mm</td><td>11 pt / 112 mm</td></tr>
      </tbody>
    </table>
  </div>
</div>
<div class="hair"></div>
<h3>Sending to a printer</h3>
<ul>
  <li>Export at <strong>300 dpi</strong> with bleed included and crop marks on.</li>
  <li>Let the printer handle CMYK conversion from the supplied hex values — the palette
  was proofed this way.</li>
  <li>Choose an <strong>uncoated or lightly textured stock</strong>. The design is built
  around low ink coverage, and a gloss finish fights it.</li>
  <li>Ask for a physical proof before any run above a few hundred pieces. The gold
  hairlines are the first thing to disappear on a cheap press.</li>
</ul>
<div class="dark">
  <h3>The 4 % rule</h3>
  <p>The approved business card prints at roughly <strong>4 % ink coverage</strong>. When
  a new printed piece is designed, measure it against that number. If it is dramatically
  heavier, the design has stopped trusting the paper — and on this brand, the paper is
  doing the premium work.</p>
</div>
"""))

# ------------------------------------------------------------------ 12 photography
PAGES.append(page("18", "11 · Photography", chapter_head(
    "11", "Real light, <i>real hands.</i>", "Photography",
    "The photography is documentary rather than styled: natural light, real workspaces, "
    "and the founder actually working. It is the warmth half of the brand's promise.") + f"""
<div class="three">
  <div><div class="shot"><img src="{PHOTO_PORTRAIT}" alt="Founder portrait"></div>
    <p class="cap"><b>Portrait.</b> Desk, daylight, direct gaze. The hero and About
    treatment.</p></div>
  <div><div class="shot"><img src="{PHOTO_CONSULT}" alt="Consultation"></div>
    <p class="cap"><b>In practice.</b> A consultation in progress — credibility without
    a claim.</p></div>
  <div><div class="shot"><img src="{PHOTO_NOURISH}" alt="Still life"></div>
    <p class="cap"><b>Still life.</b> Food and botanicals, uncomposed. Used for image
    bands.</p></div>
</div>
<div class="hair"></div>
<div class="two">
  <div>
    <h4>Direction</h4>
    <ul>
      <li>Natural, soft, directional light — never flash, never a studio sweep.</li>
      <li>Warm neutrals that sit with the palette: wood, linen, ceramic, green leaf.</li>
      <li>Real spaces with real texture. Nothing looks propped.</li>
      <li>People are working or listening, not smiling at the lens holding a salad.</li>
    </ul>
    <h4>Treatment</h4>
    <p>Images are placed inside <code>PhotoFrame</code> or run full-bleed as an
    <code>ImageBand</code>. A hairline border, never a rounded corner, never a drop
    shadow. Cropping is done with <code>object-fit: cover</code> and an explicit
    <code>objectPosition</code> — never by distorting the frame.</p>
  </div>
  <div>
    <h4>Never</h4>
    <ul>
      <li><strong>Never substitute stock imagery</strong> on this brand. If a real
      photograph does not exist, ship a placeholder and flag it — the documentary quality
      is the point, and generic wellness stock destroys it immediately.</li>
      <li>No heavy filters, no duotones, no colour grading away from the natural warmth.</li>
      <li>No text baked into a photograph. Type sits in the layout, over a quiet area if
      it must overlap.</li>
    </ul>
    <div class="warn"><p><strong>One image carries context.</strong>
    <code>desiree-womens-health.jpg</code> shows the founder visibly pregnant and sits in
    the Frauengesundheit section by explicit founder decision. Do not move it into an
    About or motherhood context, and check with the founder before writing any copy near
    it.</p></div>
  </div>
</div>
"""))

# ------------------------------------------------------------------ 13 guardrails
PAGES.append(page("19", "12 · Guardrails", chapter_head(
    "12", "Rules that are <i>law, not taste.</i>", "Content guardrails",
    "These constrain every word and image produced for this business. They are not style "
    "preferences and they are never relaxed to make something punchier.") + f"""
<div class="card" style="padding:2mm 5.5mm">
{rule("1", "Coaching and education — never medical care", 'In Spain, '
      '<em class="a">dietista-nutricionista</em> is a legally protected profession under '
      '<strong>Ley 44/2003</strong>. Position everything as holistic health coaching and '
      'education: lifestyle, habits, general nutrition education, accountability. '
      '<strong>Never</strong> diagnosis, treatment of disease, or prescriptive medical '
      'nutrition therapy.')}
{rule("2", "“Dr.” means Dr. rer. nat.", 'An academic doctorate in bioorganic chemistry, '
      'disclosed plainly wherever the title appears. <strong>Never imply a physician.</strong> '
      'That honesty is itself a brand asset.')}
{rule("3", "Complement, never replace, medical care", 'Refer out. Keep red-flag guidance and '
      'the emergency note — “see your doctor, call 112 in an emergency” — in every client-'
      'facing deliverable.')}
{rule("4", "Testimonials are real, or they do not exist", 'Never invent, embellish or '
      'composite a review — in production, in a mockup, or in a component preview. '
      'Placeholders must be visibly labelled as such.')}
{rule("5", "Health data is GDPR special category", 'Explicit consent, a lawful basis, data '
      'minimisation, EU-hosted encrypted storage, a defined retention period. Never route '
      'health details through social media, DMs or messaging apps.')}
{rule("6", "AI is assistive and human-led", 'Any AI-drafted client output is reviewed, '
      'edited and approved by the founder before it reaches a client. Educational, never '
      'diagnostic.')}
{rule("7", "Figures are directional", 'Market and financial numbers are estimates framed for '
      'validation — never presented as forecasts or fundraising-grade figures.')}
</div>
<div class="note"><p><strong>Design implication.</strong> These are not only a copywriter's
problem. A layout that has no room for a disclaimer, a testimonial component with no
placeholder state, or a form that collects health data without a consent field are all
<em class="a">design</em> failures. Build the space for compliance into the composition
from the start.</p></div>
"""))

# ------------------------------------------------------------------ 14 package
PAGES.append(page("20", "13 · The package", chapter_head(
    "13", "What ships <i>in this package.</i>", "Asset inventory",
    "Everything referenced in this handbook travels with it. Paths are relative to the "
    "root of the ZIP.") + f"""
<table><thead><tr><th>Path</th><th>What it is</th></tr></thead><tbody>
<tr><td><code>01-handbook/</code></td><td>This document, as PDF and as self-contained
HTML.</td></tr>
<tr><td><code>02-design-system/</code></td><td>The built, browser-ready bundle of
<code>@auralis/design-system</code>: 22 compiled components, typed props, per-component
usage docs, tokens, fonts, and a preview card for every component.</td></tr>
<tr><td><code>03-brand-masters/</code></td><td>The best copies of the seal that exist —
full colour at 1600 px, gold on dark, single-colour brown, the watermark variant, and the
website QR code.</td></tr>
<tr><td><code>04-print/</code></td><td>The approved business card (design 5B) and the
A5/A6 trilingual flyer as production artwork, plus their handoff notes and the CI print
check.</td></tr>
<tr><td><code>05-fonts/</code></td><td>Fraunces and Hanken Grotesk as self-hosted woff2,
latin and latin-ext, with the <code>@font-face</code> CSS.</td></tr>
<tr><td><code>06-photography/</code></td><td>The real photography library — portraits,
consultation, still life, certificates.</td></tr>
<tr><td><code>07-website/</code></td><td>The live homepage as a single HTML file — the
canonical, shipped expression of everything in this handbook.</td></tr>
</tbody></table>
<div class="hair"></div>
<h3>Using the design system</h3>
<p><code>02-design-system/</code> is the format Claude Design consumes directly:
<code>_ds_bundle.js</code> exposes every component on <code>window.AuralisNatura</code>,
<code>styles.css</code> carries the whole style closure including the self-hosted fonts,
and each component ships a <code>.d.ts</code> contract, a <code>.prompt.md</code> usage
reference and an <code>.html</code> preview card. Upload its contents at the project
root.</p>
<div class="dark">
  <h3>One last thing</h3>
  <p>This brand's premium quality does not come from anything expensive. It comes from
  <strong>restraint, hairlines, real photography and honest words</strong> — a small
  number of decisions applied without exception. When in doubt about something this
  handbook does not cover, choose the quieter option.</p>
</div>
<div style="display:flex;gap:6mm;align-items:center;margin-top:5mm;
  border-top:1px solid var(--line);padding-top:4mm">
  <img class="qr" src="{QR}" alt="QR code to auralisnatura.com">
  <div>
    <p style="margin:0"><strong>auralisnatura.com</strong></p>
    <p style="margin:0;color:var(--ink-faint);font-size:8.6pt">Dr. rer. nat. Desiree Gruber ·
    Holistic Health · Barcelona · office@auralisnatura.com</p>
  </div>
</div>
"""))


DOC = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
       f'<meta name="viewport" content="width=device-width,initial-scale=1">'
       f'<title>Auralis Natura — Design Handbook</title>'
       f'<style>{CSS}</style></head><body>{"".join(PAGES)}</body></html>')


def to_pdf(html_path: pathlib.Path, pdf_path: pathlib.Path) -> bool:
    chrome = next((c for c in CHROME_CANDIDATES if pathlib.Path(c).exists()), None) \
        or shutil.which("chromium") or shutil.which("google-chrome")
    if not chrome:
        print("! no chromium found — HTML written, PDF skipped")
        return False
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox",
               f"--user-data-dir={tmp}", "--no-pdf-header-footer",
               "--virtual-time-budget=20000",
               f"--print-to-pdf={pdf_path}", html_path.as_uri()]
        r = subprocess.run(cmd, capture_output=True, timeout=180)
    if not pdf_path.exists() or pdf_path.stat().st_size < 20_000:
        print("! PDF render failed:", r.stderr.decode()[-400:])
        return False
    return True


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(DOC, encoding="utf-8")
    print(f"✓ {OUT_HTML.relative_to(ROOT)}  ({OUT_HTML.stat().st_size/1024:.0f} KB, "
          f"{len(PAGES)} pages)")
    if to_pdf(OUT_HTML, OUT_PDF):
        print(f"✓ {OUT_PDF.relative_to(ROOT)}  ({OUT_PDF.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
