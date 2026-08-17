"""Render an approved report into the v2 premium 12-page HTML → PDF.

The founder's redesign bundle ships one finished, worked-sample document per
language (lib/report_v2/{de,en,es}.html). That file IS the design authority:
its <head> (fonts inlined, tokens, print CSS) is used verbatim, and every
piece of fixed chrome — the letter, the legend, the reading key, the box
captions, the closing page, the disclaimer — is HARVESTED from it at load
time, so the approved wording ships letter-for-letter in all three languages.
The data-driven pages (TOC, dashboard, chapters, weekly plan, tracker) are
generated here in the template's own markup vocabulary.

Data honesty: every visual is built from data that actually exists — the
radar and scale rows from the intake's real self-ratings, the plan bars from
the report's priorities and habits, the weekly page from weekly_plan, the
tracker from habits. The sample's day-curve and lever charts have no data
source in the pipeline and are therefore not rendered.

Long chapters never clip: _split_chapter() budgets content in Python and
flows it onto localized continuation pages (deterministic, testable offline).

Contracts that outlive redesigns: _CHROME_CANDIDATES / _chrome() (preflight
reaches in), to_pdf()'s html-fallback, build_html()'s signature, the six
agent section titles verbatim in the output, _split_chapter's block protocol.
"""
from __future__ import annotations
import base64, html, math, os, re, subprocess, tempfile, shutil, datetime as _dt
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


_FONT_DIR = cfg.ROOT.parent / "design-system" / "assets" / "fonts"
_CACHE: dict = {}


def _font_css() -> str:
    """Brand fonts as data: URIs (kept public — tools/build_social_guide.py)."""
    if "fonts" not in _CACHE:
        css = []
        faces = [
            ("Fraunces", 400, "normal", "fraunces-normal-300_600-latin.woff2"),
            ("Fraunces", 400, "italic", "fraunces-italic-300_500-latin.woff2"),
            ("Hanken Grotesk", 400, "normal", "hanken-grotesk-normal-300_700-latin.woff2"),
        ]
        for fam, w, style, fn in faces:
            p = _FONT_DIR / fn
            if p.exists():
                css.append(
                    f"@font-face{{font-family:'{fam}';font-weight:300 700;"
                    f"font-style:{style};font-display:block;"
                    f"src:url(data:font/woff2;base64,{_b64(p)}) format('woff2')}}")
        _CACHE["fonts"] = "\n".join(css)
    return _CACHE["fonts"]


def _norm_lang(language: str) -> str:
    l = (language or "").lower()
    return "de" if l.startswith("de") else "es" if l.startswith("es") else "en"


def _e(x) -> str:
    return html.escape(str(x or ""))


# ---------- localised strings the template cannot carry (data-dependent) ----------
_L = {
    "de": {"cont": "Fortsetzung", "first_step": "Erster Schritt",
           "days": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
           "glance_sub": "Deine Selbsteinschätzung aus dem Aufnahmebogen und die Hebel, "
                         "an denen wir arbeiten — alles Wichtige auf einer Seite.",
           "week_sub": "Ein sanfter Fokus pro Tag — kein Programm, ein Rhythmus.",
           "habit_sub": "Hake ab, was dir gelungen ist — Fortschritt zählt, nicht Perfektion. "
                        "Woche für Woche.",
           "build": "aktiv aufbauen", "hold": "halten & beobachten"},
    "en": {"cont": "continued", "first_step": "First step",
           "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
           "glance_sub": "Your self-ratings from the intake and the levers we will work on — "
                         "everything important on one page.",
           "week_sub": "One gentle focus per day — not a programme, a rhythm.",
           "habit_sub": "Tick what worked — progress counts, not perfection. Week by week.",
           "build": "actively building", "hold": "hold & observe"},
    "es": {"cont": "continuación", "first_step": "Primer paso",
           "days": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
           "glance_sub": "Tu autoevaluación del cuestionario y las palancas en las que "
                         "trabajaremos — lo importante en una página.",
           "week_sub": "Un foco suave por día — no un programa, un ritmo.",
           "habit_sub": "Marca lo que salió — cuenta el progreso, no la perfección. Semana a semana.",
           "build": "en construcción activa", "hold": "mantener y observar"},
}

