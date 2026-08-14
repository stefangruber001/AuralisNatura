#!/usr/bin/env python3
"""Build the Social-Media-Manager go-live guide as a branded PDF.

Same stack as everything else on brand: self-hosted woff2 inlined, canonical
tokens, square corners, hairlines, seal watermark — rendered by the same
headless Chromium that prints the client report.

    python3 portal/tools/build_social_guide.py [out.pdf]
"""
from __future__ import annotations
import base64
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import cfg, render  # noqa: E402

E = html.escape
MASTERS = cfg.ROOT.parent / "brand" / "masters"


def _b64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


SEAL = _b64(cfg.ASSETS_DIR / "seal.png")
WM = _b64(MASTERS / "seal-gold-watermark-1200.png")

PAGES: list[str] = []


def page(inner: str, cls: str = "") -> None:
    PAGES.append(f'<section class="page {cls}">{inner}</section>')


def head(kicker: str, title: str, sub: str = "") -> str:
    return (f'<div class="ph"><span class="kick">{E(kicker)}</span>'
            f'<h2>{E(title)}</h2>'
            + (f'<p class="sub">{E(sub)}</p>' if sub else "") + "</div>")


def step(n: str, title: str, where: str, mins: str, body: str) -> str:
    return (f'<div class="step"><div class="sn">{E(n)}</div><div class="sb">'
            f'<h3>{E(title)}</h3>'
            f'<div class="meta"><span class="tag">WO</span>{where}'
            f'<span class="tag">DAUER</span>{E(mins)}</div>{body}</div></div>')


def box(title: str, body: str, kind: str = "note") -> str:
    return (f'<div class="box {kind}"><div class="bt">{E(title)}</div>{body}</div>')


def ol(items: list[str]) -> str:
    return "<ol class='steps'>" + "".join(f"<li>{i}</li>" for i in items) + "</ol>"


def ul(items: list[str]) -> str:
    return "<ul class='bul'>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def k(s: str) -> str:
    """A UI element the reader must find on screen."""
    return f'<span class="ui">{E(s)}</span>'


def c(s: str) -> str:
    return f'<code>{E(s)}</code>'


def cb(s: str) -> str:
    """A command on its OWN line. Two inline <code> boxes side by side extract
    as one merged line when copied out of a PDF — which turns two commands
    into one nonsense command. Block level keeps them apart."""
    return f'<code class="blk">{E(s)}</code>'


# ═══════════════════════════════════════════════════════════════════ cover ══
page(f'''
<img class="wm" src="data:image/png;base64,{WM}" alt="">
<div class="cin">
  <img class="seal" src="data:image/png;base64,{SEAL}" alt="">
  <div class="ckick">Betriebskonsole · Modul 06</div>
  <div class="crule"></div>
  <h1>Social-Media-Manager<br><em>Schritt für Schritt live schalten</em></h1>
  <p class="clead">Von der leeren Registerkarte bis zum Post, der sich selbst
  veröffentlicht — jeder Klick, jede Eingabe, jeder Handgriff.</p>
  <div class="cmeta"><span>Auralis Natura</span><span class="sep"></span>
  <span>Stand 14.08.2026</span><span class="sep"></span><span>Version 1.0</span></div>
</div>''', "cover")

# ════════════════════════════════════════════════════════ how it works ══
page(head("Orientierung", "Was das Modul für dich tut",
          "Ein Blick auf die Maschine, bevor du sie einschaltest.") + f'''
<p>Der Social-Media-Manager ist ein <b>Wochenkreislauf</b>. Er läuft auf deinem eigenen
Server, kostet nichts zusätzlich und hat genau eine Stelle, an der ein Mensch entscheidet:
<b>deine Freigabe</b>. Ohne sie verlässt nichts das Haus.</p>

<div class="flow">
  <div class="fs"><span class="fn">1</span><b>Montag 05:00 — Beobachten</b>
    <span>Die Agenten lesen Fachjournale, Blogs und Newsletter deiner Wettbewerberinnen.
    Neue Fundstücke werden gesammelt.</span></div>
  <div class="fs"><span class="fn">2</span><b>Montag 05:0x — Verdichten</b>
    <span>Claude fasst die Woche auf Deutsch zusammen: Themen, Funde mit Quellenlink,
    konkrete Content-Ideen, worüber der Wettbewerb spricht.</span></div>
  <div class="fs"><span class="fn">3</span><b>Montag 05:0x — Entwerfen</b>
    <span>Aus deinem Wochenziel + dem Digest + deinem hochgeladenen Material entsteht die
    Wochenstrategie und pro Slot ein fertiger Entwurf: Caption DE/EN/ES, Hashtags,
    Alt-Text, Bildvorlage.</span></div>
  <div class="fs now"><span class="fn">4</span><b>Du: 20–30 Minuten — Prüfen &amp; Freigeben</b>
    <span>Du liest, änderst, wo du magst, und hakst „freigegeben“ an. Das ist dein Teil.</span></div>
  <div class="fs"><span class="fn">5</span><b>Automatisch — Veröffentlichen</b>
    <span>Der Server erzeugt die Bilder im Auralis-Design und postet jeden freigegebenen
    Slot zur geplanten Zeit auf Instagram. Kein Kopieren, kein Einfügen.</span></div>
</div>

{box("Zwei Wege — du entscheidest, wann du wechselst", ul([
 "<b>Weg A · Manuell (funktioniert sofort):</b> Du lädst das Wochenpaket als ZIP herunter "
 "und planst die Posts im kostenlosen Meta-Business-Suite-Planer. Aufwand: ca. 10 Minuten pro Woche.",
 "<b>Weg B · Automatisch (nach ~40 Min. Einrichtung):</b> Freigabe genügt. Der Server "
 "veröffentlicht selbst, zur geplanten Minute. Aufwand: 0 Minuten pro Woche.",
]) + "<p class='mt'>Kapitel 5 dieser Anleitung richtet Weg B ein. Bis dahin — und immer als "
     "Rückfalloption — steht Weg A bereit.</p>")}

{box("Was Instagram technisch nicht kann (und warum das hier so gelöst ist)",
 "<p>Es gibt <b>keine Schnittstelle, die Entwürfe in die Meta Business Suite legt</b> — "
 "Meta erlaubt über die API nur das echte Veröffentlichen. Deshalb ist die "
 "<b>Betriebskonsole selbst</b> dein Review-Ort: du gibst dort frei, und der Server "
 "veröffentlicht danach. Das ist der einzige Weg, der wirklich ohne Copy-Paste auskommt.</p>",
 "warn")}
''')

