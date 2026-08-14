"""Render an approved report into a premium, branded HTML → PDF.

Structure (content order unchanged — founder decision 2026-08-13; the visual
layer is new):
  Cover · Letter+legend · Table of contents · At-a-glance dashboard ·
  Chapters 01–06 (long chapters flow onto localized continuation pages) ·
  Weekly plan · 28-day tracker · Closing (QR to the website)

Design: the printed corporate ID is the reference — square corners, hairline
frames, warm-earth tokens from design-system/dist/auralis.css, flat gold, the
seal watermark bleeding off the cover edge, restraint as the premium signal.

Two decisions with history:
* Fonts are the repo's own woff2, base64-inlined. The old Google-Fonts <link>
  meant a PDF rendered without network silently lost the brand faces — the
  single worst defect of the previous design.
* Pages are fixed A4 boxes with overflow:hidden, so a too-long chapter used to
  CLIP silently. CSS break control cannot help inside overflow:hidden;
  _split_chapter() budgets content in Python instead — deterministic and
  testable offline.

PDF via headless Chromium (--print-to-pdf). Contracts that outlive redesigns:
_CHROME_CANDIDATES / _chrome() (tools/preflight.py reaches in), to_pdf()'s
html-fallback, build_html()'s signature, section titles verbatim in the output.
"""
from __future__ import annotations
import base64, html, math, os, subprocess, tempfile, shutil, datetime as _dt
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


def _b64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


def _seal_b64() -> str:
    return _b64(cfg.ASSETS_DIR / "seal.png")


_FONT_DIR = cfg.ROOT.parent / "design-system" / "assets" / "fonts"
_MASTERS = cfg.ROOT.parent / "brand" / "masters"
_CACHE: dict = {}


def _font_css() -> str:
    """The brand faces as data: URIs — the PDF renders offline, identically."""
    if "fonts" in _CACHE:
        return _CACHE["fonts"]
    faces = []
    for fam, style, weight, fname in [
        ("Fraunces", "normal", "300 600", "fraunces-normal-300_600-latin.woff2"),
        ("Fraunces", "italic", "300 500", "fraunces-italic-300_500-latin.woff2"),
        ("Hanken Grotesk", "normal", "300 700", "hanken-grotesk-normal-300_700-latin.woff2"),
        ("Hanken Grotesk", "normal", "300 700", "hanken-grotesk-normal-300_700-latin-ext.woff2"),
    ]:
        p = _FONT_DIR / fname
        if p.exists():
            faces.append(f"@font-face{{font-family:'{fam}';font-style:{style};"
                         f"font-weight:{weight};src:url(data:font/woff2;base64,{_b64(p)}) "
                         f"format('woff2');font-display:block}}")
    _CACHE["fonts"] = "\n".join(faces)
    return _CACHE["fonts"]


def _norm_lang(language: str) -> str:
    l = (language or "").lower()
    return "de" if l.startswith("de") else "es" if l.startswith("es") else "en"


def _e(x) -> str:
    return html.escape(str(x or ""))


