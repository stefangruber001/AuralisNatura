#!/usr/bin/env python3
"""Build the beginner's Customer-App build & launch guide (branded HTML + PDF)."""
import base64
from pathlib import Path

ROOT = Path("/home/user/AuralisNatura")
seal = base64.b64encode((ROOT / "portal/assets/seal.png").read_bytes()).decode()
OUT_DIR = ROOT / "handover/auralis-portal"

CSS = """
:root{--ink:#281F16;--ink-soft:#5C4A3A;--ink-faint:#8C7E6E;--forest:#3D2719;--forest-deep:#221305;--clay:#A8492A;--gold:#AD7A32;--sage:#927B4A;--sage-soft:#DAC79E;--paper:#F5EEE0;--cream:#FBF6EB;--line:rgba(61,39,25,.14);--line2:rgba(61,39,25,.26);--goldhair:rgba(173,122,50,.42);--fd:"Fraunces",Georgia,serif;--fb:"Hanken Grotesk",system-ui,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--fb);color:var(--ink);background:#fff;font-size:12px;line-height:1.6;-webkit-font-smoothing:antialiased}
.page{max-width:830px;margin:0 auto;padding:32px 44px}
h1{font-family:var(--fd);font-weight:400;font-size:2rem;line-height:1.12}
h2{font-family:var(--fd);font-weight:400;font-size:1.42rem;color:var(--forest);margin:30px 0 6px;padding-top:14px;border-top:2px solid var(--forest);page-break-after:avoid}
h2 .fig{font-family:var(--fd);font-size:1.5rem;color:var(--gold);margin-right:10px}
h3{font-family:var(--fd);font-weight:400;font-size:1.12rem;margin:16px 0 4px;color:var(--clay);page-break-after:avoid}
p{margin:6px 0;max-width:74ch;color:var(--ink-soft)}
ul,ol{margin:6px 0 6px 20px;color:var(--ink-soft)}li{margin:3px 0}
b,strong{color:var(--ink)}
em{font-style:italic;color:var(--forest)}
a{color:var(--clay);text-decoration:none;border-bottom:1px solid var(--goldhair);word-break:break-word}
code{font-family:ui-monospace,Menlo,monospace;font-size:.85em;background:var(--cream);border:1px solid var(--line);padding:1px 5px}
.kick{font-size:.64rem;letter-spacing:.22em;text-transform:uppercase;color:var(--clay);font-weight:600}
.rule{width:38px;height:1px;background:linear-gradient(90deg,var(--gold),transparent);margin:8px 0 0}
table{width:100%;border-collapse:collapse;margin:11px 0;font-size:11px;page-break-inside:avoid}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:var(--paper);font-size:.58rem;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-faint)}
.box{background:var(--cream);border:1px solid var(--line);border-left:4px solid var(--sage);padding:11px 15px;margin:11px 0;page-break-inside:avoid}
.box.warn{border-left-color:var(--clay);background:#FCEFEC}
.box.gold{border-left-color:var(--gold);background:#FBF6EC}
.box h4{font-family:var(--fd);font-weight:400;margin-bottom:3px;color:var(--ink);font-size:1rem}
.cover{min-height:90vh;display:flex;flex-direction:column;justify-content:center;text-align:center;page-break-after:always}
.cover img{width:104px;height:104px;margin:0 auto 18px;filter:drop-shadow(0 10px 24px rgba(42,33,26,.16))}
.cover h1{font-size:2.7rem;margin:8px 0 6px}
.cover .lede{font-family:var(--fd);font-style:italic;font-size:1.2rem;color:var(--clay);margin:0 0 16px}
.cover .sub{color:var(--ink-soft);max-width:56ch;margin:0 auto 18px;font-size:1.02rem}
.cover .meta{font-size:.82rem;color:var(--ink-faint)}
.spark{display:flex;gap:7px;justify-content:center;margin:14px 0}
.spark i{width:7px;height:7px;border-radius:50%;background:var(--clay)}
.spark i:nth-child(2){background:var(--gold)}.spark i:nth-child(3){background:var(--sage)}
.toc{columns:2;column-gap:34px;font-size:.9rem;margin-top:6px}.toc li{margin:3px 0}
.step{border:1px solid var(--line);border-left:4px solid var(--gold);background:var(--cream);padding:11px 15px;margin:10px 0;page-break-inside:avoid}
.step .sh{font-family:var(--fd);font-size:1.05rem;color:var(--forest);margin-bottom:2px}
.who{display:inline-block;font-size:.56rem;letter-spacing:.09em;text-transform:uppercase;font-weight:700;border:1px solid var(--line2);padding:1px 7px;margin-left:6px;vertical-align:middle}
.who.me{color:var(--sage);border-color:var(--sage)}
.who.you{color:var(--clay);border-color:var(--clay)}
.meta-row{font-size:.72rem;color:var(--ink-faint);margin-top:5px}
.meta-row b{color:var(--forest)}
.lead{font-size:1.02rem;color:var(--ink-soft)}
dl.glo{margin:8px 0}
dl.glo dt{font-weight:700;color:var(--ink);margin-top:9px;font-size:.95rem}
dl.glo dd{margin:1px 0 0;color:var(--ink-soft);font-size:.9rem}
.foot{margin-top:30px;border-top:1px solid var(--goldhair);padding-top:11px;font-size:9.5px;color:var(--ink-faint);line-height:1.6}
.big{font-family:var(--fd);color:var(--forest);font-size:1.05rem}
@media print{@page{size:A4;margin:13mm 12mm}.page{max-width:none;padding:0}h2{page-break-before:auto}}
"""

