#!/usr/bin/env python3
"""Build the Auralis Natura App-Store one-pager (branded HTML + PDF, single A4 page)."""
import base64
from pathlib import Path

ROOT = Path("/home/user/AuralisNatura")
seal = base64.b64encode((ROOT / "portal/assets/seal.png").read_bytes()).decode()
OUT_DIR = ROOT / "handover/auralis-portal"
REPO = "github.com/stefangruber001/auralisnatura"

CSS = """
:root{--ink:#281F16;--ink-soft:#5C4A3A;--ink-faint:#8C7E6E;--forest:#3D2719;--forest-deep:#221305;--clay:#A8492A;--gold:#AD7A32;--gold-b:#D6A84E;--sage:#927B4A;--paper:#F5EEE0;--cream:#FBF6EB;--line:rgba(61,39,25,.15);--gold-hair:rgba(173,122,50,.5);--fd:"Fraunces",Georgia,serif;--fb:"Hanken Grotesk",system-ui,sans-serif;--fm:"IBM Plex Mono",ui-monospace,monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--fb);color:var(--ink);background:#fff;font-size:8.6px;line-height:1.42;-webkit-font-smoothing:antialiased}
.page{width:210mm;min-height:297mm;padding:11mm 12mm;margin:0 auto}
a{color:var(--clay);text-decoration:none;border-bottom:.5px solid var(--gold-hair);word-break:break-all}
b,strong{color:var(--ink)}
.head{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid var(--forest);padding-bottom:7px}
.head .l{display:flex;gap:9px;align-items:center}
.head img{width:38px;height:38px}
.wm{font-family:var(--fd);font-size:15px;letter-spacing:.01em}
.kick{font-size:6.4px;letter-spacing:.24em;text-transform:uppercase;color:var(--clay);font-weight:700;margin-top:1px}
.head .r{text-align:right;font-style:italic;color:var(--ink-soft);font-size:8px;line-height:1.5;font-family:var(--fd)}
h1{font-family:var(--fd);font-weight:400;font-size:20px;margin:12px 0 3px;letter-spacing:-.01em}
.lede{color:var(--ink-soft);max-width:118ch;font-size:9px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:11px;margin-top:11px}
.box{border:1px solid var(--line);padding:9px 11px}
.box.me{background:var(--cream)}
.box.you{background:#FBF6EC;border-color:var(--gold-hair)}
.box h3{font-family:var(--fd);font-weight:400;font-size:11px;display:flex;align-items:center;gap:6px}
.tag{font-size:6px;letter-spacing:.1em;text-transform:uppercase;font-weight:700;padding:1px 6px;color:#fff}
.tag.c{background:var(--clay)} .tag.d{background:var(--gold);color:#2A2210}
.box ul{list-style:none;margin-top:6px;display:flex;flex-direction:column;gap:2.5px}
.box li{padding-left:14px;position:relative;color:var(--ink-soft)}
.box.me li::before{content:"✓";position:absolute;left:0;color:var(--sage);font-weight:700}
.box.you li::before{content:"›";position:absolute;left:2px;color:var(--clay);font-weight:700}
.sec{font-family:var(--fm);font-size:7px;letter-spacing:.16em;text-transform:uppercase;color:var(--clay);font-weight:600;margin:14px 0 5px;padding-top:8px;border-top:1px solid var(--line)}
table{width:100%;border-collapse:collapse}
th,td{border:1px solid var(--line);padding:4.5px 7px;text-align:left;vertical-align:top}
th{background:var(--paper);font-size:6.2px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-faint);font-weight:700}
td .s{font-family:var(--fd);font-size:11px;color:var(--gold);font-weight:500}
.done{color:var(--sage);font-weight:700}
.auto{color:var(--forest);font-weight:700}
.pill{display:inline-block;font-size:6px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;padding:1px 5px;border:1px solid}
.pill.done{border-color:var(--sage);color:var(--sage)}
.pill.auto{border-color:var(--gold);color:var(--gold)}
.pill.du{border-color:var(--clay);color:var(--clay)}
pre{font-family:var(--fm);font-size:7.6px;background:var(--forest-deep);color:#EDE7D6;padding:9px 11px;margin-top:5px;white-space:pre-wrap;line-height:1.55}
pre .c{color:#C9B896}
.foot{margin-top:12px;border-top:1px solid var(--gold-hair);padding-top:6px;font-size:6.8px;color:var(--ink-faint);line-height:1.5}
@media print{@page{size:A4;margin:0}.page{margin:0}}
"""