# ---------- localised strings ----------
_L = {
 "de": {"kicker": "Persönlicher Gesundheitsbericht", "for": "Mit Sorgfalt erstellt für",
        "chapter": "Kapitel", "page": "Seite", "cont": "Fortsetzung",
        "toc_h": "Inhalt", "toc_sub": "Der Weg durch deinen Bericht.",
        "toc_fixed": ["Ein Brief an dich", "Auf einen Blick", "Dein Wochenplan",
                      "Dein 28-Tage-Begleiter", "Dein nächster Schritt"],
        "letter_h": "Ein Brief an dich", "letter": [
            "es braucht Mut, ehrlich hinzuschauen — danke für dein Vertrauen. Auf den folgenden Seiten "
            "findest du keine Standard-Tipps, sondern eine Zusammenführung deiner eigenen Worte, deiner "
            "Zahlen und der Wissenschaft dahinter.",
            "Lies den Bericht in Ruhe, gern zweimal. Nichts hier ist eine Aufgabe, die du sofort erfüllen "
            "musst; alles ist eine Einladung, bei dir selbst anzufangen — klein, konkret und freundlich.",
            "Ich freue mich darauf, alles gemeinsam mit dir durchzugehen."],
        "legend_h": "So liest du diesen Bericht",
        "legend": [("ok", "Stärke — läuft bereits gut"),
                   ("gold", "Hebel — hier lohnt sich Aufmerksamkeit"),
                   ("warn", "Priorität — hier beginnen wir")],
        "glance_h": "Auf einen Blick", "glance_sub": "Deine Selbsteinschätzung und die drei größten Hebel.",
        "ratings": "Deine Selbsteinschätzung", "balance": "Dein Balance-Profil",
        "themes": "Deine Themen", "prio_h": "Deine 3 Prioritäten",
        "science_h": "Die Wissenschaft, einfach", "actions_h": "Deine Schritte",
        "week_h": "Dein Wochenplan", "week_sub": "Ein sanfter Fokus pro Tag — kein Programm, ein Rhythmus.",
        "days": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
        "habit_h": "Dein 28-Tage-Begleiter", "habit_sub":
            "Hake ab, was dir gelungen ist — Fortschritt zählt, nicht Perfektion. Woche für Woche.",
        "week_lbl": "Woche", "first_step": "Erster Schritt",
        "close_h": "Dein nächster Schritt",
        "close": "Nimm dir eine Sache aus diesem Bericht — die leichteste — und beginne heute. "
                 "Alles Weitere besprechen wir in deinem Gespräch.",
        "close_sign": "Von Herzen,", "scale_note": "1 = niedrig · 5 = sehr gut",
        "qr_cap": "Zum Portal & zur Website"},
 "en": {"kicker": "Personal Holistic Health Report", "for": "Prepared with care for",
        "chapter": "Chapter", "page": "Page", "cont": "continued",
        "toc_h": "Contents", "toc_sub": "The path through your report.",
        "toc_fixed": ["A letter to you", "At a glance", "Your weekly rhythm",
                      "Your 28-day companion", "Your next step"],
        "letter_h": "A letter to you", "letter": [
            "it takes courage to look honestly — thank you for your trust. On the following pages you "
            "won't find generic tips, but a synthesis of your own words, your numbers and the science "
            "behind them.",
            "Read this calmly, twice if you like. Nothing here is a task you must complete today; "
            "everything is an invitation to begin with yourself — small, concrete and kind.",
            "I look forward to walking through all of it together."],
        "legend_h": "How to read this report",
        "legend": [("ok", "Strength — already going well"),
                   ("gold", "Lever — worth your attention"),
                   ("warn", "Priority — where we start")],
        "glance_h": "At a glance", "glance_sub": "Your self-ratings and the three biggest levers.",
        "ratings": "Your self-ratings", "balance": "Your balance profile",
        "themes": "Your themes", "prio_h": "Your 3 priorities",
        "science_h": "The science, simply", "actions_h": "Your steps",
        "week_h": "Your weekly rhythm", "week_sub": "One gentle focus per day — not a programme, a rhythm.",
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "habit_h": "Your 28-day companion", "habit_sub":
            "Tick what worked — progress counts, not perfection. Week by week.",
        "week_lbl": "Week", "first_step": "First step",
        "close_h": "Your next step",
        "close": "Take one thing from this report — the easiest one — and begin today. "
                 "We'll talk through everything else in your call.",
        "close_sign": "Warmly,", "scale_note": "1 = low · 5 = great",
        "qr_cap": "To the portal & website"},
 "es": {"kicker": "Informe personal de salud holística", "for": "Elaborado con cuidado para",
        "chapter": "Capítulo", "page": "Página", "cont": "continuación",
        "toc_h": "Contenido", "toc_sub": "El camino por tu informe.",
        "toc_fixed": ["Una carta para ti", "De un vistazo", "Tu ritmo semanal",
                      "Tu compañero de 28 días", "Tu siguiente paso"],
        "letter_h": "Una carta para ti", "letter": [
            "hace falta valor para mirar con honestidad — gracias por tu confianza. En las páginas "
            "siguientes no encontrarás consejos genéricos, sino una síntesis de tus propias palabras, "
            "tus números y la ciencia detrás.",
            "Léelo con calma, dos veces si quieres. Nada aquí es una tarea que cumplir hoy; todo es una "
            "invitación a empezar contigo — pequeño, concreto y amable.",
            "Me alegra recorrerlo contigo."],
        "legend_h": "Cómo leer este informe",
        "legend": [("ok", "Fortaleza — ya va bien"),
                   ("gold", "Palanca — merece tu atención"),
                   ("warn", "Prioridad — por aquí empezamos")],
        "glance_h": "De un vistazo", "glance_sub": "Tu autoevaluación y las tres mayores palancas.",
        "ratings": "Tu autoevaluación", "balance": "Tu perfil de equilibrio",
        "themes": "Tus temas", "prio_h": "Tus 3 prioridades",
        "science_h": "La ciencia, en simple", "actions_h": "Tus pasos",
        "week_h": "Tu ritmo semanal", "week_sub": "Un foco suave por día — no un programa, un ritmo.",
        "days": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
        "habit_h": "Tu compañero de 28 días", "habit_sub":
            "Marca lo que salió — cuenta el progreso, no la perfección. Semana a semana.",
        "week_lbl": "Semana", "first_step": "Primer paso",
        "close_h": "Tu siguiente paso",
        "close": "Toma una sola cosa de este informe — la más fácil — y empieza hoy. "
                 "El resto lo hablamos en tu llamada.",
        "close_sign": "Con cariño,", "scale_note": "1 = bajo · 5 = muy bien",
        "qr_cap": "Al portal y la web"},
}

