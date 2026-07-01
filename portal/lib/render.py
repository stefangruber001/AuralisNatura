"""Render an approved report into a premium, branded HTML → PDF.

The visual design system (warm-earth palette, Fraunces/Hanken, the seal, editorial
layout, and SVG charts built from the client's own energy/sleep/stress numbers) is
what makes the report feel "super-premium". The *content* is the agent's draft that
Desiree approved.

PDF is produced with headless Chromium (`--print-to-pdf`) so background graphics
and web fonts render exactly as designed — no PDF library.
"""
from __future__ import annotations
import base64, html, os, subprocess, tempfile, shutil, datetime as _dt
from pathlib import Path
from . import cfg

_CHROME_CANDIDATES = [
    os.environ.get("AURALIS_CHROME", ""),
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
]


def _chrome() -> str | None:
    for c in _CHROME_CANDIDATES:
        if c and Path(c).exists():
            return c
    return None


def _seal_b64() -> str:
    p = cfg.ASSETS_DIR / "seal.png"
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


def _bar_chart(charts: dict) -> str:
    labels = {"energy": "Energy", "sleep": "Sleep", "stress": "Stress", "digestion": "Digestion"}
    if not charts:
        return ""
    rows = []
    for k, lab in labels.items():
        if k in charts:
            v = charts[k]
            pct = int(v / 5 * 100)
            rows.append(
                f'<div class="ch-row"><span class="ch-l">{lab}</span>'
                f'<span class="ch-track"><span class="ch-fill" style="width:{pct}%"></span></span>'
                f'<span class="ch-v">{v}/5</span></div>'
            )
    if not rows:
        return ""
    return '<div class="chart"><div class="ch-cap">Your self-ratings</div>' + "".join(rows) + "</div>"


def build_html(client_name: str, sections: list[dict], charts: dict | None = None,
               date: str | None = None, language: str = "en") -> str:
    co = cfg.company()
    date = date or _dt.date.today().strftime("%B %Y")
    seal = _seal_b64()
    kicker = {"de": "Persönlicher Gesundheitsbericht", "es": "Informe personal de salud"}.get(
        language, "Personal Holistic Health Report")
    fig = {"de": "Abschnitt", "es": "Sección", "en": "Section"}[language if language in ("de", "es") else "en"]
    blocks = []
    for i, s in enumerate(sections, 1):
        body = html.escape(s.get("body", "")).replace("\n", "<br>")
        cls = "block guard" if s.get("key") == "when_to_see_a_doctor" else "block"
        chart = _bar_chart(charts or {}) if s.get("key") == "what_were_seeing" else ""
        blocks.append(
            f'<section class="{cls}"><span class="fig">{fig} {i:02d}</span>'
            f'<h2>{html.escape(s.get("title",""))}</h2>{chart}<p>{body}</p></section>'
        )
    disc = _disclaimer(language)
    return _TEMPLATE.format(
        seal=seal, brand=html.escape(co.get("brand", "Auralis Natura")),
        kicker=kicker, client=html.escape(client_name or "—"), date=html.escape(date),
        owner=html.escape(co.get("owner", "")), blocks="".join(blocks), disclaimer=disc,
        contact=html.escape(f'{co.get("email","")} · {co.get("phone","")} · {co.get("web","")}'),
        lang=language,
    )


def to_pdf(html_text: str, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    chrome = _chrome()
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html_text)
        src = f.name
    try:
        if not chrome:
            # graceful fallback: keep the HTML next to where the PDF would be
            out_path.with_suffix(".html").write_text(html_text, encoding="utf-8")
            return out_path.with_suffix(".html")
        cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox",
               "--no-pdf-header-footer", f"--print-to-pdf={out_path}", f"file://{src}"]
        subprocess.run(cmd, capture_output=True, timeout=90)
        if not out_path.exists():
            out_path.with_suffix(".html").write_text(html_text, encoding="utf-8")
            return out_path.with_suffix(".html")
        return out_path
    finally:
        try:
            os.unlink(src)
        except OSError:
            pass