BODY = f"""
<div class="head">
  <div class="l"><img src="data:image/png;base64,{seal}" alt="">
    <div><div class="wm">Auralis Natura</div><div class="kick">Holistic Health</div></div></div>
  <div class="r">Playbook · iOS App Store<br>ohne eigenen Mac · maximal automatisiert</div>
</div>

<h1>Deine App in den App Store — fast alles läuft automatisch</h1>
<p class="lede">Der komplette Build läuft in der Cloud auf GitHubs macOS-Servern (immer aktuelles Xcode = aktuelles iOS-SDK), signiert sich selbst und lädt zu TestFlight. <b>Du brauchst nur einen Browser und ein paar Minuten.</b> Fast alle früher manuellen Schritte sind jetzt automatisiert — es bleiben nur die zwei, die Apple persönlich verlangt (und Schritt 1 ist bereits erledigt).</p>

<div class="cols">
  <div class="box me"><h3>Das erledige ich für dich <span class="tag c">Claude ✓</span></h3>
    <ul>
      <li><b>Build-Pipeline</b> — GitHub-Actions-Workflow (macOS, neuestes Xcode)</li>
      <li><b>Fastlane</b> — Build, Signierung, Upload zu TestFlight</li>
      <li><b>Code-Signing per fastlane match</b> — Zertifikat + Profil verschlüsselt im Repo, nie manuell</li>
      <li><b>Build-Nummer</b> zählt automatisch hoch · <b>Shared Scheme</b> im Projekt</li>
      <li><b>Secrets-Skript</b> — setzt alle 5 GitHub-Secrets mit <span class="fm">einem</span> Befehl</li>
      <li><b>App-Eintrag</b> wird per Workflow automatisch angelegt (kein Klicken)</li>
      <li><b>Store-Texte</b> (DE/EN/ES) liegen fertig &amp; werden automatisch hochgeladen</li>
      <li>Builds auslösen &amp; Logs lesen, Fehler fixen — direkt per GitHub</li>
    </ul></div>
  <div class="box you"><h3>Das machst nur du (Browser) <span class="tag d">Du</span></h3>
    <ul>
      <li><b>Apple Developer Program</b> — 99 €/Jahr &nbsp;<span class="pill done">bereits erledigt</span></li>
      <li><b>App-Store-Connect-API-Key</b> erstellen → <span class="fm">.p8</span> laden <span class="pill du">einmalig</span></li>
      <li><b>Team-ID</b> aus dem Developer-Konto kopieren</li>
      <li><b>Secrets setzen</b> — ein Terminal-Befehl (Skript, s. unten)</li>
      <li><b>2 Workflows starten</b> — „create_app", dann „beta" (je 1 Klick)</li>
      <li><b>Auf dem iPhone testen</b> (TestFlight)</li>
      <li>Screenshots &amp; Freigabe — Assets liefere ich, du klickst „Submit"</li>
    </ul></div>
</div>

<div class="sec">Genau wo &amp; was — jeder Schritt mit Link</div>
<table>
<tr><th style="width:5%">#</th><th style="width:16%">Schritt</th><th style="width:37%">Wo (Link)</th><th style="width:30%">Was du dort tust</th><th style="width:12%">Status</th></tr>
<tr><td><span class="s">1</span></td><td><b>Enrollment</b></td><td><a href="https://developer.apple.com/account">developer.apple.com/account</a></td><td>Apple Developer Program, 99 €/Jahr</td><td><span class="done">✓ erledigt</span></td></tr>
<tr><td><span class="s">2</span></td><td><b>API-Key</b> (einmalig)</td><td><a href="https://appstoreconnect.apple.com/access/integrations/api">appstoreconnect.apple.com/access/integrations/api</a></td><td><b>+</b> Schlüssel mit Rolle <b>App Manager</b> erzeugen → <b>Key-ID</b> + <b>Issuer-ID</b> notieren, <b>AuthKey_….p8</b> herunterladen (nur 1× möglich)</td><td><span class="pill du">Du · 5 Min</span></td></tr>
<tr><td><span class="s">3</span></td><td><b>Team-ID</b></td><td><a href="https://developer.apple.com/account">developer.apple.com/account</a> → Membership details</td><td>10-stellige <b>Team-ID</b> kopieren</td><td><span class="pill du">Du · 1 Min</span></td></tr>
<tr><td><span class="s">4</span></td><td><b>Secrets setzen</b></td><td>Terminal → <span class="fm">ios-app/scripts/setup-secrets.sh</span></td><td>Ein Befehl (unten) — verschlüsselt den .p8 und setzt alle <b>5 Secrets</b></td><td><span class="auto">automatisiert</span></td></tr>
<tr><td><span class="s">5</span></td><td><b>App anlegen</b></td><td><a href="https://{REPO}/actions">{REPO}/actions</a> → „iOS · TestFlight"</td><td>Workflow mit Lane <b>create_app</b> starten (Run workflow) → Store-Eintrag entsteht automatisch</td><td><span class="pill auto">1 Klick</span></td></tr>
<tr><td><span class="s">6</span></td><td><b>Build → TestFlight</b></td><td><a href="https://{REPO}/actions">{REPO}/actions</a> → „iOS · TestFlight"</td><td>Workflow mit Lane <b>beta</b> starten → in ~10 Min in TestFlight</td><td><span class="pill auto">1 Klick</span></td></tr>
<tr><td><span class="s">7</span></td><td><b>Testen</b></td><td><a href="https://appstoreconnect.apple.com/apps">appstoreconnect.apple.com/apps</a> → TestFlight</td><td>Dich als Tester einladen, App aufs iPhone laden</td><td><span class="pill du">Du</span></td></tr>
<tr><td><span class="s">8</span></td><td><b>Freigabe</b> (öffentlich)</td><td><a href="https://appstoreconnect.apple.com/apps">appstoreconnect.apple.com/apps</a></td><td>Screenshots hoch (ich liefere), Datenschutz-Fragebogen, Demo-Login eintragen, <b>Submit for Review</b>. Store-Texte lade ich per Lane <b>release</b> hoch.</td><td><span class="pill du">Du + Claude</span></td></tr>
</table>

<div class="sec">Der eine Terminal-Befehl für Schritt 4</div>
<pre><span class="c"># GitHub-CLI einmalig: brew install gh && gh auth login</span>
cd ios-app
./scripts/setup-secrets.sh \\
  --key-id ABC123DEF4 \\
  --issuer-id 12345678-aaaa-bbbb-cccc-1234567890ab \\
  --p8 ~/Downloads/AuthKey_ABC123DEF4.p8 \\
  --team-id 1A2B3C4D5E
<span class="c"># fragt nach MATCH_PASSWORD (frei wählbar, im Passwort-Manager speichern) — fertig.</span></pre>

<div class="foot">
<b>Auralis Natura — Holistic Health.</b> App-Bundle-ID <span class="fm">com.auralisnatura.app</span> · Ausführliche Anleitung: <span class="fm">ios-app/TESTFLIGHT-SETUP.md</span> · Store-Texte: <span class="fm">ios-app/STORE-LISTING.md</span>. Grundprinzip: alles, was über GitHub automatisierbar ist, übernehme ich — manuell nur, was Apple persönlich verlangt. Ganzheitliches Gesundheits-Coaching (Bildung, keine medizinische Versorgung). Stand: Juli 2026 · vertraulich.
</div>
"""