_CH_LABELS = {
    "en": {"energy": "Energy", "sleep": "Sleep", "stress": "Stress", "digestion": "Digestion"},
    "de": {"energy": "Energie", "sleep": "Schlaf", "stress": "Stress", "digestion": "Verdauung"},
    "es": {"energy": "Energía", "sleep": "Sueño", "stress": "Estrés", "digestion": "Digestión"},
}
_SYM_LABELS = {
    "de": {"fatigue": "Erschöpfung", "sleep": "Schlaf", "digestion": "Verdauung", "stress": "Stress",
           "hormonal": "Hormone", "weight": "Gewicht", "skin": "Haut", "mood": "Stimmung",
           "pain": "Schmerzen", "immune": "Immunsystem", "other": "Weiteres"},
    "en": {"fatigue": "Exhaustion", "sleep": "Sleep", "digestion": "Digestion", "stress": "Stress",
           "hormonal": "Hormones", "weight": "Weight", "skin": "Skin", "mood": "Mood",
           "pain": "Pain", "immune": "Immune system", "other": "Other"},
    "es": {"fatigue": "Agotamiento", "sleep": "Sueño", "digestion": "Digestión", "stress": "Estrés",
           "hormonal": "Hormonas", "weight": "Peso", "skin": "Piel", "mood": "Ánimo",
           "pain": "Dolor", "immune": "Inmunidad", "other": "Otros"},
}


# ---------- visual builders ----------
def _status(k: str, v: float) -> str:
    """Ampel: for stress high is bad; for the rest low is bad."""
    good = (6 - v) if k == "stress" else v
    return "ok" if good >= 4 else ("gold" if good >= 3 else "warn")


def _bars(charts: dict, lang: str) -> str:
    labels = _CH_LABELS.get(lang, _CH_LABELS["en"])
    ticks = "".join(f'<i style="left:{t * 20}%"></i>' for t in range(1, 5))
    rows = []
    for k in ("energy", "sleep", "stress", "digestion"):
        if k in charts:
            v = float(charts[k]); pct = int(v / 5 * 100)
            st = _status(k, v)
            rows.append(
                f'<div class="ch-row"><span class="ch-l">{_e(labels[k])}</span>'
                f'<span class="ch-track">{ticks}<span class="ch-fill st-{st}" style="width:{pct}%"></span></span>'
                f'<span class="ch-v">{v:.0f}<em>/5</em></span><span class="dot dot-{st}"></span></div>')
    return "".join(rows)


def _radar(charts: dict, lang: str) -> str:
    keys = [k for k in ("energy", "sleep", "stress", "digestion") if k in charts]
    if len(keys) < 3:
        return ""
    labels = _CH_LABELS.get(lang, _CH_LABELS["en"])
    C, R = 110, 76
    n = len(keys)
    def pt(i, val):
        a = -math.pi / 2 + i * 2 * math.pi / n
        r = R * val / 5
        return (C + r * math.cos(a), C + r * math.sin(a))
    grid = ""
    for lvl in (1, 2, 3, 4, 5):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, lvl) for i in range(n)))
        grid += (f'<polygon points="{pts}" fill="none" '
                 f'stroke="rgba(61,39,25,{".16" if lvl == 5 else ".09"})" stroke-width="1"/>')
    # level labels on the vertical axis — the rings mean something now
    lvls = "".join(f'<text x="{C + 4}" y="{C - R * l / 5 + 3:.1f}" font-size="7" '
                   f'fill="#9A8B79" font-family="Hanken Grotesk">{l}</text>' for l in (1, 3, 5))
    axes, lbls, dots = "", "", ""
    for i, k in enumerate(keys):
        x, y = pt(i, 5)
        axes += f'<line x1="{C}" y1="{C}" x2="{x:.1f}" y2="{y:.1f}" stroke="rgba(61,39,25,.14)"/>'
        lx, ly = pt(i, 6.35)
        lbls += (f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="10" '
                 f'fill="#5C4A3A" font-family="Hanken Grotesk" font-weight="600">{_e(labels[k])}</text>')
        vx, vy = pt(i, float(charts[k]))
        dots += f'<circle cx="{vx:.1f}" cy="{vy:.1f}" r="3.4" fill="#A8492A" stroke="#FBF6EB" stroke-width="1.4"/>'
    vals = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, float(charts[k])) for i, k in enumerate(keys)))
    return (f'<svg viewBox="0 0 220 220" class="radar">{grid}{axes}'
            f'<polygon points="{vals}" fill="rgba(168,73,42,.16)" stroke="#A8492A" stroke-width="2"/>'
            f'{dots}{lvls}{lbls}</svg>')