# ═══════════════════════════════════════════════════ chapter 1 · server ══
page(head("Kapitel 1", "Den Server scharf schalten",
          "Einmalig. Danach läuft die Automatik von allein.") + f'''
<p>Der Code ist bereits auf dem Server — er aktualisiert sich alle zwei Minuten selbst von
GitHub. Was der Selbst-Updater <b>nicht</b> kann: neue Zeitschaltungen (systemd-Timer)
anlegen und Systempakete installieren. Genau dafür ist dieser eine Lauf.</p>

{box("Was nach diesem Schritt anders ist", ul([
 "Der <b>Montags-Scan</b> läuft automatisch um 05:00 Uhr (statt nur auf Knopfdruck).",
 "Die <b>Veröffentlichungs-Warteschlange</b> wird alle 10 Minuten abgearbeitet.",
 "<b>ffmpeg</b> ist installiert — erst damit entstehen Reels als MP4 (und die JPEG-Umwandlung "
 "für Instagram, siehe Kapitel 5).",
 "<code>social.json</code> wandert in die nächtliche Datensicherung.",
]))}

{step("1.1", "Firewall für deinen Rechner öffnen", "Hetzner Cloud Console", "2 Min", ol([
 f"Auf {c('console.hetzner.cloud')} anmelden → Projekt → {k('Firewalls')}.",
 "Die Firewall des Servers öffnen → Regel für <b>SSH (Port 22)</b> bearbeiten.",
 "Deine aktuelle IP-Adresse eintragen (findest du auf <code>ifconfig.me</code>) — "
 "im Format <code>x.x.x.x/32</code>. Speichern.",
]) + box("Warum", "<p>Der SSH-Zugang ist absichtlich auf einzelne IP-Adressen begrenzt. "
        "Deine Heim-IP ändert sich gelegentlich — dann muss sie neu eingetragen werden.</p>"))}

{box("Beim Kopieren aus dem PDF aufpassen",
 "<p>PDF-Betrachter bauen beim Kopieren manchmal Zeilenumbrüche in lange Befehle ein — "
 "gern genau an einem Unterstrich. Der Befehl zerfällt dann in drei Teile und die Konsole "
 "meldet <code>No such file or directory</code>. Deshalb stehen hier bewusst <b>kurze "
 "Befehle mit Stern statt Unterstrich</b>. Prüfe vor dem Enter: steht wirklich alles in "
 "<b>einer</b> Zeile?</p>", "warn")}

{step("1.2", "Das Aktivierungsskript starten", "Terminal auf deinem Mac", "2–3 Min", ol([
 f"Verbinden: {cb('ssh root@178.105.10.156')}",
 f"Aktivieren: {cb('bash /opt/auralis/app/portal/deploy/social-go-live.sh')}",
 "Es zeigt zuerst, welche Pakete es installieren würde, und fragt einmal nach — "
 "mit <b>j</b> bestätigen.",
 "Am Ende steht grün „Social-Modul ist scharf geschaltet“ und darunter die zwei Timer.",
]) + box("Warum nicht der große Installer?",
        "<p><code>install_server.sh</code> ist ein <b>Empfänger</b>: er verlangt ein Paket "
        "mit Datenschlüssel, SMTP-Passwort und Claude-Token vom Mac, weil sein Auftrag ist, "
        "einen Server von null aufzubauen. All das steht längst korrekt auf der Maschine. "
        "<code>social-go-live.sh</code> macht nur die Differenz — ffmpeg, die zwei Timer, "
        "die Datensicherung — und schreibt dabei exakt dieselben Einheiten. Beide Skripte "
        "sind beliebig oft wiederholbar.</p>"))}

''')

page(head("Kapitel 1 — Fortsetzung", "Prüfen, dass es steht",
          "Zwei Befehle, und du weißt, dass die Automatik läuft.") + f'''
{step("1.3", "Prüfen, dass die Timer stehen", "Terminal (gleiche Sitzung)", "1 Min",
 f"<p>Ein Befehl, eine Antwort:</p>{c('systemctl list-timers auralis-*')}"
 + ul([
   "<code>auralis-social-scan.timer</code> → nächster Lauf: kommender <b>Montag 05:00</b>",
   "<code>auralis-social-publish.timer</code> → nächster Lauf: in <b>≤ 10 Minuten</b>",
   "<code>auralis-update.timer</code> und <code>auralis-backup.timer</code> → unverändert da",
 ]) + f"<p class='mt'>Und die Gesamtprüfung: {cb('bash /opt/auralis/app/portal/deploy/verify_server.sh')}</p>")}
''')

# ═════════════════════════════════════════════════ chapter 2 · the tab ══
page(head("Kapitel 2", "Ziel, Takt und Quellen einstellen",
          "Die Registerkarte „Social Media“ — von links nach rechts, von oben nach unten.") + f'''
{step("2.1", "Die Registerkarte öffnen", "Betriebskonsole", "10 Sek", ol([
 f"{c('api.auralisnatura.com/staff')} öffnen (oder die „Office“-App auf dem Homescreen).",
 f"In der Registerkartenleiste ganz nach rechts wischen → {k('Social Media')}.",
 "Du siehst fünf Abschnitte untereinander: <b>Ziel &amp; Kadenz</b>, <b>Beobachtungs-Agenten</b>, "
 "<b>Wochen-Digest</b>, <b>Wochenplan</b>, <b>Instagram-Verbindung</b>, <b>Material</b>.",
]))}

{step("2.2", "Wochenziel formulieren", "Abschnitt „Ziel & Kadenz 🎯“", "3 Min",
 "<p>Das ist der wichtigste Text im ganzen Modul — er steuert, worüber die Woche spricht. "
 "Zwei bis drei Sätze, konkret, in deiner Sprache.</p>"
 + box("Beispiele, die gut funktionieren", ul([
   "„Diese Woche will ich zeigen, dass Erschöpfung Ursachen hat, die man anschauen kann. "
   "Ziel: mehr Anfragen für das Kennenlerngespräch von Frauen zwischen 35 und 50.“",
   "„Fokus Perimenopause. Ich möchte als die Stimme wahrgenommen werden, die Wissenschaft "
   "warm erklärt — nicht als jemand, der Angst macht.“",
   "„Sichtbarkeit für das Paket Klarheit: was drin ist, für wen es gedacht ist, wie sich "
   "der Bericht anfühlt.“",
 ]))
 + ol([
   f"In {k('Ziel diese Woche')} tippen.",
   f"Optional in {k('Ziel diesen Monat')} den größeren Rahmen — er gibt der KI Kontext über "
   "die Woche hinaus.",
   f"Unten auf {k('💾 Speichern')} tippen.",
 ]))}

{step("2.3", "Takt festlegen", "gleicher Abschnitt", "1 Min",
 "<p>Drei Zahlenfelder bestimmen, wie viele Entwürfe pro Woche entstehen. "
 "Voreingestellt sind <b>3 Posts · 2 Stories · 1 Reel</b>.</p>"
 + box("Empfehlung für den Start",
   "<p>Fang mit <b>2 Posts · 2 Stories · 0 Reels</b> an. Weniger Entwürfe heißt weniger "
   "Prüfaufwand — und in den ersten Wochen willst du vor allem herausfinden, ob dir der "
   "Ton gefällt. Hochdrehen kannst du jederzeit; es ist nur eine Zahl.</p>")
 + f"<p class='mt'>Das Häkchen {k('Nach dem Montags-Scan automatisch Wochenentwurf erstellen')} "
   "lässt du an — genau dafür ist die Automatik da. Nicht vergessen: "
   f"{k('💾 Speichern')}.</p>")}
''')

