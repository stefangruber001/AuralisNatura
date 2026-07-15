#!/usr/bin/env python3
"""Auralis App-Store go-live — VISUAL step-by-step (mock screens + callouts) → PDF."""
import base64
from pathlib import Path

ROOT = Path("/home/user/AuralisNatura")
seal = base64.b64encode((ROOT / "portal/assets/seal.png").read_bytes()).decode()
OUT_DIR = ROOT / "handover/auralis-portal"
REPO = "github.com/stefangruber001/auralisnatura"

CSS = """
:root{--ink:#281F16;--ink-soft:#5C4A3A;--ink-faint:#8C7E6E;--forest:#3D2719;--forest-deep:#221305;--clay:#A8492A;--gold:#AD7A32;--gold-b:#D6A84E;--sage:#3F7B5A;--paper:#F5EEE0;--cream:#FBF6EB;--line:rgba(61,39,25,.16);--gold-hair:rgba(173,122,50,.5);--fd:"Fraunces",Georgia,serif;--fb:"Hanken Grotesk",system-ui,sans-serif;--fm:"IBM Plex Mono",ui-monospace,monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--fb);color:var(--ink);background:#fff;font-size:9.6px;line-height:1.5}
.page{width:210mm;padding:11mm 12mm 8mm;margin:0 auto}
a{color:var(--clay);text-decoration:none;border-bottom:.5px solid var(--gold-hair)}
b{color:var(--ink)}
.head{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid var(--forest);padding-bottom:6px}
.head .l{display:flex;gap:8px;align-items:center}.head img{width:34px;height:34px}
.wm{font-family:var(--fd);font-size:14px}.kick{font-size:6px;letter-spacing:.24em;text-transform:uppercase;color:var(--clay);font-weight:700}
.head .r{text-align:right;font-style:italic;color:var(--ink-soft);font-size:8px;font-family:var(--fd)}
h1{font-family:var(--fd);font-weight:400;font-size:19px;margin:11px 0 3px}
.lede{color:var(--ink-soft);font-size:10px;max-width:120ch}
.done{background:#EEF6EF;border:1px solid #BcdCc0;border-left:4px solid var(--sage);padding:8px 12px;margin:9px 0 4px;display:flex;gap:16px;flex-wrap:wrap;align-items:center}
.done b{color:#2b5e3f}.done .t{font-size:8px;letter-spacing:.1em;text-transform:uppercase;color:var(--sage);font-weight:700}
.done .v{font-family:var(--fm);font-size:9.5px}
.step{display:flex;gap:11px;margin-top:13px;page-break-inside:avoid}
.num{flex:0 0 auto;width:22px;height:22px;border-radius:50%;background:var(--clay);color:#fff;font-family:var(--fd);font-size:12px;display:flex;align-items:center;justify-content:center;margin-top:1px}
.body{flex:1}
.body h3{font-family:var(--fd);font-weight:400;font-size:13px;color:var(--forest)}
.body .cap{color:var(--ink-soft);font-size:9.2px;margin:1px 0 6px}
/* mock browser window */
.win{border:1px solid var(--line);box-shadow:0 1px 2px rgba(40,25,12,.05),0 10px 24px rgba(40,25,12,.07);background:#fff}
.win .bar{display:flex;align-items:center;gap:7px;background:#EDE7DC;padding:5px 9px;border-bottom:1px solid var(--line)}
.dots{display:flex;gap:4px}.dots i{width:7px;height:7px;border-radius:50%;background:#c9bfb0;display:block}
.dots i:first-child{background:#E5837A}.dots i:nth-child(2){background:#E7C15C}.dots i:nth-child(3){background:#8FBF7E}
.url{flex:1;background:#fff;border:1px solid var(--line);border-radius:20px;padding:2px 10px;font-family:var(--fm);font-size:8.4px;color:var(--ink-soft)}
.win .in{padding:10px 12px}
.win .title{font-family:var(--fd);font-size:11px;margin-bottom:7px;color:var(--ink)}
.row{display:flex;align-items:center;gap:8px;padding:5px 8px;border:1px solid var(--line);margin:5px 0;background:#FCFAF5}
.row .k{font-size:8px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-faint);font-weight:700;min-width:74px}
.row .val{font-family:var(--fm);font-size:9px}
.hl{border:2px solid var(--clay);background:#FCEFEA;position:relative}
.pin{position:absolute;right:-9px;top:-9px;width:18px;height:18px;border-radius:50%;background:var(--clay);color:#fff;font-size:9px;font-weight:700;display:flex;align-items:center;justify-content:center;box-shadow:0 1px 3px rgba(40,25,12,.3)}
.btn{display:inline-block;background:var(--clay);color:#fff;font-weight:600;font-size:8.6px;padding:3px 10px}
.btn.gh{background:#2A7d46}
.ghost{border:1px solid var(--line);color:var(--forest);font-size:8.4px;padding:3px 9px;display:inline-block;background:#fff}
.term{background:var(--forest-deep);color:#EDE7D6;font-family:var(--fm);font-size:9.2px;padding:9px 12px;line-height:1.6}
.term .c{color:#C9B896}
.sectbl{width:100%;border-collapse:collapse;margin-top:4px}
.sectbl td{border:1px solid var(--line);padding:5px 8px;vertical-align:middle}
.sectbl .nm{font-family:var(--fm);font-size:9px;font-weight:600;color:var(--forest);width:38%}
.tag{display:inline-block;font-size:6.5px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;padding:1px 6px;background:var(--gold);color:#2A2210}
.dd{border:1px solid var(--line);background:#fff;max-width:210px}
.dd .opt{padding:4px 9px;font-family:var(--fm);font-size:9px;border-bottom:1px solid var(--line)}
.dd .opt.on{background:#FCEFEA;font-weight:700;color:var(--clay)}
.note{font-size:8.6px;color:var(--ink-soft);margin-top:5px;padding-left:2px;border-left:2px solid var(--gold);padding:2px 0 2px 8px}
.foot{margin-top:13px;border-top:1px solid var(--gold-hair);padding-top:6px;font-size:7.4px;color:var(--ink-faint);line-height:1.55}
@media print{@page{size:A4;margin:0}.page{margin:0}}
"""

