#!/usr/bin/env python3
"""Render the three social-setup emails: WhatsApp, Facebook, Instagram.

Shares its content constants with build_whatsapp_guide.py so the emailed values
and the published sheet cannot drift apart.

Email HTML is not web HTML — Gmail strips <style> blocks unpredictably and
supports almost no modern layout — so everything is inline-styled with block
elements only. No flex, no grid, no custom properties, no webfonts.

  python3 brand/build_social_emails.py    ->  brand/out/{whatsapp,facebook,instagram}.{html,txt}
"""
from __future__ import annotations
import pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_whatsapp_guide import (  # noqa: E402
    DESCRIPTIONS, FIELDS, HOURS, GREETING, AWAY, QUICK_REPLIES, esc,
)

OUT = HERE / "out"
SHEET = "https://claude.ai/code/artifact/adb7fc08-296e-41bf-94ff-c6d45045ae71"

INK, SOFT, FAINT = "#281F16", "#5C4A3A", "#75685A"
PAPER, SURFACE, RULE, HAIR = "#F5EEE0", "#FFFCF6", "#DCD2C2", "#EAE1D2"
CLAY, GOLD, OLIVE = "#A8492A", "#AD7A32", "#927B4A"
SANS = "'Helvetica Neue',Helvetica,Arial,sans-serif"
SERIF = "Georgia,'Times New Roman',serif"
MONO = "'SFMono-Regular',Menlo,Consolas,monospace"

# The assets are published with the website (deploy-pages.yml already copies
# images/), so every mail can SHOW the picture and link a real download. That
# beats attaching: the avatar is ~360 KB, it would have to ride five separate
# mails, and saving an attachment out of Gmail on a phone is fiddlier than
# holding down a picture.
IMG = "https://www.auralisnatura.com/images/social"
AVATAR = f"{IMG}/auralis-avatar-cinnamon-640.png"


def picture(url: str, alt: str, caption: str, width: int = 220) -> str:
    """An image the reader can see AND save, with the download spelled out."""
    return (f'<div style="margin:0 0 16px">'
            f'<a href="{url}"><img src="{url}" alt="{esc(alt)}" width="{width}" '
            f'style="display:block;max-width:100%;height:auto;border:1px solid {RULE}"></a>'
            f'<p style="margin:6px 0 0;font-family:{SANS};font-size:12px;'
            f'line-height:1.5;color:{FAINT}">{caption}<br>'
            f'<a href="{url}" style="color:{CLAY}">Bild öffnen und sichern</a> '
            f'<span style="color:{FAINT}">· auf dem iPhone: lange drücken → Sichern</span>'
            f'</p></div>')


PIC_NOTE = ("Bild antippen, dann sichern — es liegt auf der eigenen Website, "
            "funktioniert also auf jedem Gerät ohne Anhang.")


def h1(title: str) -> str:
    return (f'<p style="margin:0 0 8px;font-family:{MONO};font-size:11px;'
            f'letter-spacing:1.8px;text-transform:uppercase;color:{OLIVE}">'
            f'Auralis Natura · Betriebsunterlage</p>'
            f'<h1 style="margin:0 0 12px;font-family:{SERIF};font-size:28px;'
            f'font-weight:normal;color:{INK};line-height:1.15">{title}</h1>')


def h2(text: str, fig: str) -> str:
    return (f'<p style="margin:34px 0 6px;font-family:{MONO};font-size:11px;'
            f'letter-spacing:1.6px;text-transform:uppercase;color:{GOLD}">{fig}</p>'
            f'<h2 style="margin:0 0 10px;font-family:{SERIF};font-size:21px;'
            f'font-weight:normal;color:{INK};line-height:1.25">{text}</h2>')


def para(text: str, color: str = SOFT, size: int = 15) -> str:
    c = "" if color == SOFT else f"color:{color};"
    z = "" if size == 15 else f"font-size:{size}px;"
    return f'<p style="margin:0 0 12px;{z}{c}">{text}</p>' 


def value(text: str, mono: bool = True) -> str:
    fam = MONO if mono else SANS
    return (f'<div style="margin:0 0 6px;padding:10px 12px;background:{SURFACE};'
            f'border:1px solid {RULE};font-family:{fam};font-size:14px;'
            f'color:{INK};white-space:pre-wrap">{esc(text)}</div>')


def label(text: str) -> str:
    return (f'<p style="margin:18px 0 4px;font-family:{MONO};font-size:11px;'
            f'letter-spacing:1.2px;text-transform:uppercase;color:{OLIVE}">'
            f'{esc(text)}</p>')


def why(text: str) -> str:
    return f'<p style="margin:0 0 2px;font-size:13px;color:{FAINT}">{text}</p>' 


def guard(title: str, body: str) -> str:
    return (f'<div style="margin:0 0 14px;padding:2px 0 2px 14px;'
            f'border-left:3px solid {CLAY}">'
            f'<p style="margin:0 0 3px;font-weight:bold;color:{CLAY}">{title}</p>'
            f'<p style="margin:0;font-size:14px">{body}</p></div>')


def field(name: str, val: str, note: str) -> str:
    return label(name) + value(val) + why(note)


def shell(inner: str) -> str:
    return (f'<div style="margin:0;padding:26px 20px 40px;background:{PAPER}">'
            f'<div style="max-width:620px;margin:0 auto">{inner}'
            f'<p style="margin:32px 0 0;padding-top:14px;border-top:1px solid {RULE};'
            f'font-family:{SANS};font-size:12px;line-height:1.6;color:{FAINT}">'
            f'Werte aus index.html, portal/config/config.json, '
            f'portal/config/availability.json und CLAUDE.md §2. '
            f'Bild aus brand/social/, erzeugt von brand/make_social_avatars.py.'
            f'</p></div></div>')


