#!/usr/bin/env python3
"""Build the Operator Onboarding Guide (branded HTML + PDF) for Auralis Natura."""
import base64, sys
from pathlib import Path

ROOT = Path("/home/user/AuralisNatura")
SEAL = ROOT / "portal/assets/seal.png"
OUT_DIR = ROOT / "handover/auralis-portal"
seal_b64 = base64.b64encode(SEAL.read_bytes()).decode()

CSS = """
:root{--ink:#281F16;--ink-soft:#5C4A3A;--ink-faint:#8C7E6E;--forest:#3D2719;--forest-deep:#221305;--clay:#A8492A;--gold:#AD7A32;--sage:#927B4A;--sage-soft:#DAC79E;--paper:#F5EEE0;--cream:#FBF6EB;--line:rgba(61,39,25,.14);--line2:rgba(61,39,25,.26);--goldhair:rgba(173,122,50,.42);--fd:"Fraunces",Georgia,serif;--fb:"Hanken Grotesk",system-ui,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--fb);color:var(--ink);background:#fff;font-size:12.5px;line-height:1.62;-webkit-font-smoothing:antialiased}
.page{max-width:820px;margin:0 auto;padding:34px 46px}
h1{font-family:var(--fd);font-weight:400;font-size:2rem;line-height:1.12;letter-spacing:-.01em}
h2{font-family:var(--fd);font-weight:400;font-size:1.5rem;color:var(--forest);margin:32px 0 6px;padding-top:15px;border-top:2px solid var(--forest);page-break-after:avoid}
h2 .fig{font-family:var(--fd);font-size:1.55rem;color:var(--gold);margin-right:11px}
h3{font-family:var(--fd);font-weight:400;font-size:1.14rem;margin:18px 0 5px;color:var(--clay);page-break-after:avoid}
p{margin:7px 0;max-width:72ch;color:var(--ink-soft)}
ul,ol{margin:7px 0 7px 22px;color:var(--ink-soft)}li{margin:4px 0}
b,strong{color:var(--ink)}
em{font-style:italic;color:var(--forest)}
code{font-family:ui-monospace,Menlo,monospace;font-size:.85em;background:var(--cream);border:1px solid var(--line);padding:1px 5px}
.kick{font-size:.66rem;letter-spacing:.22em;text-transform:uppercase;color:var(--clay);font-weight:600}
.rule{width:34px;height:1px;background:linear-gradient(90deg,var(--gold),transparent);margin:8px 0 0}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:11.6px;page-break-inside:avoid}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{background:var(--paper);font-size:.6rem;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint)}
.box{background:var(--cream);border:1px solid var(--line);border-left:4px solid var(--sage);padding:12px 16px;margin:12px 0;page-break-inside:avoid}
.box.warn{border-left-color:var(--clay);background:#FCEFEC}
.box.gold{border-left-color:var(--gold);background:#FBF6EC}
.box h4{font-family:var(--fd);font-weight:400;margin-bottom:4px;color:var(--ink)}
.cover{min-height:90vh;display:flex;flex-direction:column;justify-content:center;text-align:center;page-break-after:always}
.cover img{width:104px;height:104px;margin:0 auto 20px;filter:drop-shadow(0 10px 24px rgba(42,33,26,.16))}
.cover h1{font-size:2.8rem;margin:8px 0 6px}
.cover .lede{font-family:var(--fd);font-style:italic;font-size:1.25rem;color:var(--clay);margin:0 0 16px}
.cover .sub{color:var(--ink-soft);max-width:54ch;margin:0 auto 20px;font-size:1.05rem}
.cover .meta{font-size:.85rem;color:var(--ink-faint)}
.spark{display:flex;gap:7px;justify-content:center;margin:16px 0}
.spark i{width:7px;height:7px;border-radius:50%;background:var(--clay)}
.spark i:nth-child(2){background:var(--gold)}.spark i:nth-child(3){background:var(--sage)}
.stage{border:1px solid var(--line);border-left:4px solid var(--gold);background:var(--cream);padding:13px 18px;margin:11px 0;page-break-inside:avoid}
.stage .sn{font-family:var(--fd);font-size:1.25rem;color:var(--clay);margin-right:4px}
.pill{display:inline-block;font-size:.58rem;letter-spacing:.1em;text-transform:uppercase;font-weight:600;border:1px solid var(--line2);padding:1px 8px;margin-right:4px;background:#fff}
.pill.auto{color:var(--sage);border-color:var(--sage)}
.pill.you{color:var(--clay);border-color:var(--clay)}
.toc{columns:2;column-gap:36px;font-size:.92rem;margin-top:8px}
.toc li{margin:3px 0}
.chk{list-style:none;margin-left:0}
.chk li{padding-left:26px;position:relative;margin:6px 0}
.chk li::before{content:"";position:absolute;left:0;top:1px;width:14px;height:14px;border:1.5px solid var(--gold);background:#fff}
.lead{font-size:1.05rem;color:var(--ink-soft)}
.foot{margin-top:32px;border-top:1px solid var(--goldhair);padding-top:12px;font-size:10px;color:var(--ink-faint);line-height:1.6}
@media print{@page{size:A4;margin:14mm 12mm}.page{max-width:none;padding:0}h2{page-break-before:auto}}
"""