_CH_LABELS = {
    "en": {"energy": "Energy", "sleep": "Sleep", "stress": "Stress balance", "digestion": "Digestion",
           "mood": "Mood", "movement": "Movement"},
    "de": {"energy": "Energie", "sleep": "Schlaf", "stress": "Stressbalance", "digestion": "Verdauung",
           "mood": "Stimmung", "movement": "Bewegung"},
    "es": {"energy": "Energía", "sleep": "Sueño", "stress": "Equilibrio del estrés", "digestion": "Digestión",
           "mood": "Ánimo", "movement": "Movimiento"},
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
_CH_ORDER = ["energy", "sleep", "stress", "digestion", "mood", "movement"]


# ---------- the v2 frame: head + harvested chrome per language ----------
_V2_DIR = Path(__file__).resolve().parent / "report_v2"


def _between(s: str, a: str, b: str, start: int = 0) -> str:
    i = s.index(a, start) + len(a)
    return s[i:s.index(b, i)]


def _frame(lang: str) -> dict:
    """Parse the language's v2 sample once; cache head + chrome + strings."""
    key = f"frame:{lang}"
    if key in _CACHE:
        return _CACHE[key]
    doc = (_V2_DIR / f"{lang}.html").read_text(encoding="utf-8")
    head = doc[:doc.index("<body>") + len("<body>")]
    body = doc[doc.index("<body>"):]
    pages = body.split('<section class="page')
    P = ["<section class=\"page" + p for p in pages[1:]]  # 12 sample pages
    if len(P) < 12:
        raise AssertionError(f"report frame {lang}: expected 12 pages, got {len(P)}")
    cov, let, toc, dash, ch1, plan, week, track, close = \
        P[0], P[1], P[2], P[3], P[4], P[7], P[9], P[10], P[11]

    caps = re.findall(r'<div class="cap"[^>]*>(.*?)</div>', dash)
    def cap_split(c):
        parts = c.split('<span class="mini">')
        return parts[0].strip(), (parts[1].split("</span>")[0].strip() if len(parts) > 1 else "")

    radar_cap, radar_mini = cap_split(caps[0])       # "· 6 Bereiche" → keep the unit word
    scales_cap, scales_mini = cap_split(caps[1])
    themes_cap, _ = cap_split(caps[2])
    prio_cap, _ = cap_split(caps[-1])
    radar_unit = radar_mini.replace("·", "").strip()
    radar_unit = re.sub(r"\d+\s*", "", radar_unit).strip()

    legend = _between(let, '<div class="legend"', '<div class="pfoot"')
    legend = '<div class="legend"' + legend.rstrip()
    if legend.endswith("</div></div>"):
        legend = legend[:-len("</div>")]

    fr = {
        "head": head,
        "wm": _between(cov, '<img class="wm" src="', '"'),
        "seal": _between(cov, '<img class="seal" src="', '"'),
        "ck": _between(cov, '<div class="ck">', "</div>"),
        "h1_for": _between(cov, "<h1>", "<br>"),
        "medal": let[let.index('<div class="medal">'):let.index('<div class="kick">')].rstrip(),
        "letter_kick": _between(let, '<div class="kick"><i></i><span>', "</span>"),
        "letter_ph": _between(let, '<h2 class="ph">', "</h2>"),
        "letter": let[let.index('<div class="letter"'):let.index('<div class="legend"')],
        "legend": legend,
        "letter_wm": _between(let, '<img class="wm" src="', '"'),
        "toc_ph": _between(toc, '<h2 class="ph">', "</h2>"),
        "toc_sub": _between(toc, '<p class="psub">', "</p>"),
        "toc_fixed": re.findall(
            r'<div class="trow"><span class="tn">·</span><span class="tt">(.*?)</span>', toc),
        "glance_ph": _between(dash, '<h2 class="ph">', "</h2>"),
        "readrow": dash[dash.index('<div class="readrow">'):dash.index('<div class="dash"')],
        "radar_cap": radar_cap, "radar_unit": radar_unit,
        "scales_cap": scales_cap, "scales_mini": scales_mini,
        "themes_cap": themes_cap, "prio_cap": prio_cap,
        "chapter_lbl": _between(ch1, '<div class="chside">', "</div>").rsplit(" ", 1)[0],
        "sci_cap": _between(ch1, '<div class="sci"><div class="cap">', "</div>"),
        "acts_cap": _between(ch1, '<div class="acts"><div class="cap">', "</div>"),
        "ghd": '<div class="ghd">' + _between(plan, '<div class="ghd">', "</div>") + "</div>",
        "week_ph": _between(week, '<h2 class="ph">', "</h2>"),
        "habit_ph": _between(track, '<h2 class="ph">', "</h2>"),
        "week_lbl": _between(track, '<div class="whd"><b>', "</b>").rsplit(" ", 1)[0],
        "days_lbl": _between(track, '<div class="whd"><b>', "</span>").split("<span>")[1],
        "closing": close[close.index('<img class="seal"'):close.index('<div class="contact">')],
        "disc": _between(close, '<div class="disc">', "</div>"),
        "pfoot_left": _between(let, '<div class="pfoot"><span>', "</span>"),
        "page_lbl": re.search(r'<span>(\S+) \d{2}</span></div></section>', let).group(1),
        "fs_lbl": (m.group(1) if (m := re.search(r'<span class="fs">([^:<]+):', dash))
                   else _L[lang]["first_step"]),
    }
    _CACHE[key] = fr
    return fr


# ---------- visual builders (v2 vocabulary) ----------
def _status(k: str, v: float) -> str:
    """Ampel. EVERY scale reads higher-is-better — including stress, which is
    asked as "Stressbalance" (1 = low balance … 5 = very good), the wording the
    founder-approved v2 artwork uses. Until 2026-08-17 this function inverted
    stress while the iOS intake already asked for balance, so an app-submitted
    intake showed good balance as a red priority. One uniform reading fixes it."""
    return "ok" if v >= 4 else ("gold" if v >= 3 else "warn")


_ST_CLASS = {"ok": "hi", "gold": "", "warn": "low"}
_ST_COLOR = {"ok": "#3A4A2C", "gold": "#927B4A", "warn": "#A8492A"}


def _chart_keys(charts: dict) -> list:
    keys = [k for k in _CH_ORDER if k in charts]
    return keys + [k for k in charts if k not in keys]


def _scales(charts: dict, lang: str) -> str:
    labels = _CH_LABELS.get(lang, _CH_LABELS["en"])
    rows = []
    for k in _chart_keys(charts):
        v = max(1, min(5, int(float(charts[k]))))
        st = _ST_CLASS[_status(k, v)]
        segs = '<i class="on"></i>' * v + "<i></i>" * (5 - v)
        rows.append(f'<div class="scale {st}"><span class="sl">{_e(labels.get(k, k))}</span>'
                    f'<span class="segs">{segs}</span><span class="sv"><b>{v}</b>/5</span></div>')
    return "".join(rows)


def _radar(charts: dict, lang: str) -> str:
    keys = _chart_keys(charts)
    if len(keys) < 3:
        return ""
    labels = _CH_LABELS.get(lang, _CH_LABELS["en"])
    C, R, n = 140.0, 124.0, len(keys)

    def pt(i, val):
        a = -math.pi / 2 + i * 2 * math.pi / n
        r = R * val / 5
        return (C + r * math.cos(a), C + r * math.sin(a))

    grid = ""
    for lvl in (1, 2, 3, 4, 5):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, lvl) for i in range(n)))
        grid += (f'<polygon points="{pts}" fill="none" '
                 f'stroke="rgba(61,39,25,{".28" if lvl == 5 else ".12"})" stroke-width="1"/>')
    axes = "".join(
        f'<line x1="{C}" y1="{C}" x2="{pt(i,5)[0]:.1f}" y2="{pt(i,5)[1]:.1f}" '
        f'stroke="rgba(61,39,25,.14)" stroke-width="1"/>' for i in range(n))
    vals = " ".join(f"{x:.1f},{y:.1f}" for x, y in
                    (pt(i, float(charts[k])) for i, k in enumerate(keys)))
    marks, lbls = "", ""
    for i, k in enumerate(keys):
        v = float(charts[k])
        col = _ST_COLOR[_status(k, v)]
        mx, my = pt(i, v)
        marks += (f'<rect x="{mx - 4:.1f}" y="{my - 4:.1f}" width="8" height="8" '
                  f'transform="rotate(45 {mx:.1f} {my:.1f})" fill="{col}"/>')
        a = -math.pi / 2 + i * 2 * math.pi / n
        lx, ly = C + (R + 21) * math.cos(a), C + (R + 21) * math.sin(a)
        anchor = "middle" if abs(math.cos(a)) < .35 else ("start" if math.cos(a) > 0 else "end")
        ly += 4 if math.sin(a) > .35 else (-6 if math.sin(a) < -.35 else 4)
        lbls += (f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
                 f'font-family="Hanken Grotesk" font-size="11.5" font-weight="600" '
                 f'letter-spacing="1" fill="#5C4A3A">{_e(labels.get(k, k)).upper()} '
                 f'<tspan font-weight="700" fill="{col}">· {v:.0f}</tspan></text>')
    return (f'<svg class="radar" viewBox="-112 -12 504 310">{grid}{axes}'
            f'<polygon points="{vals}" fill="rgba(58,74,44,.14)" stroke="#3A4A2C" '
            f'stroke-width="2.2"/>{marks}{lbls}</svg>')