page(head("Kapitel 2 — Fortsetzung", "Die Beobachtungs-Agenten",
          "Wer für dich mitliest, während du arbeitest.") + f'''
<p>Jeder Agent ist eine Zeile. Er liest entweder einen <b>RSS/Atom-Feed</b> (das saubere,
maschinenlesbare Format vieler Journale und Blogs) oder eine <b>Webseite</b> (dann sammelt
er die Überschriften-Links). Vier Agenten sind fertig eingestellt und aktiv, vier weitere
warten als Platzhalter auf deine Eingaben.</p>

{box("Warum keine Instagram-Profile?",
 "<p>Instagram verbietet in seinen Nutzungsbedingungen das automatische Auslesen von "
 "Profilen, und technisch bricht es ständig. Deshalb beobachten wir Wettbewerberinnen "
 "über ihre <b>Blogs und Newsletter</b> — dort steht ohnehin, worüber sie gerade sprechen, "
 "meist ausführlicher als in der Bildunterschrift.</p>", "warn")}

{step("2.4", "Wettbewerberinnen eintragen", "Abschnitt „Beobachtungs-Agenten 🔎“", "5 Min", ol([
 f"Die Zeile {k('Wettbewerberin 1 — Blog/Newsletter-URL eintragen')} suchen.",
 "Im Namensfeld den echten Namen eintragen (z. B. „Flavia Deuchler“).",
 f"Typ auf {k('Webseite')} lassen, wenn es ein normaler Blog ist. Hat die Seite einen "
 "RSS-Feed (oft <code>…/feed</code> oder <code>…/rss</code>), ist <b>RSS/Atom-Feed</b> besser.",
 "Die URL in das breite Feld darunter. Mehrere URLs mit Leerzeichen trennen.",
 "Optional: Stichworte, auf die der Agent besonders achten soll (z. B. "
 "<code>Perimenopause, Eisen, Zyklus</code>) — Treffer werden im Digest bevorzugt.",
 f"Häkchen bei {k('aktiv')} setzen.",
 f"Auf {k('🔎')} tippen — der Live-Test holt die Quelle sofort und zeigt die ersten drei "
 "gefundenen Überschriften. So weißt du <b>vor</b> Montag, ob die URL taugt.",
 f"{k('💾 Agenten speichern')}.",
]) + box("Der Test „verbraucht“ nichts",
        "<p>Ein Live-Test merkt sich die gefundenen Artikel nicht. Der Montags-Scan meldet "
        "sie trotzdem als neu — testen kostet dich also keine Fundstücke.</p>"))}

''')

page(head("Kapitel 2 — Fortsetzung", "Die wissenschaftliche Basis",
          "PubMed-Feeds anlegen — der einzige Schritt, den nur du machen kannst.") + f'''
{step("2.5", "PubMed-Feeds anlegen (die wissenschaftliche Basis)",
 "pubmed.ncbi.nlm.nih.gov → dann Betriebskonsole", "10 Min", ol([
 f"{c('pubmed.ncbi.nlm.nih.gov')} öffnen.",
 "Eine Suche eingeben, die dein Thema trifft, z. B.<br>"
 "<code>(perimenopause) AND (nutrition) AND (&quot;last 1 year&quot;[dp])</code>",
 "Unter dem Suchfeld auf <b>„Create RSS“</b> klicken.",
 "Anzahl der Einträge auf 20 stellen → <b>„Create RSS“</b> → die angezeigte URL kopieren.",
 f"In der Konsole: die Zeile {k('PubMed: Frauengesundheit & Ernährung')} nehmen, URL "
 f"einfügen, {k('aktiv')} anhaken, mit {k('🔎')} testen, speichern.",
 "Das Ganze für zwei bis vier Themen wiederholen — z. B. Eisenmangel &amp; Fatigue, "
 "Darmgesundheit, Stillzeit &amp; Mikronährstoffe, Schlaf &amp; Hormone.",
]) + box("Warum du das selbst machen musst",
        "<p>PubMed baut in jede RSS-URL einen individuellen Schlüssel ein. Eine URL lässt "
        "sich nicht erraten oder vorkonfigurieren — sie muss einmal über den Knopf "
        "„Create RSS“ erzeugt werden. Danach läuft sie für immer.</p>", "warn"))}
''')