# ══════════════════════════════════════════════════════════════════ WHATSAPP ══
def whatsapp() -> str:
    p = [h1("WhatsApp Business einrichten")]
    p.append(para("Jedes Feld des Profils mit dem Text zum Kopieren. Die Werte "
                  "stammen aus der Website, der Portal-Konfiguration und den echten "
                  "Buchungszeiten — nicht erfunden."))
    p.append(para(f'Dieselbe Seite mit Kopier-Knöpfen: '
                  f'<a href="{SHEET}" style="color:{CLAY}">hier öffnen</a>.', SOFT, 14))

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

    p.append(h2("Profilbild", "Fig. 02 — Profilbild"))
    p.append(para(PIC_NOTE))
    p.append(para("WhatsApp schneidet rund zu und zeigt es in der Chatliste bei "
                  "etwa 48 px. Deshalb nur das Siegel, ohne Schriftzug, auf "
                  "zimtbraunem Grund: auf dem hellen Grund einer Chatliste braucht "
                  "das Bild eine eigene dunkle Silhouette, sonst verschwimmt es. "
                  "Das alte logo-ig-profile.png nicht nehmen — dessen grüner Ring "
                  "stammt aus der früheren Farbwelt und wird vom runden Zuschnitt "
                  "angeschnitten."))

    p.append(h2("Was in welches Feld gehört", "Fig. 03 — Profilfelder"))
    for name, val, note in FIELDS:
        p.append(field(name, val, note))

    p.append(h2("Beschreibung · max. 256 Zeichen", "Fig. 04 — Profilbeschreibung"))
    p.append(para("Eine Sprache auswählen."))
    for lang, tag, text in DESCRIPTIONS:
        p.append(label(f"{lang}{' — ' + tag if tag else ''}  ({len(text)}/256)"))
        p.append(value(text, mono=False))

    p.append(h2("Sprechzeiten", "Fig. 05 — Öffnungszeiten"))
    p.append(para("Genau die Fenster, die die Buchungsseite anbietet "
                  "(Europe/Madrid). So kann niemand eine Zeit sehen, die es im "
                  "Kalender nicht gibt."))
    rows = "".join(
        f'<tr><td style="padding:5px 16px 5px 0;font-family:{SANS};font-size:14px;'
        f'color:{SOFT};border-bottom:1px solid {HAIR}">{esc(d)}</td>'
        f'<td style="padding:5px 16px 5px 0;font-family:{SANS};font-size:14px;'
        f'color:{INK};border-bottom:1px solid {HAIR}">{esc(a)}</td>'
        f'<td style="padding:5px 0;font-family:{SANS};font-size:14px;color:{INK};'
        f'border-bottom:1px solid {HAIR}">{esc(b) if b else "—"}</td></tr>'
        for d, a, b in HOURS)
    p.append(f'<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;'
             f'margin:0 0 12px">{rows}</table>')
    p.append(para("Erlaubt deine WhatsApp-Version pro Tag nur ein Zeitfenster: "
                  "09:30 – 17:00 eintragen und die Mittagspause in der "
                  "Abwesenheitsnachricht erwähnen.", FAINT, 14))

    p.append(h2("Begrüßung und Abwesenheit", "Fig. 06 — Automatische Nachrichten"))
    p.append(para("Beide zweisprachig, weil du nicht steuern kannst, wer schreibt. "
                  "Die Abwesenheitsnachricht trägt die Pflichtangaben: Coaching "
                  "statt Behandlung, Dr. rer. nat. statt Ärztin, 112 im Notfall."))
    p.append(label("Begrüßungsnachricht") + value(GREETING, mono=False))
    p.append(label("Abwesenheitsnachricht") + value(AWAY, mono=False))

    p.append(h2("Schnellantworten", "Fig. 07 — Schnellantworten"))
    p.append(para("In der App unter Tools → Schnellantworten."))
    for k, v in QUICK_REPLIES:
        p.append(label(k) + value(v, mono=False))

    p.append(h2("Drei Regeln", "Fig. 08 — nicht verhandelbar"))
    p.append(guard("Keine Gesundheitskategorie",
                   "„Medical &amp; Health“ ist auf einem öffentlichen Profil eine "
                   "implizite Berufsbehauptung. <i>Dietista-nutricionista</i> ist in "
                   "Spanien nach Ley 44/2003 geschützt. <b>Professional Services</b> "
                   "oder <b>Education</b>."))
    p.append(guard("Keine Gesundheitsdaten im Chat",
                   "Was jemand über Beschwerden, Medikamente oder eine Schwangerschaft "
                   "schreibt, ist besondere Kategorie personenbezogener Daten nach "
                   "Art. 9 DSGVO — und liegt dann auf Metas Servern, außerhalb des "
                   "verschlüsselten Portals. WhatsApp ist für „wann hast du Zeit“. "
                   "Alles Inhaltliche gehört in den Aufnahmebogen im Portal."))
    p.append(guard("Keine Beratung per Chat",
                   "Eine schnelle Antwort auf „was soll ich bei X essen?“ ist genau "
                   "die Grenzüberschreitung, die das Modell schützen soll. Freundlich "
                   "auf das Erstgespräch verweisen — dafür ist /termin da. Bei "
                   "Alarmzeichen: zur Ärztin, im Notfall 112."))
    return shell("".join(p))


# ══════════════════════════════════════════════════════════════════ FACEBOOK ══
FB_FIELDS = [
    ("Seitenname", "Auralis Natura",
     "Nur die Marke. Facebook erlaubt spätere Umbenennungen nur begrenzt und mit "
     "Prüfung — den Namen also gleich richtig setzen."),
    ("Nutzername (@handle)", "auralisnatura",
     "Ergibt facebook.com/auralisnatura. Gleicher Handle wie bei Instagram, damit "
     "beide Profile auffindbar zusammengehören. Mindestens 5 Zeichen, nur "
     "Buchstaben/Ziffern/Punkte."),
    ("Kategorie 1", "Health & Wellness Website",
     "<b>Nicht</b> „Nutritionist“, „Doctor“, „Medical Service“ oder „Dietitian“ — "
     "das sind in Spanien geschützte Berufsbezeichnungen (Ley 44/2003). Wenn dir "
     "diese Kategorie zu gesundheitsnah ist, nimm stattdessen <b>Education</b>."),
    ("Kategorie 2", "Coach",
     "Beschreibt exakt, was du tust, und ist kein regulierter Beruf. Facebook "
     "erlaubt bis zu drei Kategorien."),
    ("Kategorie 3", "Professional Service",
     "Deckungsgleich mit der WhatsApp-Kategorie — konsistent über alle Profile."),
    ("E-Mail", "team@auralisnatura.com", "Dieselbe Adresse wie überall sonst."),
    ("Telefon", "+34 614 489 656", "Die Nummer von der Website."),
    ("Website", "https://www.auralisnatura.com", "Die kanonische Adresse."),
    ("Impressum-Feld", "https://www.auralisnatura.com/impressum.html",
     "Facebook hat für Seiten mit deutschsprachigem Publikum ein eigenes "
     "<i>Impressum</i>-Feld. Die Seite existiert bereits — eintragen, nicht "
     "leer lassen."),
    ("Schaltfläche (Button)", "Termin buchen → https://api.auralisnatura.com/book",
     "Der Button ist der einzige Grund, warum die Seite existiert. Nicht auf "
     "„Nachricht senden“ stehen lassen — das erzeugt DMs mit Gesundheitsdaten "
     "statt Buchungen."),
]