def _gantt(prios: list, habits: list, fr: dict, lang: str) -> str:
    """Four-week plan bars — honestly derived: priorities are actively built in
    weeks 1–2 and held in 3–4; habits are held throughout. No invented dates."""
    rows, colors = "", ["b1", "b2", "b3"]

    def cells(strong_weeks: int, cls: str, soft_all: bool = False) -> str:
        out = ""
        for w in range(4):
            soft = soft_all or w >= strong_weeks
            edge = ("right:-1px;" if w == 0 else "left:-1px;" if w == 3 else "left:-1px;right:-1px;")
            out += (f'<span class="gc"><span class="bar {cls}{" soft" if soft else ""}" '
                    f'style="{edge}"></span></span>')
        return out

    for i, p in enumerate(prios[:3]):
        sub = _e(p.get("first_step") or p.get("why") or "")
        rows += (f'<div class="grow"><span class="gl"><b>{_e(p.get("title"))}</b>'
                 f'<span>{sub}</span></span>{cells(2, colors[i % 3])}</div>')
    for h in habits[:3]:
        rows += (f'<div class="grow"><span class="gl"><b>{_e(h)}</b><span></span></span>'
                 f'{cells(0, "b3", soft_all=True)}</div>')
    if not rows:
        return ""
    L = _L[lang]
    leg = (f'<div class="gleg"><span><i style="background:var(--clay)"></i>{_e(L["build"])}</span>'
           f'<span><i style="opacity:.38;background:var(--forest)"></i>{_e(L["hold"])}</span></div>')
    return f'<div class="gantt">{fr["ghd"]}{rows}{leg}</div>'