BODY = """
<header class="cover">
  <img src="data:image/png;base64,SEAL_B64" alt="">
  <div class="kick">Auralis Natura · Holistic Health</div>
  <h1>Einarbeitung für den Betrieb</h1>
  <div class="lede">So läuft der Prozess — und so führst du ihn.</div>
  <p class="sub">Dein Willkommens- und Bedien-Leitfaden für die Betriebskonsole: die Kundenreise Station für Station, dein Tagesrhythmus, die Sprache pro Kundin, das Berichts-Freigabe-Gate und die erste Woche als Checkliste.</p>
  <div class="spark"><i></i><i></i><i></i></div>
  <div class="meta">Betriebs-Onboarding · Stand: Juli 2026 · vertraulich<br>Ergänzt das technische <em>Operations Manual</em> (Server-Setup)</div>
</header>

<h2>Inhalt</h2>
<ol class="toc">
<li>Willkommen &amp; deine Rolle</li>
<li>Die drei Oberflächen &amp; dein einer Login</li>
<li>Dein Tagesrhythmus (5 Minuten)</li>
<li>Die Kundenreise — Station für Station</li>
<li>Sprache pro Kundin — alles folgt der Auswahl</li>
<li>Der Bericht &amp; das Freigabe-Gate</li>
<li>Alle E-Mails auf einen Blick</li>
<li>Wenn etwas klemmt</li>
<li>Deine erste Woche — Checkliste</li>
</ol>

<h2><span class="fig">00</span>Willkommen &amp; deine Rolle</h2>
<p class="lead">Auralis Natura läuft über <b>eine einzige App</b> — die Betriebskonsole. Du führst darin die gesamte Kundenreise: von der ersten Anfrage bis zum fertigen Bericht und dem Feedback. Alles andere (Bestätigungen, Zugänge, Berichts-Entwürfe, Erinnerungen) bereitet das System für dich vor.</p>
<div class="box gold"><h4>Die eine goldene Regel</h4><p style="margin:0"><b>Nichts erreicht eine Kundin ohne deine Freigabe.</b> Der KI-Agent schreibt nur Entwürfe. Jede E-Mail landet als <b>Entwurf in deinem Gmail</b> — du liest, du klickst „Senden". Du bist immer die letzte, menschliche Instanz. Das ist bewusst so gebaut: fachlich, rechtlich (DSGVO) und für das Vertrauen deiner Kundinnen.</p></div>
<p>Zweitwichtigste Regel: <b>Du bist Coach &amp; Bildung, nicht Medizin.</b> Der „Dr."-Titel ist ein Chemie-Doktortitel. Nichts, was rausgeht, diagnostiziert oder behandelt. Bei Warnzeichen (Red Flags) verweist der Bericht <em>zuerst</em> zur Ärztin/zum Arzt — das erzwingt das System automatisch, aber du prüfst es.</p>

<h2><span class="fig">01</span>Die drei Oberflächen &amp; dein einer Login</h2>
<p>Ein Server auf dem Mac bedient — über <code>api.auralisnatura.com</code> — drei Oberflächen:</p>
<table>
<tr><th>Oberfläche</th><th>Adresse</th><th>Für wen</th></tr>
<tr><td><b>Buchungsseite</b></td><td><code>/book</code></td><td>Interessentinnen — 4-Schritte-Buchung mit Wellbeing-Fragen</td></tr>
<tr><td><b>Klienten-Portal</b></td><td><code>/portal</code></td><td>Kundinnen — Login, Aufnahmebogen, Fortschritt, Bericht-Download</td></tr>
<tr><td><b>Betriebskonsole</b></td><td><code>/staff</code></td><td><b>Nur du</b> — Cockpit, Journey, Finanzen, Kundinnen, Termine</td></tr>
</table>
<div class="box"><h4>Die „Office"-App auf dem iPhone</h4><p style="margin:0">Öffne <code>/staff</code> in Safari → Teilen → <b>„Zum Home-Bildschirm"</b>. Du bekommst ein App-Icon namens <b>Office</b>. Einmal den Zugangscode eingeben — die App bleibt angemeldet. Kommt ein Update, zieht sich die App die neue Version automatisch. Am Mac genauso im Browser.</p></div>

<h2><span class="fig">02</span>Dein Tagesrhythmus (5 Minuten)</h2>
<ol>
<li><b>Office-App öffnen → Cockpit.</b> Oben stehen die <b>Alerts</b>: 💶 Zahlung offen · 🔑 Zugang ausstehend · ⏰ Nachfassen · 📋 Intake wartet · 📅 nächste 24&nbsp;h. Jeder Alert hat „Anzeigen →" und springt direkt zur richtigen Karte.</li>
<li><b>Customer Journey von oben nach unten.</b> Jede Karte zeigt ihre nächste Aktion als Button. Trägt keine Karte einen goldenen oder roten Chip mehr, bist du fertig.</li>
<li><b>Gmail-Entwürfe senden.</b> Was das System vorbereitet hat (Zugänge, Berichte, Erinnerungen), liegt fertig in <code>team@auralisnatura.com</code> — kurz prüfen, senden.</li>
<li><b>Freitags, 5 Minuten:</b> Finanzen (Ist vs. Plan), Termine-Tab: nächste Woche Verfügbarkeit prüfen, Ausnahmen setzen.</li>
</ol>
<div class="box"><p style="margin:0">Farb-Ampel überall: <b style="color:#3F7B5A">grün</b> = alles im grünen Bereich · <b style="color:#AD7A32">gold</b> = bald fällig / Blick drauf · <b style="color:#A8492A">rot</b> = überfällig / Handlung nötig.</p></div>

<h2><span class="fig">03</span>Die Kundenreise — Station für Station</h2>
<p>Legende: <span class="pill auto">System</span> passiert automatisch · <span class="pill you">Du</span> ist deine Aktion in der Konsole.</p>

<div class="stage"><span class="sn">01</span> <b>Anfrage — die Buchung</b><br>
<span class="pill auto">System</span> Die Interessentin wählt auf <code>/book</code> Tag &amp; Uhrzeit (nur deine Fenster), beantwortet die Wellbeing-Fragen und willigt DSGVO-konform ein. Sie erhält sofort die Premium-Bestätigung <b>mit echter Kalender-Einladung</b> (auch in Gmail + Google Calendar von team@). In der Konsole erscheint sie in „Offene Anfragen" — mit 📋 allen Vorab-Angaben.<br>
<span class="pill you">Du</span> Vor dem Call: Karte öffnen, Vorab-Angaben lesen (2 Min.). Optional <b>🔔 Erinnerung</b> senden.</div>

<div class="stage"><span class="sn">02</span> <b>Erstgespräch (25 Min., kostenlos)</b><br>
<span class="pill you">Du</span> Gespräch über den Google-Meet-Link führen. Danach <b>☎ „Gespräch geführt"</b> klicken. Kein Abschluss? → „Verloren" (wiederherstellbar).</div>

<div class="stage"><span class="sn">03</span> <b>Gewonnen &amp; Zugang</b><br>
<span class="pill you">Du</span> <b>🎉 „Gewonnen"</b> → Paket setzen (Root 198&nbsp;€ · Bloom 398&nbsp;€ · Flourishing 798&nbsp;€ · Grove individuell) → <b>🔑 „Zugangsdaten senden"</b>.<br>
<span class="pill auto">System</span> Erzeugt ein sicheres Passwort und mailt die <b>Zugangsdaten-Karte</b> (Login + Portal-Button + „So geht es weiter"). Umsatz zählt ab jetzt in Cockpit &amp; Finanzen.</div>

<div class="stage"><span class="sn">04</span> <b>Intake &amp; Vorbereitung</b><br>
<span class="pill auto">System</span> Die Kundin füllt im Portal den tiefen Aufnahmebogen aus (~15 Min., speichert automatisch). Danach springt die Phase auf „Intake", die <b>Gesprächsvorbereitung wird automatisch erzeugt</b>.<br>
<span class="pill you">Du</span> Prep lesen → Tiefengespräch führen → Notizen <b>strukturiert</b> erfassen: 👀 Beobachtungen · 🎯 Hauptthemen · ⭐ Prioritäten (ihre Worte!) · 🤝 Vereinbart.</div>

<div class="stage"><span class="sn">05</span> <b>Bericht — Entwurf, Prüfung, Freigabe</b><br>
<span class="pill you">Du</span> „Bericht vom Agenten entwerfen" klicken.<br>
<span class="pill auto">System</span> Der KI-Agent erhält <b>nur pseudonymisierte Daten</b> (AN-Nummer, nie Name) und liefert 6 Kapitel + Wissenschafts-Notizen, 3 Prioritäten, Wochenplan, Habits — <b>in der Sprache der Kundin</b> (siehe Kapitel&nbsp;04).<br>
<span class="pill you">Du</span> Jeden Abschnitt lesen, direkt bearbeiten, 👁 Vorschau → Haken <b>„geprüft &amp; freigegeben"</b> → <b>„PDF erzeugen + E-Mail-Entwurf"</b>.</div>

<div class="stage"><span class="sn">06</span> <b>Geliefert &amp; Zahlung</b><br>
<span class="pill auto">System</span> Das <b>12-seitige Premium-PDF</b> wird gerendert; die Berichts-Mail liegt als <b>Entwurf in deinem Gmail</b>.<br>
<span class="pill you">Du</span> Senden · Review-Call führen · nach Zahlungseingang <b>💶 „Bezahlt"</b> → Umsatz final in der GuV.</div>

<div class="stage"><span class="sn">07</span> <b>Abgeschlossen — das Flywheel</b><br>
<span class="pill you">Du</span> <b>⭐ „Feedback anfragen"</b>: warme Dankes-Mail mit Bitte um 2–3 Sätze + Erlaubnis für eine Website-Stimme (nur Vorname).<br>
<div class="box warn" style="margin:8px 0 0"><b>Leitplanke:</b> Nur echte Stimmen. Niemals Testimonials erfinden oder ohne finale Freigabe der Kundin umformulieren.</div></div>

<h2><span class="fig">04</span>Sprache pro Kundin — alles folgt der Auswahl</h2>
<p>Jede Kundin hat ein <b>Sprach-Feld</b> (Deutsch · English · Español) im Tab <b>Kundinnen</b> → Kundin öffnen → Feld <em>„Sprache"</em>. Es wird bei der Buchung automatisch vorbelegt, du kannst es jederzeit ändern.</p>
<div class="box gold"><h4>🌐 Die Sprache steuert <em>alles</em> Kundenseitige</h4><p style="margin:0">Wählst du die Sprache, laufen <b>alle</b> externen Nachrichten <b>und der Bericht</b> in dieser Sprache:</p>
<ul style="margin:6px 0 0">
<li>Zugangsdaten-Karte · Terminerinnerung · Berichts-Mail · Feedback-Anfrage</li>
<li><b>Der 12-Seiten-Bericht (PDF)</b> selbst — Überschriften, Kapitel, Wochenplan</li>
</ul></div>
<h3>So gehst du vor</h3>
<ol>
<li>Kundin öffnen → <b>Sprache</b> setzen → <b>Speichern</b>.</li>
<li>Erst <em>danach</em> den Bericht entwerfen — er wird in dieser Sprache geschrieben, <b>auch wenn die Kundin den Fragebogen in einer anderen Sprache ausgefüllt hat</b>. Deine Auswahl gewinnt.</li>
<li>Hast du die Sprache <em>nach</em> dem Entwurf geändert, zeigt die Konsole eine goldene Warnung („Kundinnen-Sprache ist X, der Entwurf ist in Y"). Dann einmal <b>„↻ Neu entwerfen"</b> klicken — fertig.</li>
</ol>
<p>Im Berichts-Bereich siehst du immer die aktuelle Bericht-Sprache als kleines Etikett (z.&nbsp;B. <em>„· Sprache DE"</em>).</p>

<h2><span class="fig">05</span>Der Bericht &amp; das Freigabe-Gate</h2>
<p>Der Bericht ist das Herzstück — ein <b>12-seitiges, premium gestaltetes PDF</b>: Titelseite, persönlicher Brief, Dashboard mit Radar &amp; Ampel, 6 Kapitel (je mit 🔬 Wissenschafts-Box und ✓ konkreten Schritten), Wochenplan und 28-Tage-Tracker.</p>
<h3>Der Ablauf, den du steuerst</h3>
<ol>
<li><b>Entwerfen lassen.</b> Der Agent liefert einen ersten Entwurf — nie das Endprodukt.</li>
<li><b>Lesen &amp; bearbeiten.</b> Jeder Abschnitt ist direkt editierbar. Schärfe, streiche, ergänze in deinen Worten. Nutze 👁 <b>Vorschau</b> fürs echte PDF-Layout.</li>
<li><b>Freigeben.</b> Erst wenn du den Haken <b>„Ich habe geprüft &amp; gebe frei"</b> setzt, wird der Button „PDF erzeugen" aktiv. <b>Ohne Haken geht nichts.</b></li>
</ol>
<div class="box warn"><h4>⚠ Red Flags</h4><p style="margin:0">Nennt eine Kundin ein Warnzeichen (z.&nbsp;B. unerklärter Gewichtsverlust, Brustschmerz, Ohnmacht, Gedanken der Selbstverletzung), <b>beginnt der Entwurf erzwungenermaßen mit einem klaren Arzt-Hinweis</b> und die Karte trägt ein rotes Warnschild. Prüfe solche Berichte besonders sorgfältig und halte alle Empfehlungen sanft und allgemein. Im Notfall: 112.</p></div>

<h2><span class="fig">06</span>Alle E-Mails auf einen Blick</h2>
<p>Alle sind premium gebrandet, dreisprachig und laufen über deine Gmail-Entwürfe (Modus <code>draft</code>). Nichts wird ohne dich versendet.</p>
<table>
<tr><th>E-Mail</th><th>Wann</th><th>Ausgelöst durch</th></tr>
<tr><td><b>Buchungsbestätigung</b> + Kalender-Einladung</td><td>Sofort nach Buchung</td><td>System (Kundin bucht)</td></tr>
<tr><td><b>Terminerinnerung</b></td><td>Vor dem Call</td><td>Du · 🔔 im Termine-Tab</td></tr>
<tr><td><b>Zugangsdaten-Karte</b></td><td>Nach „Gewonnen"</td><td>Du · 🔑 Zugangsdaten senden</td></tr>
<tr><td><b>Bericht-Mail</b> (mit PDF)</td><td>Nach Freigabe</td><td>Du · PDF erzeugen</td></tr>
<tr><td><b>Feedback / Testimonial</b></td><td>Nach Abschluss</td><td>Du · ⭐ Feedback anfragen</td></tr>
<tr><td><b>Newsletter</b> (BCC an alle)</td><td>Nach Bedarf</td><td>Du · Kundinnen → Newsletter an alle</td></tr>
</table>
<p>Jede Mail wird zusätzlich als <code>.eml</code> revisionssicher auf dem Mac abgelegt (Prüfpfad).</p>

<h2><span class="fig">07</span>Wenn etwas klemmt</h2>
<table>
<tr><th>Symptom</th><th>Erste Hilfe</th></tr>
<tr><td>Konsole/Buchung lädt nicht</td><td>Läuft der Server auf dem Mac? Terminal-Fenster offen? Tunnel <code>cloudflared</code> aktiv? Mac wach?</td></tr>
<tr><td>Mail wird nicht zum Entwurf</td><td><code>AURALIS_SMTP_PASSWORD</code> (Gmail App-Passwort) in <code>.env</code> gesetzt und Modus <code>draft</code>? Details im Operations Manual, Teil D.</td></tr>
<tr><td>Bericht-Entwurf sehr generisch</td><td>Claude auf dem Mac angemeldet (<code>claude login</code>)? Sonst nutzt das System den Offline-Platzhalter — trotzdem editierbar.</td></tr>
<tr><td>Bericht in falscher Sprache</td><td>Sprache der Kundin prüfen (Kapitel 04) → setzen → „↻ Neu entwerfen".</td></tr>
<tr><td>Neue Funktion fehlt in der App</td><td>App neu laden (nach oben ziehen). Die App zieht Updates automatisch, ein Reload beschleunigt es.</td></tr>
</table>
<div class="box"><p style="margin:0">Tiefergehende Technik (Server neu starten, Tunnel, DNS, Backups, Cloudflare Access) steht vollständig im <b>Operations Manual</b>, Teil 2.</p></div>

<h2><span class="fig">08</span>Deine erste Woche — Checkliste</h2>
<ul class="chk">
<li><b>App einrichten:</b> <code>/staff</code> als „Office"-App auf iPhone <em>und</em> Mac, einmal anmelden.</li>
<li><b>Stammdaten prüfen:</b> ⚙ → Meet-Link, NIF, Bankdaten, Paketpreise stimmen.</li>
<li><b>Verfügbarkeit setzen:</b> Termine-Tab → deine echten Fenster der nächsten 2 Wochen.</li>
<li><b>Test-Buchung:</b> selbst auf <code>/book</code> buchen → in der Konsole erscheinen sehen → Karte lesen.</li>
<li><b>Sprache üben:</b> Test-Kundin auf English stellen → Zugangsdaten senden → Gmail-Entwurf prüfen (englisch).</li>
<li><b>Bericht-Probelauf:</b> Test-Intake ausfüllen → entwerfen → bearbeiten → freigeben → PDF ansehen.</li>
<li><b>Scharfschalten:</b> Gmail App-Passwort + Claude-Login auf dem Mac (Operations Manual, Teil D).</li>
<li><b>Test-Kundin löschen:</b> Kundinnen → Löschen (DSGVO-Erasure) — sauberer Start.</li>
</ul>
<div class="box gold"><p style="margin:0"><b>Denk immer daran:</b> Du führst durch — mit ein paar Klicks pro Kundin. Das System bereitet vor, du entscheidest und gibst frei. So bleibt die Qualität hoch, die Kundin fühlt sich persönlich betreut, und alles bleibt rechtlich sauber.</p></div>

<div class="foot">
<b>Auralis Natura — Holistic Health.</b> Ganzheitliches Gesundheits- und Ernährungscoaching (Bildung, keine medizinische Versorgung). „Dr." = Dr. rer. nat. (wissenschaftlicher Doktortitel in Chemie), keine Ärztin. Gesundheitsdaten (DSGVO Art.&nbsp;9) liegen verschlüsselt auf dem Mac; nichts wird ohne menschliche Freigabe versendet. · Betriebs-Onboarding, Stand Juli 2026 · vertraulich, nur intern.
</div>
"""

html = ("<!doctype html><html lang=\"de\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Auralis Natura — Einarbeitung für den Betrieb</title>"
        "<link href=\"https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..600;1,9..144,300..500&family=Hanken+Grotesk:wght@400;500;600&display=swap\" rel=\"stylesheet\">"
        f"<style>{CSS}</style></head><body><div class=\"page\">"
        + BODY.replace("SEAL_B64", seal_b64)
        + "</div></body></html>")

html_path = OUT_DIR / "OPERATOR-ONBOARDING.html"
html_path.write_text(html, encoding="utf-8")
print("HTML", html_path, len(html), "bytes")

# render to PDF via chromium
from playwright.sync_api import sync_playwright
CH = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
pdf_path = OUT_DIR / "OPERATOR-ONBOARDING.pdf"
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CH, args=["--no-sandbox", "--disable-gpu"])
    pg = b.new_page()
    pg.goto("file://" + str(html_path), wait_until="networkidle")
    pg.wait_for_timeout(1200)  # let web fonts settle
    pg.pdf(path=str(pdf_path), format="A4", print_background=True,
           margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"})
    b.close()
print("PDF", pdf_path, pdf_path.stat().st_size, "bytes")