FB_COVER = (
    "1640 × 856 px hochladen. Angezeigt wird 820 × 312 (Desktop) und "
    "640 × 360 (Handy) — der sichtbare Ausschnitt ist auf dem Handy also deutlich "
    "höher und schmaler. Alles Wichtige gehört in die mittleren ~640 × 312 px, "
    "sonst wird es abgeschnitten. Ein ruhiges Bild ohne Text funktioniert am "
    "besten; die Fotos aus images/ (nourish.jpg oder desiree-consult.jpg) passen. "
    "Sag Bescheid, wenn ich ein fertiges Titelbild bauen soll."
)


def facebook() -> str:
    p = [h1("Facebook-Seite einrichten")]
    p.append(para("Eine <b>Seite</b>, kein zweites Privatprofil — Seiten dürfen "
                  "geschäftlich sein, Privatprofile laut Facebooks Bedingungen nicht. "
                  "Du legst die Seite aus deinem bestehenden Privatprofil heraus an; "
                  "das bleibt für Besucher unsichtbar."))
    p.append(para(f'Die WhatsApp-Werte, auf denen das hier aufbaut: '
                  f'<a href="{SHEET}" style="color:{CLAY}">Setup-Seite</a>.', SOFT, 14))

    p.append(h2("Reihenfolge", "Fig. 01 — zuerst"))
    p.append(para("Facebook zuerst, Instagram danach: ein Instagram-Business-Konto "
                  "lässt sich mit einer bestehenden Facebook-Seite verbinden, und "
                  "diese Verbindung braucht man später für Werbung, den Shop und "
                  "gemeinsame Nachrichten. Andersherum ist es Nacharbeit."))

    p.append(h2("Bilder", "Fig. 02 — Bilder"))
    p.append(para(PIC_NOTE))
    p.append(para("<b>Profilbild:</b> Facebook zeigt es rund, 170 × 170 px am "
                  "Rechner und 128 × 128 px auf dem Handy. Dasselbe zimtbraune "
                  "Siegel wie bei WhatsApp — hochladen in 640 × 640 oder größer."))
    p.append(para(f"<b>Titelbild:</b> {FB_COVER}"))

    p.append(h2("Was in welches Feld gehört", "Fig. 03 — Seiteninfos"))
    for name, val, note in FB_FIELDS:
        p.append(field(name, val, note))

    p.append(h2("Beschreibung · max. 255 Zeichen", "Fig. 04 — Kurzbeschreibung"))
    p.append(para("Identisch mit der WhatsApp-Beschreibung — ein Profil, eine "
                  "Aussage."))
    lang, tag, text = DESCRIPTIONS[0]
    p.append(label(f"{lang} — empfohlen  ({len(text)}/255)") + value(text, mono=False))
    en = DESCRIPTIONS[1]
    p.append(label(f"English  ({len(en[2])}/255)") + value(en[2], mono=False))

    p.append(h2("Öffnungszeiten", "Fig. 05 — Öffnungszeiten"))
    p.append(para("Dieselben Fenster wie bei WhatsApp und auf der Buchungsseite "
                  "(Europe/Madrid): Mo 09:30–12:00 und 14:00–17:00 · Di dito · "
                  "Mi 09:30–12:00 · Do wie Mo · Fr 09:30–12:00 · Sa/So geschlossen."))

    p.append(h2("Drei Regeln", "Fig. 06 — nicht verhandelbar"))
    p.append(guard("Keine geschützte Berufsbezeichnung in Kategorie oder Text",
                   "Weder „Ernährungsberaterin“ noch „Nutritionist“ noch „Dietitian“. "
                   "Du bist Gesundheitscoach und Wissenschaftlerin — genau das steht "
                   "in der Beschreibung, und genau das darfst du sein."))
    p.append(guard("Keine Vorher-Nachher-Versprechen",
                   "Metas Werberichtlinien verbieten Vorher-Nachher-Bilder und "
                   "Aussagen über unrealistische Ergebnisse ausdrücklich, und die "
                   "Richtlinie zu persönlichen Eigenschaften verbietet, im Text zu "
                   "unterstellen, du wüsstest etwas über den Gesundheitszustand der "
                   "Leserin („Fühlst du dich ständig erschöpft?“). Solche Anzeigen "
                   "werden abgelehnt und können das Konto gefährden."))
    p.append(guard("Bewertungen bleiben echt",
                   "Die Seitenempfehlungen einschalten ist gut — aber nur echte "
                   "Stimmen, niemals erfundene. Das ist die Regel aus dem "
                   "Gesamtprojekt und sie gilt hier genauso."))
    return shell("".join(p))


# ═════════════════════════════════════════════════════════════════ INSTAGRAM ══
IG_NAME = "Auralis Natura"
IG_HANDLE = "auralisnatura"
IG_BIOS = [
    ("Deutsch", "empfohlen",
     "Wissenschaftlich fundiertes Gesundheitscoaching\n"
     "Dr. rer. nat. Desiree Gruber · Barcelona\n"
     "Bildung, keine ärztliche Behandlung\n"
     "Erstgespräch kostenlos ↓"),
    ("English", "",
     "Science-based health coaching\n"
     "Dr. rer. nat. Desiree Gruber · Barcelona\n"
     "Education, not medical care\n"
     "Free first call ↓"),
    ("Español", "",
     "Coaching de salud con base científica\n"
     "Dr. rer. nat. Desiree Gruber · Barcelona\n"
     "Educación, no atención médica\n"
     "Primera llamada gratuita ↓"),
]

