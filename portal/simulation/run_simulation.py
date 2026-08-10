#!/usr/bin/env python3
"""End-to-end simulation of the whole Auralis Natura customer journey.

Two personas drive the REAL application — no mocks, no shortcuts:

  ELENA (the customer agent) uses only what a real client can reach: the
  public booking API the /book wizard posts to, the acknowledgement mail in
  her inbox, the magic link in her Zugangsdaten mail, and the client portal
  itself, operated in a real Chromium — clicking tabs, typing answers,
  changing her password.

  DESIREE (the operator agent) uses only the Betriebskonsole API with the
  staff key: she reads the briefing, wins the lead, sets the package, sends
  credentials, writes call notes, drafts the report, edits and approves it,
  generates the PDF + report mail, and closes the flywheel with the feedback
  request.

UNLIKE the test suite, this run KEEPS everything it creates — the client
record, the encrypted intake, the report, every .eml and the PDF — because
its purpose is to leave a complete, inspectable specimen of the whole journey.
Run it on the dev machine, never against the production server's data.

Every station asserts the reads and writes that station depends on:
what landed in clients.json, what landed in the encrypted store, which .eml
files appeared, in which language, with which headers. The result is written
to portal/simulation/SIMULATION-REPORT.md.
"""
from __future__ import annotations
import datetime
import json
import re
import sys
import threading
import time
from email import message_from_bytes
from pathlib import Path
from wsgiref.simple_server import make_server, WSGIRequestHandler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib import cfg, store, auth, booking  # noqa: E402
from server.app import app  # noqa: E402

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

# Persona from argv, so a re-run uses a fresh specimen: a finished client's
# intake is (correctly) locked, so the same persona cannot run the journey twice.
NAME = sys.argv[1] if len(sys.argv) > 1 else "Sofia Ejemplo"
EMAIL = sys.argv[2] if len(sys.argv) > 2 else "sofia.ejemplo@example.com"
LOGIN = EMAIL.split("@")[0].replace("@", ".")
KEY = {"X-Auralis-Key": cfg.config().get("api_key", ""), "Content-Type": "application/json"}
REPORT: list[str] = []
CHECKS = {"pass": 0, "fail": 0}


def log(line: str = "") -> None:
    print(line)
    REPORT.append(line)


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "✅" if ok else "❌"
    CHECKS["pass" if ok else "fail"] += 1
    log(f"  {mark} {label}" + (f" — {detail}" if detail and not ok else ""))
    return ok


class Quiet(WSGIRequestHandler):
    def log_message(self, *a):
        pass


def newest_eml(folder: Path, after: float) -> tuple[Path, object] | tuple[None, None]:
    files = sorted([p for p in folder.glob("*.eml") if p.stat().st_mtime >= after - 1],
                   key=lambda p: p.stat().st_mtime)
    if not files:
        return None, None
    return files[-1], message_from_bytes(files[-1].read_bytes())


def subj(msg) -> str:
    from email.header import decode_header
    out = ""
    for part, enc in decode_header(msg.get("Subject", "")):
        out += part.decode(enc or "utf-8", "replace") if isinstance(part, bytes) else part
    return out