def _chips(items: list, table: dict) -> str:
    return "".join(f'<span class="tchip">{_e(table.get(x, x))}</span>' for x in (items or []))


# ---------- chapter pagination ----------
# The page is a fixed box (overflow:hidden), so LENGTH is our responsibility.
# Every block gets a conservative height estimate in px (96dpi ≈ 3.78 px/mm;
# usable content ≈ 256 mm ≈ 967 px; opener and margins subtracted below).
_PAGE_BUDGET = 880          # deliberately below the true ~967px — clip-proof beats tight
_CONT_BUDGET = 940          # continuation pages have a smaller opener
_CHARS_PER_LINE = 92
_LINE_H = 21


def _para_h(text: str) -> int:
    lines = max(1, math.ceil(len(text) / _CHARS_PER_LINE))
    return lines * _LINE_H + 10


def _split_chapter(s: dict, has_chart: bool) -> list[list[tuple[str, object]]]:
    """One chapter → 1..n pages of (kind, payload) blocks. Nothing is dropped:
    the concatenation of all pages' paragraphs is exactly the chapter body."""
    blocks: list[tuple[str, object, int]] = []
    if has_chart:
        blocks.append(("chart", None, 130))
    for par in (s.get("body") or "").split("\n"):
        if par.strip():
            blocks.append(("p", par.strip(), _para_h(par.strip())))
    sci = (s.get("science") or "").strip()
    if sci:
        blocks.append(("sci", sci, _para_h(sci) + 56))
    acts = s.get("actions") or []
    if acts:
        blocks.append(("act", acts, len(acts) * 26 + 52))
    pages: list[list[tuple[str, object]]] = [[]]
    used = 190                                # chapter opener on page 1
    budget = _PAGE_BUDGET
    for kind, payload, h in blocks:
        if used + h > budget and pages[-1]:
            pages.append([])
            used = 90                          # slimmer continuation opener
            budget = _CONT_BUDGET
        pages[-1].append((kind, payload))
        used += h
    return pages


