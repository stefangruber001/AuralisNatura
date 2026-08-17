#!/usr/bin/env python3
"""Generate on-brand App Store screenshots (iPhone 6.9" = 1320x2868) in DE/EN/ES
via HTML->PNG with Playwright. Output → ios-app/fastlane/screenshots/<locale>/NNN.png."""
import base64, os, pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path("/home/user/AuralisNatura")
OUT = ROOT / "ios-app/fastlane/screenshots"
EMBLEM = base64.b64encode((ROOT / "images/logo-emblem.png").read_bytes()).decode()

W, H = 1320, 2868  # Apple iPhone 6.9" display

# Warm "cozy-campfire" earth palette (from CLAUDE.md brand tokens)
FOREST="#3D2719"; FOREST_DEEP="#27170E"; FOREST_SOFT="#5A3A22"
CLAY="#A8492A"; GOLD="#AD7A32"; AMBER="#D6A84E"; SAGE="#927B4A"
SAND="#DAC79E"; CREAM="#FBF7EE"; PAPER="#F4EEE1"; INK="#2A211A"

# locale -> screen key -> (headline, subtitle)
T = {
 "en-US": {
   "hero":   ("Reclaim your energy —<br>with science you can trust", "Holistic health, guided by a PhD chemist & certified coach."),
   "method": ("A clear plan,<br>one realistic step at a time", "Listen · Analyse · Align · Sustain — your personalised method."),
   "report": ("Your personal report,<br>reviewed by Dr. Gruber", "Evidence-based, human-approved. Never automated advice."),
   "book":   ("Start with a free<br>introductory call", "No pressure. Just a warm, science-literate conversation."),
 },
 "de-DE": {
   "hero":   ("Finde deine Energie zurück —<br>mit Wissenschaft, der du vertraust", "Ganzheitliche Gesundheit — von einer promovierten Chemikerin & Coach."),
   "method": ("Ein klarer Plan —<br>Schritt für Schritt", "Zuhören · Analysieren · Ausrichten · Halten — deine Methode."),
   "report": ("Dein persönlicher Bericht —<br>geprüft von Dr. Gruber", "Wissenschaftlich fundiert, menschlich freigegeben."),
   "book":   ("Starte mit einem kostenlosen<br>Kennenlerngespräch", "Ohne Druck. Ein warmes, fundiertes Gespräch."),
 },
 "es-ES": {
   "hero":   ("Recupera tu energía —<br>con ciencia en la que confiar", "Salud holística, guiada por una doctora en química y coach."),
   "method": ("Un plan claro,<br>paso a paso", "Escuchar · Analizar · Alinear · Sostener — tu método."),
   "report": ("Tu informe personal,<br>revisado por la Dra. Gruber", "Basado en evidencia y aprobado por una persona."),
   "book":   ("Empieza con una llamada<br>gratuita de presentación", "Sin presión. Una conversación cálida y rigurosa."),
 },
}

# Per-screen phone mock content (label chips shared across languages, kept minimal/visual)
CHIP = {"en-US":{"greet":"Good morning, Elena","prog":"YOUR PROGRESS","milestone":"Desiree is preparing your report.","pcta":"Read your report","today":"Today’s focus",
                 "plan":"Your 4-week plan","week":"Week 2 of 4","report":"Your Report","radar":"Energy · Sleep · Stress · Digestion",
                 "book":"Free introductory call","pick":"Choose a time","confirm":"Confirm booking",
                 "h1":"10-min morning walk","h2":"Protein-rich breakfast","h3":"Wind-down by 22:30",
                 "m1":"Listen — your story & goals","m2":"Analyse — patterns & science","m3":"Align — 3 realistic actions","m4":"Sustain — habits that stay",
                 "r1":"The science, simply — what may help & why.","r2":"Your plan — 3 prioritised steps."},
        "de-DE":{"greet":"Guten Morgen, Elena","prog":"DEIN FORTSCHRITT","milestone":"Desiree bereitet deinen Bericht vor.","pcta":"Bericht lesen","today":"Fokus heute",
                 "plan":"Dein 4-Wochen-Plan","week":"Woche 2 von 4","report":"Dein Bericht","radar":"Energie · Schlaf · Stress · Verdauung",
                 "book":"Kostenloses Kennenlerngespräch","pick":"Zeit wählen","confirm":"Buchung bestätigen",
                 "h1":"10-Min-Morgenspaziergang","h2":"Eiweißreiches Frühstück","h3":"Ausklang bis 22:30",
                 "m1":"Zuhören — deine Geschichte & Ziele","m2":"Analysieren — Muster & Wissenschaft","m3":"Ausrichten — 3 realistische Schritte","m4":"Halten — Gewohnheiten, die bleiben",
                 "r1":"Die Wissenschaft, einfach — was helfen kann und warum.","r2":"Dein Plan — 3 priorisierte Schritte."},
        "es-ES":{"greet":"Buenos días, Elena","prog":"TU PROGRESO","milestone":"Desiree prepara tu informe.","pcta":"Leer tu informe","today":"Foco de hoy",
                 "plan":"Tu plan de 4 semanas","week":"Semana 2 de 4","report":"Tu informe","radar":"Energía · Sueño · Estrés · Digestión",
                 "book":"Llamada de presentación gratuita","pick":"Elige una hora","confirm":"Confirmar reserva",
                 "h1":"Paseo matutino de 10 min","h2":"Desayuno rico en proteínas","h3":"Desconexión a las 22:30",
                 "m1":"Escuchar — tu historia y metas","m2":"Analizar — patrones y ciencia","m3":"Alinear — 3 pasos realistas","m4":"Sostener — hábitos que permanecen",
                 "r1":"La ciencia, simple — qué puede ayudar y por qué.","r2":"Tu plan — 3 pasos priorizados."},
       }

