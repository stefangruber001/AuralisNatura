#!/usr/bin/env python3
"""Seven standalone setup sheets, one per system, as small self-contained HTML.

These are ATTACHMENTS, not email bodies, so unlike build_social_emails.py they
can use a real <style> block with classes instead of restating inline styles on
every element. That is ~4x smaller and lets the pages carry a proper hover and
copy affordance.

Fonts are the system stack on purpose: embedding Fraunces as a data URI would
add ~90 KB to every one of the seven files, and these have to travel as base64
inside a single mail.

  python3 brand/build_attachments.py     -> brand/out/attach/*.html  (+ .b64)
"""
from __future__ import annotations
import base64, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_social_emails import (  # noqa: E402
    DESCRIPTIONS, FIELDS, HOURS, GREETING, AWAY, QUICK_REPLIES,
    FB_FIELDS, FB_COVER, IG_FIELDS, IG_BIOS, LI_FIELDS, LI_ABOUT, LI_GUARDS,
    G_FIELDS, GOOGLE_DESC, G_GUARDS, IMG, AVATAR, SHEET, esc,
)

OUT = HERE / "out" / "attach"

CSS = """
:root{--paper:#F5EEE0;--surface:#FFFCF6;--ink:#281F16;--soft:#5C4A3A;
--faint:#75685A;--clay:#A8492A;--gold:#AD7A32;--olive:#927B4A;--rule:#DCD2C2;
--hair:#EAE1D2;--forest:#3D2719}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--soft);
font:16px/1.62 -apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif}
.wrap{max-width:44rem;margin:0 auto;padding:2.2rem 1.3rem 4rem}
h1,h2{font-family:Georgia,'Times New Roman',serif;font-weight:400;color:var(--ink);
margin:0;line-height:1.18;text-wrap:balance}
h1{font-size:1.95rem}
h2{font-size:1.32rem;margin-bottom:.5rem}
p{margin:0 0 .75rem;max-width:34rem}
a{color:var(--clay)}
.kick{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.68rem;
letter-spacing:.16em;text-transform:uppercase;color:var(--olive);margin:0 0 .6rem}
.fig{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.66rem;
letter-spacing:.15em;text-transform:uppercase;color:var(--gold);
margin:2.1rem 0 .35rem}
.lede{font-size:1.02rem}
header{padding-bottom:1.3rem;border-bottom:1px solid var(--rule);margin-bottom:.4rem}
.lab{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.68rem;
letter-spacing:.11em;text-transform:uppercase;color:var(--olive);margin:1.15rem 0 .25rem}
.val{background:var(--surface);border:1px solid var(--rule);padding:.65rem .8rem;
white-space:pre-wrap;color:var(--ink);font-size:.95rem;line-height:1.55;
-webkit-user-select:all;user-select:all;cursor:text}
.val.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.88rem}
.why{font-size:.86rem;color:var(--faint);margin:.35rem 0 0}
.pick{display:inline-block;font-family:ui-monospace,Menlo,Consolas,monospace;
font-size:.6rem;letter-spacing:.12em;text-transform:uppercase;color:#fff;
background:var(--clay);padding:.14rem .42rem;vertical-align:.12em;margin-left:.45rem}
.rule{border-left:3px solid var(--clay);padding:.1rem 0 .1rem 1rem;margin:0 0 1rem}
.rule b{color:var(--clay);display:block;margin-bottom:.15rem}
.rule p{font-size:.92rem;margin:0}
table{border-collapse:collapse;font-size:.93rem;margin:0 0 .8rem}
td{padding:.32rem 1.1rem .32rem 0;border-bottom:1px solid var(--hair);
font-variant-numeric:tabular-nums}
td:first-child{color:var(--soft)}
figure{margin:0 0 1.3rem}
figure img{display:block;max-width:100%;height:auto;border:1px solid var(--rule);
background:var(--surface)}
figcaption{font-size:.82rem;color:var(--faint);margin-top:.4rem}
footer{margin-top:2.6rem;padding-top:1rem;border-top:1px solid var(--rule);
font-size:.78rem;color:var(--faint)}
@media (prefers-color-scheme:dark){
:root{--paper:#1C1109;--surface:#2A1B0D;--ink:#F1E7D7;--soft:#C4B29B;
--faint:#9C8B75;--clay:#C47A52;--gold:#D6A84E;--olive:#B09765;
--rule:rgba(241,231,215,.2);--hair:rgba(241,231,215,.1)}}
"""