BODY = r"""
<header class="cover">
  <img src="data:image/png;base64,SEAL" alt="">
  <div class="kick">Auralis Natura · Holistic Health</div>
  <h1>Die Kunden-App bauen &amp; veröffentlichen</h1>
  <div class="lede">Der komplette Leitfaden — für absolute Einsteiger.</div>
  <p class="sub">Was, wo, wann und wie — mit jedem Link, den du brauchst. Gebaut für maximale Skalierbarkeit, mühelose Updates und volle DSGVO-Konformität. Recherchiert nach dem Stand der Technik 2026.</p>
  <div class="spark"><i></i><i></i><i></i></div>
  <div class="meta">Technischer Bau- &amp; Launch-Leitfaden · Stand: Juli 2026 · vertraulich<br>Du brauchst <b>kein</b> Vorwissen — jeder Fachbegriff wird erklärt (Kapitel&nbsp;1).</div>
</header>

<h2>So liest du diesen Leitfaden</h2>
<p class="lead">Dieses Dokument erklärt <b>alles</b>, was nötig ist, um aus deinem bestehenden Kunden-Portal eine echte App für Apple&nbsp;App&nbsp;Store und Google&nbsp;Play zu machen — Schritt für Schritt, ohne dass du programmieren können musst.</p>
<p>Jeder Bau-Schritt ist markiert: <span class="who me">Claude</span> = mache ich für dich · <span class="who you">Du</span> = dein aktiver Teil (meist 5–15&nbsp;Minuten, weil es dein Konto oder dein Mac ist). Fachbegriffe stehen erklärt in <b>Kapitel&nbsp;1 (Glossar)</b>. Ganz hinten findest du eine <b>Link-Sammlung</b> mit allen Adressen.</p>
<div class="box gold"><h4>Was du am Ende hast</h4><p style="margin:0">Eine App im gleichen Auralis-Look wie dein Portal, installierbar aus beiden Stores, mit <b>Push-Nachrichten</b> („Dein Bericht ist bereit"), <b>Face-ID-Login</b>, <b>Offline-Zugang</b> und der Möglichkeit, <b>Programme direkt in der App zu kaufen</b> (via Stripe, ohne Apple-Provision). Updates spielst du danach <b>ohne erneute Store-Prüfung</b> ein.</p></div>

<h2>Inhalt</h2>
<ol class="toc">
<li>Glossar — jeder Begriff einfach erklärt</li>
<li>Das große Bild &amp; unsere Entscheidungen (warum)</li>
<li>Die Konten, die du anlegst</li>
<li>Schritt für Schritt: die App bauen</li>
<li>Skalieren &amp; mühelose Updates</li>
<li>DSGVO &amp; Gesundheitsdaten</li>
<li>Kauf direkt in der App (Stripe)</li>
<li>Wartung &amp; der Jahresrhythmus</li>
<li>Kosten auf einen Blick</li>
<li>Wer macht was — deine aktiven Minuten</li>
<li>Der 3-Tage-Launch-Plan</li>
<li>Anhang: alle Links</li>
</ol>

<!-- 1 GLOSSARY -->
<h2><span class="fig">01</span>Glossar — jeder Begriff einfach erklärt</h2>
<p>Lies das einmal quer; du musst nichts auswendig lernen. Immer wenn im Text ein Begriff auftaucht, kannst du hier nachschlagen.</p>
<dl class="glo">
<dt>Web-App / Web-Oberfläche</dt><dd>Deine bestehenden Seiten (Portal, Buchung) — gebaut aus HTML/CSS/JavaScript, also der Sprache von Webseiten. Genau das steckt schon fertig in deinem Projekt.</dd>
<dt>Native App</dt><dd>Eine „echte" App, die man aus dem Store lädt und die ein Icon auf dem Homescreen hat.</dd>
<dt>Capacitor</dt><dd>Das Werkzeug, das deine Web-App in eine native App verwandelt — für iPhone <em>und</em> Android aus <b>einer</b> Vorlage. Es legt eine dünne „native Hülle" um deine Web-Oberfläche und gibt ihr Zugriff auf Handy-Funktionen (Kamera, Face&nbsp;ID, Push).</dd>
<dt>WebView</dt><dd>Das Fenster in der App, das deine Web-Oberfläche anzeigt. Für die Kundin unsichtbar — sie sieht nur „die App".</dd>
<dt>Gebündelt (bundled)</dt><dd>Die Web-Dateien liegen <em>in</em> der App auf dem Handy (nicht auf einem Server). Vorteil: die App startet sofort und funktioniert offline. Das ist der empfohlene Weg.</dd>
<dt>OTA-Update / Live-Update</dt><dd>„Over the air" = über die Luft. Ein Update deiner Inhalte (Texte, Design, Abläufe), das direkt aufs Handy kommt — <b>ohne</b> dass die Kundin etwas aus dem Store neu laden muss und <b>ohne</b> erneute Apple/Google-Prüfung. Das macht Updates mühelos. Wir nutzen dafür den Dienst <b>Capgo</b>.</dd>
<dt>App Store Connect</dt><dd>Apples Web-Seite, auf der du deine iPhone-App verwaltest und einreichst.</dd>
<dt>Play Console</dt><dd>Das Gegenstück bei Google für Android.</dd>
<dt>TestFlight</dt><dd>Apples Test-App: damit installierst du deine App vorab auf dein eigenes iPhone, bevor sie öffentlich ist. Keine Store-Prüfung nötig.</dd>
<dt>Xcode</dt><dd>Apples kostenloses Bau-Programm, läuft nur auf einem Mac (den hast du). Damit wird die iPhone-App erzeugt und hochgeladen.</dd>
<dt>Android Studio</dt><dd>Das Gegenstück für Android; läuft auf Mac/Windows.</dd>
<dt>Signieren / Provisioning</dt><dd>Ein digitaler „Ausweis", der beweist, dass die App wirklich von dir kommt. Xcode kann das automatisch — ein Klick.</dd>
<dt>SDK</dt><dd>„Software Development Kit" — der Werkzeugkasten einer Plattform. Apple/Google verlangen regelmäßig, dass Apps mit einer aktuellen Version gebaut werden (Grund für gelegentliche Neubauten, siehe Wartung).</dd>
<dt>Firebase / FCM</dt><dd>Googles kostenloser Dienst, der Push-Nachrichten an alle Handys verschickt („Firebase Cloud Messaging"). Er ist die Zentrale für „Dein Bericht ist bereit".</dd>
<dt>APNs</dt><dd>„Apple Push Notification service" — Apples Kanal für Push aufs iPhone. Man erzeugt dafür einen kleinen Schlüssel (eine <code>.p8</code>-Datei) im Apple-Konto.</dd>
<dt>Stripe Payment Sheet</dt><dd>Das schicke Bezahlfenster von Stripe, das sich in der App öffnet — inklusive Apple&nbsp;Pay und Google&nbsp;Pay in einem Fingertipp.</dd>
<dt>IAP (In-App-Purchase)</dt><dd>Apples/Googles <em>eigenes</em> Bezahlsystem, bei dem sie 15–30&nbsp;% Provision nehmen. <b>Gilt nur für digitale Güter</b> — deine Coachings sind Dienstleistungen und dürfen Stripe nutzen (Kapitel&nbsp;7).</dd>
<dt>VPS / Server</dt><dd>Ein kleiner Computer im Rechenzentrum, der rund um die Uhr läuft. Dorthin ziehen wir später den Portal-Server, damit er nicht von Desirees Mac abhängt.</dd>
<dt>Docker / Coolify</dt><dd>Docker packt deine App in eine „Kiste", die überall gleich läuft. Coolify ist eine einfache Oberfläche, die diese Kiste auf dem Server startet, SSL einrichtet und bei jedem Git-Push automatisch neu ausrollt — quasi „Vercel für deinen eigenen Server".</dd>
<dt>DSGVO Art.&nbsp;9 / Art.&nbsp;32</dt><dd>Gesundheitsdaten sind besonders geschützt (Art.&nbsp;9 → ausdrückliche Einwilligung nötig). Art.&nbsp;32 verlangt technische Schutzmaßnahmen wie Verschlüsselung (hast du bereits: Fernet).</dd>
</dl>

<!-- 2 BIG PICTURE -->
<h2><span class="fig">02</span>Das große Bild &amp; unsere Entscheidungen (warum)</h2>
<p>Wir bauen <b>nicht neu</b>. Deine Portal-Oberfläche existiert schon und sieht premium aus. Capacitor legt die native Hülle darum — eine Codebasis, beide Stores. Vier Entscheidungen prägen das Projekt; jede folgt der 2026er-Best-Practice:</p>

<h3>Entscheidung 1 · Gebündelt statt „Server-URL"</h3>
<p>Die Web-Dateien liegen <b>in</b> der App (gebündelt). So startet sie sofort und funktioniert offline. Der Alternativweg („die App lädt beim Start alles von einem Server") gilt laut Capacitor-Doku <em>ausdrücklich nicht</em> für den Produktivbetrieb — bei schlechtem Netz sähe die Kundin einen leeren Bildschirm.</p>
<div class="box"><b>Quelle:</b> <a href="https://capacitorjs.com/docs/guides/deploying-updates">capacitorjs.com/docs/guides/deploying-updates</a></div>

<h3>Entscheidung 2 · Mühelose Updates mit Capgo (OTA)</h3>
<p>Inhalts-Updates (Texte, Design, Abläufe) schieben wir <b>direkt aufs Handy</b> — ohne erneute Store-Prüfung. Apple und Google <b>erlauben das ausdrücklich</b> für Web-Inhalte (JavaScript/CSS/Design); nur echte native Änderungen gehen durch die Store-Prüfung. Werkzeug der Wahl ist <b>Capgo</b>: Apples hauseigene Alternative „Appflow" wird <em>eingestellt</em> (keine Neukunden mehr, Ende 2027 Abschaltung). Capgo ist günstig ($12/Monat), verschlüsselt und aktiv gepflegt.</p>
<div class="box"><b>Quellen:</b> <a href="https://capgo.app/">capgo.app</a> · <a href="https://capgo.app/blog/capacitor-ota-updates-vs-app-store-restrictions/">OTA vs. App-Store-Regeln</a></div>

<h3>Entscheidung 3 · Der Server zieht auf einen EU-Rechner</h3>
<p>Für eine echte App, auf die sich Kundinnen verlassen, sollte der Portal-Server <b>immer</b> laufen — nicht nur, wenn Desirees Mac wach ist. Empfehlung mit dem besten Preis-Leistungs-Verhältnis in der EU: ein kleiner <b>Hetzner-Server</b> (ab ~€4/Monat, deutsche Rechenzentren → DSGVO-freundlich) mit <b>Coolify</b> für automatische Updates &amp; SSL. Wer es ganz einfach mag, nimmt <b>Render</b> (verwaltet, EU-Region, ~$7/Monat). Beide sind für Gesundheitsdaten besser als US-Anbieter.</p>
<div class="box"><b>Quellen:</b> <a href="https://www.hetzner.com/cloud">hetzner.com/cloud</a> · <a href="https://coolify.io/">coolify.io</a> · <a href="https://render.com/">render.com</a></div>

<h3>Entscheidung 4 · Bezahlen mit Stripe — ohne Apple-Provision</h3>
<p>Deine Programme sind <b>persönliche Dienstleistungen</b> (1-zu-1-Coaching). Apples Regel 3.1.3(d) erlaubt für solche „Person-zu-Person"-Dienste ausdrücklich <b>eigene Bezahlwege</b> — also Stripe, <b>ohne</b> die 15–30&nbsp;% Provision. Du behältst ~98,5&nbsp;% (nur Stripe-Gebühr). Details &amp; die eine Grenze in Kapitel&nbsp;7.</p>
<div class="box"><b>Quellen:</b> <a href="https://developer.apple.com/app-store/review/guidelines/">App-Store-Richtlinien 3.1.3</a> · <a href="https://docs.stripe.com/payments/mobile/payment-sheet">Stripe Payment Sheet</a></div>

<!-- 3 ACCOUNTS -->
<h2><span class="fig">03</span>Die Konten, die du anlegst</h2>
<p>Diese Konten brauchst du. Einige hast du schon. Lege die drei mit Wartezeit (Apple, Google, Firebase) <b>zuerst</b> an — der Rest geht sofort.</p>
<table>
<tr><th>Konto</th><th>Wofür</th><th>Adresse</th><th>Kosten</th><th>Dein Aufwand</th></tr>
<tr><td><b>Apple Developer</b></td><td>iPhone-App veröffentlichen</td><td><a href="https://developer.apple.com/programs/">developer.apple.com/programs</a></td><td>$99/Jahr</td><td>~20 Min · Freigabe 24–48&nbsp;h</td></tr>
<tr><td><b>Google Play Console</b></td><td>Android-App veröffentlichen</td><td><a href="https://play.google.com/console">play.google.com/console</a></td><td>$25 einmalig</td><td>~15 Min</td></tr>
<tr><td><b>Firebase</b></td><td>Push-Nachrichten</td><td><a href="https://console.firebase.google.com/">console.firebase.google.com</a></td><td>kostenlos</td><td>~5 Min</td></tr>
<tr><td><b>Capgo</b></td><td>Mühelose OTA-Updates</td><td><a href="https://capgo.app/">capgo.app</a></td><td>~$12/Monat</td><td>~5 Min</td></tr>
<tr><td><b>Stripe</b></td><td>Bezahlen in der App</td><td><a href="https://dashboard.stripe.com/">dashboard.stripe.com</a></td><td>pro Transaktion</td><td>hast du schon</td></tr>
<tr><td><b>Hetzner</b> oder <b>Render</b></td><td>Server (Portal-Backend)</td><td><a href="https://www.hetzner.com/cloud">hetzner.com</a> / <a href="https://render.com/">render.com</a></td><td>~€4–7/Monat</td><td>~10 Min · optional/später</td></tr>
<tr><td><b>Apple ID</b> / <b>Google-Konto</b></td><td>Login-Basis für obiges</td><td>—</td><td>kostenlos</td><td>hast du schon</td></tr>
</table>
<div class="box warn"><h4>Wichtige Weiche bei Apple</h4><p style="margin:0"><b>Einzelperson</b> (Individual) ist schneller freigeschaltet und reicht für den Start. Ein <b>Firmen-Konto</b> zeigt den Firmennamen im Store, braucht aber eine <b>D-U-N-S-Nummer</b> (kostenlos, kann aber 1–2 Tage dauern). Für morgen/schnell: Einzelperson. Apple lässt den Typ später nicht einfach wechseln — sag mir vorher Bescheid, welchen du willst.</p></div>

<!-- 4 STEP BY STEP -->
<h2><span class="fig">04</span>Schritt für Schritt: die App bauen</h2>
<p>In Reihenfolge. Bei jedem Schritt steht, <b>wer</b> ihn macht und <b>wie lange</b> dein Teil dauert.</p>

<div class="step"><div class="sh">A · Web-Oberfläche app-fertig machen <span class="who me">Claude</span></div>
Ich richte eine kleine, für die App optimierte Fassung deines Portals ein (gleicher Look, plus native Navigation). <div class="meta-row"><b>Dein Aufwand:</b> 0 · <b>Werkzeug:</b> das bestehende Repo.</div></div>

<div class="step"><div class="sh">B · Capacitor-Projekt anlegen &amp; Plattformen hinzufügen <span class="who me">Claude</span></div>
Ich installiere Capacitor und erzeuge die iOS- und Android-Projekte (<code>npm i @capacitor/core</code>, <code>npx cap add ios</code>, <code>npx cap add android</code>). <div class="meta-row"><b>Dein Aufwand:</b> 0 · <b>Anleitung:</b> <a href="https://capacitorjs.com/docs/getting-started">capacitorjs.com/docs/getting-started</a></div></div>

<div class="step"><div class="sh">C · App-Icon &amp; Startbildschirm aus dem Siegel <span class="who me">Claude</span></div>
Aus deinem botanischen Siegel erzeuge ich alle Icon- &amp; Splash-Größen automatisch mit <code>@capacitor/assets</code> (ein Logo rein → alle Formate raus). <div class="meta-row"><b>Dein Aufwand:</b> 0 · <b>Werkzeug:</b> <a href="https://github.com/ionic-team/capacitor-assets">capacitor-assets</a></div></div>

<div class="step"><div class="sh">D · Native Funktionen: Push, Face&nbsp;ID, Offline, Stripe <span class="who me">Claude</span> <span class="who you">Du</span></div>
Ich baue Push (Plugin <code>@capacitor-firebase/messaging</code>), Face-ID-Login, Offline-Speicher und das Stripe-Bezahlfenster ein.<br>
<b>Dein Teil:</b> im Apple-Konto einen <b>APNs-Schlüssel</b> (<code>.p8</code>) erzeugen und in Firebase hochladen (ich zeige jeden Klick); Firebase-Projekt benennen. <div class="meta-row"><b>Dein Aufwand:</b> ~10 Min · <b>Anleitung:</b> <a href="https://capacitorjs.com/docs/guides/push-notifications-firebase">Push mit Firebase</a> · <a href="https://github.com/Cap-go/capacitor-stripe-pay">Stripe-Plugin</a> · <b>Hinweis:</b> Push testet man nur auf einem <em>echten</em> iPhone, nicht im Simulator.</div></div>

<div class="step"><div class="sh">E · Mühelose Updates verdrahten (Capgo) <span class="who me">Claude</span> <span class="who you">Du</span></div>
Ich verbinde die App mit Capgo, damit du künftig Inhalts-Updates per Knopfdruck ausspielst.<br>
<b>Dein Teil:</b> Capgo-Konto anlegen, einen Schlüssel kopieren. <div class="meta-row"><b>Dein Aufwand:</b> ~5 Min · <b>Anleitung:</b> <a href="https://capgo.app/">capgo.app</a></div></div>

<div class="step"><div class="sh">F · iPhone-App bauen &amp; auf dein Handy (TestFlight) <span class="who you">Du</span> <span class="who me">Claude</span></div>
Ich bereite alles in Xcode vor. <b>Dein Teil</b> (an Desirees Mac, ich führe dich Klick für Klick): in Xcode mit deiner Apple-ID anmelden, „Automatisch signieren" aktivieren, auf „Run" drücken → die App landet auf dem iPhone. Danach Test über TestFlight. <div class="meta-row"><b>Dein Aufwand:</b> ~20 Min · <b>Anleitung:</b> <a href="https://developer.apple.com/app-store/submitting/">developer.apple.com/app-store/submitting</a> · <a href="https://help.apple.com/xcode/mac/current/en.lproj/dev067853c94.html">Xcode: App verteilen</a></div></div>

<div class="step"><div class="sh">G · Android-App bauen <span class="who me">Claude</span></div>
Ich erzeuge das Android-Paket (AAB) in Android Studio und die Store-Screenshots aus deinen echten Bildschirmen. <div class="meta-row"><b>Dein Aufwand:</b> 0</div></div>

<div class="step"><div class="sh">H · Store-Einträge, Datenschutz &amp; „Data Safety" <span class="who me">Claude</span> <span class="who you">Du</span></div>
Ich entwerfe alles: Beschreibung (DE/EN/ES), Keywords, Datenschutz-Text, Apples <b>Privacy-Labels</b> und Googles <b>Data-Safety-Formular</b> (14 Datenkategorien) inkl. Googles <b>Health-Apps-Erklärung</b>.<br>
<b>Dein Teil:</b> Texte kurz prüfen, Antworten bestätigen, „Einreichen" klicken. <div class="meta-row"><b>Dein Aufwand:</b> ~30 Min · <b>Anleitung:</b> <a href="https://support.google.com/googleplay/android-developer/answer/10787469">Google Data Safety</a> · <a href="https://support.google.com/googleplay/android-developer/answer/16679511">Health Content</a></div></div>

<div class="step"><div class="sh">I · Backend auf den EU-Server (optional, empfohlen) <span class="who me">Claude</span> <span class="who you">Du</span></div>
Ich packe den Flask-Server in Docker und richte ihn mit Coolify auf Hetzner ein (oder auf Render) — inkl. HTTPS &amp; Auto-Deploy aus GitHub.<br>
<b>Dein Teil:</b> Hetzner-/Render-Konto anlegen, Zahlungsmittel hinterlegen. <div class="meta-row"><b>Dein Aufwand:</b> ~10 Min · <b>Anleitung:</b> <a href="https://coolify.io/">coolify.io</a></div></div>

<!-- 5 SCALE + UPDATES -->
<h2><span class="fig">05</span>Skalieren &amp; mühelose Updates</h2>
<h3>So läuft ein Update, wenn die App live ist</h3>
<ul>
<li><b>Inhalt ändern</b> (Text, Preis, Design, Ablauf): Ich baue neu, spiele es über <b>Capgo</b> aus → deine Kundinnen haben es beim nächsten App-Start, <b>ohne Store-Prüfung, ohne Neuinstallation</b>. Minuten statt Tage.</li>
<li><b>Native Änderung</b> (neue Handy-Funktion, SDK-Pflicht): geht einmalig durch die normale Store-Prüfung (24–48&nbsp;h). Das ist selten — meist reicht Capgo.</li>
</ul>
<h3>So skaliert das System mit</h3>
<ul>
<li><b>Wenige bis Hunderte Kundinnen:</b> Der kleine Hetzner-/Render-Server genügt locker. Verschlüsselte SQLite reicht für den Start.</li>
<li><b>Wachstum:</b> Server-Größe per Klick erhöhen (mehr RAM/CPU). Bei Bedarf später auf eine EU-gehostete Postgres-Datenbank wechseln — gleicher Code-Ansatz.</li>
<li><b>Bilder/PDFs:</b> Über den Server oder einen EU-Objektspeicher ausliefern; die App selbst bleibt schlank (gebündelt).</li>
<li><b>Push in Masse:</b> Firebase FCM ist kostenlos bis in die Millionen — kein Engpass.</li>
</ul>
<div class="box gold"><p style="margin:0"><b>Kernidee:</b> Eine Codebasis → beide Stores. Inhalte fließen per Capgo, Daten per API vom EU-Server. Du wächst, ohne die Architektur zu wechseln.</p></div>

<!-- 6 GDPR -->
<h2><span class="fig">06</span>DSGVO &amp; Gesundheitsdaten</h2>
<p>Gesundheitsdaten sind „besondere Kategorien" (Art.&nbsp;9 DSGVO). Vieles hast du bereits richtig — hier die App-spezifischen Punkte:</p>
<ul>
<li><b>Ausdrückliche Einwilligung (Art.&nbsp;9):</b> ein <em>eigener</em> Zustimmungsschritt, der die Gesundheitsdaten <b>benennt</b> — nicht in AGB versteckt. Deine Buchung/Intake hat das bereits; in der App übernehmen wir es 1:1.</li>
<li><b>Verschlüsselung (Art.&nbsp;32):</b> erledigt — deine Daten liegen Fernet-verschlüsselt. Auf dem Handy speichert die App Zugangs-Token im sicheren Schlüsselbund.</li>
<li><b>EU-Hosting:</b> nicht zwingend, aber der einfachste &amp; sicherste Weg für Gesundheitsdaten. Deshalb Hetzner (DE) oder Render-EU.</li>
<li><b>Auftragsverarbeitung (AVV/DPA):</b> mit jedem Dienstleister abschließen, der Daten berührt — Hetzner/Render (Hosting), ggf. Firebase (nur Push-Token, keine Gesundheitsdaten!). Wir halten Gesundheitsdaten bewusst von Firebase fern.</li>
<li><b>Einwilligungs-Nachweise:</b> Zeitpunkt, Version des Textes, Umfang speichern — hast du im Kundinnen-Datensatz bereits angelegt.</li>
<li><b>Store-Formulare:</b> Apples Privacy-Labels &amp; Googles Data-Safety müssen zur <em>tatsächlichen</em> App passen — Google prüft das automatisch gegen. Ich fülle sie wahrheitsgemäß aus.</li>
</ul>
<div class="box"><b>Quellen:</b> <a href="https://gdpr-info.eu/art-9-gdpr/">Art. 9 DSGVO</a> · <a href="https://gdpr-info.eu/art-32-gdpr/">Art. 32 DSGVO</a> · <a href="https://support.google.com/googleplay/android-developer/answer/16679511">Google Health Content</a></div>
<div class="box warn"><p style="margin:0"><b>Leitplanke bleibt:</b> Coaching &amp; Bildung, nicht Medizin. Die App-Beschreibung im Store muss das genauso klar sagen wie die Website — Apple prüft Gesundheits-Claims streng.</p></div>

<!-- 7 IAP -->
<h2><span class="fig">07</span>Kauf direkt in der App (Stripe)</h2>
<p>Ja — und für dich <b>ohne</b> Apple/Google-Provision, weil Coaching eine Dienstleistung ist.</p>
<table>
<tr><th>Was verkauft wird</th><th>Bezahlweg</th><th>Provision</th></tr>
<tr><td><b>Persönliche Dienstleistung</b> (Coaching, Gespräch, Bericht)</td><td>Dein Stripe ✅</td><td><b>0 %</b> (nur Stripe-Gebühr ~1,5 % + €0,25)</td></tr>
<tr><td>Rein digitales Selbstbedienungs-Produkt (E-Book, Videokurs)</td><td>Apple/Google-System</td><td>15–30 %</td></tr>
</table>
<p><b>In der App:</b> ein „Programme"-Screen (Root/Bloom/Flourishing/Grove) → antippen → <b>Stripe-Bezahlfenster</b> mit Apple&nbsp;Pay/Google&nbsp;Pay in einem Tipp → Zahlung landet im gleichen Stripe + in der Betriebskonsole („Bezahlt"), die Journey rückt automatisch weiter. Kein neues Bezahlsystem nötig.</p>
<div class="box gold"><p style="margin:0"><b>Die eine Grenze:</b> Solange jedes bezahlte Angebot an die Coaching-/Bericht-<em>Leistung</em> gekoppelt ist, bleibst du im Stripe-Weg. Ein reines Download-Produkt ohne Mensch würde die Store-Provision auslösen.</p></div>
<p><b>Aufwand:</b> ~½ Tag zusätzlich, da Stripe &amp; „Bezahlt"-Logik schon existieren. <b>Quellen:</b> <a href="https://docs.stripe.com/payments/mobile">Stripe In-App-Zahlungen</a> · <a href="https://developer.apple.com/app-store/review/guidelines/">Richtlinie 3.1.3(d)</a></p>

<!-- 8 MAINTENANCE -->
<h2><span class="fig">08</span>Wartung &amp; der Jahresrhythmus</h2>
<p>Website, Portal und Konsole laufen praktisch wartungsfrei. Die App hat den einzigen „Herzschlag":</p>
<table>
<tr><th>Aufgabe</th><th>Wie oft</th><th>Dein Aufwand (ich mache die Technik)</th></tr>
<tr><td>App gegen neues SDK neu bauen (Apple/Google-Pflicht)</td><td>1–2×/Jahr</td><td>~15 Min pro Einreichung</td></tr>
<tr><td>Verteil-Zertifikat erneuern</td><td>jährlich</td><td>~15 Min</td></tr>
<tr><td>Capgo-/Abhängigkeits-Updates</td><td>gelegentlich</td><td>~0 (mache ich)</td></tr>
<tr><td>Server-Sicherheits-Patches</td><td>2–3×/Jahr</td><td>~0 (mache ich)</td></tr>
</table>
<p><b>Summe:</b> mit meiner Hilfe ~<b>2–4&nbsp;Stunden pro Jahr</b>, in kleinen Häppchen. Ohne Hilfe eher 1–3&nbsp;Tage (fast alles davon der Store-Zyklus). Faustregel: <b>Website/Portal/Konsole = einmal bauen, läuft. Die App ist das einzige Teil, das man gelegentlich pflegt</b> — und diese Pflege kann ich übernehmen.</p>

<!-- 9 COSTS -->
<h2><span class="fig">09</span>Kosten auf einen Blick</h2>
<h3>Einmalig (Start)</h3>
<table>
<tr><th>Posten</th><th>Kosten</th></tr>
<tr><td>Google Play Konto (lebenslang)</td><td>~€23</td></tr>
<tr><td>App bauen (ich mache es)</td><td>€0</td></tr>
<tr><td><b>Start-Summe</b></td><td><b>≈ €23</b></td></tr>
</table>
<h3>Pro Jahr (Betrieb)</h3>
<table>
<tr><th>Posten</th><th>Pro Jahr</th><th>Nötig?</th></tr>
<tr><td>Apple Developer</td><td>~€92</td><td>nur für iOS</td></tr>
<tr><td>Capgo (mühelose Updates)</td><td>~€135 ($12/Mon.)</td><td>empfohlen</td></tr>
<tr><td>EU-Server (Hetzner/Render)</td><td>~€50–90</td><td>empfohlen für App-Betrieb</td></tr>
<tr><td>Domain</td><td>~€12</td><td>hast du</td></tr>
<tr><td>Claude (KI-Berichte)</td><td>~€216</td><td>hast du evtl. schon</td></tr>
<tr><td>Firebase Push · Cloudflare</td><td>€0</td><td>Gratis-Stufe</td></tr>
</table>
<p><b>Realistisch neu dazu für die App:</b> Apple €92 + Capgo €135 + Server ~€70 ≈ <b>€300/Jahr</b>. Ohne iOS (nur Android+PWA) und ohne Capgo entsprechend weniger. <b>Stripe</b> kostet nur pro Verkauf (~1,5 % + €0,25).</p>

<!-- 10 WHO DOES WHAT -->
<h2><span class="fig">10</span>Wer macht was — deine aktiven Minuten</h2>
<table>
<tr><th>Dein Teil (aktiv)</th><th>Minuten</th></tr>
<tr><td>Apple-Developer-Konto starten</td><td>~20</td></tr>
<tr><td>Google-Play-Konto starten</td><td>~15</td></tr>
<tr><td>Firebase-Projekt anlegen</td><td>~5</td></tr>
<tr><td>APNs-Schlüssel erzeugen</td><td>~5</td></tr>
<tr><td>Capgo-Konto</td><td>~5</td></tr>
<tr><td>Xcode: anmelden, signieren, „Run"</td><td>~10</td></tr>
<tr><td>App auf dem iPhone testen</td><td>~10</td></tr>
<tr><td>Store-Texte prüfen + Data-Safety bestätigen</td><td>~25</td></tr>
<tr><td>„Einreichen" klicken (×2)</td><td>~5</td></tr>
<tr><td>Server-Konto (optional)</td><td>~10</td></tr>
<tr><td><b>Summe</b></td><td><b>≈ 100 Min</b></td></tr>
</table>
<p><b>Alles andere</b> — Programmierung, Konfiguration, Icons, Screenshots, sämtliche Texte, Datenschutz, Server-Einrichtung — mache ich.</p>

<!-- 11 3 DAY -->
<h2><span class="fig">11</span>Der 3-Tage-Launch-Plan</h2>
<p>Voraussetzung: Apple-Konto am <b>Morgen von Tag 1</b> starten (24–48&nbsp;h Freigabe ist der einzige echte Engpass).</p>
<table>
<tr><th>Tag</th><th>Du (aktiv)</th><th>Ich (im Hintergrund)</th></tr>
<tr><td><b>1</b></td><td>Konten starten: Apple, Google, Firebase (~40 Min)</td><td>Capacitor-Projekt, Icons/Splash, Android-Build, Store-Texte</td></tr>
<tr><td><b>2</b></td><td>APNs-Schlüssel · Xcode signieren · auf iPhone testen (~25 Min)</td><td>Push, Face ID, Offline, Stripe, Capgo verdrahten</td></tr>
<tr><td><b>3</b></td><td>Texte prüfen · Data-Safety bestätigen · einreichen (~30 Min)</td><td>Feinschliff, beide Stores einreichen</td></tr>
</table>
<p><b>„Fertig in 3 Tagen"</b> heißt: beide Apps laufen auf deinem iPhone und sind eingereicht. Google ist meist Tag&nbsp;3 live; Apple genehmigt üblicherweise 24–48&nbsp;h nach Einreichung (also Tag 4–5). <b>Quelle:</b> <a href="https://developer.apple.com/app-store/submitting/">Apple-Einreichung</a></p>

<!-- 12 LINKS -->
<h2><span class="fig">12</span>Anhang: alle Links</h2>
<h3>Werkzeuge &amp; Doku</h3>
<ul>
<li>Capacitor — Start: <a href="https://capacitorjs.com/docs/getting-started">capacitorjs.com/docs/getting-started</a></li>
<li>Capacitor — Updates/Deploy: <a href="https://capacitorjs.com/docs/guides/deploying-updates">/guides/deploying-updates</a></li>
<li>Icons &amp; Splash: <a href="https://github.com/ionic-team/capacitor-assets">github.com/ionic-team/capacitor-assets</a></li>
<li>Capgo (OTA-Updates): <a href="https://capgo.app/">capgo.app</a></li>
<li>Push mit Firebase: <a href="https://capacitorjs.com/docs/guides/push-notifications-firebase">capacitorjs.com/docs/guides/push-notifications-firebase</a></li>
<li>Stripe In-App: <a href="https://docs.stripe.com/payments/mobile">docs.stripe.com/payments/mobile</a> · Plugin: <a href="https://github.com/Cap-go/capacitor-stripe-pay">Cap-go/capacitor-stripe-pay</a></li>
</ul>
<h3>Konten &amp; Stores</h3>
<ul>
<li>Apple Developer: <a href="https://developer.apple.com/programs/">developer.apple.com/programs</a> · Einreichen: <a href="https://developer.apple.com/app-store/submitting/">/app-store/submitting</a> · Richtlinien: <a href="https://developer.apple.com/app-store/review/guidelines/">/review/guidelines</a></li>
<li>Google Play Console: <a href="https://play.google.com/console">play.google.com/console</a> · Data Safety: <a href="https://support.google.com/googleplay/android-developer/answer/10787469">Hilfe 10787469</a> · Health: <a href="https://support.google.com/googleplay/android-developer/answer/16679511">Hilfe 16679511</a></li>
<li>Firebase: <a href="https://console.firebase.google.com/">console.firebase.google.com</a></li>
<li>Stripe: <a href="https://dashboard.stripe.com/">dashboard.stripe.com</a></li>
</ul>
<h3>Server &amp; Recht</h3>
<ul>
<li>Hetzner Cloud: <a href="https://www.hetzner.com/cloud">hetzner.com/cloud</a> · Coolify: <a href="https://coolify.io/">coolify.io</a> · Render: <a href="https://render.com/">render.com</a></li>
<li>DSGVO: <a href="https://gdpr-info.eu/art-9-gdpr/">Art. 9</a> · <a href="https://gdpr-info.eu/art-32-gdpr/">Art. 32</a></li>
</ul>

<div class="foot">
<b>Auralis Natura — Holistic Health.</b> Technischer Bau- &amp; Launch-Leitfaden für die Kunden-App · Stand Juli 2026 · recherchiert nach aktuellem Stand der Technik. Coaching &amp; Bildung, keine medizinische Versorgung. Gesundheitsdaten (DSGVO Art.&nbsp;9) bleiben verschlüsselt und in der EU. Preise/Links können sich ändern — vor dem Kauf kurz prüfen. Vertraulich, nur intern.
</div>
"""

html = ("<!doctype html><html lang=\"de\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Auralis Natura — Kunden-App bauen &amp; veroeffentlichen</title>"
        "<link href=\"https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..600;1,9..144,300..500&family=Hanken+Grotesk:wght@400;500;600&display=swap\" rel=\"stylesheet\">"
        f"<style>{CSS}</style></head><body><div class=\"page\">"
        + BODY.replace("SEAL", seal) + "</div></body></html>")

html_path = OUT_DIR / "CUSTOMER-APP-BUILD-GUIDE.html"
html_path.write_text(html, encoding="utf-8")
print("HTML", html_path, len(html), "bytes")

from playwright.sync_api import sync_playwright
CH = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
pdf_path = OUT_DIR / "CUSTOMER-APP-BUILD-GUIDE.pdf"
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CH, args=["--no-sandbox", "--disable-gpu"])
    pg = b.new_page()
    pg.goto("file://" + str(html_path), wait_until="networkidle")
    pg.wait_for_timeout(1200)
    pg.pdf(path=str(pdf_path), format="A4", print_background=True,
           margin={"top": "13mm", "bottom": "13mm", "left": "12mm", "right": "12mm"})
    b.close()
print("PDF", pdf_path, pdf_path.stat().st_size, "bytes")
