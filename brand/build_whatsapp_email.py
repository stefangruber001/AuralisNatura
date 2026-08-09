#!/usr/bin/env python3
"""Render the WhatsApp setup sheet as an email body (HTML + plain text).

Imports the content constants from build_whatsapp_guide.py rather than restating
them, so the emailed version and the published sheet cannot drift apart.

Email HTML is not web HTML: Gmail's clients strip <style> blocks unpredictably
and support almost no modern layout, so everything here is inline-styled and
laid out with nothing but block elements. No flex, no grid, no custom
properties, no webfonts — a serif/sans stack the client already has.

  python3 brand/build_whatsapp_email.py
      -> brand/out/email.html, email.txt, avatar.jpg.b64
"""
from __future__ import annotations
import base64, io, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_whatsapp_guide import (  # noqa: E402
    DESCRIPTIONS, FIELDS, HOURS, GREETING, AWAY, QUICK_REPLIES, SOCIAL, esc,
)

OUT = HERE / "out"
ARTIFACT = "https://claude.ai/code/artifact/adb7fc08-296e-41bf-94ff-c6d45045ae71"

INK, SOFT, FAINT = "#281F16", "#5C4A3A", "#75685A"
PAPER, SURFACE, RULE = "#F5EEE0", "#FFFCF6", "#DCD2C2"
CLAY, GOLD, OLIVE, FOREST = "#A8492A", "#AD7A32", "#927B4A", "#3D2719"
SANS = "'Helvetica Neue',Helvetica,Arial,sans-serif"
SERIF = "Georgia,'Times New Roman',serif"
MONO = "'SFMono-Regular',Menlo,Consolas,monospace"


def h2(text: str, fig: str) -> str:
    return (f'<p style="margin:34px 0 6px;font-family:{MONO};font-size:11px;'
            f'letter-spacing:1.6px;text-transform:uppercase;color:{GOLD}">{fig}</p>'
            f'<h2 style="margin:0 0 10px;font-family:{SERIF};font-size:21px;'
            f'font-weight:normal;color:{INK};line-height:1.25">{text}</h2>')


def para(text: str, color: str = SOFT, size: int = 15) -> str:
    return (f'<p style="margin:0 0 12px;font-family:{SANS};font-size:{size}px;'
            f'line-height:1.6;color:{color}">{text}</p>')


def value(text: str, mono: bool = True) -> str:
    fam = MONO if mono else SANS
    return (f'<div style="margin:0 0 6px;padding:10px 12px;background:{SURFACE};'
            f'border:1px solid {RULE};font-family:{fam};font-size:14px;'
            f'line-height:1.55;color:{INK};white-space:pre-wrap">{esc(text)}</div>')


def label(text: str) -> str:
    return (f'<p style="margin:18px 0 4px;font-family:{MONO};font-size:11px;'
            f'letter-spacing:1.2px;text-transform:uppercase;color:{OLIVE}">'
            f'{esc(text)}</p>')


def guard(title: str, body: str) -> str:
    return (f'<div style="margin:0 0 14px;padding:2px 0 2px 14px;'
            f'border-left:3px solid {CLAY}">'
            f'<p style="margin:0 0 3px;font-family:{SANS};font-size:15px;'
            f'font-weight:bold;color:{CLAY}">{title}</p>'
            f'<p style="margin:0;font-family:{SANS};font-size:14px;line-height:1.6;'
            f'color:{SOFT}">{body}</p></div>')