# ══════════════════════════════════════════════ chapter 3 · material ══
page(head("Kapitel 3", "Dein Material einspeisen",
          "Fotos und Texte, die in Postings verwendet werden dürfen.") + f'''
<p>Die Wochenstrategie greift auf alles zu, was hier liegt. Fotos werden namentlich mit
deiner Notiz angeboten („Foto vom Retreat, Querformat“) und können in Bildvorlagen
eingesetzt werden; Textdokumente fließen inhaltlich in die Entwürfe ein.</p>

{step("3.1", "Dateien hochladen", "Abschnitt „Material 📁“", "3 Min", ol([
 f"{k('Datei auswählen')} → ein oder mehrere Dateien markieren (auch direkt aus der "
 "Foto-Mediathek des iPhones).",
 f"{k('⬆ Hochladen')} tippen.",
 "Für jede Datei erscheint ein kleines Fenster für eine <b>Notiz</b>. Die lohnt sich: "
 "„Porträt hell, Hochformat“ hilft der Planung, „IMG_4821“ nicht.",
 "Die Datei erscheint in der Liste mit Vorschaubild, Größe und Notiz.",
]))}

{box("Formate und Grenzen", ul([
 "Erlaubt: <b>JPG, PNG, WebP, PDF, TXT, MD</b> — bis 20 MB pro Datei.",
 "iPhone-Fotos sind intern HEIC; Safari wandelt sie beim Hochladen automatisch in JPG um. "
 "Du musst nichts tun.",
 "Die Prüfung schaut in die Datei hinein, nicht auf die Endung — eine umbenannte Datei "
 "wird abgelehnt.",
]))}

{box("Was hier NICHT hingehört",
 "<p>Keine Klientinnen-Fotos, keine Berichte, keine Screenshots aus dem Portal — "
 "auch nicht anonymisiert. Gesundheitsdaten sind besonders geschützt (Art. 9 DSGVO) und "
 "haben in Social-Media-Material nichts verloren. Die KI-Anweisung verbietet erfundene "
 "Testimonials und Klientinnen-Geschichten ausdrücklich; diese Ablage muss die zweite "
 "Absicherung sein.</p>", "warn")}

{step("3.2", "Pflege", "gleicher Abschnitt", "laufend", ul([
 f"{k('✎')} — Notiz nachträglich ändern.",
 f"{k('↓')} — Datei herunterladen.",
 f"{k('✕')} — Datei löschen (mit Rückfrage).",
]) + "<p class='mt'>Ein guter Rhythmus: nach jedem Shooting, jeder Reise, jedem Vortrag "
     "fünf Minuten investieren und die besten Bilder hochladen. Je mehr echtes Material "
     "vorliegt, desto weniger generisch werden die Entwürfe.</p>")}
''')

# ════════════════════════════════════════════ chapter 4 · weekly loop ══
page(head("Kapitel 4", "Die Wochenroutine",
          "Was montags von allein passiert — und was du tust.") + f'''
{step("4.1", "Den ersten Scan von Hand starten", "Abschnitt „Wochen-Digest 📰“", "2–5 Min", ol([
 f"{k('📡 Scan jetzt starten')} tippen. Der Knopf zeigt „Scan läuft …“.",
 "Warten. Je nach Anzahl der Quellen dauert es ein bis fünf Minuten; die Seite fragt "
 "selbstständig nach und meldet „Scan fertig“.",
 "Danach steht im Digest-Feld: <b>Themen der Woche</b>, <b>Funde</b> (jeder mit anklickbarem "
 "Quellenlink), <b>Content-Ideen</b> und <b>worüber der Wettbewerb spricht</b>.",
]) + box("Wenn die Zusammenfassung fehlt",
        f"<p>Steht dort „Die Zusammenfassung fehlt“, war das Sprachmodell kurz nicht "
        f"erreichbar — <b>die Funde selbst sind gesichert</b>. Ein Tipp auf "
        f"{k('↻ Digest nachholen')} erledigt nur die Zusammenfassung neu. Eine Woche "
        f"Beobachtung geht nie verloren.</p>"))}

{step("4.2", "Den Wochenentwurf erzeugen", "Abschnitt „Wochenplan ✍️“", "2–7 Min", ol([
 f"{k('✨ Wochenentwurf erstellen')} tippen.",
 "Der Knopf schreibt „kann einige Minuten dauern“ — das stimmt: hier entstehen alle Slots "
 "in drei Sprachen auf einmal.",
 "Danach steht oben das <b>Wochenthema</b> mit Begründung, darunter eine Karte je Slot.",
]) + box("Ab jetzt automatisch",
        "<p>Diesen Knopf brauchst du nur beim ersten Mal. Ab dem nächsten Montag erzeugt "
        "der Server Digest <i>und</i> Wochenentwurf um 05:00 Uhr von selbst — sie liegen "
        "fertig da, wenn du die Konsole öffnest.</p>"))}

''')

page(head("Kapitel 4 — Fortsetzung", "Prüfen, freigeben, Bilder erzeugen",
          "Die 25 Minuten, in denen du entscheidest.") + f'''
{step("4.3", "Prüfen, ändern, freigeben", "die Slot-Karten", "20–30 Min", ul([
 "<b>Kopfzeile</b> — Format, Tag, Uhrzeit. Die Uhrzeit ist die geplante Veröffentlichung.",
 "<b>Hook</b> — die erste Zeile der Caption. Der wichtigste Satz überhaupt; lies ihn zuerst.",
 "<b>Drei Caption-Felder</b> — 🇩🇪 ist der Master, 🇬🇧 und 🇪🇸 sind daraus abgeleitet. "
 "Änderst du das Deutsche inhaltlich, passe die anderen beiden mit an.",
 "<b>Hashtags</b> — mit Leerzeichen getrennt; das Rautezeichen wird bei Bedarf ergänzt.",
 "<b>Alt-Text</b> — beschreibt das Bild für blinde Nutzerinnen. Bitte nie leer lassen.",
 "<b>Call-to-Action</b> — der Handlungsaufruf am Ende.",
]) + f"<p class='mt'>Jede Änderung speichert sich, sobald du das Feld verlässt. "
     f"Wenn ein Entwurf dir grundsätzlich nicht gefällt: {k('↻')} erzeugt genau diesen einen "
     f"Slot neu, mit frischem Blickwinkel — deine bereits freigegebenen Slots bleiben "
     f"unangetastet.</p>"
 + box("Die Compliance-Warnung ernst nehmen",
   "<p>Erscheint ein <b>⚠ Formulierung prüfen</b>-Balken, hat der automatische Sprachtest "
   "Wörter wie „heilt“, „Diagnose“, „garantiert“ oder „clinically proven“ gefunden. "
   "Der Text wird <b>nie stillschweigend geändert</b> — du entscheidest. Aber: Auralis "
   "bietet Gesundheitscoaching und Gesundheitsbildung, keine Heilversprechen. Formuliere "
   "um, bevor du freigibst.</p>", "warn"))}

{step("4.4", "Bilder erzeugen", "auf jeder Slot-Karte", "1–3 Min gesamt", ol([
 f"Pro Karte auf {k('🖼 Bilder erzeugen')} tippen.",
 "Es entstehen die passenden Dateien: ein Post-Bild (1080×1350), fünf Karussell-Slides, "
 "eine Story-Fläche (1080×1920) oder Reel-Karten plus MP4.",
 "Die Vorschaubilder erscheinen direkt daneben; mit ↓ lädst du einzelne herunter.",
]) + box("Alles im Auralis-Design",
        "<p>Die Bilder verwenden die echten Markenschriften, die Erd-Palette, eckige Ecken "
        "und das Siegel — dieselben Regeln wie Visitenkarte und Flyer. Du musst kein Canva "
        "öffnen und nichts nachbauen.</p>"))}
''')