def _themes(items: list, lang: str) -> str:
    table = _SYM_LABELS.get(lang, _SYM_LABELS["en"])
    return "".join(f'<span class="chip">{_e(table.get(x, x))}</span>' for x in (items or []))


# ---------- chapter pagination ----------
# The page is a fixed box (overflow:hidden), so LENGTH is our responsibility.
# The v2 chapter column is ~144mm wide (24mm number rail + 8mm gap), so lines
# are shorter and taller than the old full-width layout; the budgets sit well
# below the true ~975px so estimate drift can never clip.
_PAGE_BUDGET = 780
_CONT_BUDGET = 840
_CHARS_PER_LINE = 78
_LINE_H = 23


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


def _block_h(kind: str, payload) -> int:
    if kind == "p":
        return _para_h(payload)
    if kind == "sci":
        return _para_h(payload) + 56
    if kind == "act":
        return len(payload) * 26 + 52
    if kind == "chart":
        return 130
    if kind == "gantt":
        prios, habits = payload
        return 60 + 44 * (min(len(prios), 3) + min(len(habits), 3)) + 34
    if kind == "med":
        return _para_h(payload[1]) + 80
    return 0


def _attach_extra(pages: list, kind: str, payload) -> None:
    """Append a build-level block (gantt, medbox) to a chapter's pages,
    spilling onto a fresh continuation page when the budget says so."""
    used = 190 if len(pages) == 1 else 90
    for k, p in pages[-1]:
        used += _block_h(k, p)
    budget = _PAGE_BUDGET if len(pages) == 1 else _CONT_BUDGET
    if used + _block_h(kind, payload) > budget and pages[-1]:
        pages.append([(kind, payload)])
    else:
        pages[-1].append((kind, payload))