def build_html() -> str:
    p = []
    p.append(f'<div style="margin:0;padding:26px 20px 40px;background:{PAPER}">'
             f'<div style="max-width:620px;margin:0 auto">')

    p.append(f'<p style="margin:0 0 8px;font-family:{MONO};font-size:11px;'
             f'letter-spacing:1.8px;text-transform:uppercase;color:{OLIVE}">'
             f'Auralis Natura · Betriebsunterlage</p>')
    p.append(f'<h1 style="margin:0 0 12px;font-family:{SERIF};font-size:28px;'
             f'font-weight:normal;color:{INK};line-height:1.15">'
             f'WhatsApp Business einrichten</h1>')
    p.append(para("Jedes Feld des Profils mit dem Text zum Kopieren. Die Werte "
                  "stammen aus der Website, der Portal-Konfiguration und den echten "
                  "Buchungszeiten — nicht erfunden."))
    p.append(f'<p style="margin:0 0 4px;font-family:{SANS};font-size:14px;'
             f'line-height:1.6;color:{SOFT}">Dieselbe Seite mit Kopier-Knöpfen: '
             f'<a href="{ARTIFACT}" style="color:{CLAY}">hier öffnen</a>.</p>')

    # 01 — the number
    p.append(h2("Die Nummer", "Fig. 01 — zuerst prüfen"))
    p.append(para("WhatsApp Business und das normale WhatsApp können nicht "
                  "gleichzeitig dieselbe Nummer benutzen. <b>+34 614 489 656</b> "
                  "steht auf der Website als Geschäftsnummer."))
    p.append(para("<b>Liegt die Nummer heute im privaten WhatsApp:</b> die "
                  "Business-App bietet beim ersten Start an, den Verlauf zu "
                  "übernehmen — danach ist die Nummer nur noch geschäftlich. "
                  "Einbahnstraße.", FAINT, 14))
    p.append(para("<b>Privat und geschäftlich trennen:</b> zweite Nummer nötig "
                  "(eSIM, ~5 €/Monat). Dann müsste die Website-Nummer geändert "
                  "werden.", FAINT, 14))

    # 02 — picture
    p.append(h2("Profilbild", "Fig. 02 — Profilbild"))
    p.append(para("Im Anhang: <b>auralis-whatsapp-profil-640.jpg</b> — das ist das "
                  "Bild, das hochgeladen wird. Auf dem iPhone: Anhang antippen → "
                  "Sichern → in WhatsApp Business als Profilbild wählen."))
    p.append(para("WhatsApp schneidet rund zu und zeigt es in der Chatliste bei "
                  "etwa 48 px. Deshalb nur das Siegel, ohne Schriftzug, auf "
                  "zimtbraunem Grund: auf dem hellen Grund einer Chatliste braucht "
                  "das Bild eine eigene dunkle Silhouette, sonst verschwimmt es. "
                  "Das alte <span style=\"font-family:" + MONO + ";font-size:13px\">"
                  "logo-ig-profile.png</span> nicht nehmen — dessen grüner Ring "
                  "stammt aus der früheren Farbwelt und wird vom runden Zuschnitt "
                  "angeschnitten."))

    # 03 — fields
    p.append(h2("Was in welches Feld gehört", "Fig. 03 — Profilfelder"))
    for name, val, why in FIELDS:
        p.append(label(name))
        p.append(value(val))
        p.append(f'<p style="margin:0 0 2px;font-family:{SANS};font-size:13px;'
                 f'line-height:1.55;color:{FAINT}">{why}</p>')

    # 04 — description
    p.append(h2("Beschreibung · max. 256 Zeichen", "Fig. 04 — Profilbeschreibung"))
    p.append(para("Eine Sprache auswählen."))
    for lang, tag, text in DESCRIPTIONS:
        suffix = f" — {esc(tag)}" if tag else ""
        p.append(label(f"{lang}{suffix}  ({len(text)}/256)"))
        p.append(value(text, mono=False))

    # 05 — hours
    p.append(h2("Sprechzeiten", "Fig. 05 — Öffnungszeiten"))
    p.append(para("Genau die Fenster, die die Buchungsseite anbietet "
                  "(Europe/Madrid). So kann niemand eine Zeit sehen, die es im "
                  "Kalender nicht gibt."))
    rows = "".join(
        f'<tr><td style="padding:5px 16px 5px 0;font-family:{SANS};font-size:14px;'
        f'color:{SOFT};border-bottom:1px solid #EAE1D2">{esc(d)}</td>'
        f'<td style="padding:5px 16px 5px 0;font-family:{SANS};font-size:14px;'
        f'color:{INK};border-bottom:1px solid #EAE1D2">{esc(a)}</td>'
        f'<td style="padding:5px 0;font-family:{SANS};font-size:14px;color:{INK};'
        f'border-bottom:1px solid #EAE1D2">{esc(b) if b else "—"}</td></tr>'
        for d, a, b in HOURS)
    p.append(f'<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;'
             f'margin:0 0 12px">{rows}</table>')
    p.append(para("Erlaubt deine WhatsApp-Version pro Tag nur ein Zeitfenster: "
                  "09:30 – 17:00 eintragen und die Mittagspause in der "
                  "Abwesenheitsnachricht erwähnen.", FAINT, 14))

    # 06 — auto messages
    p.append(h2("Begrüßung und Abwesenheit", "Fig. 06 — Automatische Nachrichten"))
    p.append(para("Beide zweisprachig, weil du nicht steuern kannst, wer schreibt. "
                  "Die Abwesenheitsnachricht trägt die Pflichtangaben: Coaching "
                  "statt Behandlung, Dr. rer. nat. statt Ärztin, 112 im Notfall."))
    p.append(label("Begrüßungsnachricht"))
    p.append(value(GREETING, mono=False))
    p.append(label("Abwesenheitsnachricht"))
    p.append(value(AWAY, mono=False))

    # 07 — quick replies
    p.append(h2("Schnellantworten", "Fig. 07 — Schnellantworten"))
    p.append(para("In der App unter Tools → Schnellantworten."))
    for k, v in QUICK_REPLIES:
        p.append(label(k))
        p.append(value(v, mono=False))

    # 08 — guardrails
    p.append(h2("Drei Regeln", "Fig. 08 — nicht verhandelbar"))
    p.append(guard("Keine Gesundheitskategorie",
                   "„Medical &amp; Health“ als Kategorie ist auf einem öffentlichen "
                   "Profil eine implizite Berufsbehauptung. "
                   "<i>Dietista-nutricionista</i> ist in Spanien nach Ley 44/2003 "
                   "geschützt. <b>Professional Services</b> oder <b>Education</b>."))
    p.append(guard("Keine Gesundheitsdaten im Chat",
                   "Was jemand über Beschwerden, Medikamente oder eine "
                   "Schwangerschaft schreibt, ist besondere Kategorie "
                   "personenbezogener Daten nach Art. 9 DSGVO — und liegt dann auf "
                   "Metas Servern, außerhalb des verschlüsselten Portals. WhatsApp "
                   "ist für „wann hast du Zeit“. Alles Inhaltliche gehört in den "
                   "Aufnahmebogen im Portal."))
    p.append(guard("Keine Beratung per Chat",
                   "Eine schnelle Antwort auf „was soll ich bei X essen?“ ist genau "
                   "die Grenzüberschreitung, die das Modell schützen soll. "
                   "Freundlich auf das Erstgespräch verweisen — dafür ist "
                   "<span style=\"font-family:" + MONO + ";font-size:13px\">/termin"
                   "</span> da. Bei Alarmzeichen: zur Ärztin, im Notfall 112."))

    p.append(f'<p style="margin:32px 0 0;padding-top:14px;border-top:1px solid {RULE};'
             f'font-family:{SANS};font-size:12px;line-height:1.6;color:{FAINT}">'
             f'Erstellt aus index.html, portal/config/config.json, '
             f'portal/config/availability.json und CLAUDE.md §2. '
             f'Bild erzeugt von brand/make_social_avatars.py.</p>')
    p.append("</div></div>")
    return "".join(p)