# ═══════════════════════════════════════════ chapter 5 · instagram api ══
page(head("Kapitel 5", "Instagram automatisch verbinden",
          "Einmalig ca. 40 Minuten. Danach postet der Server für dich.") + f'''
{box("Voraussetzungen — bitte vorher prüfen", ul([
 "Ein <b>Instagram-Konto</b>, das auf <b>Professionell</b> (Business) umgestellt ist.",
 "Eine <b>Facebook-Seite</b> für Auralis Natura (kann leer sein, muss aber existieren).",
 "Beide müssen <b>miteinander verknüpft</b> sein.",
 "Ein Facebook-Konto, mit dem du dich bei <code>developers.facebook.com</code> anmelden kannst.",
]))}

{step("5.1", "Instagram auf Professionell umstellen", "Instagram-App", "3 Min", ol([
 "Profil → Menü (☰) → <b>Einstellungen und Privatsphäre</b>.",
 "<b>Kontotyp und Tools</b> → <b>Zu Professionell-Konto wechseln</b>.",
 "Kategorie wählen (z. B. „Gesundheit/Schönheit“) → <b>Business</b> auswählen.",
]))}

{step("5.2", "Mit der Facebook-Seite verknüpfen", "Instagram-App", "3 Min", ol([
 "Einstellungen → <b>Konten-Center</b> → <b>Konten hinzufügen</b>.",
 "Die Facebook-Seite von Auralis Natura auswählen und bestätigen.",
 "Prüfen: Unter <b>Konten-Center → Konten</b> müssen Instagram und die Seite gemeinsam "
 "gelistet sein.",
]) + box("Ohne diese Verknüpfung geht es nicht",
        "<p>Die Instagram-Schnittstelle arbeitet ausschließlich über eine verbundene "
        "Facebook-Seite. Das ist Metas Konstruktion, nicht unsere.</p>", "warn"))}

''')

page(head("Kapitel 5 — Fortsetzung", "Die Meta-App und das Token",
          "Der technische Teil — Feld für Feld, Klick für Klick.") + f'''
{step("5.3", "Meta-App anlegen", "developers.facebook.com", "8 Min", ol([
 f"{c('developers.facebook.com')} öffnen, oben rechts anmelden.",
 "<b>Meine Apps</b> → <b>App erstellen</b>.",
 "Anwendungsfall: <b>Andere</b> → Typ: <b>Business</b>.",
 "Name z. B. <code>Auralis Publisher</code>, Kontakt-E-Mail eintragen → <b>App erstellen</b>.",
 "Im linken Menü: <b>Produkt hinzufügen</b> → bei <b>Instagram</b> auf <b>Einrichten</b>.",
]) + box("Die App bleibt im Entwicklungsmodus",
        "<p>Für dein <b>eigenes</b> Konto ist das völlig ausreichend — es ist keine "
        "Prüfung durch Meta („App Review“) nötig und es entstehen keinerlei Kosten. "
        "Ein Review bräuchtest du erst, wenn <i>fremde</i> Nutzerinnen die App verwenden sollen.</p>"))}

{step("5.4", "Zugriffstoken und Konto-ID holen", "Graph-API-Explorer", "10 Min", ol([
 f"{c('developers.facebook.com/tools/explorer')} öffnen.",
 "Oben rechts <b>deine App</b> auswählen.",
 "Bei <b>Berechtigungen</b> diese vier hinzufügen:<br>"
 "<code>instagram_basic</code> · <code>instagram_content_publish</code> · "
 "<code>pages_show_list</code> · <code>pages_read_engagement</code>",
 "<b>Generate Access Token</b> → im Popup mit Facebook bestätigen und die Seite freigeben.",
 "Im Abfragefeld <code>me/accounts</code> eingeben → <b>Submit</b>. "
 "Notiere die <code>id</code> deiner Facebook-Seite.",
 "Jetzt abfragen: <code>&lt;SEITEN-ID&gt;?fields=instagram_business_account</code> → "
 "die zurückgegebene Nummer ist deine <b>Instagram-User-ID</b>. Notieren.",
 "Das Token oben aus dem Feld kopieren.",
]))}

{step("5.5", "Token auf 60 Tage verlängern", "Access Token Debugger", "2 Min", ol([
 f"{c('developers.facebook.com/tools/debug/accesstoken')} öffnen.",
 "Das kopierte Token einfügen → <b>Debug</b>.",
 "Unten auf <b>Extend Access Token</b> → das <b>neue, längere</b> Token kopieren.",
]) + box("Danach kümmert sich der Server",
        "<p>Ab hier verlängert sich das Token von selbst: zehn Tage vor Ablauf tauscht der "
        "Server es automatisch gegen ein frisches. Du musst nie wieder hierher.</p>"))}
''')