IG_FIELDS = [
    ("Nutzername", IG_HANDLE,
     "Gleicher Handle wie bei Facebook. Kurz, ohne Punkte oder Unterstriche — "
     "leichter zu diktieren und zu tippen."),
    ("Name (Suchfeld)", IG_NAME,
     "Das Namensfeld ist durchsuchbar, der Nutzername auch. Maximal 30 Zeichen; "
     "„Auralis Natura“ sind 14. Kein „Dr.“ und kein Gesundheitsberuf hier — das "
     "Feld wird von Meta als Namensangabe behandelt."),
    ("Kontotyp", "Business (nicht Creator)",
     "Business schaltet Kontaktbuttons, WhatsApp-Verknüpfung und Statistiken frei. "
     "Creator ist für Einzelpersonen mit Publikum gedacht, nicht für eine Praxis."),
    ("Kategorie", "Health & Wellness Website  ·  oder  Education",
     "Wie bei Facebook: <b>nicht</b> „Nutritionist“ und nicht „Medical“. Die "
     "Kategorie steht sichtbar unter dem Namen — sie ist eine öffentliche "
     "Berufsangabe."),
    ("Kontakt-E-Mail", "team@auralisnatura.com", "Erzeugt den E-Mail-Button."),
    ("Kontakt-Telefon", "+34 614 489 656",
     "Erzeugt den Anruf-Button. Wenn du keine Anrufe willst, dieses Feld leer "
     "lassen — der Button erscheint sonst prominent."),
    ("Aktionsschaltfläche", "Termin buchen → https://api.auralisnatura.com/book",
     "Unter „Öffentliche Geschäftsinformationen bearbeiten → Aktionsschaltfläche“. "
     "Das ist der Weg vom Profil in den Kalender."),
    ("Link im Profil", "https://www.auralisnatura.com",
     "Instagram erlaubt inzwischen bis zu fünf Links. Zwei reichen: die Website "
     "und https://api.auralisnatura.com/book — dann braucht es kein Linktree, das "
     "nur eine weitere Station zwischen Interesse und Buchung wäre."),
]


def instagram() -> str:
    p = [h1("Instagram einrichten")]
    p.append(para("Ein <b>Business-Konto</b>, verbunden mit der Facebook-Seite. "
                  "Wenn Facebook schon steht, dauert das hier zehn Minuten."))
    p.append(para(f'Die WhatsApp-Werte, auf denen das hier aufbaut: '
                  f'<a href="{SHEET}" style="color:{CLAY}">Setup-Seite</a>.', SOFT, 14))

    p.append(h2("Profilbild", "Fig. 01 — Profilbild"))
    p.append(para(PIC_NOTE))
    p.append(para("Instagram zeigt es rund bei 320 × 320 px, in der Story-Leiste "
                  "noch kleiner. Dasselbe zimtbraune Siegel wie bei WhatsApp und "
                  "Facebook — ein Bild über alle drei Profile, damit dich Leute "
                  "wiedererkennen. Hochladen in 640 × 640."))

    p.append(h2("Was in welches Feld gehört", "Fig. 02 — Profilfelder"))
    for name, val, note in IG_FIELDS:
        p.append(field(name, val, note))

    p.append(h2("Steckbrief · max. 150 Zeichen", "Fig. 03 — Bio"))
    p.append(para("Das engste Textfeld von allen. Zeilenumbrüche zählen mit. "
                  "Der Pfeil zeigt auf den Link direkt darunter."))
    for lang, tag, text in IG_BIOS:
        p.append(label(f"{lang}{' — ' + tag if tag else ''}  ({len(text)}/150)"))
        p.append(value(text, mono=False))

    p.append(h2("Was zuerst hochladen", "Fig. 04 — die ersten neun Beiträge"))
    p.append(para("Ein leeres Profil überzeugt niemanden, der über den Button "
                  "kommt. Neun Beiträge füllen das sichtbare Raster; Material dafür "
                  "liegt bereits im Projekt:"))
    p.append(para("• das Porträt und das Beratungsfoto (images/desiree-portrait.jpg, "
                  "desiree-consult.jpg, desiree-womens-health.jpg)<br>"
                  "• die vier Zertifikate — Promotion, Akademie der Naturheilkunde, "
                  "Frauengesundheit, Yoga (images/cert-*.jpg)<br>"
                  "• die drei Angebote Klarheit · Wandel · Balance mit je einem Satz, "
                  "was drinsteckt<br>"
                  "• ein Beitrag „Was Auralis Natura <i>nicht</i> ist“ — das ist "
                  "Positionierung und Compliance in einem", SOFT, 14))

    p.append(h2("Drei Regeln", "Fig. 05 — nicht verhandelbar"))
    p.append(guard("Keine Diagnosen, keine Heilversprechen",
                   "Instagram ist die Plattform, auf der das am schnellsten passiert: "
                   "„Diese 3 Lebensmittel bei Hashimoto“ ist eine Behandlungsaussage. "
                   "„Was die Studienlage zu X sagt — und was sie nicht sagt“ ist "
                   "Bildung. Der Unterschied ist die ganze Geschäftsgrundlage."))
    p.append(guard("Keine Gesundheitsdaten in DMs",
                   "Dieselbe Art-9-DSGVO-Frage wie bei WhatsApp, nur öffentlicher. "
                   "Wenn jemand in den Direktnachrichten Beschwerden schildert: "
                   "freundlich ins Erstgespräch überführen, nicht im Chat "
                   "weiterberaten. Auch nicht in den Kommentaren."))
    p.append(guard("Keine erfundenen Stimmen",
                   "Keine Testimonials, keine Erfolgsgeschichten, keine "
                   "Vorher-Nachher-Bilder ohne echte, belegbare Grundlage und ohne "
                   "ausdrückliche schriftliche Einwilligung der Klientin — bei "
                   "Gesundheitsdaten ist die Einwilligung Pflicht, nicht Höflichkeit."))
    return shell("".join(p))



# ══════════════════════════════════════════════════════════════════ LINKEDIN ══
# LinkedIn is the one platform where the PERSON outranks the brand: people
# search for a name and a credential, not for a logo. So the personal profile
# carries her face and her headline, and the company page carries the seal.
LI_HEADLINE = ("Dr. rer. nat. Desiree Gruber · Wissenschaftlich fundiertes "
               "Gesundheitscoaching für Frauen · Gründerin Auralis Natura · "
               "15+ Jahre Forschung und pharmazeutische Industrie")