# ---------- main ----------
def build_html(client_name: str, sections: list[dict], charts: dict | None = None,
               date: str | None = None, language: str = "en",
               report: dict | None = None, profile: dict | None = None) -> str:
    lang = _norm_lang(language)
    L = _L[lang]
    fr = _frame(lang)
    co = cfg.company()
    charts = charts or {}
    report = report or {}
    profile = profile or {}
    date = date or _dt.date.today().strftime("%d.%m.%Y" if lang == "de" else "%d %b %Y")
    name = _e(client_name or "—")
    first = _e((client_name or "").split(" ")[0] or "—")
    owner = _e(co.get("owner", "Dr. rer. nat. Desiree Gruber"))
    brand = _e(co.get("brand", "Auralis Natura"))

    pages: list[str] = []
    pageno = [0]

    def page(cls: str, inner: str, pre: str = "") -> None:
        pageno[0] += 1
        pf = (f'<div class="pfoot"><span>{fr["pfoot_left"]}</span><span>{name}</span>'
              f'<span>{fr["page_lbl"]} {pageno[0]:02d}</span></div>')
        pages.append(f'<section class="page {cls}">{pre}<div class="pin">{inner}</div>{pf}</section>')

    def kick(text: str) -> str:
        return f'<div class="kick"><i></i><span>{text}</span></div>'

    # ── cover (no footer, like the sample) ──
    pageno[0] += 1
    pages.append(
        f'<section class="page cover"><div class="frame"></div>'
        f'<img class="wm" src="{fr["wm"]}" alt="">'
        f'<div class="pin"><img class="seal" src="{fr["seal"]}" alt="{brand}">'
        f'<div class="ck">{fr["ck"]}</div><div class="rule"></div>'
        f'<h1>{fr["h1_for"]}<br><em>{name}</em></h1>'
        f'<div class="cm"><span>{_e(date)}</span><i></i><span>{owner}</span><i></i>'
        f'<span>{brand} · Holistic Health</span></div></div></section>')

    # ── letter + legend (chrome harvested; only the salutation is ours) ──
    letter = fr["letter"]
    if ">Elena,<" not in letter:
        raise AssertionError("report frame drift: letter salutation anchor missing")
    letter = letter.replace(">Elena,<", f">{first},<")
    page("", f'{fr["medal"]}{kick(fr["letter_kick"])}<h2 class="ph">{fr["letter_ph"]}</h2>'
             f'{letter}{fr["legend"]}',
         pre=f'<img class="wm" src="{fr["letter_wm"]}" alt="">')

    # ── chapters pre-split so the TOC carries real page numbers ──
    doctor = next((s for s in sections if s.get("key") == "when_to_see_a_doctor"), None)
    chapters = [s for s in sections if s is not doctor]
    if not chapters:                       # degenerate: only the doctor section
        chapters, doctor = list(sections), None

    ch_pages: list[list] = []
    for i, s in enumerate(chapters):
        has_chart = bool(s.get("key") == "what_were_seeing" and charts)
        pg = _split_chapter(s, has_chart)
        if s.get("key") == "your_plan" and (report.get("priorities") or report.get("habits")):
            _attach_extra(pg, "gantt",
                          (report.get("priorities") or [], report.get("habits") or []))
        if doctor and i == len(chapters) - 1:
            body = (doctor.get("body") or "").strip()
            _attach_extra(pg, "med", (doctor.get("title") or "", body))
        ch_pages.append(pg)

    toc_no, dash_no = 3, 4
    ch_start = dash_no + 1
    ch_first: dict[int, int] = {}
    n = ch_start
    for i, pg in enumerate(ch_pages):
        ch_first[i] = n
        n += len(pg)
    week_no, habit_no, close_no = n, n + 1, n + 2

    # ── TOC ──
    tf = fr["toc_fixed"]
    def trow(t, no, num="·", cls=""):
        return (f'<div class="trow{cls}"><span class="tn">{num}</span><span class="tt">{t}</span>'
                f'<span class="dots"></span><span class="tp">{no:02d}</span></div>')
    rows = trow(tf[0], 2) + trow(tf[1], dash_no)
    for i, s in enumerate(chapters):
        rows += trow(_e(s.get("title")), ch_first[i], f"{i + 1:02d}", " chp")
    for t, no in ((tf[2], week_no), (tf[3], habit_no), (tf[4], close_no)):
        rows += trow(t, no)
    page("", f'{kick(fr["toc_ph"])}<h2 class="ph">{fr["toc_ph"]}</h2>'
             f'<p class="psub">{fr["toc_sub"]}</p><div class="toc">{rows}</div>')

    # ── dashboard: readrow, radar + scales, priorities — all from real data ──
    prios = (report.get("priorities") or [])[:3]
    radar = _radar(charts, lang)
    scales = _scales(charts, lang)
    cells = ""
    if radar:
        cells += (f'<div class="dcell"><div class="cap">{fr["radar_cap"]} '
                  f'<span class="mini">· {len(_chart_keys(charts))} {fr["radar_unit"]}</span></div>{radar}</div>')
    if scales:
        themes = _themes(profile.get("symptoms"), lang)
        th = (f'<div class="cap" style="margin:3.4mm 0 1.8mm">{fr["themes_cap"]}</div>'
              f'<div class="themes">{themes}</div>') if themes else ""
        cells += (f'<div class="dcell"><div class="cap">{fr["scales_cap"]} '
                  f'<span class="mini">{fr["scales_mini"]}</span></div>'
                  f'<div class="scales" style="margin-top:4mm">{scales}</div>{th}</div>')
    dash = f'<div class="dash" style="margin-bottom:3.4mm">{cells}</div>' if cells else ""
    pr = "".join(
        f'<div class="pr"><span class="pn">{i + 1}</span><span><b>{_e(p.get("title"))}</b>'
        f'<span>{_e(p.get("why"))}</span>'
        f'<span class="fs">{fr["fs_lbl"]}: {_e(p.get("first_step"))}</span></span></div>'
        for i, p in enumerate(prios))
    prio = (f'<div class="dcell"><div class="cap">{fr["prio_cap"]}</div>'
            f'<div class="prio3">{pr}</div></div>') if pr else ""
    page("", f'{kick(fr["glance_ph"])}<h2 class="ph">{fr["glance_ph"]}</h2>'
             f'<p class="psub" style="margin-bottom:2.4mm">{_e(L["glance_sub"])}</p>'
             f'{fr["readrow"]}{dash}{prio}')

    # ── chapters ──
    def act_row(a) -> str:
        a = str(a)
        if " — " in a:
            b, _, ad = a.partition(" — ")
            detail = f'<span class="ad">{_e(ad)}</span>'
        else:
            b, detail = a, ""
        return (f'<div class="act"><span class="cb"></span><span>'
                f'<b style="font-weight:700;color:inherit">{_e(b)}</b>{detail}</span></div>')

    for i, pg in enumerate(ch_pages):
        s = chapters[i]
        num = f"{i + 1:02d}"
        for pi, blocks in enumerate(pg):
            # the design places the viz after the prose, not above it
            if any(k == "chart" for k, _ in blocks):
                chart = [b for b in blocks if b[0] == "chart"]
                rest = [b for b in blocks if b[0] != "chart"]
                cut = max((j + 1 for j, (k, _) in enumerate(rest) if k == "p"), default=0)
                blocks = rest[:cut] + chart + rest[cut:]
            parts, lead_done = [], pi > 0
            for kind, payload in blocks:
                if kind == "chart":
                    parts.append(
                        f'<div class="viz"><div class="cap">{fr["scales_cap"]} '
                        f'<span class="mini">{fr["scales_mini"]}</span></div>'
                        f'<div class="scales" style="margin-top:2.5mm">{_scales(charts, lang)}</div></div>')
                elif kind == "p":
                    if not lead_done:
                        parts.append(f'<p class="lead" style="margin:3mm 0 3.5mm">{_e(payload)}</p>')
                        lead_done = True
                    else:
                        parts.append(f"<p>{_e(payload)}</p>")
                elif kind == "sci":
                    parts.append(f'<div class="sci"><div class="cap">{fr["sci_cap"]}</div>'
                                 f'<p>{_e(payload)}</p></div>')
                elif kind == "act":
                    parts.append(f'<div class="acts"><div class="cap">{fr["acts_cap"]}</div>'
                                 + "".join(act_row(a) for a in payload) + "</div>")
                elif kind == "gantt":
                    parts.append(_gantt(payload[0], payload[1], fr, lang))
                elif kind == "med":
                    mtitle, mbody = payload
                    paras = "".join(f"<p>{_e(x.strip())}</p>"
                                    for x in mbody.split("\n") if x.strip()) or "<p></p>"
                    parts.append(f'<div class="medbox"><div class="cap">{_e(mtitle)}</div>'
                                 f'{paras}</div>')
            side = f'{fr["chapter_lbl"]} {num}'
            if pi == 0:
                opener = (f'{kick(side)}<h2 class="ph">{_e(s.get("title"))}</h2>')
            else:
                side = f'{side} — {L["cont"]}'
                opener = kick(side)
            page("", f'<div class="ch"><div><div class="chnum">{num}</div>'
                     f'<div class="chside">{side}</div></div>'
                     f'<div class="chbody">{opener}{"".join(parts)}</div></div>')

    # ── weekly plan ──
    week = report.get("weekly_plan") or {}
    wk = "".join(
        f'<div class="wrow"><span class="wd">{_e(L["days"][i])}</span>'
        f'<span class="wf">{_e(week.get(k) or "—")}</span></div>'
        for i, k in enumerate(["mon", "tue", "wed", "thu", "fri", "sat", "sun"]))
    page("", f'{kick(fr["week_ph"])}<h2 class="ph">{fr["week_ph"]}</h2>'
             f'<p class="psub">{_e(L["week_sub"])}</p><div class="week">{wk}</div>')

    # ── 28-day tracker ──
    habits = (report.get("habits") or [])[:5]
    hnum = '<div class="hnum"><span class="hl0"></span>' + \
        "".join(f"<span>{d}</span>" for d in range(1, 8)) + "</div>"
    wkbs = ""
    for w in range(4):
        rows = "".join(
            f'<div class="hrow"><span class="hl">{_e(h)}</span>'
            + '<span class="hc"><i></i></span>' * 7 + "</div>" for h in habits)
        wkbs += (f'<div class="wkb"><div class="whd"><b>{fr["week_lbl"]} {w + 1}</b>'
                 f'<span>{fr["days_lbl"]}</span></div>{hnum}{rows}</div>')
    page("", f'{kick(fr["habit_ph"])}<h2 class="ph">{fr["habit_ph"]}</h2>'
             f'<p class="psub">{_e(L["habit_sub"])}</p><div class="wk2">{wkbs}</div>')

    # ── closing (dark) — chrome harvested; contact from live config ──
    contact = _e(f'{co.get("email", "")} · {co.get("phone", "")} · {co.get("web", "")}')
    page("dark close",
         f'{fr["closing"]}<div class="contact"><b>{owner}</b> · {brand}<br>{contact}</div>'
         f'<div class="disc">{fr["disc"]}</div>')

    head = re.sub(r"<title>.*?</title>", f"<title>{fr['ck']} · {name}</title>",
                  fr["head"], count=1, flags=re.S)
    out = head + "".join(pages) + "</body></html>"

    # the one unacceptable outcome: the sample client inside a real report
    if "Elena" not in (client_name or ""):
        for probe in ("Elena", "elena.martin"):
            if probe in out:
                raise AssertionError(f"report render: sample data survived ({probe})")
    return out


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