def _disclaimer(lang: str) -> str:
    if lang == "de":
        return ("<strong>Wichtig.</strong> Dieser Bericht bietet ganzheitliches Gesundheits- und "
                "Ernährungscoaching zur Bildung und zum allgemeinen Wohlbefinden. Er diagnostiziert, "
                "behandelt oder heilt keine Krankheit und ersetzt keine medizinische Versorgung. „Dr.“ "
                "bezeichnet einen wissenschaftlichen Doktortitel (Dr. rer. nat.) in Chemie, keine "
                "medizinische Qualifikation. Im Notfall wähle die 112. Deine Daten werden gemäß der "
                "DSGVO vertraulich behandelt.")
    if lang == "es":
        return ("<strong>Importante.</strong> Este informe ofrece coaching holístico de salud y nutrición "
                "con fines educativos y de bienestar general. No diagnostica, trata ni cura ninguna "
                "enfermedad y no sustituye la atención médica. «Dr.» designa un doctorado académico "
                "(Dr. rer. nat.) en química, no una cualificación médica. En una emergencia llama al 112. "
                "Tus datos se tratan de forma confidencial conforme al RGPD.")
    return ("<strong>Important.</strong> This report provides holistic health &amp; nutrition coaching for "
            "education and general wellbeing. It does not diagnose, treat or cure any condition and is not a "
            "substitute for medical care. “Dr.” denotes an academic doctorate (Dr. rer. nat.) in chemistry, "
            "not a medical qualification. In an emergency call 112. Your data is handled confidentially under "
            "the GDPR.")


_TEMPLATE = """<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,360..600&family=Hanken+Grotesk:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--ink:#2A211A;--ink-soft:#5C4A3A;--ink-faint:#8C7E6E;--forest:#3D2719;--forest-deep:#27170E;--clay:#A8492A;--gold:#AD7A32;--sage:#927B4A;--sage-soft:#DAC79E;--paper:#F5EEE0;--cream:#FBF6EB;--line:rgba(61,39,25,.16);--fd:"Fraunces",Georgia,serif;--fb:"Hanken Grotesk",system-ui,sans-serif}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:var(--fb);color:var(--ink);background:#fff;font-size:13.5px;line-height:1.62;-webkit-font-smoothing:antialiased}}
.cover{{min-height:96vh;display:flex;flex-direction:column;justify-content:center;text-align:center;background:linear-gradient(160deg,var(--cream),var(--paper));padding:0 12mm;page-break-after:always}}
.cover img{{width:96px;height:96px;margin:0 auto 20px}}
.cover .kick{{font-family:var(--fb);font-size:.66rem;letter-spacing:.24em;text-transform:uppercase;color:var(--clay);font-weight:600}}
.cover h1{{font-family:var(--fd);font-weight:400;font-size:2.7rem;line-height:1.08;color:var(--ink);margin:12px 0 18px}}
.cover .meta{{font-size:.9rem;color:var(--ink-soft)}}
.cover .meta b{{color:var(--ink)}}
.wrap{{max-width:720px;margin:0 auto;padding:16mm 14mm}}
.block{{margin-bottom:26px;page-break-inside:avoid}}
.fig{{font-family:var(--fb);font-size:.62rem;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-faint);font-weight:600}}
.block h2{{font-family:var(--fd);font-weight:400;font-size:1.7rem;color:var(--forest);margin:4px 0 10px}}
.block p{{color:var(--ink-soft)}}
.guard{{background:linear-gradient(160deg,var(--forest-deep),var(--forest));color:#EDE7D6;padding:20px 24px}}
.guard .fig{{color:var(--sage-soft)}}.guard h2{{color:#F3EEDF}}.guard p{{color:#DED7C4}}
.chart{{margin:8px 0 14px;border:1px solid var(--line);padding:14px 16px;background:var(--cream)}}
.ch-cap{{font-family:var(--fb);font-size:.6rem;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:9px;font-weight:600}}
.ch-row{{display:flex;align-items:center;gap:10px;margin:5px 0;font-size:12px}}
.ch-l{{width:70px;color:var(--ink-soft)}}
.ch-track{{flex:1;height:8px;background:var(--sage-soft);position:relative}}
.ch-fill{{position:absolute;left:0;top:0;bottom:0;background:linear-gradient(90deg,var(--clay),var(--gold))}}
.ch-v{{width:34px;text-align:right;color:var(--ink);font-weight:600}}
.foot{{margin-top:22px;border-top:1px solid var(--line);padding-top:12px;font-size:10px;color:var(--ink-faint);line-height:1.6}}
@media print{{@page{{size:A4;margin:0}}}}
</style></head><body>
<header class="cover">
  <img src="data:image/png;base64,{seal}" alt="">
  <div class="kick">{kicker}</div>
  <h1>Prepared with care<br>for {client}.</h1>
  <div class="meta"><b>{client}</b> · {date}<br>{owner} · {brand}</div>
</header>
<main class="wrap">
{blocks}
<div class="foot">{disclaimer}<br><br>{contact}</div>
</main></body></html>"""