BODY = f"""
<div class="head">
  <div class="l"><img src="data:image/png;base64,{seal}" alt="">
    <div><div class="wm">Auralis Natura</div><div class="kick">Holistic Health</div></div></div>
  <div class="r">App Store · Go-Live<br>visuell · Schritt für Schritt</div>
</div>

<h1>Die App live bringen — genau das, in dieser Reihenfolge</h1>
<p class="lede">Fast alles im <b>Browser</b>. Nur <b>ein</b> Terminal-Befehl. Ich habe alles fest eingebaut, was ich schon von dir habe — <b>diese Werte musst du nicht mehr eingeben.</b></p>

<div class="done">
  <span class="t">Schon erledigt / fest eingebaut ✓</span>
  <span><span class="t" style="color:var(--ink-faint)">Team-ID</span><br><span class="v">5V62K942X6</span></span>
  <span><span class="t" style="color:var(--ink-faint)">Key-ID</span><br><span class="v">VD3YP9HGS5</span></span>
  <span><span class="t" style="color:var(--ink-faint)">Bundle-ID</span><br><span class="v">com.auralisnatura.app</span></span>
  <span><span class="t" style="color:var(--ink-faint)">Build-Pipeline</span><br><span class="v">fertig im Repo</span></span>
</div>

<!-- STEP 1 -->
<div class="step"><div class="num">1</div><div class="body">
  <h3>Issuer-ID kopieren + .p8 laden</h3>
  <div class="cap">In App Store Connect, Seite „App Store Connect API".</div>
  <div class="win"><div class="bar"><div class="dots"><i></i><i></i><i></i></div>
    <div class="url">appstoreconnect.apple.com/access/integrations/api</div></div>
    <div class="in">
      <div class="title">App Store Connect API</div>
      <div class="row hl"><span class="pin">A</span><span class="k">Issuer ID</span>
        <span class="val">69a6de70-1a2b-3c4d-5e6f-1234567890ab</span><span class="ghost" style="margin-left:auto">Copy</span></div>
      <div class="row"><span class="k">Aktiver Key</span><span class="val">Name: CI · Key ID: VD3YP9HGS5</span>
        <span class="ghost" style="margin-left:auto">Download API Key (.p8)</span></div>
    </div></div>
  <div class="note"><b>A</b> — Klick oben auf <b>Copy</b> bei der <b>Issuer ID</b> (die lange UUID). Die .p8-Datei hast du bereits geladen ✓ (sie liegt in <span class="fm">~/Downloads</span>).</div>
</div></div>

<!-- STEP 2 -->
<div class="step"><div class="num">2</div><div class="body">
  <h3>Den Schlüssel in die Zwischenablage kopieren — 1 Befehl</h3>
  <div class="cap">Terminal öffnen: <b>⌘ + Leertaste</b> → „Terminal" tippen → Enter. Dann diese eine Zeile einfügen und Enter. (Kein Ordnerwechsel, kein weiteres Setup.)</div>
  <div class="term"><span class="c"># kopiert die .p8-Datei kodiert in die Zwischenablage</span><br>base64 -i ~/Downloads/AuthKey_VD3YP9HGS5.p8 | pbcopy</div>
  <div class="note">Es passiert scheinbar „nichts" — das ist richtig: der Wert liegt jetzt in der Zwischenablage und wird in Schritt 3 eingefügt.</div>
</div></div>

<!-- STEP 3 -->
<div class="step"><div class="num">3</div><div class="body">
  <h3>3 Secrets auf GitHub anlegen</h3>
  <div class="cap">GitHub-Repo → Settings → Secrets and variables → Actions. Für jedes: <b>New repository secret</b> → Name exakt eingeben → Wert → <b>Add secret</b>.</div>
  <div class="win"><div class="bar"><div class="dots"><i></i><i></i><i></i></div>
    <div class="url">{REPO}/settings/secrets/actions</div></div>
    <div class="in">
      <div style="display:flex;justify-content:space-between;align-items:center"><div class="title" style="margin:0">Actions secrets</div><span class="btn gh">New repository secret</span></div>
      <table class="sectbl">
        <tr><td class="nm">ASC_ISSUER_ID</td><td>die <b>Issuer ID</b> aus Schritt 1 (⌘V wenn du sie kopiert hast)</td></tr>
        <tr><td class="nm">ASC_KEY_P8_BASE64</td><td><b>⌘V</b> — den Wert aus Schritt 2 einfügen <span class="tag">Zwischenablage</span></td></tr>
        <tr><td class="nm">MATCH_PASSWORD</td><td>ein Passwort, das du dir <b>ausdenkst</b> (im Passwort-Manager speichern)</td></tr>
      </table>
    </div></div>
  <div class="note">Namen müssen <b>exakt</b> so heißen (Großbuchstaben, Unterstriche). Mehr brauchst du nicht — Team-ID &amp; Key-ID sind schon eingebaut.</div>
</div></div>

<!-- STEP 4 -->
<div class="step"><div class="num">4</div><div class="body">
  <h3>Zwei Workflows starten → App in TestFlight</h3>
  <div class="cap">GitHub-Repo → Reiter <b>Actions</b> → links „iOS · TestFlight" → rechts <b>Run workflow</b>.</div>
  <div class="win"><div class="bar"><div class="dots"><i></i><i></i><i></i></div>
    <div class="url">{REPO}/actions</div></div>
    <div class="in">
      <div style="display:flex;gap:12px;align-items:flex-start">
        <div style="flex:1"><div class="title" style="margin:0 0 4px">iOS · TestFlight</div>
          <span class="btn gh">Run workflow ▾</span></div>
        <div class="dd"><div class="opt on">create_app &nbsp;← zuerst (A)</div><div class="opt on">beta &nbsp;← danach (B)</div><div class="opt" style="border:0;color:var(--ink-faint)">release · signing</div></div>
      </div>
    </div></div>
  <div class="note"><b>A</b> — Run workflow mit Lane <b>create_app</b> (legt den App-Eintrag automatisch an). &nbsp; <b>B</b> — danach nochmal Run workflow mit Lane <b>beta</b> → nach ~10 Min erscheint der Build in <b>App Store Connect → TestFlight</b>. Läuft ein Workflow rot? Schick mir den Log-Link, ich fixe es, du klickst nur erneut Run.</div>
</div></div>

<div class="foot">
<b>Auralis Natura — Holistic Health.</b> Genau 4 Schritte: Issuer-ID kopieren · 1 Terminal-Befehl · 3 Secrets · 2× Run workflow. Alle Links: <a href="https://appstoreconnect.apple.com/access/integrations/api">appstoreconnect.apple.com/access/integrations/api</a> · <a href="https://{REPO}/settings/secrets/actions">{REPO}/settings/secrets/actions</a> · <a href="https://{REPO}/actions">{REPO}/actions</a>. Ausführlich: <span class="fm">ios-app/TESTFLIGHT-SETUP.md</span>. Stand Juli 2026 · vertraulich.
</div>
"""

