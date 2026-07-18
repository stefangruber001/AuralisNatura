# Auralis Natura — Portal, Betriebskonsole & Cloud Report Agent

The running application behind auralisnatura.com: a **Client-Portal** (login → premium health
intake), a **Betriebskonsole** (Desiree's ops cockpit), and a **Cloud Report Agent** that
drafts the premium report → she reviews & approves → one click renders the PDF and drops a
ready email (with a review-call booking link) into Gmail drafts.

> Concept & full documentation: `../handover/auralis-portal/`. This folder is the code.

## Quick start (local / Mac)
```bash
cd portal
python3 -m pip install -r requirements.txt
cp .env.example .env            # fill in secrets (never commit .env)
python3 run.py                  # → http://127.0.0.1:5056
```
- Client portal: `/portal` · Betriebskonsole: `/staff` (enter the staff key).
- Or double-click **`start_auralis.command`** (macOS) — one launcher that starts BOTH the
  Flask server AND the Cloudflare tunnel, **auto-restarting the tunnel** if it drops (no more
  Error 1033), self-updates from GitHub `main` every ~120s, and keeps the Mac awake. The
  tunnel command is auto-detected from `~/.cloudflared/auralis.yml` (template:
  `deploy/auralis-tunnel.example.yml`) or `TUNNEL_CMD`/`AURALIS_TUNNEL` in `.env`.
  Windows: `start_auralis.ps1`.

## The pipeline
`invite → client login → premium intake (consent + red-flag) → encrypted store →
console: review + call notes → agent draft → ★ you review & approve → generate (premium
PDF + Gmail draft with booking link) → send → client books the review call.`

Only the discovery/review calls and the **approval** are human; everything else is automated.

## Configuration (`config/*.json`; secrets via env)
- `company.json` — legal + brand master (fill NIF/address before real invoices).
- `config.json` — runtime. Secrets come from env: `AURALIS_API_KEY`, `AURALIS_SECRET`,
  `AURALIS_DATA_KEY` (backbone encryption), `AURALIS_SMTP_PASSWORD` (Gmail app password),
  `AURALIS_AGENT_PROVIDER` (`claude_cli` on the Pro subscription / `stub`), `AURALIS_EMAIL_MODE`
  (`draft`/`send`/`off`).
- `clients.json` — portal logins only (**no health data** — that lives encrypted in the
  backbone, `auralis.db`, git-ignored).
- `report_engine.json` — the agent (model, sections, safety rules).

## The Cloud Report Agent
Runs Claude via **Claude Code on Desiree's Pro/Max subscription** (`claude login`; no API
key, no per-token cost). It receives only **pseudonymised** data (identifiers stripped) and
returns a six-part draft. `stub` provider gives an offline deterministic draft for testing.
It never emails a client and never bypasses the approval gate.

## Security & GDPR (special-category health data)
- Binds `127.0.0.1` only; the internet reaches it solely via the Cloudflare tunnel; `/staff`
  is additionally behind Cloudflare Access. See `../handover/auralis-portal/guides/`.
- Backbone + backups encrypted at rest (Fernet, key from env). Consent captured with
  timestamp + version. One-click **GDPR export & erase** per client in the console.
- Coaching & education, never medical care. "Dr." = Dr. rer. nat. (chemistry), not a
  physician. Every report/email carries the scope + 112 + GDPR footer.

## Tests
```bash
python3 tests/test_e2e.py        # backend pipeline (Flask test client)
python3 .ci/ui_test.py           # full browser E2E (Playwright): portal + console
```

## Layout
```
config/   company.json config.json clients.json report_engine.json
lib/      cfg store auth agent render mailer          (the engine)
server/   app.py                                       (Flask API + routes)
web/      portal.html staff.html                       (client + staff UIs)
tests/ .ci/                                             (backend + browser E2E)
run.py  start_auralis.command/.ps1  requirements.txt   (run + self-updating launchers)
```


## Journey-SOP (was du je Phase tust — die Konsole zeigt es auch als Aktion)
| Phase | Deine Aktion | System macht |
|---|---|---|
| Anfrage | vorbereiten (📋 Vorab-Angaben lesen), ggf. 🔔 Erinnerung | Bestätigung + Kalender-Invite an Kundin & team@ |
| Erstgespräch | ☎ „Gespräch geführt" nach dem Call | — |
| Gewonnen | Paket + Preis setzen → 🔑 Zugangsdaten senden | Zugangs-Karte per Mail |
| Intake | Prep lesen, Tiefengespräch führen, Notizen strukturiert erfassen | Auto-Gesprächsvorbereitung |
| Bericht | Entwurf erzeugen → prüfen/bearbeiten → freigeben → PDF+Mail | 12-Seiten-PDF, Gmail-Entwurf |
| Geliefert | Review-Call · 💶 Bezahlt | Umsatz in Cockpit/Finanzen |
| Abgeschlossen | ⭐ Feedback anfragen (Testimonial — nur echte!) | Dankes-Mail |