page(head("Kapitel 5 — Fortsetzung", "Die vier Werte hinterlegen",
          "Der letzte Handgriff im Terminal — dann ist die Automatik scharf.") + f'''
{step("5.6", "App-ID und App-Secret holen", "developers.facebook.com", "2 Min", ol([
 "In deiner App: linkes Menü → <b>App-Einstellungen</b> → <b>Allgemein</b>.",
 "<b>App-ID</b> notieren.",
 "Bei <b>App-Geheimnis</b> auf <b>Anzeigen</b> → Passwort bestätigen → notieren.",
]))}

{step("5.7", "In die Server-Konfiguration eintragen", "Terminal", "3 Min",
 f"<p>Verbinden und die Datei öffnen:</p>{cb('ssh root@178.105.10.156')}"
 f"{cb('nano /etc/auralis/portal.env')}"
 "<p class='mt'>Am Ende der Datei vier Zeilen ergänzen (ohne Anführungszeichen, "
 "ohne Leerzeichen um das Gleichheitszeichen):</p>"
 + f"{cb('AURALIS_IG_USER_ID=17841400000000000')}"
   f"{cb('AURALIS_IG_TOKEN=EAAG...das-lange-token...')}"
   f"{cb('AURALIS_IG_APP_ID=1234567890')}"
   f"{cb('AURALIS_IG_APP_SECRET=abcdef1234567890')}"
 + "<p class='mt'>Speichern mit <b>Strg+O</b>, Enter, schließen mit <b>Strg+X</b>. "
   "Dann den Dienst neu starten:</p>"
 + c('systemctl restart auralis-portal')
 + box("Warum nicht in der Konsole eingeben?",
   "<p>Das Token ist ein Schlüssel zu deinem Instagram-Konto. Es gehört in die "
   "root-geschützte Umgebungsdatei des Servers — nicht in eine JSON-Datei, die in "
   "Sicherungen und Git-Verläufen landen kann. Deshalb dieser eine Terminal-Schritt.</p>",
   "warn"))}

''')

page(head("Kapitel 5 — Fortsetzung", "Verbinden und der erste Post",
          "Der Moment, in dem die Automatik übernimmt.") + f'''
{step("5.8", "Verbindung prüfen", "Betriebskonsole → Social Media", "1 Min", ol([
 f"Registerkarte neu laden → Abschnitt {k('Instagram-Verbindung 📱')}.",
 "Dort muss jetzt stehen: <b>✅ Verbunden als @dein_konto</b> mit Ablaufdatum des Tokens.",
 f"Steht dort eine Fehlermeldung, sagt sie, was fehlt — meist ein Tippfehler im Token oder "
 f"eine fehlende Berechtigung. Mit {k('↻ Token verlängern')} lässt sich das Token jederzeit "
 "auffrischen.",
]))}

{step("5.9", "Den ersten echten Post", "Slot-Karte", "1 Min", ol([
 "Einen Slot vollständig prüfen, Bilder erzeugen lassen.",
 f"Häkchen {k('freigegeben')} setzen → die Karte zeigt <b>⏳ geplant</b> und bekommt die "
 "geplante Zeit.",
 f"Für den Test: {k('🚀 Sofort')} tippen → nach Rückfrage geht der Post <b>jetzt</b> live.",
 "Danach zeigt die Karte <b>✅ veröffentlicht</b>. In Instagram nachsehen — er ist da.",
]) + box("Ab jetzt gilt", "<p>Freigeben genügt. Jeder freigegebene Slot geht zur geplanten "
        "Minute automatisch raus; die Karte zeigt jederzeit ⏳ geplant, ✅ veröffentlicht "
        "oder ⚠ mit Fehlergrund. Nimmst du eine Freigabe zurück, verschwindet der Slot "
        "wieder aus der Warteschlange.</p>"))}
''')

# ══════════════════════════════════════════════ chapter 6 · manual way ══
page(head("Kapitel 6", "Weg A: manuell über Meta Business Suite",
          "Für sofort — und als Rückfalloption, falls die Verbindung einmal klemmt.") + f'''
{step("6.1", "Wochenpaket herunterladen", "unter den Slot-Karten", "1 Min", ol([
 "Alle Slots freigeben, die raus sollen.",
 f"Ganz unten auf {k('⬇ Wochenpaket (ZIP)')} tippen.",
 "Im ZIP liegt pro Slot ein Ordner mit den Bildern und einer <code>captions.txt</code> "
 "(fertige Caption in allen drei Sprachen plus Alt-Text) sowie eine "
 "<code>README-Checkliste.txt</code>.",
]) + f"<p class='mt'>Alternativ schickt {k('✉ Paket an team@ mailen')} dir alles per E-Mail — "
     "praktisch, wenn du am Telefon planst.</p>")}

{step("6.2", "In Meta Business Suite planen", "business.facebook.com", "8 Min", ol([
 f"{c('business.facebook.com')} öffnen → linkes Menü → <b>Planer</b>.",
 "<b>Beitrag erstellen</b> → oben das <b>Instagram-Konto</b> auswählen.",
 "Bilder hochladen — bei Karussells alle Slides <b>in der richtigen Reihenfolge</b>.",
 "Caption aus <code>captions.txt</code> einfügen (Deutsch, Englisch, Spanisch und Hashtags "
 "sind bereits fertig gestapelt — einfach alles kopieren).",
 "<b>Erweiterte Einstellungen</b> → <b>Alternativtext</b> → den Alt-Text aus derselben Datei.",
 "<b>Planen</b> → Tag und Uhrzeit aus der Datei übernehmen → speichern.",
]))}

{box("Stories und Reels", ul([
 "<b>Stories</b> lassen sich im Planer nur eingeschränkt terminieren — poste "
 "<code>story.png</code> direkt in der Instagram-App und lege den Frage-Sticker auf die "
 "dafür markierte Fläche.",
 "<b>Reels</b>: <code>reel.mp4</code> hochladen und den <b>Trend-Ton in der App</b> "
 "hinzufügen. Lizenzierte Musik gibt es nur dort — genau deshalb ist das Video absichtlich "
 "ohne Ton.",
]))}
''')