# ---------- main ----------
def build_html(client_name: str, sections: list[dict], charts: dict | None = None,
               date: str | None = None, language: str = "en",
               report: dict | None = None, profile: dict | None = None) -> str:
    lang = _norm_lang(language)
    L = _L[lang]
    co = cfg.company()
    charts = charts or {}
    report = report or {}
    profile = profile or {}
    date = date or _dt.date.today().strftime("%d.%m.%Y" if lang == "de" else "%d %b %Y")
    seal = _seal_b64()
    wm = _b64(_MASTERS / "seal-gold-watermark-1200.png")
    qr = _b64(_MASTERS / "qr-website-1480.png")
    first = _e((client_name or "").split(" ")[0] or "—")
    owner = _e(co.get("owner", "Dr. rer. nat. Desiree Gruber"))
    brand = _e(co.get("brand", "Auralis Natura"))
    contact = _e(f'{co.get("email","")} · {co.get("phone","")} · {co.get("web","")}')
    accents = ["#A8492A", "#AD7A32", "#927B4A", "#3D2719", "#8A4A2A", "#5C4A3A"]

    pages: list[str] = []
    pageno = [0]

    def page(cls: str, inner: str) -> None:
        pageno[0] += 1
        pages.append(f'<section class="page {cls}"><div class="pin">{inner}</div>'
                     f'<div class="pfoot"><span>{brand} · {_e(L["kicker"])}</span>'
                     f'<span>{_e(L["page"])} {pageno[0]:02d}</span></div></section>')

    wm_img = (f'<img class="wm" src="data:image/png;base64,{wm}" alt="">') if wm else ""

    # ── cover ──
    def _page_cover():
        page("cover", f'''{wm_img}
      <div class="c-in">
      <img class="seal" src="data:image/png;base64,{seal}" alt="">
      <div class="kick">{_e(L["kicker"])}</div>
      <div class="rule"></div>
      <h1>{_e(L["for"])}<br><em>{_e(client_name or "—")}</em></h1>
      <div class="c-meta"><span>{_e(date)}</span><span class="sep"></span><span>{owner}</span>
      <span class="sep"></span><span>{brand} · Holistic Health</span></div></div>''')

    # ── letter + legend ──
    def _page_letter():
        letter = "".join(f"<p>{_e(p)}</p>" for p in L["letter"])
        legend = "".join(f'<div class="lg"><span class="dot dot-{c}"></span>{_e(t)}</div>'
                         for c, t in L["legend"])
        page("", f'''
      <span class="fig">{_e(L["letter_h"])}</span><h2 class="ph">{_e(L["letter_h"])}</h2>
      <div class="letter"><p class="salut">{first},</p>{letter}
      <p class="sign">{_e(L["close_sign"])}<br><span class="signname">Desiree</span></p></div>
      <div class="legendbox"><div class="boxcap">{_e(L["legend_h"])}</div>{legend}</div>''')

    # ── chapters (pre-split so the TOC can carry真 page numbers) ──
    ch_pages: list[tuple[int, str, list]] = []      # (chapter idx, cls, blocks)
    for i, s in enumerate(sections):
        has_chart = bool(s.get("key") == "what_were_seeing" and charts)
        for pi, blocks in enumerate(_split_chapter(s, has_chart)):
            ch_pages.append((i, "cont" if pi else "first", blocks))

    toc_page_no = 3                                  # cover, letter, TOC
    dash_page_no = toc_page_no + 1
    ch_start = dash_page_no + 1
    ch_first_page: dict[int, int] = {}
    for n, (i, cls, _b2) in enumerate(ch_pages):
        if cls == "first":
            ch_first_page[i] = ch_start + n
    week_page_no = ch_start + len(ch_pages)
    habit_page_no = week_page_no + 1
    close_page_no = habit_page_no + 1

    # ── TOC ──
    def _page_toc():
        rows = f'''<div class="trow"><span class="tn">·</span><span class="tt">{_e(L["toc_fixed"][0])}</span>
          <span class="dots"></span><span class="tp">02</span></div>
          <div class="trow"><span class="tn">·</span><span class="tt">{_e(L["toc_fixed"][1])}</span>
          <span class="dots"></span><span class="tp">{dash_page_no:02d}</span></div>'''
        for i, s in enumerate(sections):
            rows += (f'<div class="trow ch"><span class="tn" style="color:{accents[i % 6]}">{i + 1:02d}</span>'
                     f'<span class="tt">{_e(s.get("title"))}</span><span class="dots"></span>'
                     f'<span class="tp">{ch_first_page.get(i, 0):02d}</span></div>')
        for title, no in ((L["toc_fixed"][2], week_page_no), (L["toc_fixed"][3], habit_page_no),
                          (L["toc_fixed"][4], close_page_no)):
            rows += (f'<div class="trow"><span class="tn">·</span><span class="tt">{_e(title)}</span>'
                     f'<span class="dots"></span><span class="tp">{no:02d}</span></div>')
        page("", f'''
      <span class="fig">{_e(L["toc_h"])}</span><h2 class="ph">{_e(L["toc_h"])}</h2>
      <p class="psub">{_e(L["toc_sub"])}</p><div class="toc">{rows}</div>''')

    # ── dashboard ──
    def _page_dashboard():
        prios = (report.get("priorities") or [])[:3]
        prio_cards = "".join(
            f'<div class="pcard"><div class="pnum">{i+1}</div><div><b>{_e(p.get("title"))}</b>'
            f'<div class="pwhy">{_e(p.get("why"))}</div></div></div>'
            for i, p in enumerate(prios))
        page("", f'''
      <span class="fig">{_e(L["glance_h"])}</span><h2 class="ph">{_e(L["glance_h"])}</h2>
      <p class="psub">{_e(L["glance_sub"])}</p>
      <div class="dash2">
        <div class="dcell"><div class="boxcap">{_e(L["balance"])}</div>{_radar(charts, lang)}</div>
        <div class="dcell"><div class="boxcap">{_e(L["ratings"])} <span class="mini">{_e(L["scale_note"])}</span></div>
          {_bars(charts, lang)}
          <div class="boxcap" style="margin-top:14px">{_e(L["themes"])}</div>
          <div>{_chips(profile.get("symptoms"), _SYM_LABELS.get(lang, _SYM_LABELS["en"]))}</div>
        </div>
      </div>
      <div class="boxcap" style="margin-top:16px">{_e(L["prio_h"])}</div>
      <div class="prow">{prio_cards}</div>''')

    # ── one chapter page ──
    def _page_chapter(i: int, cls: str, blocks: list) -> None:
        s = sections[i]
        accent = accents[i % 6]
        guard = s.get("key") == "when_to_see_a_doctor"
        parts = []
        for kind, payload in blocks:
            if kind == "chart":
                parts.append(f'<div class="chmini">{_bars(charts, lang)}</div>')
            elif kind == "p":
                parts.append(f"<p>{_e(payload)}</p>")
            elif kind == "sci":
                parts.append(f'<div class="scibox"><div class="boxcap">{_e(L["science_h"])}</div>'
                             f'<p>{_e(payload)}</p></div>')
            elif kind == "act":
                parts.append(f'<div class="actbox"><div class="boxcap">{_e(L["actions_h"])}</div>' +
                             "".join(f'<div class="act"><span class="cb"></span>{_e(a)}</div>'
                                     for a in payload) + "</div>")
        if cls == "first":
            opener = (f'<div class="chop"><span class="chnum" style="color:{accent}">{i + 1:02d}</span>'
                      f'<div><span class="fig" style="color:{accent}">{_e(L["chapter"])} {i + 1:02d}</span>'
                      f'<h2 class="ph">{_e(s.get("title"))}</h2></div></div>'
                      f'<div class="chrule" style="background:{accent}"></div>')
        else:
            opener = (f'<span class="fig" style="color:{accent}">{_e(L["chapter"])} {i + 1:02d} — '
                      f'{_e(L["cont"])}</span><div class="chrule slim" style="background:{accent}"></div>')
        page("guardpage" if guard else "", opener + "".join(parts))

    # ── weekly plan ──
    def _page_week():
        prios = (report.get("priorities") or [])[:3]
        week = report.get("weekly_plan") or {}
        wk_keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        rows = "".join(f'<tr><td class="wd">{_e(L["days"][i])}</td><td>{_e(week.get(k, "—"))}</td></tr>'
                       for i, k in enumerate(wk_keys))
        prio_recap = "".join(
            f'<div class="pcard"><div class="pnum">{i+1}</div><div><b>{_e(p.get("title"))}</b>'
            f'<div class="pwhy">{_e(L["first_step"])}: {_e(p.get("first_step"))}</div></div></div>'
            for i, p in enumerate(prios))
        page("", f'''
      <span class="fig">{_e(L["week_h"])}</span><h2 class="ph">{_e(L["week_h"])}</h2>
      <p class="psub">{_e(L["week_sub"])}</p>
      <table class="wtab">{rows}</table>
      <div class="boxcap" style="margin-top:18px">{_e(L["prio_h"])} — {_e(L["first_step"])}</div>
      <div class="prow">{prio_recap}</div>''')

    # ── habit tracker ──
    def _page_tracker():
        habits = (report.get("habits") or [])[:5]
        weeks_html = ""
        for w in range(4):
            head = "".join(f"<th>{d+1}</th>" for d in range(7))
            body_rows = "".join(
                f'<tr><td class="hname">{_e(h)}</td>'
                + "".join('<td><span class="cb"></span></td>' for _ in range(7)) + "</tr>"
                for h in habits)
            weeks_html += (f'<div class="hweek"><div class="boxcap">{_e(L["week_lbl"])} {w+1}</div>'
                           f'<table class="htab"><tr><th></th>{head}</tr>{body_rows}</table></div>')
        page("", f'''
      <span class="fig">{_e(L["habit_h"])}</span><h2 class="ph">{_e(L["habit_h"])}</h2>
      <p class="psub">{_e(L["habit_sub"])}</p>{weeks_html}''')

    # ── closing ──
    def _page_closing():
        qr_html = (f'<div class="qrbox"><img src="data:image/png;base64,{qr}" alt="">'
                   f'<div class="boxcap" style="margin:8px 0 0">{_e(L["qr_cap"])}</div></div>') if qr else ""
        page("cover closing", f'''{wm_img}
      <div class="c-in">
      <img class="seal" src="data:image/png;base64,{seal}" alt="">
      <h2 class="ph" style="text-align:center;border:0">{_e(L["close_h"])}</h2>
      <p class="closep">{_e(L["close"])}</p>
      <p class="sign" style="text-align:center">{_e(L["close_sign"])}<br><span class="signname">Desiree</span></p>
      {qr_html}
      <div class="c-meta" style="margin-top:20px"><span>{owner}</span><span class="sep"></span>
      <span>{brand}</span><span class="sep"></span><span>{contact}</span></div>
      <div class="disc">{_disclaimer(lang)}</div></div>''')

    _page_cover()
    _page_letter()
    _page_toc()
    _page_dashboard()
    for i, cls, blocks in ch_pages:
        _page_chapter(i, cls, blocks)
    _page_week()
    _page_tracker()
    _page_closing()

    return (_TEMPLATE
            .replace("__LANG__", lang)
            .replace("__FONTS__", _font_css())
            .replace("__PAGES__", "".join(pages)))