HTML = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Auralis Natura</title><style>{css}</style></head>
<body><div class="wrap"><header><p class="kick">Auralis Natura · Betriebsunterlage</p>
<h1>{title}</h1><p class="lede">{lede}</p>
<p style="font-size:.9rem">Werte antippen — sie markieren sich mit einem Tipp,
dann Kopieren. Alles auch auf der <a href="{sheet}">Setup-Seite</a>.</p>
</header>{body}
<footer>Werte aus index.html, portal/config/config.json und
portal/config/availability.json · Regeln aus CLAUDE.md §2 ·
Bilder aus brand/masters/seal-1600.png über brand/make_social_avatars.py</footer>
</div></body></html>"""


def fig(n, t):
    return f'<p class="fig">Fig. {n:02d} — {esc(t)}</p>'


def h2(t):
    return f"<h2>{esc(t)}</h2>"


def p(t, cls=""):
    return f'<p{f" class={cls}" if cls else ""}>{t}</p>'


def val(text, mono=True, pick=False):
    return f'<div class="val{" mono" if mono else ""}">{esc(text)}</div>'


def field(name, value_, why, pick=False):
    tag = '<span class="pick">nimm dieses</span>' if pick else ""
    return (f'<p class="lab">{esc(name)}{tag}</p>{val(value_)}'
            f'<p class="why">{why}</p>')


def rule(t, b):
    return f'<div class="rule"><b>{t}</b><p>{b}</p></div>'


def image(url, cap, w=340):
    return (f'<figure><a href="{url}"><img src="{url}" alt="" width="{w}"></a>'
            f'<figcaption>{cap}<br><a href="{url}">Bild öffnen und sichern</a>'
            f' · auf dem iPhone: lange drücken → Sichern</figcaption></figure>')


def page(title, lede, body):
    return HTML.format(title=esc(title), lede=lede, css=CSS, body=body, sheet=SHEET)


# ─────────────────────────────────────────────────────────────────── sheets ──
def whatsapp():
    b = [fig(1, "zuerst prüfen"), h2("Die Nummer"),
         p("WhatsApp Business und das normale WhatsApp können nicht gleichzeitig "
           "dieselbe Nummer benutzen. <b>+34 614 489 656</b> steht auf der Website "
           "als Geschäftsnummer."),
         p("<b>Liegt sie heute im privaten WhatsApp:</b> die Business-App bietet beim "
           "ersten Start an, den Verlauf zu übernehmen — danach ist die Nummer nur "
           "noch geschäftlich. Einbahnstraße.", "why"),
         p("<b>Trennen:</b> zweite Nummer nötig (eSIM, ~5 €/Monat). Dann müsste die "
           "Website-Nummer geändert werden.", "why"),
         fig(2, "Profilbild"), h2("Profilbild"),
         image(AVATAR, "<b>Zimtbraun, 640 × 640</b> — nimm dieses. WhatsApp schneidet "
                       "rund zu und zeigt es bei ~48 px; auf dem hellen Grund einer "
                       "Chatliste braucht das Bild eine eigene dunkle Silhouette.", 240),
         fig(3, "Profilfelder"), h2("Was in welches Feld gehört")]
    for n, v, w in FIELDS:
        b.append(field(n, v, w, pick=(n == "Kategorie")))
    b += [fig(4, "Profilbeschreibung"), h2("Beschreibung · max. 256 Zeichen")]
    for lang, tag, t in DESCRIPTIONS:
        b.append(f'<p class="lab">{esc(lang)} ({len(t)}/256)'
                 f'{"<span class=pick>empfohlen</span>" if tag == "empfohlen" else ""}</p>'
                 f'{val(t, mono=False)}')
    b += [fig(5, "Öffnungszeiten"), h2("Sprechzeiten"),
          p("Genau die Fenster, die die Buchungsseite anbietet (Europe/Madrid). So "
            "kann niemand eine Zeit sehen, die es im Kalender nicht gibt."),
          "<table>" + "".join(
              f"<tr><td>{esc(d)}</td><td>{esc(a)}</td><td>{esc(x) if x else '—'}</td></tr>"
              for d, a, x in HOURS) + "</table>",
          fig(6, "Automatische Nachrichten"), h2("Begrüßung und Abwesenheit"),
          '<p class="lab">Begrüßungsnachricht</p>' + val(GREETING, False),
          '<p class="lab">Abwesenheitsnachricht</p>' + val(AWAY, False),
          fig(7, "Schnellantworten"), h2("Drei Kürzel"),
          p("In der App unter Tools → Schnellantworten.")]
    for k, v in QUICK_REPLIES:
        b.append(f'<p class="lab">{esc(k)}</p>{val(v, False)}')
    b += [fig(8, "nicht verhandelbar"), h2("Drei Regeln"),
          rule("Keine Gesundheitskategorie",
               "„Medical &amp; Health“ ist auf einem öffentlichen Profil eine implizite "
               "Berufsbehauptung. <i>Dietista-nutricionista</i> ist in Spanien nach "
               "Ley 44/2003 geschützt."),
          rule("Keine Gesundheitsdaten im Chat",
               "Beschwerden, Medikamente, Schwangerschaft — besondere Kategorie nach "
               "Art. 9 DSGVO, und dann auf Metas Servern statt im verschlüsselten "
               "Portal. WhatsApp ist für „wann hast du Zeit“."),
          rule("Keine Beratung per Chat",
               "Freundlich auf das Erstgespräch verweisen — dafür ist /termin da. "
               "Bei Alarmzeichen: zur Ärztin, im Notfall 112.")]
    return page("WhatsApp Business einrichten",
                "Jedes Feld mit dem Text zum Kopieren.", "".join(b))


def facebook():
    b = [fig(1, "Reihenfolge"), h2("Facebook zuerst"),
         p("Ein Instagram-Business-Konto wird mit einer bestehenden Facebook-Seite "
           "verbunden, und diese Verbindung braucht man später für Werbung und "
           "gemeinsame Nachrichten. Andersherum ist es Nacharbeit."),
         p("Eine <b>Seite</b>, kein zweites Privatprofil — Seiten dürfen geschäftlich "
           "sein, Privatprofile laut Facebooks Bedingungen nicht."),
         fig(2, "Bilder"), h2("Bilder"),
         image(AVATAR, "<b>Profilbild</b> — rund dargestellt, 170 × 170 am Rechner.", 200),
         image(f"{IMG}/auralis-facebook-cover.jpg",
               "<b>Titelbild</b> 1640 × 856 px. " + FB_COVER.split(". ", 1)[1], 420),
         fig(3, "Seiteninfos"), h2("Was in welches Feld gehört")]
    for n, v, w in FB_FIELDS:
        b.append(field(n, v, w, pick=(n == "Kategorie 1")))
    b += [fig(4, "Kurzbeschreibung"), h2("Beschreibung · max. 255 Zeichen"),
          p("Identisch mit WhatsApp — ein Profil, eine Aussage."),
          f'<p class="lab">Deutsch ({len(DESCRIPTIONS[0][2])}/255)'
          f'<span class="pick">empfohlen</span></p>{val(DESCRIPTIONS[0][2], False)}',
          f'<p class="lab">English ({len(DESCRIPTIONS[1][2])}/255)</p>'
          f'{val(DESCRIPTIONS[1][2], False)}',
          fig(5, "nicht verhandelbar"), h2("Drei Regeln"),
          rule("Keine geschützte Berufsbezeichnung",
               "Weder „Ernährungsberaterin“ noch „Nutritionist“ noch „Dietitian“ — "
               "in Kategorie, Beschreibung oder Beiträgen."),
          rule("Keine Vorher-Nachher-Versprechen",
               "Metas Werberichtlinien verbieten Vorher-Nachher-Bilder und "
               "unrealistische Ergebnisse ausdrücklich; die Richtlinie zu persönlichen "
               "Eigenschaften verbietet zu unterstellen, du wüsstest etwas über den "
               "Gesundheitszustand der Leserin („Fühlst du dich ständig erschöpft?“)."),
          rule("Bewertungen bleiben echt",
               "Empfehlungen einschalten ist gut — aber nur echte Stimmen.")]
    return page("Facebook-Seite einrichten",
                "Die Seite, die Instagram später braucht.", "".join(b))


def instagram():
    b = [fig(1, "Profilbild"), h2("Profilbild"),
         image(AVATAR, "<b>Dasselbe Siegel wie überall</b> — rund bei 320 × 320. "
                       "Ein Bild über alle Profile, damit dich Leute wiedererkennen.", 200),
         fig(2, "Profilfelder"), h2("Was in welches Feld gehört")]
    for n, v, w in IG_FIELDS:
        b.append(field(n, v, w, pick=(n == "Kontotyp")))
    b += [fig(3, "Bio"), h2("Steckbrief · max. 150 Zeichen"),
          p("Das engste Textfeld von allen. Zeilenumbrüche zählen mit. Der Pfeil "
            "zeigt auf den Link direkt darunter.")]
    for lang, tag, t in IG_BIOS:
        b.append(f'<p class="lab">{esc(lang)} ({len(t)}/150)'
                 f'{"<span class=pick>empfohlen</span>" if tag else ""}</p>'
                 f'{val(t, mono=False)}')
    b += [fig(4, "die ersten neun Beiträge"), h2("Was zuerst hochladen"),
          p("Ein leeres Profil überzeugt niemanden, der über den Button kommt. "
            "Neun Beiträge füllen das sichtbare Raster; Material liegt im Projekt:"),
          p("• Porträt und Beratungsfoto (<code>images/desiree-*.jpg</code>)<br>"
            "• die vier Zertifikate (<code>images/cert-*.jpg</code>)<br>"
            "• die drei Angebote Klarheit · Wandel · Balance, je ein Satz<br>"
            "• ein Beitrag „Was Auralis Natura <i>nicht</i> ist“ — Positionierung "
            "und Compliance in einem", "why"),
          fig(5, "nicht verhandelbar"), h2("Drei Regeln"),
          rule("Keine Diagnosen, keine Heilversprechen",
               "„Diese 3 Lebensmittel bei Hashimoto“ ist eine Behandlungsaussage. "
               "„Was die Studienlage zu X sagt — und was nicht“ ist Bildung. Der "
               "Unterschied ist die ganze Geschäftsgrundlage."),
          rule("Keine Gesundheitsdaten in DMs",
               "Dieselbe Art-9-Frage wie bei WhatsApp, nur öffentlicher. Auch nicht "
               "in den Kommentaren."),
          rule("Keine erfundenen Stimmen",
               "Keine Testimonials und keine Vorher-Nachher-Bilder ohne echte "
               "Grundlage und ausdrückliche schriftliche Einwilligung.")]
    return page("Instagram einrichten",
                "Business-Konto, verbunden mit der Facebook-Seite.", "".join(b))


def linkedin():
    b = [fig(1, "Bilder"), h2("Bilder"),
         image(f"{IMG}/auralis-linkedin-portrait.jpg",
               "<b>Profilfoto Personenprofil</b> — dein Gesicht, nicht das Siegel. "
               "Menschen suchen hier nach einer Person und einer Qualifikation.", 200),
         image(f"{IMG}/auralis-linkedin-banner.jpg",
               "<b>Profil-Banner</b> 1584 × 396 px. Links absichtlich frei — dort "
               "liegt das Profilfoto.", 420),
         image(f"{IMG}/auralis-linkedin-company-cover.jpg",
               "<b>Titelbild Unternehmensseite</b> 1128 × 191 px.", 420),
         image(AVATAR, "<b>Logo Unternehmensseite</b> 300 × 300 px.", 170),
         fig(2, "Profilfelder"), h2("Was in welches Feld gehört")]
    for n, v, w in LI_FIELDS:
        b.append(field(n, v, w, pick=(n == "Berufsbezeichnung / Headline")))
    b += [fig(3, "Info / About"), h2("Info-Bereich · max. 2.600 Zeichen"),
          p("Nur die ersten <b>zwei Zeilen</b> sind ohne Klick auf „mehr“ sichtbar — "
            "deshalb steht der Satz, um den es geht, ganz oben. Der Compliance-Absatz "
            "gehört hinein, nicht in eine Fußnote."),
          f'<p class="lab">Deutsch ({len(LI_ABOUT)}/2600)</p>{val(LI_ABOUT, False)}',
          fig(4, "nicht verhandelbar"), h2("Drei Regeln")]
    for t, x in LI_GUARDS:
        b.append(rule(t, x))
    return page("LinkedIn einrichten",
                "Personenprofil aktualisieren und Unternehmensseite anlegen. "
                "Das Personenprofil bringt die Reichweite — auf LinkedIn folgt man "
                "Menschen, nicht Logos.", "".join(b))


def google():
    b = [fig(1, "Bilder"), h2("Bilder"),
         image(AVATAR, "<b>Logo</b> — quadratisch.", 170),
         image(f"{IMG}/auralis-google-cover.jpg", "<b>Titelbild</b> 1024 × 576 px.", 400),
         p("Danach mindestens drei weitere Fotos hochladen — Profile mit Fotos werden "
           "deutlich häufiger angeklickt. Porträt, Beratungsfoto und ein Zertifikat "
           "reichen für den Anfang.", "why"),
         fig(2, "Profilfelder"), h2("Was in welches Feld gehört")]
    for n, v, w in G_FIELDS:
        b.append(field(n, v, w, pick=(n in ("Hauptkategorie", "Dienstgebiet statt Adresse"))))
    b += [fig(3, "Beschreibung"), h2("Beschreibung · max. 750 Zeichen"),
          p("Google liest diesen Text für die Suche mit — deshalb stehen die Begriffe, "
            "unter denen du gefunden werden willst, hier in ganzen Sätzen."),
          f'<p class="lab">Deutsch ({len(GOOGLE_DESC)}/750)</p>{val(GOOGLE_DESC, False)}',
          fig(4, "Öffnungszeiten"), h2("Öffnungszeiten"),
          "<table>" + "".join(
              f"<tr><td>{esc(d)}</td><td>{esc(a)}</td><td>{esc(x) if x else '—'}</td></tr>"
              for d, a, x in HOURS) + "</table>",
          fig(5, "nicht verhandelbar"), h2("Drei Regeln")]
    for t, x in G_GUARDS:
        b.append(rule(t, x))
    return page("Google-Unternehmensprofil einrichten",
                "Google Maps <i>und</i> der Kasten rechts in der Suche — dieselbe "
                "Sache, und das einzige der Profile, das echte Suchnachfrage "
                "abgreift. Anlegen unter <b>business.google.com</b>.", "".join(b))


def bildmaterial():
    rows = [
        (AVATAR, "Profilbild · zimtbraun", "640 × 640 PNG",
         "WhatsApp, Facebook, Instagram, LinkedIn-Unternehmensseite, Google-Logo. "
         "<b>Das Standard-Profilbild.</b>", 220, True),
        (f"{IMG}/auralis-avatar-cinnamon-1000.png", "Profilbild · zimtbraun, groß",
         "1000 × 1000 PNG", "Wenn eine Plattform mehr als 640 px will.", 180, False),
        (f"{IMG}/auralis-avatar-cream-640.png", "Profilbild · creme",
         "640 × 640 PNG", "Alternative für dunkle Hintergründe. In einer hellen "
         "Chatliste verschwimmt sie — dort das zimtbraune nehmen.", 180, False),
        (f"{IMG}/auralis-linkedin-portrait.jpg", "Porträt", "JPG",
         "LinkedIn-<b>Personen</b>profil. Dort gehört dein Gesicht hin, nicht das "
         "Siegel.", 180, False),
        (f"{IMG}/auralis-facebook-cover.jpg", "Titelbild Facebook", "1640 × 856 JPG",
         "Angezeigt 820 × 312 (Desktop) und 640 × 360 (Handy).", 400, False),
        (f"{IMG}/auralis-linkedin-banner.jpg", "Banner LinkedIn", "1584 × 396 JPG",
         "Links frei — dort liegt das Profilfoto.", 400, False),
        (f"{IMG}/auralis-linkedin-company-cover.jpg", "Titelbild LinkedIn-Firma",
         "1128 × 191 JPG", "", 400, False),
        (f"{IMG}/auralis-google-cover.jpg", "Titelbild Google", "1024 × 576 JPG",
         "", 380, False),
    ]
    b = [fig(1, "Qualität"), h2("Woher die Bilder kommen"),
         p("Alle Bilder werden aus <b>brand/masters/seal-1600.png</b> erzeugt — dem "
           "1600-px-Master aus deiner Flyer-Übergabe, mit sauberem Alphakanal. Bis "
           "zum 9. August stammten sie aus einem 426-px-Ausschnitt der Logo-Datei "
           "und mussten hochskaliert werden; jetzt wird nur noch verkleinert, was "
           "immer die bessere Richtung ist."),
         p("Die Dateien liegen auf der eigenen Website, nicht als Anhang — so "
           "funktionieren sie auf jedem Gerät und bleiben erreichbar.", "why"),
         fig(2, "alle Dateien"), h2("Zum Herunterladen")]
    for url, name, spec, note, w, pick in rows:
        tag = '<span class="pick">Standard</span>' if pick else ""
        b.append(f'<p class="lab">{esc(name)} · {esc(spec)}{tag}</p>')
        b.append(image(url, note or f"{esc(name)}, {esc(spec)}.", w))
    b += [fig(3, "wenn ein Bild nicht lädt"), h2("Cloudflare"),
          rule("Bot-Schutz kann Bilder blockieren",
               "Für <code>auralisnatura.com</code> ist derzeit Cloudflares "
               "Bot-Schutz aktiv. Im Browser passierst du ihn automatisch, "
               "E-Mail-Programme manchmal nicht — dann zeigt das Vorschaubild "
               "nichts, der Link funktioniert aber trotzdem. Dauerhaft lösen: "
               "Cloudflare → Security → Bots → Bot Fight Mode für diese Domain aus.")]
    return page("Bildmaterial", "Jedes Bild, seine Maße und wofür es gedacht ist.",
                "".join(b))


def corporate_id():
    decisions = [
        ("Quadratische Ecken, überall",
         "<code>--r</code> und <code>--r-lg</code> sind <code>0px</code>. Nie ein "
         "<code>border-radius</code> — es ist die prägendste strukturelle "
         "Entscheidung des Systems, und die Karte ist darauf gebaut."),
        ("Das Siegel ist die wiederkehrende Marke",
         "Auf der Karte zweimal: klein und deckend als Signatur, und groß mit "
         "<b>10 % Deckkraft über den Rand hinauslaufend</b> als Wasserzeichen. "
         "Dieses Wasserzeichen ist der Signature-Move der Marke — für große ruhige "
         "Flächen, nie als laute Dekoration."),
        ("Clay ist Akzent, nie Fläche",
         "<code>#A8492A</code> für Rollenzeile, Marken und Icons — kleine, präzise, "
         "wertvolle Setzungen. Ein primärer Clay-Button pro Ansicht. Große Flächen "
         "sind Papier, Creme oder das dunkle Braunband."),
        ("Gold ist strukturell, nicht glänzend",
         "Haarlinien, Kapitälchen, das Siegel — flach. Verspiegeltes oder "
         "Verlaufs-Gold wurde als altmodisch verworfen."),
        ("Kanten sind Haarlinien, Schatten weit und weich",
         "Der Rahmen der Karte ist eine 0,2-mm-Haarlinie. Nie enge, dunkle Schatten."),
        ("Zurückhaltung ist das Premium-Signal",
         "Die Karte druckt mit etwa <b>4 % Farbdeckung</b> — das Papier arbeitet. "
         "Im Web: großzügiger Weißraum, wenige Elemente pro Bildschirm."),
        ("Der Name bricht nie",
         "„Desiree“ und „Gruber“ stehen immer auf einer Zeile, bei jeder Breite."),
        ("Nie trennen",
         "<code>hyphens: none</code> durchgehend. Deutsche Komposita werden über "
         "kleinere Schrift gelöst, nicht über Worttrennung. Jede Überschrift bei "
         "360 px prüfen."),
    ]
    b = [fig(1, "Grundlage"), h2("Die Karte ist jetzt die Referenz"),
         p("Zwei fertige Übergaben liegen im Projekt unter <code>brand/print/</code>: "
           "die freigegebene <b>Visitenkarte 5B „Reine Fläche“</b> samt gebundenem "
           "Design-System und der <b>A5/A6-Flyer</b> in drei Sprachen mit "
           "Druck-Prüfung. Beides ist vermessene, gedruckte Arbeit — sie hat "
           "Vorrang vor älteren Notizen im Projekt, wo sie sich unterscheiden."),
         fig(2, "entschieden"), h2("Acht Festlegungen")]
    for t, x in decisions:
        b.append(rule(t, x))
    b += [fig(3, "Druckgeometrie"), h2("Zwei Zahlen, die niemand „korrigieren“ darf"),
          rule("A6 ist 95 × 148 mm, A5 ist 138 × 210 mm",
               "Zehn Millimeter schmaler als DIN bei gleicher Höhe — bewusst, damit "
               "die Proportion näher am Goldenen Schnitt liegt (1 : 1,56 statt "
               "1 : 1,41). Kein Fehler."),
          rule("Keine Seite darf ihre Geometrie vom Inhalt ableiten",
               "Feste Seitenbox, Artboard mit festem Versatz absolut positioniert. "
               "Genau das war die Ursache eines echten Registerfehlers, bei dem die "
               "Rückseite 20 mm höher gedruckt wurde als die Vorderseite. Die "
               "CI-Prüfung im Flyer-Paket sichert es ab."),
          fig(4, "Dateien"), h2("Master-Dateien"),
          p("In <code>brand/masters/</code> — die besten Kopien, die existieren:"),
          val("seal-1600.png                 das Siegel, 1600 px, sauberes Alpha\n"
              "seal-gold-1200.png            Gold auf Dunkel (Karte, dunkle Flächen)\n"
              "seal-brown-1200.png           Braun auf Hell\n"
              "seal-gold-watermark-1200.png  für das 10-%-Wasserzeichen\n"
              "qr-website-1480.png           QR auf auralisnatura.com"),
          rule("Ein Siegel, das nicht verwendet werden darf",
               "<code>handover/assets/emblem_seal_360.png</code> ist ein "
               "<b>anderes, deutlich verspielteres Siegel</b>. Es sieht auf den "
               "ersten Blick ähnlich aus und ist es nicht. Nie kundenseitig "
               "verwenden.")]
    return page("Corporate ID", "Was Visitenkarte und Flyer bereits entschieden haben.",
                "".join(b))


SHEETS = [
    ("01-whatsapp-business", whatsapp),
    ("02-facebook-seite", facebook),
    ("03-instagram", instagram),
    ("04-linkedin", linkedin),
    ("05-google-unternehmensprofil", google),
    ("06-bildmaterial", bildmaterial),
    ("07-corporate-id", corporate_id),
]

def minify(h: str) -> str:
    """These files travel as base64 inside one mail, so bytes are the budget.
    Strip CSS whitespace and inter-tag newlines only — never inside a tag, and
    never inside the .val blocks, whose content is white-space: pre-wrap and
    IS the copy-paste payload."""
    head, sep, rest = h.partition("<style>")
    css, sep2, tail = rest.partition("</style>")
    css = re.sub(r"\s*\n\s*", "", css)
    css = re.sub(r";\}", "}", css)
    out = head + sep + css + sep2 + tail
    # Collapse only the newlines the templates introduce between tags.
    out = re.sub(r">\n+<", "><", out)
    return out


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for name, fn in SHEETS:
        html = minify(fn())
        (OUT / f"{name}.html").write_text(html, encoding="utf-8")
        b64 = base64.b64encode(html.encode()).decode()
        (OUT / f"{name}.b64").write_text(b64)
        total += len(b64)
        print(f"  {name:32} {len(html.encode()) // 1024:>3} KB html   "
              f"{len(b64) // 1024:>3} KB base64")
    print(f"  {'TOTAL base64':32} {total // 1024:>3} KB")