# English (U.K.) = en-GB is the app's primary App Store locale, so mirror en-US into it
# (deliver only fills the locales you provide; the primary must be complete or it looks empty).
T["en-GB"] = T["en-US"]
CHIP["en-GB"] = CHIP["en-US"]

def phone_screen(kind, c):
    """Return inner HTML of the phone screen for a given kind."""
    header = f"""
      <div class="ph-head">
        <img class="ph-emblem" src="data:image/png;base64,{EMBLEM}"/>
        <div class="ph-brand">Auralis Natura</div>
      </div>"""
    if kind == "hero":
        body = f"""
          <div class="ph-greet">{c['greet']}</div>
          <div class="pband">
            <div class="pb-top"><span class="pb-k">{c['prog']}</span>
              <span class="pb-f"><b>2</b>/4</span></div>
            <div class="pb-segs"><i class="on"></i><i class="on"></i><i class="now"></i><i></i></div>
            <div class="pb-ms">{c['milestone']}</div>
            <div class="pb-cta">{c['pcta']}</div>
          </div>
          <div class="ph-sec">{c['today']}</div>
          <div class="ph-card"><span class="dot"></span>{c['h1']}</div>
          <div class="ph-card"><span class="dot"></span>{c['h2']}</div>
          <div class="ph-card"><span class="dot"></span>{c['h3']}</div>"""
    elif kind == "method":
        body = f"""
          <div class="ph-sec">{c['plan']}</div>
          <div class="ph-week">{c['week']}</div>
          <div class="ph-step done"><span class="tick">✓</span>{c['m1']}</div>
          <div class="ph-step done"><span class="tick">✓</span>{c['m2']}</div>
          <div class="ph-step now"><span class="tick">◐</span>{c['m3']}</div>
          <div class="ph-step"><span class="tick">○</span>{c['m4']}</div>
          <div class="ph-bar"><div class="ph-bar-fill"></div></div>"""
    elif kind == "report":
        body = f"""
          <div class="ph-sec">{c['report']}</div>
          <div class="radar"><div class="radar-poly"></div></div>
          <div class="radar-cap">{c['radar']}</div>
          <div class="ph-card lite">{c['r1']}</div>
          <div class="ph-card lite">{c['r2']}</div>"""
    else:  # book
        body = f"""
          <div class="ph-sec">{c['book']}</div>
          <div class="cal">
            {''.join(f'<div class="cal-d {"on" if d==17 else ""}">{d}</div>' for d in range(13,20))}
          </div>
          <div class="slot">{c['pick']}</div>
          <div class="slot on">09:30</div>
          <div class="slot">17:00</div>
          <div class="cta">{c['confirm']}</div>"""
    return header + f'<div class="ph-body">{body}</div>'