LI_ABOUT = """Ich übersetze Wissenschaft in Gesundheit, die im Alltag funktioniert.

Promoviert in bioorganischer Chemie, seit über fünfzehn Jahren in Forschung und pharmazeutischer Industrie — und zertifiziert in ganzheitlicher Gesundheit, Ernährung und Frauengesundheit (Akademie der Naturheilkunde, Abschluss mit 97,22 %). Zusätzlich ausgebildete Yoga- und Meditationslehrerin (200 h Ashtanga).

Diese Kombination ist der Punkt. In der Gesundheitsberatung gibt es viel Wärme ohne Evidenz und viel Evidenz ohne Wärme. Auralis Natura ist der Versuch, beides zusammenzubringen: eine Einschätzung, die dem aktuellen Stand der Forschung standhält, in einer Sprache, die man nach einem langen Arbeitstag noch versteht — und mit zwei bis drei Schritten, die tatsächlich in ein Leben passen.

Woran ich arbeite:
· Energie, Schlaf, Verdauung und Stressbelastung — was die Studienlage hergibt und was nicht
· Frauengesundheit über die Lebensphasen, von Zyklus bis Perimenopause
· Ernährung als Bildungsthema, nicht als Diätvorschrift

Wichtig und ausdrücklich: Auralis Natura ist Gesundheitscoaching und Bildung. Es ist keine medizinische Behandlung und ersetzt sie nicht. „Dr. rer. nat." ist ein akademischer Doktortitel in Chemie — ich bin keine Ärztin. Ich arbeite neben deiner Ärztin, nie an ihrer Stelle.

Kostenloses Kennenlerngespräch: auralisnatura.com"""

LI_FIELDS = [
    ("Profilfoto", f"{IMG}/auralis-linkedin-portrait.jpg",
     "Auf LinkedIn <b>dein Gesicht</b>, nicht das Siegel. Menschen suchen hier nach "
     "einer Person und einer Qualifikation; ein Logo auf einem Personenprofil wirkt "
     "wie ein Firmenaccount und senkt die Kontaktrate. Das Siegel gehört auf die "
     "Unternehmensseite."),
    ("Profil-Banner", f"{IMG}/auralis-linkedin-banner.jpg",
     "1584 × 396 px. Das Profilfoto liegt unten links darüber — deshalb ist die "
     "linke Fläche im Bild absichtlich frei."),
    ("Eigene Profil-URL", "linkedin.com/in/desiree-gruber",
     "Unter „Profil bearbeiten → Öffentliches Profil und URL“. Eine URL mit Namen "
     "statt Zahlensalat ist der einzige SEO-Hebel, den LinkedIn direkt in die "
     "Google-Suche gibt."),
    ("Berufsbezeichnung / Headline", LI_HEADLINE,
     "220 Zeichen, und das <b>wichtigste durchsuchbare Feld auf LinkedIn</b> — es "
     "erscheint in jeder Suche, jedem Kommentar, jeder Einladung. Deshalb stehen "
     "die Suchbegriffe vorne: Gesundheitscoaching, Frauen, Wissenschaft. "
     "<b>Nicht</b> „Ernährungsberaterin“ — geschützt (Ley 44/2003)."),
    ("Unternehmensseite anlegen", "Auralis Natura",
     "Getrennt vom Personenprofil: Seite erstellen → Kleinunternehmen. Logo = das "
     "Siegel (300 × 300), Titelbild 1128 × 191, Branche „Gesundheit, Wellness und "
     "Fitness“ oder „Berufliche Weiterbildung und Coaching“, Website "
     "auralisnatura.com. Danach im Personenprofil unter Erfahrung verknüpfen — dann "
     "erscheint das Logo neben deinem Namen."),
    ("Erfahrung: neuer Eintrag", "Gründerin · Auralis Natura · Barcelona (Remote)",
     "Nur diesen Eintrag anlegen. Deinen bestehenden Novartis-Eintrag <b>nicht "
     "anfassen</b> — und dort nichts hinzufügen, was nach Leitungsfunktion klingt."),
]

LI_GUARDS = [
    ("Dein Arbeitgeber liest mit",
     "LinkedIn ist die eine Plattform, auf der dein Nebenerwerb unmittelbar für "
     "Kolleginnen und Vorgesetzte sichtbar wird — und sie benachrichtigt dein "
     "Netzwerk aktiv über Profiländerungen. Vor dem Speichern: unter Einstellungen "
     "→ Sichtbarkeit → „Netzwerk über Profiländerungen informieren“ auf <b>Nein</b> "
     "stellen. Ob und wann der Nebenerwerb sichtbar sein soll, ist deine "
     "Entscheidung; sie sollte nur nicht aus Versehen fallen."),
    ("Keine geschützte Berufsbezeichnung",
     "Nicht in der Headline, nicht in „Info“, nicht in den Kenntnissen. "
     "„Gesundheitscoaching“, „Ernährungsbildung“, „Frauengesundheit“ — ja. "
     "„Ernährungsberaterin“, „Nutritionist“, „Diätologin“ — nein."),
    ("Kein Klientinnen-Material",
     "Keine Fallbeispiele, keine Vorher-Nachher-Geschichten, auch nicht anonymisiert, "
     "ohne ausdrückliche schriftliche Einwilligung. Gesundheitsdaten sind Art. 9 "
     "DSGVO; „man erkennt sie ja nicht“ ist keine Rechtsgrundlage."),
]


