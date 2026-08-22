#!/usr/bin/env python3
"""build_flowmap.py — die Prozess- und Datenkarte von Auralis Natura als PDF.

WOFÜR
  Ein Bild davon, was zwischen dem ersten Klick einer Besucherin und dem
  abgeschlossenen Programm passiert: welcher Schritt LÄUFT VON SELBST, wo
  DESIREE ENTSCHEIDET, welche Mail wann rausgeht und wo die Daten landen.
  Nicht als Fließtext, sondern als Karte, die man neben die Konsole legt.

WARUM ALS WERKZEUG UND NICHT ALS EINMAL-DOKUMENT
  Der Ablauf ändert sich mit dem Code. Ein Generator lässt sich nach jeder
  Änderung neu laufen; ein hübsches PDF von letzter Woche wird still falsch.

    python3 tools/build_flowmap.py            # → output_docs/Auralis-Prozesskarte.pdf
    python3 tools/build_flowmap.py --html     # nur das HTML (schneller zum Prüfen)

Gestalt: das Marken-System — eckig, Gold-Haarlinien, Fraunces, Clay als
einziger Akzent. Schriften sind base64 eingebettet (ein PDF darf offline
nicht fontlos werden — derselbe Fehler wie früher beim Bericht).
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import cfg, render  # noqa: E402

SEAL = ROOT.parent / "brand" / "masters" / "seal-1600.png"


def b64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


# ── Bausteine ────────────────────────────────────────────────────────────────
def chain(*steps: tuple[str, str]) -> str:
    """Die waagrechte Kette oben auf jeder Stationsseite.
    steps = (kind, text) mit kind ∈ auto | you | mail | data | client"""
    out = []
    for i, (kind, text) in enumerate(steps):
        if i:
            out.append('<span class="arw">▸</span>')
        out.append(f'<span class="node {kind}">{text}</span>')
    return '<div class="chain">' + "".join(out) + "</div>"


def cols(auto: list[str], you: list[str], data: list[str]) -> str:
    def ul(items):
        return "".join(f"<li>{x}</li>" for x in items)
    return f"""<div class="cols">
  <div class="col auto"><h4><i>⚙</i> Läuft von selbst</h4><ul>{ul(auto)}</ul></div>
  <div class="col you"><h4><i>✋</i> Du entscheidest</h4><ul>{ul(you)}</ul></div>
  <div class="col data"><h4><i>🗄</i> Daten &amp; Post</h4><ul>{ul(data)}</ul></div>
</div>"""


def station(num: str, title: str, sub: str, body: str, note: str = "") -> str:
    n = f'<div class="note">{note}</div>' if note else ""
    return f"""<section class="page">
  <div class="sec-head"><span class="fig">Station {num}</span>
    <h2>{title}</h2><p class="sub">{sub}</p></div>
  {body}{n}
</section>"""


def opts(*rows: tuple[str, str]) -> str:
    """Ihre Handlungsmöglichkeiten: exakt der Knopf, dann was er auslöst."""
    tr = "".join(f'<tr><td class="btn">{b}</td><td>{w}</td></tr>' for b, w in rows)
    return f'<table class="opts"><tr><th>Knopf in der Konsole</th><th>Was dann passiert</th></tr>{tr}</table>'


# ── Das Dokument ─────────────────────────────────────────────────────────────
def build_html() -> str:
    today = _dt.date.today().strftime("%d.%m.%Y")
    seal = b64(SEAL)

    css = f"""
{render._font_css()}
:root{{--ink:#2A211A;--ink-soft:#5C4A3A;--ink-faint:#75685A;--forest:#3D2719;
 --forest-deep:#221305;--clay:#A8492A;--clay-d:#8F3D22;--gold:#AD7A32;
 --gold-bright:#D6A84E;--sage:#927B4A;--paper:#F5EEE0;--cream:#FBF6EB;
 --pine:#3c7a4e;--hair:rgba(61,39,25,.16);--gold-hair:rgba(173,122,50,.45);
 --fd:'Fraunces',Georgia,serif;--fb:'Hanken Grotesk',system-ui,sans-serif}}