def to_pdf(html_text: str, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    chrome = _chrome()
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html_text)
        src = f.name
    try:
        if not chrome:
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


# One template, plain token replacement — no str.format, no doubled braces.
_TEMPLATE = """<!doctype html><html lang="__LANG__"><head><meta charset="utf-8">
<style>
__FONTS__
:root{--ink:#281F16;--ink-soft:#5C4A3A;--ink-faint:#75685A;
--forest:#3D2719;--forest-soft:#5A3A22;--forest-deep:#221305;--forest-2:#8A4A2A;
--sage:#927B4A;--sage-soft:#DAC79E;--clay:#A8492A;--clay-deep:#8F3D22;
--gold:#AD7A32;--gold-bright:#D6A84E;--paper:#F5EEE0;--paper-2:#ECE2CE;--cream:#FBF6EB;
--line:rgba(61,39,25,.14);--line-strong:rgba(61,39,25,.26);--gold-hair:rgba(173,122,50,.42);
--ok:#3F7B5A;--okbg:#EEF6EF;--wa:#B0553F;--wabg:#FCEFEC;--go:#6F4F2C;--gobg:#FBF6EC;
--fd:"Fraunces",Georgia,serif;--fb:"Hanken Grotesk",system-ui,sans-serif}
*{box-sizing:border-box;margin:0;padding:0;border-radius:0!important;
  -webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:var(--fb);color:var(--ink);background:#fff;font-size:12.5px;line-height:1.62;-webkit-font-smoothing:antialiased;hyphens:none}
.page{width:210mm;min-height:297mm;position:relative;page-break-after:always;background:#fff;overflow:hidden}
.pin{padding:17mm 16mm 24mm}
.pfoot{position:absolute;left:16mm;right:16mm;bottom:9mm;display:flex;justify-content:space-between;font-size:8.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-faint);border-top:1px solid var(--gold-hair);padding-top:6px}
.fig{font-family:var(--fb);font-size:.62rem;letter-spacing:.24em;text-transform:uppercase;color:var(--ink-faint);font-weight:600}
.ph{font-family:var(--fd);font-weight:420;font-size:1.9rem;color:var(--forest);margin:6px 0 12px;line-height:1.16;letter-spacing:-.01em}
.psub{color:var(--ink-soft);margin-bottom:16px}
p{color:var(--ink-soft);margin:0 0 10px}
/* cover + closing — the quiet pages: paper, hairline, watermark off the edge */
.cover{background:var(--paper)}
.cover .wm{position:absolute;right:-64mm;bottom:-64mm;width:150mm;opacity:.10}
.cover .c-in{position:absolute;inset:12mm;border:1px solid var(--gold-hair);display:flex;flex-direction:column;justify-content:center;text-align:center;padding:0 14mm}
.cover .seal{width:96px;height:96px;margin:0 auto 24px}
.cover .kick{font-size:.68rem;letter-spacing:.3em;text-transform:uppercase;color:var(--clay);font-weight:600}
.cover .rule{width:44px;height:2px;background:var(--gold);margin:16px auto}
.cover h1{font-family:var(--fd);font-weight:420;font-size:2.7rem;line-height:1.14;margin:8px 0 26px;letter-spacing:-.015em}
.cover h1 em{font-style:italic;color:var(--clay)}
.c-meta{display:flex;justify-content:center;align-items:center;gap:12px;flex-wrap:wrap;font-size:.82rem;color:var(--ink-soft)}
.c-meta .sep{width:22px;height:1px;background:var(--gold-hair);display:inline-block}
/* letter */
.letter{background:var(--cream);border:1px solid var(--line);border-top:1px solid var(--gold-hair);padding:26px 30px;margin:12px 0 18px;position:relative}
.letter::before{content:"";position:absolute;left:0;top:0;width:44px;height:2px;background:var(--gold)}
.letter .salut{font-family:var(--fd);font-size:1.3rem;color:var(--ink);margin-bottom:12px}
.sign{margin-top:16px}
.signname{font-family:var(--fd);font-size:1.5rem;color:var(--ink)}
.legendbox{border:1px solid var(--line);padding:14px 18px}
.lg{display:flex;gap:10px;align-items:center;font-size:.85rem;color:var(--ink-soft);margin:5px 0}
.boxcap{font-size:.62rem;letter-spacing:.18em;text-transform:uppercase;color:var(--ink-faint);font-weight:600;margin-bottom:8px}
.boxcap .mini{text-transform:none;letter-spacing:0;font-weight:400}
.dot{display:inline-block;width:9px;height:9px}
.dot-ok{background:var(--ok)}.dot-gold{background:var(--gold)}.dot-warn{background:var(--wa)}
/* toc */
.toc{margin-top:8px;border-top:1px solid var(--line)}
.trow{display:flex;align-items:baseline;gap:12px;padding:11px 2px;border-bottom:1px solid var(--line)}
.trow .tn{font-family:var(--fd);font-size:1.05rem;min-width:30px;color:var(--ink-faint)}
.trow.ch .tt{font-family:var(--fd);font-size:1.05rem;color:var(--ink)}
.trow .tt{color:var(--ink-soft)}
.trow .dots{flex:1;border-bottom:1px dotted var(--line-strong);transform:translateY(-3px)}
.trow .tp{font-variant-numeric:tabular-nums;color:var(--ink-faint);font-size:.85rem}
/* dashboard */
.dash2{display:grid;grid-template-columns:1fr 1.2fr;gap:16px;align-items:start}
.dcell{background:var(--cream);border:1px solid var(--line);padding:16px 18px}
.radar{width:100%;max-width:240px;display:block;margin:0 auto}
.ch-row{display:flex;align-items:center;gap:8px;margin:8px 0;font-size:11.5px}
.ch-l{width:64px;color:var(--ink-soft)}
.ch-track{flex:1;height:8px;background:var(--paper-2);position:relative}
.ch-track i{position:absolute;top:0;bottom:0;width:1px;background:rgba(61,39,25,.12)}
.ch-fill{position:absolute;left:0;top:0;bottom:0}
.st-ok{background:var(--sage)}.st-gold{background:var(--gold)}.st-warn{background:var(--clay)}
.ch-v{width:30px;text-align:right;font-weight:600;font-variant-numeric:tabular-nums}
.ch-v em{font-style:normal;color:var(--ink-faint);font-weight:400;font-size:.72rem}
.tchip{display:inline-block;font-size:.74rem;background:#fff;border:1px solid var(--line);padding:2px 10px;margin:2px 3px 2px 0}
.prow{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.pcard{display:flex;gap:10px;background:#fff;border:1px solid var(--line);border-top:2px solid var(--clay);padding:12px 13px;font-size:.82rem}
.pcard .pnum{font-family:var(--fd);font-size:1.5rem;color:var(--gold);line-height:1}
.pcard .pwhy{color:var(--ink-faint);font-size:.76rem;margin-top:3px}
/* chapters — editorial openers */
.chop{display:flex;gap:16px;align-items:flex-start}
.chnum{font-family:var(--fd);font-size:4.4rem;line-height:.9;opacity:.22;font-weight:500;letter-spacing:-.02em}
.chrule{width:56px;height:2px;margin:10px 0 16px}
.chrule.slim{margin:8px 0 14px;width:36px}
.scibox{background:var(--gobg);border:1px solid var(--line);border-left:3px solid var(--gold);padding:12px 16px;margin:14px 0}
.scibox p{margin:0;font-size:.85rem}
.actbox{background:var(--okbg);border:1px solid var(--line);border-left:3px solid var(--ok);padding:12px 16px;margin:14px 0}
.act{display:flex;gap:10px;align-items:flex-start;margin:6px 0;font-size:.88rem;color:var(--ink-soft)}
.cb{display:inline-block;width:13px;height:13px;border:1.5px solid var(--sage);background:#fff;flex:0 0 auto;margin-top:3px}
.chmini{background:var(--cream);border:1px solid var(--line);padding:12px 16px;margin:0 0 14px}
.guardpage{background:linear-gradient(165deg,#5A3A22 0%,#3D2719 55%,#221305 100%)}
.guardpage .ph{color:#F6EFE3}
.guardpage .fig,.guardpage .chnum{color:#D6A84E!important}
.guardpage .chrule{background:#D6A84E!important}
.guardpage p{color:#E4DCCB}
.guardpage .scibox,.guardpage .actbox{background:rgba(251,246,235,.07);border-color:rgba(214,168,78,.35)}
.guardpage .scibox p,.guardpage .act{color:#E4DCCB}
.guardpage .boxcap{color:#D6A84E}
.guardpage .cb{border-color:#D6A84E;background:transparent}
.guardpage .pfoot{color:rgba(237,231,214,.55);border-color:rgba(214,168,78,.3)}
/* weekly */
.wtab{width:100%;border-collapse:collapse;background:var(--cream);border:1px solid var(--line)}
.wtab td{padding:9px 14px;border-bottom:1px solid var(--line);font-size:.9rem;color:var(--ink-soft)}
.wtab .wd{width:110px;font-weight:500;color:var(--forest);font-family:var(--fd);font-size:.95rem}
/* habits */
.hweek{margin-bottom:14px}
.htab{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line)}
.htab th{font-size:.6rem;letter-spacing:.1em;color:var(--ink-faint);padding:5px;border-bottom:1px solid var(--line);text-align:center}
.htab td{padding:6px 5px;border-bottom:1px solid var(--line);text-align:center}
.htab .hname{text-align:left;font-size:.8rem;color:var(--ink-soft);width:34%}
/* closing */
.closing .c-in{justify-content:center}
.closing .seal{width:80px;height:80px;margin:0 auto 18px}
.closep{max-width:52ch;margin:0 auto 14px;text-align:center;font-size:1rem}
.qrbox{text-align:center;margin-top:10px}
.qrbox img{width:88px;height:88px;border:1px solid var(--line);padding:6px;background:#fff}
.disc{margin-top:20px;font-size:8.6px;color:var(--ink-faint);line-height:1.6;text-align:left;border-top:1px solid var(--line);padding-top:10px}
@media print{@page{size:A4;margin:0} .page{margin:0}}
</style></head><body>
__PAGES__
</body></html>"""