def linkedin() -> str:
    p = [h1("LinkedIn einrichten")]
    p.append(para("Zwei Dinge: dein <b>Personenprofil</b> aktualisieren und eine "
                  "<b>Unternehmensseite</b> anlegen. Das Personenprofil bringt die "
                  "Reichweite — auf LinkedIn folgt man Menschen, nicht Logos."))
    p.append(para(f'Die gemeinsamen Werte: '
                  f'<a href="{SHEET}" style="color:{CLAY}">Setup-Seite</a>.', SOFT, 14))

    p.append(h2("Bilder", "Fig. 01 — Bilder"))
    p.append(para(PIC_NOTE, FAINT, 14))
    p.append(picture(f"{IMG}/auralis-linkedin-portrait.jpg", "Portrait Desiree Gruber",
                     "<b>Profilfoto Personenprofil</b> — dein Gesicht, nicht das Siegel.", 200))
    p.append(picture(f"{IMG}/auralis-linkedin-banner.jpg", "LinkedIn Banner",
                     "<b>Profil-Banner</b> 1584 × 396 px. Links frei, weil dort das "
                     "Profilfoto liegt.", 460))
    p.append(picture(f"{IMG}/auralis-linkedin-company-cover.jpg", "LinkedIn Titelbild",
                     "<b>Titelbild Unternehmensseite</b> 1128 × 191 px.", 460))
    p.append(picture(AVATAR, "Auralis Natura Siegel",
                     "<b>Logo Unternehmensseite</b> 300 × 300 px (dieses Bild "
                     "hochladen, LinkedIn skaliert).", 160))

    p.append(h2("Was in welches Feld gehört", "Fig. 02 — Profilfelder"))
    for name, val, note in LI_FIELDS:
        p.append(field(name, val, note))

    p.append(h2("Info-Bereich", "Fig. 03 — „Info“ / About"))
    p.append(para("2.600 Zeichen erlaubt; die ersten <b>zwei Zeilen</b> sind alles, "
                  "was ohne Klick auf „mehr“ zu sehen ist — deshalb steht der Satz, "
                  "um den es geht, ganz oben. Der Compliance-Absatz gehört mit "
                  "hinein, nicht in eine Fußnote."))
    p.append(label(f"Deutsch  ({len(LI_ABOUT)}/2600)"))
    p.append(value(LI_ABOUT, mono=False))

    p.append(h2("Drei Regeln", "Fig. 04 — nicht verhandelbar"))
    for t, b in LI_GUARDS:
        p.append(guard(t, b))
    return shell("".join(p))


# ════════════════════════════════════════════════════════ GOOGLE BUSINESS ══
# The only one of the five that is really a search product. Everything here is
# in service of one query: someone in Barcelona typing "Gesundheitscoaching"
# or "health coach Barcelona" into Google or Maps.
GOOGLE_DESC = """Auralis Natura ist wissenschaftlich fundiertes Gesundheitscoaching von Dr. rer. nat. Desiree Gruber in Barcelona — auf Deutsch, Englisch und Spanisch, online und persönlich.

Promoviert in bioorganischer Chemie, über fünfzehn Jahre in Forschung und pharmazeutischer Industrie, zertifiziert in ganzheitlicher Gesundheit, Ernährung und Frauengesundheit. Themen: Energie und Erschöpfung, Schlaf, Verdauung, Stress und Frauengesundheit über alle Lebensphasen.

Jede Begleitung beginnt mit einem kostenlosen Kennenlerngespräch.

Auralis Natura ist Bildung und Begleitung — keine medizinische Behandlung und kein Ersatz dafür. Dr. rer. nat. ist ein akademischer Doktortitel in Chemie, keine ärztliche Approbation."""

G_FIELDS = [
    ("Unternehmensname", "Auralis Natura",
     "<b>Nur der Name.</b> Kein „Auralis Natura Gesundheitscoaching Barcelona“ — "
     "Google verbietet Schlüsselwörter im Namensfeld ausdrücklich, und Verstöße "
     "führen zu Sperrungen. Die Suchbegriffe gehören in Kategorien und Beschreibung, "
     "wo Google sie ohnehin liest."),
    ("Hauptkategorie", "Life coach  (Lebensberater/in)",
     "Die Hauptkategorie bestimmt praktisch allein, für welche Suchen du überhaupt "
     "erscheinst. „Ernährungsberater“ / „Nutritionist“ würde besser ranken und ist "
     "genau die Behauptung, die du nicht aufstellen darfst. „Life coach“ ist "
     "eindeutig unbedenklich. Wenn dir das zu unscharf ist: <b>Health consultant</b> "
     "(Gesundheitsberater/in) — noch zulässig, aber näher an der Grenze."),
    ("Weitere Kategorien", "Health consultant · Wellness program · Educational consultant",
     "Bis zu neun erlaubt. Jede weitere Kategorie öffnet weitere Suchanfragen, ohne "
     "die Hauptkategorie zu verwässern."),
    ("Dienstgebiet statt Adresse", "Barcelona · Katalonien · online in ganz Spanien, DACH",
     "<b>Der wichtigste Schalter.</b> Bei „Kunden besuchen dich?“ → <b>Nein</b>, "
     "dann Dienstgebiete eintragen. Sonst verlangt Google deine Privatadresse "
     "und zeigt sie öffentlich auf der Karte."),
    ("Telefon", "+34 614 489 656", "Exakt dieselbe Schreibweise wie überall sonst."),
    ("Website", "https://www.auralisnatura.com", "Die kanonische Adresse."),
    ("Termin-Link", "https://api.auralisnatura.com/book",
     "Feld „Termine“. Google zeigt daraus einen eigenen Buchungsbutton direkt im "
     "Suchergebnis — der kürzeste Weg von der Suche in den Kalender, den es gibt."),
    ("Leistungen", "Klarheit 199 € · Wandel 399 € · Balance 899 € · The Grove (Firmen)",
     "Unter „Leistungen“ einzeln anlegen, je mit Beschreibung. Leistungen sind "
     "durchsuchbarer Text — hier gehören „Frauengesundheit“, „Ernährungsbildung“, "
     "„Perimenopause“ hin, nicht in den Namen."),
    ("Attribute", "Inhaberin: Frau · Online-Termine · Sprachen Deutsch, Englisch, Spanisch",
     "Die Sprachen sind für Barcelona ein echtes Unterscheidungsmerkmal — Expats "
     "suchen genau danach."),
]

G_GUARDS = [
    ("Verifizierung dauert und ist Pflicht",
     "Ohne Verifizierung erscheint das Profil nicht. Ohne Ladenadresse bietet Google "
     "meist Video-Verifizierung an: ein durchgehender Clip, der dich, Arbeitsmittel "
     "und etwas Ortsbezug zeigt. Vorher <b>keine</b> Werbung darauf verlinken."),
    ("Keine erfundenen Bewertungen",
     "Google erkennt Bewertungsmuster und entfernt ganze Profile dafür. Bewertungen "
     "aktiv erbitten ist erlaubt und richtig — aber nur bei echten Klientinnen, "
     "nach Abschluss, ohne Gegenleistung. Anreize sind ein Richtlinienverstoß."),
    ("Ein Name, eine Nummer, eine Adresse — überall gleich",
     "„NAP-Konsistenz“ ist der stärkste einzelne Faktor der lokalen Suche: Google "
     "gleicht Name, Telefon und Ort über Website, Maps, Facebook und Instagram ab. "
     "Deshalb steht in allen fünf Mails <b>dieselbe</b> Schreibweise — „Auralis "
     "Natura“, „+34 614 489 656“, „Barcelona, España“. Nicht variieren, auch nicht "
     "kosmetisch."),
]