def page(locale, kind):
    head, sub = T[locale][kind]
    c = CHIP[locale]
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
      *{{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',system-ui,-apple-system,sans-serif}}
      .stage{{width:{W}px;height:{H}px;position:relative;overflow:hidden;
        background:linear-gradient(165deg,{CREAM} 0%,{PAPER} 46%,{SAND} 100%);}}
      .halo{{position:absolute;width:1700px;height:1700px;left:-260px;top:-680px;border-radius:50%;
        background:radial-gradient(circle,{'rgba(214,168,78,.30)'} 0%,rgba(214,168,78,0) 62%);}}
      .cap{{position:absolute;top:150px;left:96px;right:96px;text-align:center}}
      .cap h1{{font-family:Georgia,'Times New Roman',serif;color:{FOREST};font-size:104px;line-height:1.08;
        font-weight:700;letter-spacing:-1px}}
      .cap .em{{color:{CLAY};font-style:italic}}
      .cap p{{margin-top:34px;color:{INK};opacity:.78;font-size:44px;line-height:1.35;font-weight:500}}
      .spark{{margin:44px auto 0;width:150px;height:12px;display:flex;gap:16px;justify-content:center}}
      .spark i{{width:12px;height:12px;border-radius:50%}}
      .spark i:nth-child(1){{background:{CLAY}}} .spark i:nth-child(2){{background:{SAGE}}} .spark i:nth-child(3){{background:{GOLD}}}
      /* phone */
      .phone{{position:absolute;left:50%;transform:translateX(-50%);bottom:-70px;width:830px;height:1720px;
        background:{FOREST_DEEP};border-radius:96px;padding:26px;box-shadow:0 60px 120px rgba(42,33,26,.34);}}
      .screen{{width:100%;height:100%;background:{CREAM};border-radius:74px;overflow:hidden;position:relative;padding:64px 56px}}
      .island{{position:absolute;top:34px;left:50%;transform:translateX(-50%);width:220px;height:44px;background:#000;border-radius:24px}}
      .ph-head{{display:flex;align-items:center;gap:22px;margin-top:40px}}
      .ph-emblem{{width:92px;height:92px;object-fit:contain}}
      .ph-brand{{font-family:Georgia,serif;color:{FOREST};font-size:52px;font-weight:700}}
      .ph-body{{margin-top:44px}}
      .ph-greet{{color:{INK};opacity:.7;font-size:40px;margin-bottom:10px}}
      .ph-sec{{color:{FOREST};font-weight:700;font-size:46px;margin:8px 0 26px}}
      .ring-wrap{{display:flex;justify-content:center;margin:28px 0 40px}}
      .ring{{width:400px;height:400px;border-radius:50%;
        background:conic-gradient({CLAY} 0turn,{GOLD} .55turn,{SAND} .82turn,{'#efe6d4'} .82turn 1turn);
        display:flex;align-items:center;justify-content:center;position:relative}}
      .ring::after{{content:'';position:absolute;width:300px;height:300px;border-radius:50%;background:{CREAM}}}
      .ring-num{{position:relative;font-family:Georgia,serif;font-size:150px;font-weight:700;color:{FOREST};z-index:1;line-height:1}}
      .ring-lbl{{position:absolute;bottom:74px;font-size:34px;color:{INK};opacity:.6;z-index:1}}
      .ph-card{{background:#fff;border:2px solid rgba(42,33,26,.08);border-radius:30px;padding:34px 36px;margin-bottom:24px;
        font-size:40px;color:{INK};display:flex;align-items:center;gap:26px;box-shadow:0 10px 30px rgba(42,33,26,.05)}}
      .ph-card.lite{{color:#4a4034;font-size:37px}}
      .dot{{width:26px;height:26px;border-radius:50%;background:{SAGE};flex:none}}
      .ph-week{{color:{CLAY};font-weight:700;font-size:38px;margin-bottom:28px}}
      .ph-step{{background:#fff;border:2px solid rgba(42,33,26,.08);border-radius:30px;padding:34px 36px;margin-bottom:22px;
        font-size:39px;color:{INK};display:flex;align-items:center;gap:26px}}
      .ph-step .tick{{width:60px;height:60px;border-radius:50%;display:flex;align-items:center;justify-content:center;
        font-size:34px;background:#efe6d4;color:{INK};flex:none}}
      .ph-step.done .tick{{background:{SAGE};color:#fff}} .ph-step.now .tick{{background:{GOLD};color:#fff}}
      .ph-bar{{height:26px;background:#efe6d4;border-radius:20px;margin-top:26px;overflow:hidden}}
      .ph-bar-fill{{width:52%;height:100%;background:linear-gradient(90deg,{GOLD},{CLAY})}}
      .radar{{width:440px;height:440px;margin:14px auto 8px;border-radius:50%;
        background:radial-gradient(circle,#fff 0,#fff 58%,rgba(0,0,0,0) 58%);position:relative;
        border:none}}
      .radar::before{{content:'';position:absolute;inset:60px;border-radius:50%;border:3px solid rgba(146,123,74,.35)}}
      .radar::after{{content:'';position:absolute;inset:140px;border-radius:50%;border:3px solid rgba(146,123,74,.25)}}
      .pband{{margin:14px 0 30px;padding:34px 32px;background:linear-gradient(150deg,#5A3A22,#3D2719 55%,#221305);
        border:2px solid rgba(173,122,50,.42)}}
      .pb-top{{display:flex;align-items:baseline;justify-content:space-between}}
      .pb-k{{font-size:26px;letter-spacing:5px;color:#D6A84E;font-weight:600}}
      .pb-f{{font-family:'Fraunces',Georgia,serif;font-size:38px;color:rgba(246,239,227,.55)}}
      .pb-f b{{font-size:80px;color:#D6A84E;font-weight:600}}
      .pb-segs{{display:flex;gap:10px;margin:26px 0 22px}}
      .pb-segs i{{flex:1;height:12px;background:rgba(246,239,227,.12)}}
      .pb-segs i.on{{background:#D6A84E}}
      .pb-segs i.now{{background:rgba(214,168,78,.45)}}
      .pb-ms{{font-size:32px;color:rgba(246,239,227,.78);line-height:1.4}}
      .pb-cta{{margin-top:26px;padding:26px;text-align:center;font-size:36px;font-weight:600;
        color:#221305;background:linear-gradient(180deg,#D6A84E,#AD7A32)}}
      .radar-poly{{position:absolute;inset:0;clip-path:polygon(50% 8%,88% 34%,78% 82%,26% 88%,10% 40%);
        background:rgba(168,73,42,.34);border:4px solid {CLAY};border-radius:12px}}
      .radar-cap{{text-align:center;color:{INK};opacity:.62;font-size:33px;margin-bottom:30px}}
      .cal{{display:flex;gap:14px;justify-content:space-between;margin:6px 0 34px}}
      .cal-d{{flex:1;text-align:center;padding:30px 0;border-radius:24px;background:#fff;border:2px solid rgba(42,33,26,.08);
        font-size:40px;color:{INK}}}
      .cal-d.on{{background:{FOREST};color:{CREAM}}}
      .slot{{background:#fff;border:2px solid rgba(42,33,26,.10);border-radius:26px;padding:34px;margin-bottom:22px;font-size:40px;color:{INK}}}
      .slot.on{{border-color:{CLAY};color:{CLAY};font-weight:700}}
      .cta{{margin-top:20px;background:{CLAY};color:#fff;text-align:center;border-radius:30px;padding:40px;font-size:44px;font-weight:700}}
    </style></head><body>
      <div class="stage">
        <div class="halo"></div>
        <div class="cap">
          <h1>{head}</h1>
          <p>{sub}</p>
          <div class="spark"><i></i><i></i><i></i></div>
        </div>
        <div class="phone"><div class="screen"><div class="island"></div>{phone_screen(kind,c)}</div></div>
      </div>
    </body></html>"""

ORDER = ["hero","method","report","book"]
import glob as _glob
def _chrome():
    if os.environ.get("CHROME_BIN"): return os.environ["CHROME_BIN"]
    for g in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome", "/opt/pw-browsers/chromium-*/chrome-linux64/chrome"):
        hits = sorted(_glob.glob(g))
        if hits: return hits[-1]
    return None

with sync_playwright() as p:
    _exe = _chrome()
    b = p.chromium.launch(**({"executable_path": _exe} if _exe else {}))
    pg = b.new_page(viewport={"width":W,"height":H}, device_scale_factor=1)
    for loc in T:
        d = OUT / loc
        d.mkdir(parents=True, exist_ok=True)
        for i,kind in enumerate(ORDER,1):
            pg.set_content(page(loc,kind), wait_until="networkidle")
            f = d / f"{i}_{kind}.png"
            pg.screenshot(path=str(f), clip={"x":0,"y":0,"width":W,"height":H})
            print("wrote", f)
    b.close()
print("done")