def main() -> int:
    started = datetime.datetime.now()
    log(f"# Auralis Natura — End-to-End-Simulation · {started:%Y-%m-%d %H:%M}")
    log()
    log(f"Personas: **{NAME}** (Kundin, Spanisch-Muttersprachlerin, bucht auf")
    log("Deutsch, wechselt im Portal zu Spanisch) und **Desiree** (Betriebskonsole).")
    log("Die Simulation läuft gegen die ECHTE Anwendung und lässt alle Daten stehen.")
    log()

    srv = make_server("127.0.0.1", 0, app, handler_class=Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    import urllib.request

    def api(path, payload=None, headers=None, method=None):
        req = urllib.request.Request(
            base + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers or {"Content-Type": "application/json"},
            method=method or ("POST" if payload is not None else "GET"))
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    from playwright.sync_api import sync_playwright

    # ── Station 1: Elena books the free introductory call ────────────────────
    log("## Station 1 — Elena bucht das kostenlose Kennenlerngespräch (/book)")
    t0 = time.time()
    st, slots = api("/api/booking/slots")
    day = next((d for d in slots.get("days", []) if d.get("slots")), None)
    check("Slots werden öffentlich angeboten", st == 200 and day is not None)
    slot = day["slots"][0]["utc"]
    st, r = api("/api/booking/book", {
        "slot": slot, "name": NAME, "email": EMAIL,
        "language": "de", "note": "Ich freue mich auf das Gespräch.",
        "consent": {"gdpr": True, "health_data": True},
        "profile": {"goal": "Wieder Energie für meinen Alltag finden — ich bin seit "
                            "Monaten erschöpft, obwohl ich genug schlafe.",
                    "symptoms": ["fatigue", "sleep", "cycle"], "since": "months",
                    "age": 34, "life_stage": "postpartum",
                    "scales": {"energy": 2, "sleep": 3, "stress": 4, "digestion": 3},
                    "tried": "Mehr Sport, weniger Kaffee — beides hält nie lange.",
                    "red_flags": ["none"]}})
    ok = check("Buchung angenommen (200, ok:true)", st == 200 and r.get("ok"))
    if not ok:
        log(f"    ABBRUCH: {r}")
        return 1
    bid = r["id"]
    log(f"    Buchung `{bid}` für `{slot}`.")

    booked = next((b for b in booking.list_bookings() if b["id"] == bid), None)
    check("WRITE bookings-DB: Buchung persistiert, Status confirmed",
          booked is not None and booked.get("status") == "confirmed")
    ics_file = cfg.OUTPUT_DIR / "bookings" / f"{bid}.ics"
    check("WRITE .ics auf Platte (Audit)", ics_file.exists())
    ics = ics_file.read_text()
    check("Einladung: METHOD:REQUEST + beide Teilnehmer + eine UID",
          "METHOD:REQUEST" in ics and ics.count("ATTENDEE") == 2 and f"UID:{bid}@" in ics)

    # the three mails of a booking
    sent_dir = cfg.OUTPUT_DIR / "bookings" / "sent"
    ack_dir = cfg.OUTPUT_DIR / "bookings" / "ack"
    int_dir = cfg.OUTPUT_DIR / "bookings" / "internal"
    _, ack = newest_eml(ack_dir, t0)
    _, confirm = newest_eml(sent_dir, t0)
    _, brief = newest_eml(int_dir, t0)
    check("MAIL 1 Sofort-Bestätigung an Sofia (gesendet, nicht Entwurf)",
          ack is not None and EMAIL in ack.get("To", ""))
    check("  … auf Deutsch (Buchungssprache)", ack is not None and "Anfrage" in subj(ack))
    check("  … mit Date + Message-ID", ack is not None and ack.get("Date") and ack.get("Message-ID"))
    check("MAIL 2 Termin-Bestätigung mit Einladung (Entwurf-Pfad, .eml)",
          confirm is not None and "bestätigt" in subj(confirm))
    cal_parts = [p for p in (confirm.walk() if confirm else []) if p.get_content_type() == "text/calendar"]
    check("  … trägt die Kalender-Einladung", len(cal_parts) == 1)
    check("MAIL 3 internes Briefing an team@ (gesendet)",
          brief is not None and "Neue Buchung" in subj(brief))
    bcal = [p for p in (brief.walk() if brief else []) if p.get_content_type() == "text/calendar"]
    check("  … trägt DIESELBE Einladung (Kalender-Eintrag ab Buchung)",
          len(bcal) == 1 and f"UID:{bid}@" in bcal[0].get_payload(decode=True).decode("utf-8", "replace"))
    for nm, m in (("ack", ack), ("confirm", confirm), ("briefing", brief)):
        imgs = [p for p in (m.walk() if m else []) if p.get_content_maintype() == "image"]
        check(f"  Logo (Lockup, cid) in {nm}", len(imgs) == 1)

    # lead auto-created
    st, cl = api("/api/clients", headers=KEY, method="GET")
    elena = next((c for c in cl.get("clients", []) if c.get("email") == EMAIL), None)
    check("WRITE clients.json: Lead automatisch angelegt", elena is not None)
    cid = elena["client_id"]
    check("Login-ID aus dem Namen abgeleitet", elena.get("login_id", "").startswith(LOGIN),
          elena.get("login_id", ""))
    rec = store.get(cid) or {}
    check("WRITE Store (verschlüsselt): Vorab-Angaben am Datensatz",
          (rec.get("pre_intake") or {}).get("goal", "").startswith("Wieder Energie"))
    check("Stage = lead (Funnel-Anfang)", rec.get("stage") == "lead")
    log()

    # ── Station 2: Desiree wins the lead and sends access ────────────────────
    log("## Station 2 — Desiree: Erstgespräch geführt, gewonnen, Zugang gesendet")
    t1 = time.time()
    st, _ = api(f"/api/client/{cid}/stage", {"stage": "won", "force": True}, headers=KEY)
    check("Stage → won", st == 200 and (store.get(cid) or {}).get("stage") == "won")
    st, _ = api(f"/api/client/{cid}/profile", {"package": "bloom"}, headers=KEY)
    pkg = (store.get(cid) or {}).get("package") or {}
    check("Paket Wandel (bloom, 399 €) gesetzt", st == 200 and pkg.get("key") == "bloom"
          and pkg.get("price") == 399, str(pkg))
    st, creds = api(f"/api/client/{cid}/credentials", {}, headers=KEY)
    check("Zugangsdaten erzeugt", st == 200 and bool(creds.get("password")))
    check("Antwort nennt die Login-ID (nicht die AN-Nummer)",
          creds.get("login_id", "").startswith(LOGIN))
    elena_pw = creds["password"]
    _, cmail = newest_eml(cfg.OUTPUT_DIR / cid / "sent", t1)
    check("MAIL 4 Zugangsdaten-Karte (.eml)", cmail is not None and "Zugang" in subj(cmail))
    html_part = next((p.get_payload(decode=True).decode("utf-8", "replace")
                      for p in (cmail.walk() if cmail else [])
                      if p.get_content_type() == "text/html"), "")
    m = re.search(r'href="([^"]*?/portal#k=[^"]+)"', html_part)
    check("  … enthält den Ein-Klick-Link (Fragebogen öffnen)", m is not None)
    check("  … und die Fragebogen-Botschaft (speichert automatisch / gemeinsam im Gespräch)",
          "speichert automatisch" in html_part and "Erstgespräch gemeinsam" in html_part)
    magic_url = m.group(1).replace("&amp;", "&") if m else ""
    check("Store: Stage → invited", (store.get(cid) or {}).get("stage") == "invited")
    log()

    # ── Station 3: Elena opens the portal and fills in the intake ────────────
    log("## Station 3 — Elena: Ein-Klick ins Portal, Fragebogen, Passwort, Programme")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 414, "height": 896})
        errs: list[str] = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        # the mail's magic link, retargeted at the simulation server
        frag = magic_url.split("#", 1)[1]
        pg.goto(f"{base}/portal#{frag}")
        pg.wait_for_selector("#intake:not(.hidden)", timeout=10000)
        check("Magic-Link: ohne ID/Passwort direkt im Fragebogen", True)
        check("Schlüssel aus der Adresszeile entfernt", "#k=" not in pg.url)

        # Elena is a Spanish native speaker: she switches the portal to Spanish
        pg.click('#langTop button[lang="es"]')
        check("Sprachwechsel im Portal → Spanisch",
              "Sobre ti" in pg.inner_text('[data-step="0"] h1'))

        # Step A
        pg.fill('[data-k="goal"]', "Recuperar mi energía para el día a día — llevo meses agotada.")
        pg.fill('[data-k="why_now"]', "Después del posparto nada volvió a ser como antes; ahora quiero entenderlo.")
        pg.fill('[data-k="tried"]', "Más deporte y menos café, pero nunca se mantiene.")
        pg.click("#next")
        # Step B
        for k, v in (("energy", 2), ("sleep", 3), ("stress", 4), ("digestion", 3)):
            pg.click(f'[data-scale="{k}"] button:nth-child({v})')
        pg.fill('[data-k="eating"]', "Café con leche por la mañana, pasta o arroz al mediodía, cena ligera.")
        pg.fill('[data-k="hydration"]', "1,5 l de agua, 2 cafés, casi nada de alcohol")
        pg.fill('[data-k="movement"]', "Paseos con el bebé, yoga suave 1× por semana")
        pg.fill('[data-k="life_stage"]', "Posparto (8 meses), todavía doy el pecho")
        pg.click("#next")
        # Step C
        pg.fill('[data-k="symptoms"]', "Cansancio constante, antojos de dulce por la tarde, sueño ligero.")
        pg.fill('[data-k="stress_sources"]', "Volver al trabajo + noches cortas con el bebé.")
        pg.fill('[data-k="wish_3m"]', "Llegar a la tarde con energía y sin necesitar azúcar.")
        pg.click("#next")
        # Step D — safety: nothing applies
        pg.fill('[data-k="conditions"]', "Ninguna diagnosticada")
        pg.fill('[data-k="medications"]', "Ninguna")
        pg.click("#flagNone")
        pg.click("#next")
        # Step E — consent
        pg.click("#c1"); pg.click("#c2")
        pg.click("#next")
        pg.wait_for_selector("#view-home:not(.hidden)", timeout=10000)
        check("Fragebogen abgesendet → Übersicht", True)
        check("Keine JavaScript-Fehler", not errs, "; ".join(errs[:2]))

        rec = store.get(cid) or {}
        intake = rec.get("intake") or {}
        check("WRITE Store: Intake verschlüsselt persistiert",
              intake.get("goal", "").startswith("Recuperar"))
        check("Intake trägt die PORTAL-Sprache (es)", intake.get("language") == "es")
        check("Red-Flag-Werte kanonisch (None of the above)",
              intake.get("red_flags") == ["None of the above"])
        check("Stage → intake→prep (Gesprächsvorbereitung wird direkt mitberechnet)",
              rec.get("stage") in ("intake", "prep"), rec.get("stage"))
        check("READ Übersicht: Selbsteinschätzung sichtbar",
              "2/5" in pg.inner_text("#wbBars"))

        # she changes her password herself
        pg.click('#tabbar button:nth-child(5)')
        pg.fill("#pwOld", elena_pw)
        pg.fill("#pwNew", "MiNuevaClave2026")
        pg.fill("#pwRep", "MiNuevaClave2026")
        pg.click("#view-access .btn")
        pg.wait_for_selector(".ptoast.on", timeout=5000)
        check("Passwort selbst geändert (Zugang-Tab)", True)

        # cross-sell surface
        pg.click('#tabbar button:nth-child(4)')
        pg.wait_for_selector(".prog")
        progs = pg.inner_text("#progList")
        check("Programme-Tab: lokalisierte Namen (Claridad/Cambio/Equilibrio)",
              "Claridad" in progs and "Cambio" in progs and "Equilibrio" in progs)
        check("Ihr Programm (Cambio) ist markiert", pg.locator(".prog.mine").count() == 1,
              f"ME.package={pg.evaluate('ME&&ME.package')}")
        check("Stripe-Links eingebunden",
              pg.locator('#progList a[href*="buy.stripe.com"]').count() >= 1)
        b.close()

    # old password no longer works, new one does — via the real login
    st, r = api("/api/login", {"client_id": LOGIN.title(), "password": elena_pw})
    check("Altes Passwort abgelehnt", st == 401)
    st, r = api("/api/login", {"client_id": LOGIN, "password": "MiNuevaClave2026"})
    check("Neues Passwort + Namens-Login (case-insensitiv) funktioniert", st == 200)
    log()

    # ── Station 4: Desiree runs the deep-dive call and the report ────────────
    log("## Station 4 — Desiree: Notizen, KI-Entwurf, Freigabe, PDF, Bericht-Mail")
    t3 = time.time()
    st, _ = api(f"/api/client/{cid}/notes", {"notes": {
        "beobachtungen": "Wirkt müde, aber sehr motiviert. Stillt noch — Eisenstatus ansprechen (ärztlich!).",
        "themen": "Energie am Nachmittag, Heißhunger auf Süßes, leichter Schlaf",
        "prioritaeten": "1) Frühstück mit Protein 2) Nachmittagsroutine 3) Abendritual",
        "vereinbart": "Start mit Wandel-Programm nach Berichtsversand"}}, headers=KEY)
    check("WRITE Notizen (strukturiert) + Stage call", st == 200)
    # the operator-chosen language governs the report: Desiree sets Spanish,
    # matching what Elena chose in the portal
    st, _ = api(f"/api/client/{cid}/profile", {"language": "es"}, headers=KEY)
    check("Kundinnen-Sprache in der Konsole: es", st == 200)
    st, r = api(f"/api/client/{cid}/draft", {}, headers=KEY)
    rep = r.get("report") or {}
    check("KI-Entwurf erstellt", st == 200 and len(rep.get("sections", [])) >= 6)
    check("Bericht in Kundinnen-Sprache (es)", rep.get("language") == "es")
    check("Kein Red-Flag (keine angekreuzt)", rep.get("red_flag") is False)
    # Desiree edits one sentence — the human-review gate in action
    secs = rep["sections"]
    secs[0]["body"] = secs[0]["body"].rstrip() + "\n\nRevisado personalmente por Desiree."
    st, r = api(f"/api/client/{cid}/report/save", {"sections": secs, "approved": True}, headers=KEY)
    check("Bericht redigiert + FREIGEGEBEN (Gate)", st == 200 and r.get("approved") is True)
    st, r = api(f"/api/client/{cid}/generate", {}, headers=KEY)
    check("PDF gerendert + Bericht-Mail erstellt", st == 200, str(r))
    pdf = cfg.OUTPUT_DIR / cid / "report" / "report.pdf"
    check("WRITE report.pdf auf Platte", pdf.exists() and pdf.stat().st_size > 50_000)
    _, rmail = newest_eml(cfg.OUTPUT_DIR / cid / "sent", t3)
    check("MAIL 5 Bericht-Mail, spanischer Betreff",
          rmail is not None and "informe personal" in subj(rmail))
    check("  … PDF hängt an", any(p.get_content_type() == "application/pdf"
                                   for p in (rmail.walk() if rmail else [])))
    check("  … Logo (Lockup, cid)", any(p.get_content_maintype() == "image"
                                        for p in (rmail.walk() if rmail else [])))
    check("Stage → sent", (store.get(cid) or {}).get("stage") == "sent")
    log()

    # ── Station 4b: Desiree plans the programme calls ────────────────────────
    log("## Station 4b — Desiree plant die Programm-Termine (Wandel, 4 Gespräche)")
    t3b = time.time()
    st, prop = api(f"/api/client/{cid}/sessions/propose", {}, headers=KEY)
    check("Vorschlag aus Paket + Verfügbarkeit", st == 200 and len(prop.get("plan", [])) == 4,
          str(prop)[:120])
    plan = prop["plan"]
    check("wöchentlicher Rhythmus, Kick-off 60 Min.",
          plan[0]["minutes"] == 60 and all(p["minutes"] == 45 for p in plan[1:]))
    check("jede Zeile mit Alternativen zum Verschieben",
          all(len(p.get("alternatives", [])) > 3 for p in plan))
    # Desiree adjusts one call — takes the second alternative for session 2
    alt = next(a for a in plan[1]["alternatives"] if a["utc"] != plan[1]["utc"])
    plan[1] = {**plan[1], "utc": alt["utc"]}
    slots_before = {s["utc"] for d in api("/api/booking/slots")[1]["days"] for s in d["slots"]}
    st, saved = api(f"/api/client/{cid}/sessions",
                    {"sessions": [{"utc": p["utc"], "minutes": p["minutes"],
                                   "key": p["key"], "n": p["n"]} for p in plan],
                     "notify": True}, headers=KEY)
    check("4 Termine gespeichert (einer manuell verschoben)",
          st == 200 and len(saved.get("created", [])) == 4, str(saved)[:120])
    slots_after = {s["utc"] for d in api("/api/booking/slots")[1]["days"] for s in d["slots"]}
    blocked = {p["utc"] for p in plan} & slots_before
    check("WRITE→READ /book: belegte Zeiten sofort aus dem öffentlichen Angebot",
          blocked and not (blocked & slots_after), f"blocked={len(blocked)}")
    st, r = api("/api/booking/book", {
        "slot": saved["created"][0]["utc"], "name": "Drängler", "email": "d@example.invalid",
        "language": "de", "note": "", "consent": {"gdpr": True}})
    check("direkter POST auf eine Session-Zeit → abgelehnt", st == 409)
    _, smail = newest_eml(cfg.OUTPUT_DIR / cid / "sent", t3b)
    check("MAIL Terminplan an die Kundin (spanisch, Programmname)",
          smail is not None and "Cambio" in subj(smail))
    scal = [p for p in (smail.walk() if smail else []) if p.get_content_type() == "text/calendar"]
    check("  … EINE Einladung mit 4 Terminen",
          len(scal) == 1 and scal[0].get_payload(decode=True).decode("utf-8", "replace").count("BEGIN:VEVENT") == 4)
    log()

    # ── Station 5: delivered, paid, feedback ─────────────────────────────────
    log("## Station 5 — Abschluss: bezahlt, Feedback-Anfrage (Flywheel)")
    t4 = time.time()
    st, _ = api(f"/api/client/{cid}/profile", {"paid": True}, headers=KEY)
    check("Bezahlt markiert (Umsatz zählt ins Cockpit)", st == 200
          and (store.get(cid) or {}).get("paid") is True)
    st, _ = api(f"/api/client/{cid}/stage", {"stage": "done", "force": True}, headers=KEY)
    check("Stage → done", st == 200)
    st, _ = api(f"/api/client/{cid}/feedback-request", {}, headers=KEY)
    _, fmail = newest_eml(cfg.OUTPUT_DIR / cid / "sent", t4)
    check("MAIL 6 Feedback-Anfrage, spanisch", fmail is not None
          and "tiempo con Auralis" in subj(fmail))
    log()

    # ── Elena's view at the end ──────────────────────────────────────────────
    log("## Abschlussbild — Elenas Portal nach Berichtsversand")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 414, "height": 896})
        pg.goto(base + "/portal")
        pg.wait_for_selector("#langLogin button")
        pg.click('#langLogin button[lang="es"]')
        pg.fill("#cid", LOGIN)
        pg.fill("#pw", "MiNuevaClave2026")
        pg.click("#login .btn")
        pg.wait_for_selector("#shell:not(.hidden)", timeout=10000)
        home = pg.inner_text("#view-home")
        check("Journey: vier Stationen ✓, Programm läuft", home.count("✓") >= 4)
        check("Prioritäten aus dem Bericht sichtbar", "Tus prioridades" in home)
        check("Programm-Termine im Portal (Tus citas, 4 Gespräche, spanisch)",
              "Tus citas" in home and home.count("Sesión") + home.count("sesión") >= 3, home[:400])
        pg.click('#tabbar button:nth-child(3)')  # Informe
        ok_dl = pg.locator("#reportCard .btn").count() == 1
        check("Bericht-Tab: Download angeboten", ok_dl)
        pg.screenshot(path=str(ROOT / "simulation" / "final-home.png"), full_page=True)
        b.close()
    srv.shutdown()
    log()

    # ── Assessment ───────────────────────────────────────────────────────────
    log("## Daten-Bestand (bewusst NICHT gelöscht)")
    log(f"- clients.json → `{cid}` {NAME} · login `{LOGIN}` · es · bezahlt")
    log(f"- Verschlüsselter Datensatz (auralis.db) → Vorab-Angaben, Intake, Notizen, freigegebener Bericht")
    log(f"- `output_docs/bookings/` → {bid}.ics + Bestätigung/Ack/Briefing (.eml)")
    log(f"- `output_docs/{cid}/sent/` → Zugangsdaten-, Bericht-, Feedback-Mail (.eml)")
    log(f"- `output_docs/{cid}/report/report.pdf` → das 12-Seiten-Dokument")
    log(f"- `portal/simulation/final-home.png` → das Portal der Kundin am Ende")
    log()
    total = CHECKS["pass"] + CHECKS["fail"]
    log(f"**Ergebnis: {CHECKS['pass']}/{total} Prüfungen bestanden.**")
    dur = (datetime.datetime.now() - started).total_seconds()
    log(f"Laufzeit {dur:.0f}s · Provider: {rep.get('provider', '?')} (Konsole nutzt in Produktion die Claude CLI).")
    (ROOT / "simulation" / "SIMULATION-REPORT.md").write_text("\n".join(REPORT) + "\n", encoding="utf-8")
    return 0 if CHECKS["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