def google() -> str:
    p = [h1("Google-Unternehmensprofil einrichten")]
    p.append(para("Das ist Google Maps <i>und</i> der Kasten rechts in der "
                  "Google-Suche — dieselbe Sache. Von den fünf Profilen ist dieses "
                  "das einzige, das echte Suchnachfrage abgreift: jemand in "
                  "Barcelona tippt „Gesundheitscoaching“ und findet dich, ohne "
                  "dich zu kennen."))
    p.append(para('Anlegen unter <b>business.google.com</b>.', SOFT, 14))
    p.append(para(f'Die gemeinsamen Werte: '
                  f'<a href="{SHEET}" style="color:{CLAY}">Setup-Seite</a>.', SOFT, 14))

    p.append(h2("Bilder", "Fig. 01 — Bilder"))
    p.append(para(PIC_NOTE, FAINT, 14))
    p.append(picture(AVATAR, "Auralis Natura Siegel", "<b>Logo</b> — quadratisch.", 160))
    p.append(picture(f"{IMG}/auralis-google-cover.jpg", "Google Titelbild",
                     "<b>Titelbild</b> 1024 × 576 px.", 400))
    p.append(para("Danach mindestens drei weitere Fotos hochladen — Profile mit "
                  "Fotos werden deutlich häufiger angeklickt. Das Porträt, das "
                  "Beratungsfoto und eines der Zertifikate reichen für den Anfang.",
                  SOFT, 14))

    p.append(h2("Was in welches Feld gehört", "Fig. 02 — Profilfelder"))
    for name, val, note in G_FIELDS:
        p.append(field(name, val, note))

    p.append(h2("Beschreibung · max. 750 Zeichen", "Fig. 03 — Beschreibung"))
    p.append(para("Google liest diesen Text für die Suche mit. Deshalb stehen die "
                  "Begriffe, unter denen du gefunden werden willst, hier in ganzen "
                  "Sätzen — und der Compliance-Absatz steht mit drin, nicht als "
                  "Kleingedrucktes."))
    p.append(label(f"Deutsch  ({len(GOOGLE_DESC)}/750)"))
    p.append(value(GOOGLE_DESC, mono=False))

    p.append(h2("Öffnungszeiten", "Fig. 04 — Öffnungszeiten"))
    p.append(para("Dieselben Fenster wie überall (Europe/Madrid): Mo 09:30–12:00 und "
                  "14:00–17:00 · Di dito · Mi 09:30–12:00 · Do wie Mo · "
                  "Fr 09:30–12:00 · Sa/So geschlossen."))

    p.append(h2("Drei Regeln", "Fig. 05 — nicht verhandelbar"))
    for t, b in G_GUARDS:
        p.append(guard(t, b))
    return shell("".join(p))


def linkedin_text() -> str:
    fields = "\n".join(f"{n}:\n    {v}" for n, v, _ in LI_FIELDS)
    return to_text("Auralis Natura — LinkedIn einrichten", [
        ("BILDER", f"Profilfoto (Person): {IMG}/auralis-linkedin-portrait.jpg\n"
                   f"Banner 1584x396:     {IMG}/auralis-linkedin-banner.jpg\n"
                   f"Titelbild Firma:     {IMG}/auralis-linkedin-company-cover.jpg\n"
                   f"Logo Firma 300x300:  {AVATAR}"),
        ("PROFILFELDER", fields),
        (f"INFO / ABOUT ({len(LI_ABOUT)}/2600)", LI_ABOUT),
        ("DREI REGELN",
         "1. Dein Arbeitgeber liest mit — Profiländerungs-Benachrichtigung vorher aus.\n"
         "2. Keine geschützte Berufsbezeichnung.\n"
         "3. Kein Klientinnen-Material ohne schriftliche Einwilligung."),
        ("SETUP-SEITE", SHEET),
    ])


def google_text() -> str:
    fields = "\n".join(f"{n}:\n    {v}" for n, v, _ in G_FIELDS)
    return to_text("Auralis Natura — Google-Unternehmensprofil einrichten", [
        ("ANLEGEN", "business.google.com"),
        ("BILDER", f"Logo:       {AVATAR}\nTitelbild:  {IMG}/auralis-google-cover.jpg"),
        ("PROFILFELDER", fields),
        (f"BESCHREIBUNG ({len(GOOGLE_DESC)}/750)", GOOGLE_DESC),
        ("OEFFNUNGSZEITEN", "Wie ueberall, Europe/Madrid."),
        ("DREI REGELN",
         "1. Verifizierung ist Pflicht und dauert.\n"
         "2. Keine erfundenen Bewertungen, keine Anreize.\n"
         "3. NAP-Konsistenz: Name, Telefon, Ort ueberall identisch."),
        ("SETUP-SEITE", SHEET),
    ])



# ═══════════════════════════════════════════════════════════════════ compact ══
# The full prose lives on the setup page; the mail is the scannable version that
# still carries every value you have to type somewhere and every picture you
# have to upload. Keeping it short is not a compromise — a 22 KB HTML mail is
# clipped by Gmail ("Message truncated") on exactly the phone she will read it on.
def compact(title: str, intro: str, images: list, fields: list,
            longs: list, guards: list) -> str:
    p = [h1(title), para(intro)]
    p.append(para(f'Alle Werte mit Kopier-Knöpfen: '
                  f'<a href="{SHEET}" style="color:{CLAY}">Setup-Seite öffnen</a>.',
                  SOFT, 14))
    if images:
        p.append(h2("Bilder", "Fig. 01 — herunterladen"))
        p.append(para(PIC_NOTE, FAINT, 14))
        for url, alt, cap, wpx in images:
            p.append(picture(url, alt, cap, wpx))
    p.append(h2("Felder", "Fig. 02 — zum Kopieren"))
    for name, val, note in fields:
        p.append(field(name, val, note))
    for head, fig, note, items in longs:
        p.append(h2(head, fig))
        if note:
            p.append(para(note))
        for lab, text in items:
            p.append(label(lab) + value(text, mono=False))
    p.append(h2("Drei Regeln", "Fig. 09 — nicht verhandelbar"))
    for t, b in guards:
        p.append(guard(t, b))
    return shell("".join(p))