# ═════════════════════════════════════════════ chapter 7 · operations ══
page(head("Kapitel 7", "Betrieb, Störungen, Grenzen",
          "Was normal ist, was nicht, und was du dann tust.") + f'''
{box("Deine Wochenroutine in Kurzform", ol([
 "<b>Montag früh:</b> Konsole öffnen. Digest und Wochenentwurf liegen bereit.",
 "<b>20–30 Minuten:</b> Slots lesen, anpassen, Bilder erzeugen, freigeben.",
 "<b>Fertig.</b> Der Rest passiert von allein.",
 "<b>Sonntags 5 Minuten:</b> Ziel für die kommende Woche eintragen.",
]))}

<table class="tt">
<tr><th>Symptom</th><th>Ursache &amp; Behebung</th></tr>
<tr><td>Ein Agent zeigt <b>⚠ Fehler</b></td>
<td>Die Quelle war nicht erreichbar oder hat ihr Format geändert. Mit 🔎 testen; hilft das
nicht, URL prüfen oder Agent deaktivieren. <b>Ein toter Agent stoppt den Scan nie.</b></td></tr>
<tr><td>Digest ohne Zusammenfassung</td>
<td>Sprachmodell war kurz nicht erreichbar. ↻ Digest nachholen. Funde sind gesichert.</td></tr>
<tr><td>Entwürfe wirken generisch</td>
<td>Meist ein zu vages Wochenziel oder zu wenig eigenes Material. Beides nachschärfen,
dann einzelne Slots mit ↻ neu erzeugen.</td></tr>
<tr><td><b>⚠ Veröffentlichung fehlgeschlagen</b></td>
<td>Die Karte zeigt Metas Originalfehler. Häufig: Token abgelaufen (→ ↻ Token verlängern)
oder Bilder fehlen (→ 🖼 Bilder erzeugen).</td></tr>
<tr><td>Reel wird nicht erzeugt</td>
<td>ffmpeg fehlt — Kapitel 1 nachholen. Die Reel-Karten als PNG sind trotzdem da.</td></tr>
<tr><td>Nichts läuft montags</td>
<td>Timer nicht installiert. <code>systemctl list-timers auralis-*</code> prüfen,
sonst Kapitel 1.2.</td></tr>
</table>

{box("Grenzen, die du kennen solltest", ul([
 "Instagram erlaubt <b>maximal 50 API-Veröffentlichungen pro 24 Stunden</b> — bei deinem "
 "Takt unerreichbar.",
 "Ein Karussell fasst <b>2 bis 10 Bilder</b>.",
 "Der Server wandelt Bilder vor dem Posten automatisch nach JPEG um (Instagram akzeptiert "
 "kein PNG) — dafür wird ffmpeg gebraucht.",
 "Die Bilder werden Meta über <b>signierte Links geliefert, die nach vier Stunden "
 "erlöschen</b>. Nichts anderes aus deinen Dokumenten wird dadurch erreichbar.",
]))}

{box("Was Geld kostet: nichts",
 "<p>Kein Abo, keine Schnittstellengebühr, kein Werkzeug. Alles läuft über deinen "
 "bestehenden Server, dein Claude-Pro-Abo, das kostenlose ffmpeg und Metas kostenlose "
 "Schnittstelle. Es gibt keine versteckte Stufe, die später etwas kostet.</p>")}
''')

# ══════════════════════════════════════════════════════════ checklist ══
page(head("Zum Abhaken", "Deine Go-live-Checkliste",
          "Ausdrucken oder abfotografieren — und der Reihe nach abarbeiten.") + f'''
<div class="ck">
  <div class="ckh">Einmalig · Server (Kapitel 1)</div>
  <div class="ci"><span class="cb"></span>Firewall für die eigene IP geöffnet</div>
  <div class="ci"><span class="cb"></span><code>install_server.sh</code> gelaufen, 13/13 grün</div>
  <div class="ci"><span class="cb"></span>Beide neuen Timer stehen in <code>list-timers</code></div>

  <div class="ckh">Einmalig · Inhalte (Kapitel 2–3)</div>
  <div class="ci"><span class="cb"></span>Wochenziel formuliert und gespeichert</div>
  <div class="ci"><span class="cb"></span>Takt festgelegt (Empfehlung zum Start: 2 · 2 · 0)</div>
  <div class="ci"><span class="cb"></span>3–5 PubMed-Feeds angelegt und getestet</div>
  <div class="ci"><span class="cb"></span>3–6 Wettbewerberinnen-Blogs eingetragen und getestet</div>
  <div class="ci"><span class="cb"></span>Erste 10–20 Fotos mit Notizen hochgeladen</div>

  <div class="ckh">Einmalig · Instagram (Kapitel 5)</div>
  <div class="ci"><span class="cb"></span>Instagram auf Professionell umgestellt</div>
  <div class="ci"><span class="cb"></span>Facebook-Seite verknüpft</div>
  <div class="ci"><span class="cb"></span>Meta-App erstellt, Instagram-Produkt hinzugefügt</div>
  <div class="ci"><span class="cb"></span>Token erzeugt, verlängert, Konto-ID notiert</div>
  <div class="ci"><span class="cb"></span>Vier Werte in <code>portal.env</code>, Dienst neu gestartet</div>
  <div class="ci"><span class="cb"></span>Konsole zeigt „✅ Verbunden als @…“</div>
  <div class="ci"><span class="cb"></span>Erster Testpost über 🚀 Sofort veröffentlicht</div>

  <div class="ckh">Jede Woche · ca. 25 Minuten</div>
  <div class="ci"><span class="cb"></span>Digest lesen</div>
  <div class="ci"><span class="cb"></span>Slots prüfen, anpassen, Warnungen klären</div>
  <div class="ci"><span class="cb"></span>Bilder erzeugen</div>
  <div class="ci"><span class="cb"></span>Freigeben</div>
  <div class="ci"><span class="cb"></span>Ziel für die kommende Woche setzen</div>
</div>

''')

page(head("Zum Schluss", "Und dann?",
          "Was bleibt, wenn die Einrichtung hinter dir liegt.") + f'''
<div class="closing">
  <img class="cseal" src="data:image/png;base64,{SEAL}" alt="">
  <p class="cnote">Alles, was hier steht, ist einmalige Arbeit. Danach kostet dich
  Instagram eine halbe Stunde pro Woche — und die verbringst du mit dem, was nur du
  kannst: entscheiden, ob es klingt wie du.</p>
  <div class="cmeta2">Auralis Natura · Betriebskonsole · Modul 06 „Social Media“</div>
</div>
''')