html = ("<!doctype html><html lang=\"de\"><head><meta charset=\"utf-8\">"
        "<title>Auralis Natura — App Store Go-Live (visuell)</title>"
        "<link href=\"https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..600;1,9..144,300..500&family=Hanken+Grotesk:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap\" rel=\"stylesheet\">"
        f"<style>{CSS}</style></head><body><div class=\"page\">{BODY}</div></body></html>")

html_path = OUT_DIR / "APP-STORE-ONE-PAGER.html"
html_path.write_text(html, encoding="utf-8")

from playwright.sync_api import sync_playwright
CH = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
pdf_path = OUT_DIR / "APP-STORE-ONE-PAGER.pdf"
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CH, args=["--no-sandbox", "--disable-gpu"])
    pg = b.new_page(viewport={"width": 900, "height": 1400}, device_scale_factor=2)
    pg.goto("file://" + str(html_path), wait_until="networkidle")
    pg.wait_for_timeout(1200)
    print("content height px (A4=1123):", pg.evaluate("document.querySelector('.page').scrollHeight"))
    pg.screenshot(path=str(OUT_DIR / "_preview.png"), full_page=True)
    pg.pdf(path=str(pdf_path), format="A4", print_background=True, margin={"top":"0","bottom":"0","left":"0","right":"0"})
    b.close()
print("PDF", pdf_path.stat().st_size)