# ═══════════════════════════════════════════════════════════════════════ txt ══
def to_text(title: str, pairs: list[tuple[str, str]]) -> str:
    out = [title.upper(), "=" * len(title), ""]
    for head, body in pairs:
        out += [head, "-" * 46, body, ""]
    return "\n".join(out)


def whatsapp_text() -> str:
    fields = "\n".join(f"{n}:\n    {v}" for n, v, _ in FIELDS)
    descs = "\n".join(f"{l}{' — ' + t if t else ''} ({len(x)}/256)\n    {x}"
                      for l, t, x in DESCRIPTIONS)
    hours = "\n".join(f"    {d:12} {a}{'  ·  ' + b if b else ''}" for d, a, b in HOURS)
    qr = "\n".join(f"{k}:\n{v}\n" for k, v in QUICK_REPLIES)
    return to_text("Auralis Natura — WhatsApp Business einrichten", [
        ("SEITE MIT KOPIER-KNÖPFEN", SHEET),
        ("FIG. 01 — DIE NUMMER",
         "WhatsApp Business und normales WhatsApp können nicht dieselbe Nummer\n"
         "benutzen. +34 614 489 656 steht auf der Website als Geschäftsnummer."),
        ("FIG. 02 — PROFILBILD",
         "auralis-avatar-cinnamon-640.png (in der Claude-Unterhaltung, und auf der\n"
         "oben verlinkten Seite eingebettet). Nur das Siegel, zimtbrauner Grund."),
        ("FIG. 03 — PROFILFELDER", fields),
        ("FIG. 04 — BESCHREIBUNG (max. 256)", descs),
        ("FIG. 05 — SPRECHZEITEN (Europe/Madrid)", hours),
        ("FIG. 06 — BEGRÜSSUNG", GREETING),
        ("FIG. 06 — ABWESENHEIT", AWAY),
        ("FIG. 07 — SCHNELLANTWORTEN", qr),
        ("FIG. 08 — DREI REGELN",
         "1. Keine Gesundheitskategorie (Ley 44/2003).\n"
         "2. Keine Gesundheitsdaten im Chat (Art. 9 DSGVO).\n"
         "3. Keine Beratung per Chat — ins Erstgespräch überführen."),
    ])


def facebook_text() -> str:
    fields = "\n".join(f"{n}:\n    {v}" for n, v, _ in FB_FIELDS)
    return to_text("Auralis Natura — Facebook-Seite einrichten", [
        ("REIHENFOLGE", "Facebook zuerst, Instagram danach — das IG-Business-Konto\n"
                        "wird mit dieser Seite verbunden."),
        ("BILDER", "Profilbild: auralis-avatar-cinnamon-640.png, rund, 170x170 Anzeige.\n"
                   "Titelbild: 1640x856 hochladen, Wichtiges in die mittleren 640x312."),
        ("SEITENINFOS", fields),
        ("BESCHREIBUNG (max. 255)", DESCRIPTIONS[0][2]),
        ("ÖFFNUNGSZEITEN", "Wie WhatsApp/Buchungsseite, Europe/Madrid."),
        ("DREI REGELN",
         "1. Keine geschützte Berufsbezeichnung in Kategorie oder Text.\n"
         "2. Keine Vorher-Nachher-Versprechen (Meta-Werberichtlinien).\n"
         "3. Bewertungen bleiben echt."),
        ("SETUP-SEITE", SHEET),
    ])


def instagram_text() -> str:
    fields = "\n".join(f"{n}:\n    {v}" for n, v, _ in IG_FIELDS)
    bios = "\n".join(f"{l}{' — ' + t if t else ''} ({len(x)}/150)\n{x}\n"
                     for l, t, x in IG_BIOS)
    return to_text("Auralis Natura — Instagram einrichten", [
        ("KONTOTYP", "Business, verbunden mit der Facebook-Seite."),
        ("PROFILBILD", "auralis-avatar-cinnamon-640.png — rund, 320x320 Anzeige."),
        ("PROFILFELDER", fields),
        ("BIO (max. 150)", bios),
        ("DREI REGELN",
         "1. Keine Diagnosen, keine Heilversprechen.\n"
         "2. Keine Gesundheitsdaten in DMs oder Kommentaren.\n"
         "3. Keine erfundenen Stimmen; echte nur mit schriftlicher Einwilligung."),
        ("SETUP-SEITE", SHEET),
    ])


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    built = [("whatsapp", whatsapp(), whatsapp_text()),
             ("facebook", facebook(), facebook_text()),
             ("instagram", instagram(), instagram_text()),
             ("linkedin", linkedin(), linkedin_text()),
             ("google", google(), google_text())]
    for name, html, text in built:
        (OUT / f"{name}.html").write_text(html, encoding="utf-8")
        (OUT / f"{name}.txt").write_text(text, encoding="utf-8")
        print(f"  {name:10} html {len(html) // 1024:>3} KB   txt {len(text) // 1024:>3} KB")

    print("\n  length checks")
    for lang, _, t in DESCRIPTIONS:
        flag = "ok  " if len(t) <= 255 else "OVER"
        print(f"    {flag} description {lang:20} {len(t):>3}/255")
    for lang, _, t in IG_BIOS:
        flag = "ok  " if len(t) <= 150 else "OVER"
        print(f"    {flag} instagram bio {lang:18} {len(t):>3}/150")
    print(f"    {'ok  ' if len(IG_NAME) <= 30 else 'OVER'} instagram name "
          f"{'':17} {len(IG_NAME):>3}/30")
    print(f"    {'ok  ' if len(LI_HEADLINE) <= 220 else 'OVER'} linkedin headline "
          f"{'':14} {len(LI_HEADLINE):>3}/220")
    print(f"    {'ok  ' if len(LI_ABOUT) <= 2600 else 'OVER'} linkedin about "
          f"{'':17} {len(LI_ABOUT):>4}/2600")
    print(f"    {'ok  ' if len(GOOGLE_DESC) <= 750 else 'OVER'} google description "
          f"{'':13} {len(GOOGLE_DESC):>4}/750")