# ═══════════════════════════════════════════════════════════════ render ══
CSS = """
__FONTS__
:root{--ink:#281F16;--ink-soft:#5C4A3A;--ink-faint:#75685A;--forest:#3D2719;
--forest-deep:#221305;--sage:#927B4A;--sage-soft:#DAC79E;--clay:#A8492A;
--gold:#AD7A32;--gold-bright:#D6A84E;--paper:#F5EEE0;--paper-2:#ECE2CE;--cream:#FBF6EB;
--line:rgba(61,39,25,.14);--line-strong:rgba(61,39,25,.26);--gold-hair:rgba(173,122,50,.42);
--fd:"Fraunces",Georgia,serif;--fb:"Hanken Grotesk",system-ui,sans-serif}
*{box-sizing:border-box;margin:0;padding:0;border-radius:0!important;
-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:var(--fb);color:var(--ink);background:#fff;font-size:11.6px;line-height:1.6;hyphens:none}
.page{width:210mm;min-height:297mm;position:relative;page-break-after:always;
background:#fff;overflow:hidden;padding:17mm 16mm 20mm}
.ph{margin-bottom:16px;border-bottom:1px solid var(--gold-hair);padding-bottom:12px}
.kick{font-size:.62rem;letter-spacing:.26em;text-transform:uppercase;color:var(--clay);font-weight:600}
.ph h2{font-family:var(--fd);font-weight:420;font-size:1.95rem;color:var(--forest);
margin:6px 0 4px;line-height:1.14;letter-spacing:-.012em}
.ph .sub{color:var(--ink-soft);font-size:.95rem}
p{color:var(--ink-soft);margin:0 0 9px}
b{color:var(--ink)}
.mt{margin-top:8px}
code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.8em;background:var(--cream);
border:1px solid var(--line);padding:2px 6px;color:var(--forest);display:inline-block;margin:2px 0;
white-space:nowrap;word-break:keep-all;overflow-wrap:normal}
code.blk{display:block;margin:4px 0;width:fit-content}
.ui{font-weight:600;color:var(--forest);background:var(--paper-2);padding:1px 7px;
border:1px solid var(--line);white-space:nowrap}
/* cover */
.cover{background:var(--paper);padding:0}
.cover .wm{position:absolute;right:-60mm;bottom:-60mm;width:145mm;opacity:.10}
.cover .cin{position:absolute;inset:12mm;border:1px solid var(--gold-hair);
display:flex;flex-direction:column;justify-content:center;text-align:center;padding:0 16mm}
.cover .seal{width:96px;height:96px;margin:0 auto 22px}
.ckick{font-size:.66rem;letter-spacing:.3em;text-transform:uppercase;color:var(--clay);font-weight:600}
.crule{width:44px;height:2px;background:var(--gold);margin:16px auto}
.cover h1{font-family:var(--fd);font-weight:420;font-size:2.5rem;line-height:1.14;
margin:6px 0 20px;letter-spacing:-.015em;color:var(--ink)}
.cover h1 em{font-style:italic;color:var(--clay)}
.clead{max-width:46ch;margin:0 auto 26px;font-size:1rem}
.cmeta{display:flex;justify-content:center;align-items:center;gap:12px;font-size:.8rem;color:var(--ink-soft)}
.cmeta .sep{width:20px;height:1px;background:var(--gold-hair)}
/* steps */
.step{display:flex;gap:14px;margin:0 0 13px;page-break-inside:avoid}
.sn{font-family:var(--fd);font-size:1.6rem;color:var(--gold);line-height:1;min-width:44px;
padding-top:2px;letter-spacing:-.02em}
.sb{flex:1;border-left:1px solid var(--line);padding-left:16px}
.sb h3{font-family:var(--fd);font-weight:500;font-size:1.12rem;color:var(--forest);margin-bottom:5px}
.meta{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px;
font-size:.78rem;color:var(--ink-faint)}
.tag{font-size:.56rem;letter-spacing:.16em;text-transform:uppercase;color:var(--sage);
font-weight:700;border:1px solid var(--line);padding:1px 6px}
ol.steps{margin:0 0 6px 0;padding-left:20px;color:var(--ink-soft)}
ol.steps li{margin:4px 0;padding-left:3px}
ul.bul{margin:0 0 6px 0;padding-left:18px;color:var(--ink-soft)}
ul.bul li{margin:4px 0}
/* boxes */
.box{background:var(--cream);border:1px solid var(--line);border-left:3px solid var(--gold);
padding:9px 15px;margin:8px 0;page-break-inside:avoid}
.box.warn{background:#FCF3EF;border-left-color:var(--clay)}
.bt{font-size:.6rem;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-faint);
font-weight:700;margin-bottom:6px}
.box.warn .bt{color:var(--clay)}
.box p:last-child,.box ul:last-child,.box ol:last-child{margin-bottom:0}
/* flow */
.flow{margin:14px 0}
.fs{display:flex;gap:12px;align-items:baseline;padding:9px 0;border-bottom:1px solid var(--line)}
.fs .fn{font-family:var(--fd);font-size:1.1rem;color:var(--gold);min-width:20px}
.fs b{min-width:230px;color:var(--ink)}
.fs span:last-child{color:var(--ink-soft);flex:1}
.fs.now{background:var(--cream);border-left:3px solid var(--clay);padding-left:10px}
.fs.now b{color:var(--clay)}
/* table */
.tt{width:100%;border-collapse:collapse;margin:12px 0;font-size:.86rem}
.tt th{text-align:left;font-size:.6rem;letter-spacing:.14em;text-transform:uppercase;
color:var(--ink-faint);padding:7px 10px;border-bottom:1px solid var(--line-strong);background:var(--cream)}
.tt td{padding:7px 10px;border-bottom:1px solid var(--line);color:var(--ink-soft);vertical-align:top}
.tt td:first-child{width:32%;color:var(--ink)}
/* checklist */
.ck{margin-top:6px}
.ckh{font-size:.6rem;letter-spacing:.18em;text-transform:uppercase;color:var(--clay);
font-weight:700;margin:16px 0 8px;padding-bottom:5px;border-bottom:1px solid var(--gold-hair)}
.ci{display:flex;gap:11px;align-items:flex-start;padding:5px 0;color:var(--ink-soft)}
.cb{width:13px;height:13px;border:1.5px solid var(--sage);flex:0 0 auto;margin-top:2px;background:#fff}
.closing{margin-top:26px;padding-top:18px;border-top:1px solid var(--gold-hair);text-align:center}
.cseal{width:56px;height:56px;margin:0 auto 12px;display:block}
.cnote{max-width:52ch;margin:0 auto;font-size:.95rem;color:var(--ink-soft)}
.cmeta2{margin-top:14px;font-size:.66rem;letter-spacing:.18em;text-transform:uppercase;color:var(--ink-faint)}
@media print{@page{size:A4;margin:0} .page{margin:0}}
"""

DOC = ("<!doctype html><html lang=\"de\"><head><meta charset=\"utf-8\"><style>"
       + CSS.replace("__FONTS__", render._font_css())
       + "</style></head><body>" + "".join(PAGES) + "</body></html>")

out = Path(sys.argv[1] if len(sys.argv) > 1
           else cfg.OUTPUT_DIR / "Auralis-Social-Media-Anleitung.pdf")
got = render.to_pdf(DOC, out)
print(f"{got}  ({got.stat().st_size // 1024} KB, {len(PAGES)} Seiten)")