*{{box-sizing:border-box;border-radius:0}}
@page{{size:A4;margin:14mm 13mm 12mm}}
body{{margin:0;font-family:var(--fb);font-size:9.3pt;line-height:1.5;color:var(--ink);
 background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
h1,h2,h3,h4{{font-family:var(--fd);font-weight:600;margin:0}}
.page{{page-break-after:always;break-after:page}}
.page:last-child{{page-break-after:auto;break-after:auto}}

/* ── Deckblatt ── */
.cover{{position:relative;height:258mm;background:var(--forest);color:var(--cream);
 padding:26mm 20mm;overflow:hidden;display:flex;flex-direction:column}}
.cover .wm{{position:absolute;right:-52mm;bottom:-52mm;width:150mm;opacity:.10}}
.cover .kick{{font-size:8pt;letter-spacing:.30em;text-transform:uppercase;
 color:var(--gold-bright);font-weight:600}}
.cover h1{{font-size:29pt;line-height:1.10;margin:7mm 0 0;max-width:152mm;hyphens:none}}
.cover h1 em{{font-style:italic;color:var(--gold-bright)}}
.cover .lead{{margin-top:6mm;max-width:118mm;font-size:11pt;line-height:1.65;
 color:#E8DCC8}}
.cover .rule{{width:34mm;height:2px;background:var(--gold);margin:9mm 0}}
.cover .meta{{margin-top:auto;font-size:8.4pt;color:#C9B79C;line-height:1.7}}
.cover .meta b{{color:var(--cream)}}
.cover .meta code{{background:transparent;color:#C9B79C;padding:0}}
.legend{{margin-top:8mm;display:grid;grid-template-columns:1fr 1fr;gap:3mm 6mm;
 max-width:132mm}}
.legend div{{font-size:8.6pt;color:#E8DCC8;border-left:2px solid;padding-left:3.5mm}}
.legend .l1{{border-color:var(--pine)}} .legend .l2{{border-color:var(--clay-soft,#C47A52)}}
.legend .l3{{border-color:var(--gold)}} .legend .l4{{border-color:#8C7E6E}}
.legend b{{color:#fff}}

/* ── Abschnittsköpfe ── */
.sec-head{{border-bottom:1px solid var(--gold-hair);padding-bottom:2.5mm;margin-bottom:5mm}}
.fig{{font-family:ui-monospace,Menlo,monospace;font-size:7.4pt;letter-spacing:.20em;
 text-transform:uppercase;color:var(--gold);font-weight:600}}
h2{{font-size:19pt;line-height:1.12;margin:1.5mm 0 1mm}}
.sub{{margin:0;color:var(--ink-soft);font-size:9.4pt;max-width:150mm}}

/* ── Kette ── */
.chain{{display:flex;align-items:stretch;flex-wrap:wrap;gap:0;margin:0 0 5mm}}
.node{{flex:1 1 0;min-width:26mm;padding:3mm 3.2mm;font-size:8.1pt;line-height:1.38;
 border:1px solid var(--hair);border-top:2.5px solid var(--ink-faint);background:var(--cream)}}
.node.auto{{border-top-color:var(--pine);background:rgba(60,122,78,.06)}}
.node.you{{border-top-color:var(--clay);background:rgba(168,73,42,.07);font-weight:600}}
.node.mail{{border-top-color:var(--gold);background:rgba(173,122,50,.08)}}
.node.data{{border-top-color:#8C7E6E;background:#F7F3EA}}
.node.client{{border-top-color:var(--forest);background:var(--paper)}}
.arw{{align-self:center;color:var(--gold);padding:0 1.6mm;font-size:11pt}}

/* ── Drei Spalten ── */
.cols{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:4mm;margin-bottom:4mm}}
.col{{border:1px solid var(--hair);border-top:2.5px solid;padding:3.2mm 3.6mm;background:#fff}}
.col.auto{{border-top-color:var(--pine)}} .col.you{{border-top-color:var(--clay)}}
.col.data{{border-top-color:#8C7E6E}}
.col h4{{font-size:8.6pt;letter-spacing:.02em;margin-bottom:2mm;display:flex;gap:1.6mm;align-items:baseline}}
.col.auto h4{{color:var(--pine)}} .col.you h4{{color:var(--clay-d)}} .col.data h4{{color:var(--ink-faint)}}
.col h4 i{{font-style:normal;font-size:9.5pt}}
.col ul{{margin:0;padding-left:3.6mm}}
.col li{{margin-bottom:1.5mm;font-size:8.2pt;line-height:1.45}}
.col li:last-child{{margin-bottom:0}}
code{{font-family:ui-monospace,Menlo,monospace;font-size:7.4pt;background:var(--paper);
 padding:.5mm 1.1mm;color:var(--ink-soft)}}

/* ── Optionen-Tabelle ── */
table.opts{{width:100%;border-collapse:collapse;margin-top:1mm}}
table.opts th{{font-size:7.2pt;letter-spacing:.14em;text-transform:uppercase;
 color:var(--ink-faint);text-align:left;padding:0 3mm 1.6mm;border-bottom:1px solid var(--gold-hair);font-weight:600}}
table.opts td{{padding:2.1mm 3mm;border-bottom:1px solid var(--hair);
 font-size:8.4pt;vertical-align:top;line-height:1.45}}
table.opts td.btn{{width:52mm;font-weight:600;color:var(--clay-d);white-space:nowrap}}
table.opts tr:last-child td{{border-bottom:none}}

/* ── Hinweiskästen ── */
.note{{margin-top:4mm;border:1px solid var(--gold-hair);border-left:3px solid var(--gold);
 background:rgba(173,122,50,.06);padding:3mm 4mm;font-size:8.3pt;line-height:1.55;color:var(--ink-soft)}}
.note b{{color:var(--ink)}}
.warn{{border-color:rgba(168,73,42,.4);border-left-color:var(--clay);background:rgba(168,73,42,.06)}}
.warn b{{color:var(--clay-d)}}

/* ── Speicher-Karten ── */
.stores{{display:grid;grid-template-columns:1fr 1fr;gap:4mm}}
.store{{border:1px solid var(--hair);border-top:2.5px solid var(--sage);padding:3.4mm 4mm;background:#fff}}
.store h4{{font-size:10pt}}
.store .pth{{font-family:ui-monospace,Menlo,monospace;font-size:7.4pt;color:var(--gold);
 margin:.8mm 0 2mm;word-break:break-all}}
.store ul{{margin:0;padding-left:3.6mm}} .store li{{font-size:8.2pt;margin-bottom:1.2mm;line-height:1.45}}

/* ── Übersicht ── */
.lane{{display:grid;grid-template-columns:16mm 1fr;gap:0;border-left:2px solid var(--gold-hair);
 margin-left:2mm}}
.lane .st{{padding:2.4mm 0 2.4mm 4mm;border-bottom:1px solid var(--hair);position:relative}}
.lane .st:last-child{{border-bottom:none}}
.lane .n{{font-family:var(--fd);font-size:12pt;color:var(--gold);padding:2.4mm 0 0;
 text-align:right;padding-right:3mm;border-bottom:1px solid var(--hair)}}
.lane .n:last-of-type{{border-bottom:none}}
.lane .st b{{font-family:var(--fd);font-size:10.5pt;display:block;margin-bottom:.8mm}}
.lane .st .who{{font-size:7.6pt;letter-spacing:.1em;text-transform:uppercase;font-weight:600}}
.who.a{{color:var(--pine)}} .who.y{{color:var(--clay-d)}} .who.b{{color:var(--gold)}}
.lane .st p{{margin:.8mm 0 0;font-size:8.3pt;color:var(--ink-soft);line-height:1.45}}
.foot{{margin-top:6mm;border-top:1px solid var(--gold-hair);padding-top:2.5mm;
 font-size:7.4pt;color:var(--ink-faint);line-height:1.5}}
"""

    # ── Deckblatt ────────────────────────────────────────────────────────────
    cover = f"""<section class="page cover">
  {'<img class="wm" src="data:image/png;base64,' + seal + '">' if seal else ''}
  <div class="kick">Auralis Natura · Betriebshandbuch</div>
  <h1>Wie eine Anfrage zu einer<br>betreuten Klientin wird —<br><em>und wer was entscheidet.</em></h1>
  <div class="rule"></div>
  <p class="lead">Jede Station des Weges: was das System von selbst tut, wo deine
  Entscheidung gebraucht wird, welche E-Mail wann hinausgeht und wo die Daten
  liegen bleiben. Zum Danebenlegen, während du in der Betriebskonsole arbeitest.</p>
  <div class="legend">
    <div class="l1"><b>⚙ Läuft von selbst.</b> Das System handelt ohne dich —
      auch nachts, auch wenn du nicht hinsiehst.</div>
    <div class="l2"><b>✋ Du entscheidest.</b> Nichts davon passiert automatisch.
      Ohne deinen Klick bleibt der Vorgang stehen.</div>
    <div class="l3"><b>✉ Post geht raus.</b> Entweder sofort versendet oder als
      Gmail-Entwurf, den du selbst absendest.</div>
    <div class="l4"><b>🗄 Daten bleiben liegen.</b> Verschlüsselt auf deinem
      Server in Frankfurt, stündlich gesichert.</div>
  </div>
  <div class="meta">Dr. rer. nat. Desiree Gruber · Auralis Natura, Barcelona<br>
    Stand <b>{today}</b> · erzeugt aus dem laufenden System
    (<code style="color:#C9B79C">tools/build_flowmap.py</code>)</div>
</section>"""

    # ── Übersicht ────────────────────────────────────────────────────────────
    lanes = [
        ("01", "Anfrage", "a", "Besucherin bucht auf /book · Termin wird gehalten, "
         "Datensatz angelegt, drei Mails gehen raus — alles ohne dich."),
        ("02", "Erstgespräch", "y", "Du führst das Gespräch und hältst es in vier "
         "Feldern fest. Der Knopf öffnet die Notizen, bevor er die Phase wechselt."),
        ("03", "Gewonnen · Zahlung & Zugang", "b", "Zwei Wege: du setzt Paket und "
         "Zahlung von Hand — oder sie kauft über Stripe und alles passiert in einem Moment."),
        ("04", "Programm-Termine", "y", "Die Konsole schlägt den Rhythmus vor, du "
         "verschiebst per Dropdown, Speichern blockt die Zeiten und lädt sie ein."),
        ("05", "Intake", "a", "Sie füllt den tiefen Fragebogen im Portal aus. Die "
         "Gesprächsvorbereitung entsteht daraus von selbst."),
        ("06", "Bericht", "b", "Der Agent entwirft — pseudonymisiert. Du prüfst jedes "
         "Wort und gibst frei. Ohne Freigabe entsteht kein PDF."),
        ("07", "Abschluss & Stimme", "y", "Abgeschlossen setzen, Feedback erbitten. "
         "Nur echte Stimmen, nie erfundene."),
    ]
    lane_html = ""
    who_lbl = {"a": "läuft von selbst", "y": "deine Entscheidung", "b": "beides"}
    for n, t, w, d in lanes:
        lane_html += (f'<div class="n">{n}</div><div class="st">'
                      f'<b>{t}</b><span class="who {w}">{who_lbl[w]}</span>'
                      f'<p>{d}</p></div>')

    overview = f"""<section class="page">
  <div class="sec-head"><span class="fig">Überblick</span>
    <h2>Der Weg in sieben Stationen</h2>
    <p class="sub">Jede Station ist eine Karte in der Customer Journey. Die Farbe sagt,
    wer am Zug ist.</p></div>
  <div class="lane">{lane_html}</div>
  <div class="note"><b>Die eine Regel, die über allem steht:</b> Nichts, was
  Gesundheit oder Geld berührt, verlässt das Haus ohne dich. Der Bericht braucht
  deine Freigabe, die Terminbestätigung liegt als Entwurf in deinem Gmail, und die
  Zahlung ist immer <b>Vorkasse</b> — sie ist der Startschuss des Programms, nicht
  die Schlussrechnung.</div>
  <div class="note warn"><b>Was das System niemals von selbst tut:</b> einen
  Bericht an eine Klientin schicken · eine Diagnose stellen oder eine Therapie
  empfehlen · eine Stimme erfinden · eine Kundin löschen · ein Gruppen-Angebot
  verkaufen (Verbindung bleibt Anfrage-Weg, Apple 3.1.3(d)).</div>
</section>"""

    # ── Wo die Daten liegen ──────────────────────────────────────────────────
    stores = f"""<section class="page">
  <div class="sec-head"><span class="fig">Fundament</span>
    <h2>Wo die Daten liegen</h2>
    <p class="sub">Vier Orte, ein Server: Hetzner in Frankfurt, erreichbar über
    <code>api.auralisnatura.com</code>. Stündliche Sicherung, nichts bei Dritten.</p></div>
  <div class="stores">
    <div class="store"><h4>Die Datenbank</h4>
      <div class="pth">/var/lib/auralis/auralis.db · SQLite</div>
      <ul>
        <li><b>records</b> — die Journey jeder Kundin: Phase, Vorab-Angaben, Intake,
          Notizen, Bericht. Der Inhalt ist <b>verschlüsselt</b> (Art. 9 DSGVO).</li>
        <li><b>bookings</b> — Anfragen <i>und</i> Programm-Termine, ebenfalls
          verschlüsselt. Eine eigene Tabelle: darum reicht „Kundin löschen“ nie.</li>
        <li><b>events</b> — anonyme Zählwerte für Cockpit und Trichter. Keine Namen,
          keine IP. Überlebt eine Löschung, ohne sie zu verraten.</li>
        <li><b>buch_entries / buch_meta / buch_scans</b> — Buchhaltung, Fristen-Häkchen
          und das Gedächtnis des Beleg-Lesers.</li>
      </ul></div>
    <div class="store"><h4>Die Kontaktdaten</h4>
      <div class="pth">/var/lib/auralis/clients.json</div>
      <ul>
        <li>Name, E-Mail, Telefon, Sprache, Login-ID, Passwort-<b>Hash</b> (nie das
          Passwort selbst), Status.</li>
        <li>Bewusst getrennt von den Gesundheitsdaten — zwei Orte, zwei Schlüssel.</li>
        <li><b>Sprache</b> ist hier das Maß aller Dinge: sie steuert jede Mail
          <i>und</i> das Bericht-PDF.</li>
      </ul></div>
    <div class="store"><h4>Die Unterlagen</h4>
      <div class="pth">/var/lib/auralis/output_docs/</div>
      <ul>
        <li><code>AN-0001/</code> — ihr Bericht-PDF und jede Mail, die sie bekommen hat,
          als <code>.eml</code>: dein Papierpfad.</li>
        <li><code>bookings/</code> Kalender-Einladungen · <code>buchhaltung/</code>
          Belege (6 Jahre) · <code>social/</code> fertige Posts · <code>journal/</code>
          Impulse-Artikel.</li>
        <li>Genau diese Dateien zeigt das Detail-Panel unter <b>Dokumente</b>.</li>
      </ul></div>
    <div class="store"><h4>Die Geheimnisse</h4>
      <div class="pth">/etc/auralis/portal.env · nie im Git</div>
      <ul>
        <li>Gmail-App-Passwort · Stripe-Signaturschlüssel · Staff-Schlüssel ·
          Datenschlüssel.</li>
        <li>Preise, Pakete und Schalter liegen dagegen <b>im Repo</b> — darüber werden
          sie ausgeliefert. Deshalb ändert man den Shop-Schalter per Commit, nicht
          auf dem Server.</li>
      </ul></div>
  </div>
  <div class="note"><b>Warum das wichtig ist:</b> Gesundheitsangaben sind die
  höchste Schutzstufe der DSGVO. Sie liegen verschlüsselt, in der EU, auf einer
  Maschine, die dir gehört — und der KI-Agent, der den Bericht entwirft, sieht
  <b>nie</b> Name oder Kontakt, nur die AN-Nummer.</div>
</section>"""

    pages = [cover, overview, stores]

    # ── Station 01 ───────────────────────────────────────────────────────────
    pages.append(station(
        "01", "Anfrage", "Sie bucht ein Kennenlerngespräch auf /book — vier Schritte, "
        "mit Vorab-Angaben zur Gesundheit und ausdrücklicher Einwilligung.",
        chain(("client", "Sie füllt <b>/book</b> aus<br>4 Schritte + Einwilligung"),
              ("auto", "Termin wird <b>gehalten</b><br>verschlüsselt gespeichert"),
              ("auto", "Datensatz angelegt<br>Phase <b>Anfrage</b>"),
              ("mail", "3 Mails<br>gehen hinaus"),
              ("you", "Du siehst sie<br>in Karte 01"))
        + cols(
            ["Der Slot wird <b>atomar</b> belegt — zwei gleichzeitige Buchungen können "
             "denselben Termin nicht bekommen.",
             "Kundendatensatz wird angelegt <i>oder</i> über die E-Mail wiedererkannt "
             "(keine Doppelten).",
             "Vorab-Angaben, Red-Flag-Antworten und Sprache hängen sofort am Datensatz.",
             "Die Antwort kommt <b>sofort</b>; die Mails laufen dahinter — früher "
             "wartete sie zehn Sekunden."],
            ["<b>Nichts</b> — diese Station braucht dich nicht. Sie läuft auch um 3 Uhr nachts.",
             "Danach: Termin bestätigen, indem du den <b>Gmail-Entwurf absendest</b>.",
             "Oder: Erinnerung schicken, stornieren, Notizen schreiben."],
            ["<b>①  Eingangsbestätigung</b> — geht <i>sofort</i> raus, damit sie nach der "
             "Preisgabe von Gesundheitsdaten nicht im Leeren steht.",
             "<b>②  Terminbestätigung + Kalender-Einladung</b> — liegt als <b>Entwurf</b> "
             "in deinem Gmail. Du bestätigst, nicht das System.",
             "<b>③  Briefing an team@</b> — wird gesendet, mit Einladung: der Termin "
             "steht sofort in deinem Google-Kalender.",
             "Ablage: <code>bookings</code>-Tabelle · <code>records</code> · "
             "<code>output_docs/bookings/</code>"])
        + opts(
            ("Öffnen", "Detail-Panel rechts: Termin, Vorab-Angaben, Red-Flag-Box, "
             "Selbsteinschätzung, alle Dokumente."),
            ("☎ Gespräch geführt", "Öffnet <b>zuerst die Notizen</b> (vier Felder), "
             "speichert sie und setzt dann die Phase auf Erstgespräch."),
            ("🔔 Termin-Erinnerung", "Premium-Mail mit Kalender-Einladung in ihrer Sprache."),
            ("✉️ Persönliche Nachricht", "Dein freier Text in der Marken-Vorlage."),
            ("⛔ Anfrage stornieren", "Sagt alle künftigen Termine ab (auch in ihrem "
             "Kalender), entzieht den Zugang, Phase auf Verloren. Datensatz bleibt."),
            ("Verloren", "Nur die Phase — ohne Absage-Mail, ohne Zugriffsentzug.")),
        "<b>Die Anfrage einer bestehenden Kundin</b> bewegt ihre Phase nicht — sie "
        "erscheint deshalb zusätzlich in Karte 01 unter „Auch angefragt“, damit sie "
        "nicht zwischen den Phasen verschwindet."))

    # ── Station 02 ───────────────────────────────────────────────────────────
    pages.append(station(
        "02", "Erstgespräch", "Das kostenlose Kennenlerngespräch — und der Moment, in "
        "dem die Notizen entstehen, die später den Bericht tragen.",
        chain(("you", "Du führst<br>das Gespräch"),
              ("you", "<b>☎ Gespräch geführt</b><br>öffnet die Notizen"),
              ("auto", "Notizen gespeichert<br>verschlüsselt"),
              ("auto", "Phase → <b>Erstgespräch</b>"),
              ("you", "Gewonnen<br>oder verloren?"))
        + cols(
            ["Die vier Notizfelder liegen ab der <b>ersten Anfrage</b> bereit — nicht "
             "erst nach dem Intake.",
             "Leere Felder überschreiben nichts: du kannst jederzeit nachtragen.",
             "Eine Notiz allein verschiebt die Phase <b>nicht</b> — nur der Knopf tut das."],
            ["Das Gespräch selbst, natürlich.",
             "Was du festhältst: 👀 Beobachtungen · 🎯 Hauptthemen · ⭐ ihre Prioritäten "
             "(in <i>ihren</i> Worten) · 🤝 Vereinbart.",
             "Die Entscheidung danach: <b>🎉 Gewonnen</b> oder <b>Verloren</b>.",
             "Ob und wann du ein Angebot machst."],
            ["Notizen → <code>records</code>, verschlüsselt.",
             "Keine Mail in dieser Station — hier redest du, nicht das System.",
             "Die Notizen sind später die Grundlage der KI-Gesprächsvorbereitung "
             "und fließen in den Berichtsentwurf ein."])
        + opts(
            ("☎ Gespräch geführt", "Notizen-Dialog → speichern → Phase Erstgespräch."),
            ("✎ Notizen schreiben", "Dieselben vier Felder ohne Phasenwechsel — für "
             "alles, was dir hinterher einfällt."),
            ("🎉 Gewonnen", "Phase Gewonnen; fragt direkt, ob die Zugangsdaten raus sollen."),
            ("Verloren", "Phase Verloren. Wiederherstellbar.")),
        "<b>Warum die Notizen vor dem Phasenwechsel kommen:</b> Wer erst weiterklickt "
        "und dann die Notizen sucht, schreibt sie nicht mehr auf. Der Knopf fragt "
        "deshalb zuerst."))

    # ── Station 03 ───────────────────────────────────────────────────────────
    pages.append(station(
        "03", "Gewonnen · Zahlung &amp; Zugang",
        "Vorkasse: Die Zahlung ist der Startschuss des Programms, nicht die "
        "Schlussrechnung. Zwei Wege führen hierher.",
        '<div class="chain"><span class="node you" style="flex:1 1 100%;'
        'border-top-color:var(--clay)"><b>Weg A — von Hand (nach dem Gespräch)</b></span></div>'
        + chain(("you", "<b>🎉 Gewonnen</b>"),
                ("you", "Paket wählen<br>Klarheit · Wandel · Balance"),
                ("you", "<b>💶 Zahlung erhalten</b><br>wenn das Geld da ist"),
                ("you", "<b>🔑 Zugangsdaten</b><br>senden"),
                ("mail", "Zugangs-Karte<br>mit Ein-Klick-Login"))
        + '<div class="chain" style="margin-top:1mm"><span class="node auto" '
        'style="flex:1 1 100%;border-top-color:var(--pine)"><b>Weg B — sie kauft selbst '
        '(App, Portal oder Website)</b></span></div>'
        + chain(("client", "Sie klickt<br><b>Jetzt buchen</b>"),
                ("client", "Zahlt bei <b>Stripe</b><br>199 / 399 / 899 €"),
                ("auto", "Webhook prüft<br>die Signatur"),
                ("auto", "Paket + bezahlt<br>Zugang erzeugt"),
                ("mail", "Zugang an sie<br>💶 Verkauf an dich"))
        + cols(
            ["<b>Weg B läuft komplett ohne dich</b> — auch sonntags: Stripe meldet die "
             "Zahlung, das Portal legt Paket, Zahlung und Zugang an und schickt beides los.",
             "Die Signatur wird geprüft; eine Fälschung wird abgewiesen wie jede andere.",
             "Doppelte Meldungen von Stripe werden erkannt — das Passwort wird nicht "
             "zweimal neu vergeben.",
             "Zahlt sie in Dollar (Stripe rechnet um), wird trotzdem <b>unser</b> "
             "Euro-Betrag zugeordnet.",
             "Die Einnahme erscheint automatisch im Cockpit <i>und</i> in der Buchhaltung."],
            ["Bei Weg A: Paket setzen, Zahlung bestätigen, Zugang senden — drei bewusste Klicks.",
             "Die Reihenfolge ist Absicht: <b>erst Geld, dann Zugang</b>.",
             "Ob du überhaupt ein Paket verkaufst — das Gespräch ist frei und "
             "unverbindlich, auf beiden Seiten.",
             "Bei einem unzuordenbaren Betrag: du entscheidest, was damit geschieht "
             "(das System verwirft nie stillschweigend Geld)."],
            ["<b>Zugangsdaten-Karte</b> — Login-ID, Passwort, Ein-Klick-Link (14 Tage gültig).",
             "<b>💶 Verkauf</b> an team@ — Betrag, Paket, AN-Nummer, Sprache <i>und</i> "
             "ob der Zugang wirklich raus ist.",
             "Zahlungen → <code>events</code> → Cockpit-Umsatz, Trichter, Buchhaltung.",
             "Ein Testkauf aus der Stripe-Sandbox wird als <b>[TEST]</b> markiert."])
        + opts(
            ("💶 Zahlung erhalten", "Erfasst <b>nur</b> die Zahlung — schiebt die Kundin "
             "nicht ans Ende des Programms."),
            ("🔑 Zugangsdaten senden", "Neues Passwort + Portal-Karte. Wirkt auch als "
             "Reaktivierung nach einem Storno."),
            ("✅ Abgeschlossen", "Erst am Ende, auf Karte 06 — eine eigene Handlung.")),
        "<b>Zwei Wächter passen auf:</b> „Programm läuft ohne Zahlung“ (Fehler — du "
        "arbeitest gerade umsonst) und „Zahlung ausstehend“ (Warnung ab drei Tagen). "
        "Beim Direktkauf über Stripe fallen Zusage und Zahlung in denselben Moment."))

    # ── Station 04 ───────────────────────────────────────────────────────────
    pages.append(station(
        "04", "Programm-Termine",
        "Sobald ein Paket steht, plant die Konsole die Gespräche, die dazugehören — "
        "über deine echten Sprechzeiten.",
        chain(("auto", "Vorschlag aus<br>Paket × Verfügbarkeit"),
              ("you", "Du verschiebst<br>Zeile für Zeile"),
              ("you", "<b>Speichern</b>"),
              ("auto", "Zeiten sofort<br>auf /book blockiert"),
              ("mail", "Eine Einladung<br>für alle Termine"))
        + cols(
            ["Der Rhythmus kommt aus dem Paket: Klarheit 90′ + 45′ · Wandel 60′ + 3 × 45′ "
             "wöchentlich · Balance über 12 Wochen.",
             "Gelegt wird über deine Verfügbarkeit, <b>sommerzeitsicher</b>: gleicher "
             "Wochentag, gleiche lokale Uhrzeit.",
             "Gespeicherte Termine blocken die Zeiten <b>sofort</b> auf der öffentlichen "
             "Buchungsseite.",
             "Die Kalender-Identität bleibt stabil — ein neuer Plan <b>verschiebt</b> "
             "Termine, statt sie zu verdoppeln."],
            ["Jede Zeile per Dropdown verschieben, bevor du speicherst.",
             "Einzelne Termine absagen — die Absage verlässt auch <i>ihren</i> Kalender.",
             "Die Terminliste erneut schicken, wenn die Mail verloren ging.",
             "Ob überhaupt geplant wird: manche Programme laufen freier."],
            ["<b>Programm-Terminplan</b> — die Liste plus <b>eine</b> Einladung mit "
             "allen Terminen.",
             "Entfallene Termine reisen als Absage mit, damit ihr Kalender sauber bleibt.",
             "Ablage: <code>bookings</code> mit <code>kind=session</code> — "
             "darum sieht die Buchungsseite sie."])
        + opts(
            ("📅 Terminplan vorschlagen", "Erzeugt den Vorschlag; noch ist nichts gebucht."),
            ("Speichern", "Ersetzt die künftigen Termine, blockt die Zeiten, verschickt die Einladung."),
            ("📅 Programm-Terminliste", "Schickt dieselbe Mail erneut — Kalender aktualisiert sich, statt zu doppeln."),
            ("✕ am Termin", "Sagt genau diesen einen Termin ab, mit Absage-Mail."))))

    # ── Station 05 ───────────────────────────────────────────────────────────
    pages.append(station(
        "05", "Intake", "Der tiefe Fragebogen im Klientinnen-Portal — die Grundlage "
        "des Berichts.",
        chain(("client", "Sie füllt aus<br>im Portal oder in der App"),
              ("auto", "Verschlüsselt<br>gespeichert"),
              ("auto", "<b>Gesprächs-<br>vorbereitung</b> entsteht"),
              ("you", "Du liest,<br>ergänzt Notizen"),
              ("you", "Bericht<br>anstoßen"))
        + cols(
            ["Antworten landen verschlüsselt am Datensatz; die Phase zieht mit.",
             "Aus Intake + Notizen entsteht automatisch die Gesprächsvorbereitung.",
             "Die Selbsteinschätzung hat <b>überall dieselbe Leserichtung</b>: höher ist "
             "besser — auch bei „Stressbalance“.",
             "Rote Angaben (Red Flags) werden hervorgehoben, nicht versteckt."],
            ["Ob du nachfragst, bevor du den Bericht anstößt.",
             "Ob die Vorbereitung neu erzeugt wird, nachdem du Notizen ergänzt hast.",
             "Ob eine ärztliche Abklärung angeraten ist — <b>diese Einschätzung trifft "
             "kein Programm.</b>"],
            ["Intake → <code>records</code>, verschlüsselt (Art. 9 DSGVO).",
             "Keine Mail — der Fragebogen ist ihr Weg zu dir, nicht umgekehrt.",
             "Sie sieht ihren Fortschritt im Portal; erfundene Aufgaben gibt es dort nicht."])
        + opts(
            ("Neu erzeugen", "Erstellt die Gesprächsvorbereitung noch einmal — sinnvoll, "
             "nachdem du Notizen ergänzt hast."),
            ("Passwort zurücksetzen", "Wenn sie nicht ins Portal kommt: neues Passwort "
             "zum Vorlesen am Telefon."),
            ("🔔 Termin-Erinnerung", "Falls das Gespräch näher rückt als der Intake.")),
        "<b>Die Sprache der Kundin</b> (Feld im Kundinnen-Tab) bestimmt ab hier alles: "
        "jede Mail <i>und</i> die Sprache des Bericht-PDFs. Änderst du sie später, warnt "
        "die Konsole, dass der Entwurf noch in der alten Sprache steht."))

    # ── Station 06 ───────────────────────────────────────────────────────────
    pages.append(station(
        "06", "Bericht", "Der Kern der Arbeit — und die Stelle mit dem strengsten Tor.",
        chain(("you", "Du stößt an"),
              ("auto", "Agent entwirft<br><b>nur AN-Nummer</b>"),
              ("you", "<b>Du prüfst<br>jedes Wort</b>"),
              ("you", "Freigabe-Haken"),
              ("auto", "12-Seiten-PDF<br>+ Mail-Entwurf"))
        + cols(
            ["Der Agent bekommt <b>pseudonymisierte</b> Daten: AN-Nummer, nie Name oder Kontakt.",
             "Red Flags erzwingen einen Arzt-Hinweis am Anfang des Berichts.",
             "Nach der Freigabe: Premium-PDF mit Titelblatt, Dashboard, sechs Kapiteln, "
             "Wochenplan und 28-Tage-Tracker.",
             "Lange Kapitel bekommen Fortsetzungsseiten, statt abgeschnitten zu werden.",
             "Die Berichts-Mail wird als <b>Gmail-Entwurf</b> vorbereitet."],
            ["<b>Jeden Abschnitt lesen und redigieren.</b> Der Entwurf ist ein Vorschlag, "
             "kein Ergebnis.",
             "Den Freigabe-Haken setzen — <b>ohne ihn erzeugt niemand ein PDF</b>.",
             "Vorschau ansehen, bevor du freigibst.",
             "Den Entwurf in Gmail absenden — auch das ist deine Handlung.",
             "Bei geänderter Sprache: neu entwerfen lassen."],
            ["Entwurf und Freigabe → <code>records</code>.",
             "PDF → <code>output_docs/AN-xxxx/</code>, dort auch die verschickte Mail als "
             "<code>.eml</code>.",
             "<b>Berichts-Mail</b> — Entwurf mit PDF im Anhang.",
             "Alles davon steht im Detail-Panel unter <b>Dokumente</b>."])
        + opts(
            ("Bericht entwerfen lassen", "Der Agent schreibt den ersten Entwurf."),
            ("↻ Neu entwerfen", "Verwirft den Entwurf und beginnt neu — z. B. nach einem Sprachwechsel."),
            ("👁 Vorschau", "Zeigt den fertigen Bericht, ohne etwas zu erzeugen."),
            ("Änderungen speichern", "Deine Redaktion sichern (ohne Freigabe)."),
            ("✓ PDF erzeugen + Mail-Entwurf", "Erst nach dem Freigabe-Haken anklickbar.")),
        "<b>Das ist die wichtigste Regel des ganzen Betriebs:</b> Kein KI-Text erreicht "
        "je eine Klientin, ohne dass du ihn gelesen und freigegeben hast. Der Bericht "
        "bildet, er diagnostiziert nicht — und wo Anlass besteht, verweist er zuerst "
        "zur Ärztin."))

    # ── Station 07 ───────────────────────────────────────────────────────────
    pages.append(station(
        "07", "Abschluss &amp; Stimme", "Das Programm endet — und beginnt den nächsten "
        "Kreis, wenn sie zufrieden war.",
        chain(("you", "<b>✅ Abgeschlossen</b>"),
              ("auto", "Umsatz zählt<br>im Cockpit"),
              ("you", "<b>⭐ Feedback</b><br>erbitten"),
              ("mail", "Dankes-Mail<br>mit Bitte"),
              ("you", "Stimme prüfen<br>und nutzen"))
        + cols(
            ["Der Trichter im Cockpit zieht mit; die Zahlen bleiben nach einer Löschung wahr.",
             "Der Umsatz steht in Cockpit und Finanzen; die Buchhaltung hat ihn längst.",
             "Nichts erinnert sie automatisch, nichts drängt."],
            ["Wann du abschließt.",
             "Ob du um Feedback bittest — und ob eine Stimme auf die Website darf.",
             "<b>Nur echte Stimmen.</b> Erfinden ist ausgeschlossen, auch wenn die "
             "Website noch leer wirkt."],
            ["<b>Feedback-Anfrage</b> — Dankes-Mail mit der Bitte um zwei, drei Sätze "
             "und die Erlaubnis, einen davon zu zitieren.",
             "Ihre Antwort kommt ganz normal in dein Postfach."])
        + opts(
            ("✅ Abgeschlossen", "Phase Abgeschlossen."),
            ("⭐ Feedback anfragen", "Sendet bzw. entwirft die Dankes-Mail."),
            ("Export", "DSGVO-Auskunft: alles, was über sie gespeichert ist."),
            ("Löschen", "Art. 17: Datensatz, Unterlagen und Login in einem Zug — "
             "unwiderruflich."))))

    # ── Querschnitt: Geld ────────────────────────────────────────────────────
    pages.append(station(
        "08", "Querschnitt: Buchhaltung &amp; Finanzamt",
        "Was aus dem Geld wird, nachdem es angekommen ist — spanisches Recht, "
        "estimación directa simplificada.",
        chain(("auto", "Bezahltes Programm<br>= Einnahme"),
              ("you", "Beleg <b>fotografieren</b>"),
              ("auto", "Leser schlägt vor<br>und lernt"),
              ("you", "<b>Jede Zeile ✓</b><br>bestätigen"),
              ("auto", "303 · 130 · Renta<br>rechnen sich"))
        + cols(
            ["Einnahmen entstehen <b>von selbst</b> aus bezahlten Programmen "
             "(Endpreise inkl. 21 % IVA).",
             "Der Beleg-Leser liest Foto oder PDF und füllt das Formular als Vorschlag.",
             "Er merkt sich deine Praxis je Lieferant („3× Canva → Software“) und lernt "
             "aus jeder Korrektur.",
             "Modelo 303, 130 und die Renta-Rubriken rechnen sich aus <b>einer</b> "
             "Auswertung — der Finanzamt-Tab rechnet nie selbst.",
             "Fristen tragen ein <b>Startfenster</b>: nicht nur wann es zu spät ist, "
             "sondern ab wann es geht."],
            ["<b>Jede gelesene Zeile bestätigen</b> — ohne alle Haken bleibt Speichern gesperrt.",
             "Ausgaben erfassen (Einnahmen kommen von allein).",
             "Privatanteil setzen, z. B. beim Internet im Homeoffice.",
             "Einreichen bei der AEAT — die Konsole legt die Zahlen bereit, "
             "abschicken musst du.",
             "Erledigt-Häkchen setzen (und zurücknehmen, wenn es ein Versehen war)."],
            ["Belege: <code>output_docs/buchhaltung/</code>, sechs Jahre.",
             "Buchungen: <code>buch_entries</code> — lückenlose Nummern, nie gelöscht, "
             "nur storniert.",
             "Jahres-Export als PDF und CSV für die Gestoría, nach Renta-Rubriken.",
             "Pro Frist ein Einreichungs-Dossier — das, was du bei einer Rückfrage in "
             "der Hand hast."])
        + opts(
            ("📷 Beleg fotografieren", "Datei wird immer behalten; der Leser macht einen Vorschlag."),
            ("✓ stimmt", "Bestätigt eine gelesene Zeile. Bearbeiten bestätigt auch."),
            ("✓ bezahlt", "Bucht eine offene Rechnung um — das <b>Zahldatum</b> wird das Buchungsdatum."),
            ("kopieren", "Legt die Kennzahl in die Zwischenablage — abgetippte Beträge sind Zahlendreher."),
            ("📄 Dossier", "PDF mit Kennzahlen und Belegen des Zeitraums.")),
        "<b>Ohne dein Alta-Datum (Modelo 036/037) zeigt der Finanzamt-Tab keine "
        "einzige Frist</b> — vor der Gründung gibt es keine Pflichten, und eine Konsole, "
        "die einen frisch gegründeten Betrieb mit überfälligen Terminen begrüßt, hat "
        "unrecht."))

    # ── Querschnitt: Aufmerksamkeit ──────────────────────────────────────────
    pages.append(station(
        "09", "Querschnitt: Was dich von selbst findet",
        "Du musst nicht suchen. Cockpit und Trichter melden sich, wenn etwas liegen "
        "bleibt — und schweigen, wenn alles läuft.",
        chain(("client", "Website-Besuch<br>cookielos gezählt"),
              ("auto", "Trichter<br>7 Stufen"),
              ("auto", "Wächter prüfen<br>stündlich"),
              ("you", "Du siehst<br>nur Auffälliges"),
              ("you", "Ein Klick<br>zur Kundin"))
        + cols(
            ["Die Website meldet <b>anonym</b>, dass jemand da war — kein Cookie, keine "
             "IP, keine Kennung. Darum braucht sie kein Banner.",
             "Der Trichter zeigt, wo Menschen verloren gehen — der Engpass ist die Stufe "
             "mit den meisten verlorenen <b>Menschen</b>, nicht mit der schlechtesten Quote.",
             "Alarme: neue Anfrage · Zugangsdaten fehlen · Programm läuft ohne Zahlung · "
             "Bericht liegt zu lange · Intake fehlt.",
             "Social-Media: Montagsscan, Wochenentwurf, Freigabe-Brett.",
             "Sicherung: stündlich, verschlüsselt, außerhalb des Programmordners."],
            ["Welchem Alarm du folgst — jeder ist ein Link zur Kundin.",
             "Ob ein Social-Beitrag erscheint: nichts wird ohne deine Freigabe veröffentlicht.",
             "Welche Impulse-Artikel öffentlich sind (sie füllen den Gast-Bereich der App).",
             "Ob ein Angebot online kaufbar ist (Shop-Schalter)."],
            ["Zählwerte → <code>events</code>: anonym, ohne Personenbezug.",
             "„Wir zählen Seitenaufrufe, keine Personen“ — das steht auch so in der "
             "Oberfläche, damit niemand es später verwechselt.",
             "Kein Countdown, keine künstliche Knappheit, kein Streak — weder zu "
             "Klientinnen noch zu dir."])
        + opts(
            ("Anzeigen →", "Springt aus dem Alarm direkt zur betroffenen Kundin."),
            ("30 / 90 / 365 Tage", "Zeitfenster des Trichters."),
            ("Freigeben", "Ein Social-Beitrag geht in die Warteschlange — erst dann wird "
             "veröffentlicht.")),
        "<b>Ehrlich by construction:</b> Ein leerer Zustand sagt, <i>wann</i> er sich "
        "füllt. Eine Stufe ohne Messung ist schraffiert, nicht null. Und ein "
        "Gleichstand wird als Gleichstand ausgewiesen, statt einen Sieger zu behaupten."))

    # ── Abschluss ────────────────────────────────────────────────────────────
    pages.append(f"""<section class="page">
  <div class="sec-head"><span class="fig">Zum Mitnehmen</span>
    <h2>Die sechs Sätze, die alles tragen</h2>
    <p class="sub">Wenn du dir aus diesem Dokument nur eine Seite merkst, dann diese.</p></div>
  <table class="opts">
    <tr><th>Grundsatz</th><th>Warum</th></tr>
    <tr><td class="btn">Vorkasse</td><td>Die Zahlung ist der <b>Startschuss</b> des
      Programms, nicht die Schlussrechnung. Zwei Wächter melden, wenn Arbeit ohne
      Zahlung läuft.</td></tr>
    <tr><td class="btn">Freigabe vor Versand</td><td>Kein KI-Text erreicht eine
      Klientin ungelesen. Die Terminbestätigung und die Berichts-Mail liegen als
      <b>Entwurf</b> in deinem Gmail — du sendest.</td></tr>
    <tr><td class="btn">Coaching, nicht Medizin</td><td>Bildung und Begleitung, nie
      Diagnose oder Therapie. Wo Anlass besteht, verweist der Bericht zuerst zur
      Ärztin. „Dr.“ heißt sichtbar: Doktorat der Chemie.</td></tr>
    <tr><td class="btn">Nur echte Stimmen</td><td>Kein Testimonial wird erfunden,
      keine Zahl geschönt, keine Knappheit behauptet — auch nicht, solange die
      Website noch leer wirkt.</td></tr>
    <tr><td class="btn">Ihre Sprache</td><td>Ein Feld pro Kundin steuert jede Mail
      <b>und</b> das Bericht-PDF. Deutsch ist das Original; Englisch und Spanisch
      werden daraus abgeleitet, nie getrennt gepflegt.</td></tr>
    <tr><td class="btn">Löschen heißt löschen</td><td>Art. 17 entfernt Datensatz,
      Unterlagen und Login in einem Zug. Ein Storno dagegen <b>behält</b> alles und
      nimmt nur den Zugang — zwei verschiedene Dinge, zwei Knöpfe.</td></tr>
  </table>
  <div class="note"><b>Und wenn etwas nicht stimmt:</b> Die Konsole sagt lieber
  „noch nicht gemessen“ als eine erfundene Null, lieber „Lesen fehlgeschlagen“ als
  einen geratenen Betrag, und lieber „Zugang NICHT versendet“ als ein stilles
  Häkchen. Ein Werkzeug, das über den eigenen Zustand lügt, ist schlimmer als
  keines.</div>
  <div class="foot">Auralis Natura · Dr. rer. nat. Desiree Gruber · Barcelona ·
  team@auralisnatura.com — Erzeugt am {today} aus dem laufenden System.
  Auralis Natura bietet Gesundheitscoaching und Gesundheitsbildung, keine
  medizinische Diagnose oder Therapie.</div>
</section>""")

    return ("<!doctype html><meta charset='utf-8'>"
            "<title>Auralis Natura — Prozess- und Datenkarte</title>"
            f"<style>{css}</style>" + "".join(pages))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--html", action="store_true", help="nur das HTML schreiben")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    html = build_html()
    out = Path(args.out) if args.out else (cfg.OUTPUT_DIR / "Auralis-Prozesskarte.pdf")
    if args.html:
        p = out.with_suffix(".html")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")
        print(p)
        return 0
    p = render.to_pdf(html, out)
    print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