html = ("<!doctype html><html lang=\"de\"><head><meta charset=\"utf-8\">"
        "<title>Auralis Natura — App Store Playbook (One-Pager)</title>"
        "<link href=\"https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..600;1,9..144,300..500&family=Hanken+Grotesk:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap\" rel=\"stylesheet\">"
        f"<style>{CSS}</style></head><body><div class=\"page\">{BODY}</div></body></html>")

html_path = OUT_DIR / "APP-STORE-ONE-PAGER.html"
html_path.write_text(html, encoding="utf-8")
print("HTML", len(html), "bytes")

from playwright.sync_api import sync_playwright
CH = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
pdf_path = OUT_DIR / "APP-STORE-ONE-PAGER.pdf"
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CH, args=["--no-sandbox", "--disable-gpu"])
    pg = b.new_page(viewport={"width": 900, "height": 1300}, device_scale_factor=2)
    pg.goto("file://" + str(html_path), wait_until="networkidle")
    pg.wait_for_timeout(1200)
    ph = pg.evaluate("document.querySelector('.page').scrollHeight")
    print("page content height px (A4≈1123 at 96dpi):", ph)
    pg.screenshot(path=str(OUT_DIR / "_onepager_preview.png"), full_page=True)
    pg.pdf(path=str(pdf_path), format="A4", print_background=True,
           margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    b.close()
print("PDF", pdf_path.stat().st_size, "bytes")