def build_text() -> str:
    L = ["AURALIS NATURA — WHATSAPP BUSINESS EINRICHTEN", "=" * 46, "",
         "Jedes Feld mit dem Text zum Kopieren. Werte aus Website, "
         "Portal-Konfiguration und echten Buchungszeiten.",
         f"Seite mit Kopier-Knöpfen: {ARTIFACT}", "",
         "FIG. 01 — DIE NUMMER", "-" * 46,
         "WhatsApp Business und normales WhatsApp können nicht dieselbe Nummer",
         "benutzen. +34 614 489 656 steht auf der Website als Geschäftsnummer.",
         "Liegt sie heute im privaten WhatsApp: die Business-App bietet an, den",
         "Verlauf zu übernehmen — Einbahnstraße. Sonst zweite Nummer (eSIM).", "",
         "FIG. 02 — PROFILBILD", "-" * 46,
         "Im Anhang: auralis-whatsapp-profil-640.jpg — das ist das Bild.",
         "Nur das Siegel, kein Schriftzug, zimtbrauner Grund: WhatsApp schneidet",
         "rund zu und zeigt es bei ~48 px. Das alte logo-ig-profile.png nicht",
         "nehmen (grüner Ring aus der alten Farbwelt, wird angeschnitten).", "",
         "FIG. 03 — PROFILFELDER", "-" * 46]
    for name, val, _ in FIELDS:
        L += [f"{name}:", f"    {val}", ""]
    L += ["FIG. 04 — BESCHREIBUNG (max. 256 Zeichen)", "-" * 46]
    for lang, tag, text in DESCRIPTIONS:
        L += [f"{lang}{' — ' + tag if tag else ''}  ({len(text)}/256)", f"    {text}", ""]
    L += ["FIG. 05 — SPRECHZEITEN (Europe/Madrid)", "-" * 46]
    for d, a, b in HOURS:
        L.append(f"    {d:12} {a}{'  ·  ' + b if b else ''}")
    L += ["", "FIG. 06 — AUTOMATISCHE NACHRICHTEN", "-" * 46, "Begrüßung:", GREETING,
          "", "Abwesenheit:", AWAY, "", "FIG. 07 — SCHNELLANTWORTEN", "-" * 46]
    for k, v in QUICK_REPLIES:
        L += [f"{k}:", v, ""]
    L += ["FIG. 08 — DREI REGELN", "-" * 46,
          "1. Keine Gesundheitskategorie. 'Medical & Health' ist eine implizite",
          "   Berufsbehauptung; dietista-nutricionista ist in Spanien nach",
          "   Ley 44/2003 geschützt. Professional Services oder Education.",
          "2. Keine Gesundheitsdaten im Chat. Art. 9 DSGVO — gehört in den",
          "   Aufnahmebogen im Portal, nicht auf Metas Server.",
          "3. Keine Beratung per Chat. Auf das Erstgespräch verweisen (/termin).",
          "   Bei Alarmzeichen zur Ärztin, im Notfall 112.", ""]
    return "\n".join(L)


def build_attachment() -> tuple[str, int]:
    """640x640 JPEG q92. WhatsApp re-encodes the profile photo to JPEG anyway, so
    this loses nothing where it is actually used, and it is a quarter of the PNG."""
    from PIL import Image
    im = Image.open(SOCIAL / "auralis-avatar-cinnamon-640.png").convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92, optimize=True, progressive=True)
    raw = buf.getvalue()
    return base64.b64encode(raw).decode(), len(raw)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    html, text = build_html(), build_text()
    b64, raw_len = build_attachment()
    (OUT / "email.html").write_text(html, encoding="utf-8")
    (OUT / "email.txt").write_text(text, encoding="utf-8")
    (OUT / "avatar.jpg.b64").write_text(b64)
    print(f"  email.html      {len(html) // 1024} KB")
    print(f"  email.txt       {len(text) // 1024} KB")
    print(f"  avatar.jpg      {raw_len // 1024} KB raw -> {len(b64) // 1024} KB base64")
