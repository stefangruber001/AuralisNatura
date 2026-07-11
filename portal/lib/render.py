"""Render an approved report into a premium, branded 12-page HTML → PDF.

Structure (best-practice premium wellness report):
  p1  Cover                     p7  Chapter 04 (Your plan)
  p2  Personal letter + legend  p8  Chapter 05 (Doctor / safety — dark guard page)
  p3  At-a-glance dashboard     p9  Chapter 06 (Next steps)
  p4  Chapter 01                p10 Weekly plan (7-day table + priorities recap)
  p5  Chapter 02                p11 28-day habit tracker
  p6  Chapter 03 (science)      p12 Closing page (signature, contact, disclaimer)

Visuals: radar (SVG) + bars from the client's self-ratings, color-coded status
chips, science boxes, action checklists — warm-earth palette, Fraunces/Hanken.
PDF via headless Chromium (--print-to-pdf) so fonts + backgrounds render 1:1.
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


def _seal_b64() -> str:
    p = cfg.ASSETS_DIR / "seal.png"
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


def _norm_lang(language: str) -> str:
    l = (language or "").lower()
    return "de" if l.startswith("de") else "es" if l.startswith("es") else "en"


def _e(x) -> str:
    return html.escape(str(x or ""))


# ---------- localised strings ----------
_L = {
 "de": {"kicker": "Persönlicher Gesundheitsbericht", "for": "Mit Sorgfalt erstellt für",
        "chapter": "Kapitel", "page": "Seite",
        "letter_h": "Ein Brief an dich", "letter": [
            "es braucht Mut, ehrlich hinzuschauen — danke für dein Vertrauen. Auf den folgenden Seiten "
            "findest du keine Standard-Tipps, sondern eine Zusammenführung deiner eigenen Worte, deiner "
            "Zahlen und der Wissenschaft dahinter.",
            "Lies den Bericht in Ruhe, gern zweimal. Nichts hier ist eine Aufgabe, die du sofort erfüllen "
            "musst; alles ist eine Einladung, bei dir selbst anzufangen — klein, konkret und freundlich.",
            "Ich freue mich darauf, alles gemeinsam mit dir durchzugehen."],
        "legend_h": "So liest du diesen Bericht",
        "legend": [("chip-ok", "Stärke — läuft bereits gut"),
                   ("chip-gold", "Hebel — hier lohnt sich Aufmerksamkeit"),
                   ("chip-warn", "Priorität — hier beginnen wir")],
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
        "close_sign": "Von Herzen,", "scale_note": "1 = niedrig · 5 = sehr gut"},
 "en": {"kicker": "Personal Holistic Health Report", "for": "Prepared with care for",
        "chapter": "Chapter", "page": "Page",
        "letter_h": "A letter to you", "letter": [
            "it takes courage to look honestly — thank you for your trust. On the following pages you "
            "won't find generic tips, but a synthesis of your own words, your numbers and the science "
            "behind them.",
            "Read this calmly, twice if you like. Nothing here is a task you must complete today; "
            "everything is an invitation to begin with yourself — small, concrete and kind.",
            "I look forward to walking through all of it together."],
        "legend_h": "How to read this report",
        "legend": [("chip-ok", "Strength — already going well"),
                   ("chip-gold", "Lever — worth your attention"),
                   ("chip-warn", "Priority — where we start")],
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
        "close_sign": "Warmly,", "scale_note": "1 = low · 5 = great"},
 "es": {"kicker": "Informe personal de salud holística", "for": "Elaborado con cuidado para",
        "chapter": "Capítulo", "page": "Página",
        "letter_h": "Una carta para ti", "letter": [
            "hace falta valor para mirar con honestidad — gracias por tu confianza. En las páginas "
            "siguientes no encontrarás consejos genéricos, sino una síntesis de tus propias palabras, "
            "tus números y la ciencia detrás.",
            "Léelo con calma, dos veces si quieres. Nada aquí es una tarea que cumplir hoy; todo es una "
            "invitación a empezar contigo — pequeño, concreto y amable.",
            "Me alegra recorrerlo contigo."],
        "legend_h": "Cómo leer este informe",
        "legend": [("chip-ok", "Fortaleza — ya va bien"),
                   ("chip-gold", "Palanca — merece tu atención"),
                   ("chip-warn", "Prioridad — por aquí empezamos")],
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
        "close_sign": "Con cariño,", "scale_note": "1 = bajo · 5 = muy bien"},
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
    rows = []
    for k in ("energy", "sleep", "stress", "digestion"):
        if k in charts:
            v = float(charts[k]); pct = int(v / 5 * 100)
            st = _status(k, v)
            rows.append(
                f'<div class="ch-row"><span class="ch-l">{_e(labels[k])}</span>'
                f'<span class="ch-track"><span class="ch-fill st-{st}" style="width:{pct}%"></span></span>'
                f'<span class="ch-v">{v:.0f}/5</span><span class="dot dot-{st}"></span></div>')
    return "".join(rows)


def _radar(charts: dict, lang: str) -> str:
    keys = [k for k in ("energy", "sleep", "stress", "digestion") if k in charts]
    if len(keys) < 3:
        return ""
    labels = _CH_LABELS.get(lang, _CH_LABELS["en"])
    C, R = 110, 78
    n = len(keys)
    def pt(i, val):
        a = -math.pi / 2 + i * 2 * math.pi / n
        r = R * val / 5
        return (C + r * math.cos(a), C + r * math.sin(a))
    grid = ""
    for lvl in (1, 2, 3, 4, 5):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, lvl) for i in range(n)))
        grid += f'<polygon points="{pts}" fill="none" stroke="rgba(61,39,25,.12)" stroke-width="1"/>'
    axes = ""
    lbls = ""
    for i, k in enumerate(keys):
        x, y = pt(i, 5)
        axes += f'<line x1="{C}" y1="{C}" x2="{x:.1f}" y2="{y:.1f}" stroke="rgba(61,39,25,.15)"/>'
        lx, ly = pt(i, 6.3)
        anchor = "middle"
        lbls += (f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
                 f'font-size="10" fill="#5C4A3A" font-family="Hanken Grotesk">{_e(labels[k])}</text>')
    vals = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, float(charts[k])) for i, k in enumerate(keys)))
    return (f'<svg viewBox="0 0 220 220" class="radar">{grid}{axes}'
            f'<polygon points="{vals}" fill="rgba(168,73,42,.18)" stroke="#A8492A" stroke-width="2"/>'
            f'{lbls}</svg>')


def _chips(items: list, table: dict) -> str:
    return "".join(f'<span class="tchip">{_e(table.get(x, x))}</span>' for x in (items or []))


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
    first = _e((client_name or "").split(" ")[0] or "—")
    owner = _e(co.get("owner", "Dr. rer. nat. Desiree Gruber"))
    brand = _e(co.get("brand", "Auralis Natura"))
    contact = _e(f'{co.get("email","")} · {co.get("phone","")} · {co.get("web","")}')

    pages = []
    pageno = [0]
    def page(cls, inner):
        pageno[0] += 1
        pages.append(f'<section class="page {cls}"><div class="pin">{inner}</div>'
                     f'<div class="pfoot"><span>{brand} · {_e(L["kicker"])}</span>'
                     f'<span>{_e(L["page"])} {pageno[0]:02d}</span></div></section>')

    # ── p1 cover ──
    page("cover", f'''
      <img class="seal" src="data:image/png;base64,{seal}" alt="">
      <div class="kick">{_e(L["kicker"])}</div>
      <h1>{_e(L["for"])}<br><em>{_e(client_name or "—")}</em>.</h1>
      <div class="spark"><i></i><i></i><i></i></div>
      <div class="meta">{_e(date)} · {owner}<br>{brand} · Holistic Health</div>''')

    # ── p2 letter + legend ──
    letter = "".join(f"<p>{_e(p)}</p>" for p in L["letter"])
    legend = "".join(f'<div class="lg"><span class="dot dot-{c.split("-")[1]}"></span>{_e(t)}</div>'
                     for c, t in L["legend"])
    page("", f'''
      <span class="fig">01</span><h2 class="ph">{_e(L["letter_h"])}</h2>
      <div class="letter"><p class="salut">{first},</p>{letter}
      <p class="sign">{_e(L["close_sign"])}<br><span class="signname">Desiree</span></p></div>
      <div class="legendbox"><div class="boxcap">{_e(L["legend_h"])}</div>{legend}</div>''')

    # ── p3 dashboard ──
    prios = (report.get("priorities") or [])[:3]
    prio_cards = "".join(
        f'<div class="pcard"><div class="pnum">{i+1}</div><div><b>{_e(p.get("title"))}</b>'
        f'<div class="pwhy">{_e(p.get("why"))}</div></div></div>'
        for i, p in enumerate(prios))
    page("", f'''
      <span class="fig">02</span><h2 class="ph">{_e(L["glance_h"])}</h2>
      <p class="psub">{_e(L["glance_sub"])}</p>
      <div class="dash2">
        <div class="dcell"><div class="boxcap">{_e(L["balance"])}</div>{_radar(charts, lang)}</div>
        <div class="dcell"><div class="boxcap">{_e(L["ratings"])} <span class="mini">{_e(L["scale_note"])}</span></div>
          {_bars(charts, lang)}
          <div class="boxcap" style="margin-top:12px">{_e(L["themes"])}</div>
          <div>{_chips(profile.get("symptoms"), _SYM_LABELS.get(lang, _SYM_LABELS["en"]))}</div>
        </div>
      </div>
      <div class="boxcap" style="margin-top:14px">{_e(L["prio_h"])}</div>
      <div class="prow">{prio_cards}</div>''')

    # ── p4-9 chapters ──
    accents = ["#A8492A", "#AD7A32", "#927B4A", "#3D2719", "#8A4A2A", "#5C4A3A"]
    for i, s in enumerate(sections):
        body = "".join(f"<p>{_e(par)}</p>" for par in (s.get("body") or "").split("\n") if par.strip())
        sci = s.get("science") or ""
        acts = s.get("actions") or []
        sci_html = (f'<div class="scibox"><div class="boxcap">🔬 {_e(L["science_h"])}</div>'
                    f'<p>{_e(sci)}</p></div>') if sci else ""
        act_html = ""
        if acts:
            act_html = (f'<div class="actbox"><div class="boxcap">✓ {_e(L["actions_h"])}</div>' +
                        "".join(f'<div class="act"><span class="cb"></span>{_e(a)}</div>' for a in acts) +
                        "</div>")
        guard = s.get("key") == "when_to_see_a_doctor"
        chart = ""
        if s.get("key") == "what_were_seeing" and charts:
            chart = f'<div class="chmini">{_bars(charts, lang)}</div>'
        page("guardpage" if guard else "", f'''
          <span class="fig" style="color:{accents[i % 6]}">{_e(L["chapter"])} {i+1:02d}</span>
          <h2 class="ph" style="border-left:4px solid {accents[i % 6]};padding-left:12px">{_e(s.get("title"))}</h2>
          {chart}{body}{sci_html}{act_html}''')

    # ── p10 weekly plan ──
    week = report.get("weekly_plan") or {}
    wk_keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    rows = "".join(f'<tr><td class="wd">{_e(L["days"][i])}</td><td>{_e(week.get(k, "—"))}</td></tr>'
                   for i, k in enumerate(wk_keys))
    prio_recap = "".join(
        f'<div class="pcard"><div class="pnum">{i+1}</div><div><b>{_e(p.get("title"))}</b>'
        f'<div class="pwhy">{_e(L["first_step"])}: {_e(p.get("first_step"))}</div></div></div>'
        for i, p in enumerate(prios))
    page("", f'''
      <span class="fig">03</span><h2 class="ph">{_e(L["week_h"])}</h2>
      <p class="psub">{_e(L["week_sub"])}</p>
      <table class="wtab">{rows}</table>
      <div class="boxcap" style="margin-top:16px">{_e(L["prio_h"])} — {_e(L["first_step"])}</div>
      <div class="prow">{prio_recap}</div>''')

    # ── p11 habit tracker ──
    habits = (report.get("habits") or [])[:5]
    weeks_html = ""
    for w in range(4):
        head = "".join(f"<th>{d+1}</th>" for d in range(7))
        body_rows = "".join(
            f'<tr><td class="hname">{_e(h)}</td>' + "".join('<td><span class="cb"></span></td>' for _ in range(7)) + "</tr>"
            for h in habits)
        weeks_html += (f'<div class="hweek"><div class="boxcap">{_e(L["week_lbl"])} {w+1}</div>'
                       f'<table class="htab"><tr><th></th>{head}</tr>{body_rows}</table></div>')
    page("", f'''
      <span class="fig">04</span><h2 class="ph">{_e(L["habit_h"])}</h2>
      <p class="psub">{_e(L["habit_sub"])}</p>{weeks_html}''')

    # ── p12 closing ──
    page("cover closing", f'''
      <img class="seal" src="data:image/png;base64,{seal}" alt="">
      <h2 class="ph" style="text-align:center;border:0">{_e(L["close_h"])}</h2>
      <p class="closep">{_e(L["close"])}</p>
      <div class="spark"><i></i><i></i><i></i></div>
      <p class="sign" style="text-align:center">{_e(L["close_sign"])}<br><span class="signname">Desiree</span></p>
      <div class="meta" style="margin-top:26px">{owner} · {brand}<br>{contact}</div>
      <div class="disc">{_disclaimer(lang)}</div>''')

    return _TEMPLATE.format(lang=lang, pages="".join(pages))


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


_TEMPLATE = """<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..600;1,9..144,300..500&family=Hanken+Grotesk:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--ink:#281F16;--ink-soft:#5C4A3A;--ink-faint:#8C7E6E;--forest:#3D2719;--forest-deep:#221305;--goldhair:rgba(173,122,50,.42);--clay:#A8492A;--gold:#AD7A32;--sage:#927B4A;--sage-soft:#DAC79E;--paper:#F5EEE0;--cream:#FBF6EB;--line:rgba(61,39,25,.16);--ok:#3F7B5A;--okbg:#EEF6EF;--wa:#B0553F;--wabg:#FCEFEC;--go:#6F4F2C;--gobg:#FBF6EC;--fd:"Fraunces",Georgia,serif;--fb:"Hanken Grotesk",system-ui,sans-serif}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:var(--fb);color:var(--ink);background:#fff;font-size:12.5px;line-height:1.62;-webkit-font-smoothing:antialiased}}
.page{{width:210mm;min-height:297mm;position:relative;page-break-after:always;background:#fff;overflow:hidden}}
.pin{{padding:17mm 16mm 24mm}}
.pfoot{{position:absolute;left:16mm;right:16mm;bottom:9mm;display:flex;justify-content:space-between;font-size:8.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-faint);border-top:1px solid var(--goldhair);padding-top:6px}}
.fig{{font-family:var(--fb);font-size:.62rem;letter-spacing:.2em;text-transform:uppercase;color:var(--ink-faint);font-weight:600}}
.ph{{font-family:var(--fd);font-weight:400;font-size:1.9rem;color:var(--forest);margin:6px 0 12px;line-height:1.15}}
.psub{{color:var(--ink-soft);margin-bottom:16px}}
p{{color:var(--ink-soft);margin:0 0 10px}}
/* cover */
.cover{{background:linear-gradient(165deg,var(--cream),var(--paper))}}
.cover .pin{{display:flex;flex-direction:column;justify-content:center;text-align:center;min-height:270mm}}
.cover .seal{{width:104px;height:104px;margin:0 auto 22px}}
.cover .kick{{font-size:.68rem;letter-spacing:.28em;text-transform:uppercase;color:var(--clay);font-weight:600}}
.cover h1{{font-family:var(--fd);font-weight:400;font-size:2.6rem;line-height:1.12;margin:16px 0 20px}}
.cover h1 em{{font-style:italic;color:var(--clay)}}
.cover .meta{{font-size:.9rem;color:var(--ink-soft);line-height:1.7}}
.spark{{display:flex;gap:7px;justify-content:center;margin:14px 0}}
.spark i{{width:7px;height:7px;border-radius:50%;background:var(--clay)}}
.spark i:nth-child(2){{background:var(--gold)}}.spark i:nth-child(3){{background:var(--sage)}}
/* letter */
.letter{{background:var(--cream);border:1px solid var(--line);border-top:3px solid var(--gold);padding:24px 28px;margin:10px 0 18px}}
.letter .salut{{font-family:var(--fd);font-size:1.25rem;color:var(--ink);margin-bottom:12px}}
.sign{{margin-top:16px}}
.signname{{font-family:var(--fd);font-size:1.45rem;color:var(--ink)}}
.legendbox{{border:1px dashed var(--line);padding:14px 18px}}
.lg{{display:flex;gap:10px;align-items:center;font-size:.85rem;color:var(--ink-soft);margin:5px 0}}
.boxcap{{font-size:.62rem;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-faint);font-weight:600;margin-bottom:8px}}
.boxcap .mini{{text-transform:none;letter-spacing:0;font-weight:400}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:50%}}
.dot-ok{{background:var(--ok)}}.dot-gold{{background:#C4A882}}.dot-warn{{background:var(--wa)}}
/* dashboard */
.dash2{{display:grid;grid-template-columns:1fr 1.2fr;gap:16px;align-items:start}}
.dcell{{background:var(--cream);border:1px solid var(--line);padding:16px 18px}}
.radar{{width:100%;max-width:240px;display:block;margin:0 auto}}
.ch-row{{display:flex;align-items:center;gap:8px;margin:7px 0;font-size:11.5px}}
.ch-l{{width:64px;color:var(--ink-soft)}}
.ch-track{{flex:1;height:9px;background:var(--sage-soft);position:relative}}
.ch-fill{{position:absolute;left:0;top:0;bottom:0}}
.st-ok{{background:linear-gradient(90deg,var(--sage),var(--ok))}}
.st-gold{{background:linear-gradient(90deg,var(--gold),#C4A882)}}
.st-warn{{background:linear-gradient(90deg,var(--clay),var(--wa))}}
.ch-v{{width:28px;text-align:right;font-weight:600;font-variant-numeric:tabular-nums}}
.tchip{{display:inline-block;font-size:.74rem;background:#fff;border:1px solid var(--line);padding:2px 10px;margin:2px 3px 2px 0}}
.prow{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}}
.pcard{{display:flex;gap:10px;background:#fff;border:1px solid var(--line);border-top:3px solid var(--clay);padding:12px 13px;font-size:.82rem}}
.pcard .pnum{{font-family:var(--fd);font-size:1.5rem;color:var(--gold);line-height:1}}
.pcard .pwhy{{color:var(--ink-faint);font-size:.76rem;margin-top:3px}}
/* chapters */
.scibox{{background:var(--gobg);border:1px solid #C4A882;border-left:4px solid var(--gold);padding:12px 16px;margin:14px 0}}
.scibox p{{margin:0;font-size:.85rem}}
.actbox{{background:var(--okbg);border:1px solid #6DA986;border-left:4px solid var(--ok);padding:12px 16px;margin:14px 0}}
.act{{display:flex;gap:10px;align-items:flex-start;margin:6px 0;font-size:.88rem;color:var(--ink-soft)}}
.cb{{display:inline-block;width:13px;height:13px;border:1.5px solid var(--sage);background:#fff;flex:0 0 auto;margin-top:3px}}
.chmini{{background:var(--cream);border:1px solid var(--line);padding:12px 16px;margin:0 0 14px}}
.guardpage{{background:linear-gradient(165deg,var(--forest-deep),var(--forest))}}
.guardpage .ph,.guardpage .fig{{color:#F3EEDF!important;border-color:#D6A84E!important}}
.guardpage p{{color:#DED7C4}}
.guardpage .scibox,.guardpage .actbox{{background:rgba(255,255,255,.07);border-color:rgba(255,255,255,.25)}}
.guardpage .scibox p,.guardpage .act{{color:#DED7C4}}
.guardpage .boxcap{{color:#D6A84E}}
.guardpage .pfoot{{color:rgba(237,231,214,.5);border-color:rgba(255,255,255,.15)}}
/* weekly */
.wtab{{width:100%;border-collapse:collapse;background:var(--cream);border:1px solid var(--line)}}
.wtab td{{padding:9px 14px;border-bottom:1px solid var(--line);font-size:.9rem;color:var(--ink-soft)}}
.wtab .wd{{width:110px;font-weight:600;color:var(--forest);font-family:var(--fd);font-size:.95rem}}
/* habits */
.hweek{{margin-bottom:14px}}
.htab{{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line)}}
.htab th{{font-size:.6rem;letter-spacing:.1em;color:var(--ink-faint);padding:5px;border-bottom:1px solid var(--line);text-align:center}}
.htab td{{padding:6px 5px;border-bottom:1px solid var(--line);text-align:center}}
.htab .hname{{text-align:left;font-size:.8rem;color:var(--ink-soft);width:34%}}
/* closing */
.closing .pin{{min-height:270mm}}
.closep{{max-width:52ch;margin:0 auto 8px;text-align:center;font-size:1rem}}
.closing .seal{{width:84px;height:84px}}
.disc{{margin-top:24px;font-size:8.8px;color:var(--ink-faint);line-height:1.6;text-align:left;border-top:1px solid var(--line);padding-top:10px}}
@media print{{@page{{size:A4;margin:0}} .page{{margin:0}}}}
</style></head><body>
{pages}
</body></html>"""
