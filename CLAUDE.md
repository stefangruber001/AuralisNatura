# ⚑ PROJECT STATUS — Website Launch & Live Ops (updated 2026-06-14)

> This addendum sits ABOVE the original handover (below) and takes precedence
> where they differ. The original handover is preserved verbatim for reference
> and the full bundle lives in `handover/`.

## Repo, hosting & where things live
- **This repo is PRIVATE** (owner has GitHub Pro). The website is published via
  **GitHub Pages from `main`** using `.github/workflows/deploy-pages.yml`.
- **Live site:** https://stefangruber001.github.io/AuralisNatura/
- Pages sites are publicly visible even from a private repo, so the deploy
  workflow publishes **only `index.html` + `images/`** (staged into `_site/`).
  **Never** add confidential files to that staging step — `handover/` must stay
  unpublished.
- Layout of this repo:
  - `index.html` — the live website (edited directly; this is the source of truth for the site now).
  - `images/` — website imagery (published).
  - `handover/` — the full founder package from the strategy chat: `deliverables/`,
    `source/` (build system), `assets/` (brand seal/logo), `qa-screenshots/`. PRIVATE, not published.
  - `CLAUDE.md` (this file) — authoritative project memory.

## ⚑ STANDING FOUNDER PREFERENCE (applies to every decision)
- **Always choose the low-cost / free option when it is reliably good enough.** Prefer
  open-source + self-host + free tiers over paid SaaS unless reliability genuinely
  demands paying. (E.g. app OTA updates: self-host Capgo / OtaKit free tier, not paid
  Capgo; hosting: Hetzner/Render small tier; push: Firebase free; payments: Stripe
  Payment Links, no extra fees.) Explicitly requested 2026-07 — keep this always.

## ⚑ APPLE / APP STORE STATUS (persistent facts)
- **Apple Developer Program: ENROLLED & PAID (99 €/yr).** Confirmed by founder 2026-07.
  So the iOS app can go straight to TestFlight/App Store — no enrolment step remains.
- **Apple Team ID: `5V62K942X6`** (from developer.apple.com/account) → `APPLE_TEAM_ID` secret.
- **App Store Connect API Key ID: `JR5U6K9HHB`** (the dedicated Auralis key) → `ASC_KEY_ID`.
  ⚑ An ASC API key is **account/Team-wide, not per-app**. Superseded IDs (do NOT use):
  `VD3YP9HGS5` (never in the account), `5695PLUZS2` (Paramur CI, briefly committed),
  `Q29MBUAL6K` (its .p8/keyID didn't match → auth failed). The key in use is `JR5U6K9HHB`.
  ⚠️ The `.p8` stored in the `ASC_KEY_P8_BASE64` secret MUST be the private key that
  belongs to this exact Key ID, or Apple rejects the token ("invalid bearer token"). Note: `.p8` download does NOT work in iPhone browsers (Apple limitation)
  — generate/download on a computer. **Issuer ID:
  `10347fb1-a3c7-4894-a183-18d98a79a8d0`** → `ASC_ISSUER_ID`. Team-ID, Key-ID and
  Issuer-ID are all **baked into `.github/workflows/ios-testflight.yml` as defaults**
  (identifiers, not secrets), so they never need re-entering.
- **🔐 The private `.p8` lives ONLY in the `ASC_KEY_P8_BASE64` GitHub Actions secret**
  (encrypted), never committed to the repo. The Fastfile reads it from that secret
  (raw PEM or base64, auto-detected) and errors clearly if it is missing.
  ⚠️ The older `5695PLUZS2` `.p8` was briefly committed under `AppProducer/` and remains
  in git history (commits before 2026-07-18 secret-switch); since we rotated to
  `Q29MBUAL6K` (secret-only, never committed), consider revoking `5695PLUZS2` in App
  Store Connect if it is no longer needed for Paramur.
- **The two real secrets** (set once in the GitHub UI, NOT stored in repo/memory):
  `ASC_KEY_P8_BASE64` (the private `.p8` — raw file text OR base64 one-liner; the
  Fastfile auto-detects via the `-----BEGIN PRIVATE KEY-----` header) and `MATCH_PASSWORD`
  (a passphrase the founder invents to encrypt the signing certs). Both are now set.
  Everything else is automated. Visual go-live guide: `handover/auralis-portal/APP-STORE-ONE-PAGER.pdf`.
- Native iOS app lives in `ios-app/` (SwiftUI). Mac-free cloud build pipeline is set up:
  GitHub Actions (`.github/workflows/ios-testflight.yml`) + Fastlane + `match` → TestFlight.
  ✅ **FIRST BUILD SUCCESSFULLY UPLOADED TO TESTFLIGHT 2026-07-18** (run #21). Working facts:
  - **Bundle id `com.auralisnatura.book`** (matches the existing App Store Connect app
    record named "Auralis Natura"; the earlier `com.auralisnatura.app` had no ASC record —
    Apple's API cannot create app records, so we aligned to the existing `.book` one).
  - Runner **`macos-26`**, and the workflow selects the **newest `Xcode_26*.app`** (Apple
    requires the iOS 26 SDK for uploads; pinning 26.0 broke actool on a simulator-runtime
    mismatch). objectVersion 77 project; SWIFT_VERSION=5.0 set in BOTH Debug+Release.
  - Key ID **`JR5U6K9HHB`**, `.p8` ONLY in the `ASC_KEY_P8_BASE64` secret; `MATCH_PASSWORD`
    set. `create_app` lane (spaceship ConnectAPI) registers the Bundle ID + verifies the
    app record; `beta` lane signs, builds, uploads. Just **Run workflow → beta** for updates.
  Setup/automation: `ios-app/TESTFLIGHT-SETUP.md`. Also a Capacitor web-bundle app in
  `app/` (served at `/app`).
- **Lanes (`.github/workflows/ios-testflight.yml` → `Run workflow → <lane>`):** `beta`
  (sign+build+upload to TestFlight; also ensures the internal group), `create_app`
  (register Bundle ID + verify ASC app record), `internal_testers` (create the internal
  "Founders" group with **access to all builds**), `release` (push trilingual metadata +
  screenshots via `deliver`; `submit_for_review:false`), `signing` (reset certs).
- **App Store listing pushed 2026-07-18:** trilingual DE/EN/ES metadata + URLs + review
  contact + category (Health & Fitness) + **12 generated screenshots** (4/locale, 6.9"
  1320×2868). Screenshot generator: `ios-app/scripts/gen_screenshots.py` (HTML→PNG via
  Playwright; on-brand, no simulator). Regenerate → `release` lane re-uploads.
- **Before hitting "Submit for Review" (founder-only, App Store Connect UI):** real
  **demo login** for reviewers (a portal test account; the deliver review fields are
  blank), **age rating** questionnaire, **App Privacy** data-collection labels,
  **pricing/availability**, attach the build, then flip submit. `beta` builds already
  reach internal TestFlight once members are added to the "Founders" group once.
- **🤖 AppBuilder agent + playbook (2026-07-18):** all iOS ship-to-store learnings are
  captured in `.claude/agents/appbuilder.md` (invokable subagent) and mirrored in
  `AppProducer/APPBUILDER-PLAYBOOK.md` — copy the agent file into any repo/template to reuse
  it. Use it for future iOS build/sign/upload/store work. Verification harnesses (both PASS):
  `python3 ios-app/audit.py` (L10n parity, braces, assets, Swift API paths vs server) and
  `python3 portal/tests/test_ios_contract.py` (25 in-process API-contract checks). Reminder:
  a workflow `conclusion: success` can hide a rescued error — read the job log, not just the
  conclusion.

## Decisions that OVERRIDE the original handover
- **🎨 Colour palette (overrides §3 "deep forest green").** The founder chose to
  move OFF green to a warm-earth palette; **2026-06-20 refreshed to a warm "cozy-campfire"
  earth concept** (inspired by a founder reference: cinnamon brown / amber-ochre gold /
  olive / ember red). Current website tokens:
  - `--forest:#3D2719` (primary — dark cinnamon-brown) · hover `#5A3A22`
    - Dark sections (`.problem`, `.tmt`, `.cta-card`, `.pkg.feat`) use a warm-brown
      gradient `--forest-soft #5A3A22` → `--forest #3D2719` → `--forest-deep #27170E`.
    - Emphasis (`.em`) inside dark sections is amber gold `#D6A84E`.
  - `--forest-2:#8A4A2A` (cinnamon-rust, italics/accents on LIGHT backgrounds only)
  - `--sage:#927B4A` (warm olive-taupe) · `--sage-soft:#DAC79E` (warm sand)
  - Accent **`--clay:#A8492A`** (ember rust — buttons/spark/tags) · `--clay-soft:#C47A52`
    (caramel). **`--gold:#AD7A32`** (amber/ochre). paper/cream warm; `--ink #2A211A`.
  - Note: this is the opposite of the handover's anti-cliché rationale; it was a
    deliberate, informed founder decision. Keep earth palette unless told otherwise.
- **💶 Pricing (overrides §8 ladder).** Three one-time individual products, ordered cheapest→most expensive: **Klarheit / Clarity / Claridad €199 · Wandel / Change / Cambio €399 (4-week) · Balance / Balance / Equilibrio €899 (12-week)** — single payments, no instalments. Stripe (Sandbox) products created with these exact names/prices. ⚑ **RENAMED 2026-08-05** — the packages were "The Root Session / The Bloom / The Flourishing"; they are now localised per language (DE Klarheit·Wandel·Balance, EN Clarity·Change·Balance, ES Claridad·Cambio·Equilibrio). Website, portal config, report agent, staff console, iOS app and llms.txt are updated; **the Stripe product names must still be changed by the founder.** The internal keys stay `root`/`bloom`/`flourish(ing)` everywhere — do NOT rename those. ⚠️ **Prices raised 2026-08-04** (was 198/398/798) and **The Bloom shortened 6→4 weeks** — the website, portal config, iOS app and llms.txt are updated; **the Stripe product prices must still be changed by the founder in the Stripe dashboard.** **Offer 04 (added 2026-06-19): "The Grove" — a corporate/teams offer** (science-led nutrition & wellbeing workshops: lunch-&-learn talks, half-day workshops, multi-session series). Priced bespoke ("Tailored · request a quote"); CTA is a `mailto:` enquiry (NOT Stripe/booking — it stays active during the pre-launch gate). Lives as a distinct dark espresso band at the end of the Services section (`#corporate`, `.corp`). ⚠️ **OPEN TASK:** Document 02 financials + §8 below still show OLD prices/offers and must be reworked to match. Treat §8 numbers as stale.
- **🧘 Yoga & Meditation (added 2026-06-19).** Desiree is a **certified Yoga & Meditation teacher** (200-hr Ashtanga, Elemental Yoga & the Mind Arts, 2021, under maiden name Pressnitz). Integrated on the homepage as: a credentials-ribbon chip (`creds.5`), a 4th certificate slide (`cert-yoga.jpg`, `cert.c4`), a bio line (`about.p3`), programme features (Bloom `svc.reset.f5`, Flourishing `svc.trans.f6`) and the method footer. Education **and** service.
- **🖼️ Photo `images/desiree-womens-health.jpg` — MOVED 2026-08-10** out of *Die Gründerin*
  and into **Frauengesundheit**, directly under the life-phases emblem (`.seasons-media`).
  Founder's reason: *"Foto mit Babybauch passt nicht"* in the About section, and she wanted a
  pregnancy photo by the emblem — the same file, so it was one move, not a delete plus a hunt.
  ⚠️ It shows her visibly pregnant. The older §1 note *"Desiree is NOT a mother"* predates it —
  re-confirm before writing any motherhood-related copy. The photo itself makes no claim.
  (`.about-photo` CSS is now unused but left in place; harmless, and cheap to reuse.)
- **🌸 Frauengesundheit reworked 2026-08-10** on the founder's change list: the emblem carries
  **seven** phases now (Stillzeit inserted between Schwangerschaft and Wochenbett, so all seven
  were re-spaced from 60° to ~51° apart — nudging one in would have collided); `seasons.l2` gained
  Stillzeit to match; two new paragraphs position nutrition/lifestyle in hormonally shaped phases;
  and `.seasons .lead`/`.u-subsoft` are one size, because stacked they made the first paragraph
  read heavier than the rest.
- **🏷️ "The Grove" renamed 2026-08-10** → DE **Verbindung** · EN **Connection** · ES **Conexión**,
  matching the localised session names. Internal keys `corp.*` / `#corporate` are unchanged.
- **🖼️ Photos (2026-06-19).** Real photos of Desiree: solo desk portrait = `images/desiree-portrait.jpg` (HERO); consultation-with-client = `images/desiree-consult.jpg` (ABOUT). `about-evidence.jpg` is now orphaned/unused.
- **🎠 Certificates carousel** now infinite-loops (wraps last→first) with gentle 6s autoplay that stops once the user navigates; respects reduced-motion.
- **✍️ Wording decision (2026-08-04, supersedes the 2026-07-01 "12+" rule):** "15+ Jahre / 15+ years / 15+ años" **research and pharmaceutical industry** is now the approved
  MASTER wording for the pharma-experience credential (supersedes the Word master's
  "Fast 12 Jahre"). Applied in creds.2 and about.m2.v ("Mehr als fünfzehn Jahre …") in all three languages. (The old diff.1.p carrier was removed with the differentiators section.)
- **🩺 Doctor title.** Use **"Dr. rer. nat. Desiree Gruber"** as the credentialed name **everywhere** (the term "PhD" was removed in ALL languages; credential lines use "Dr. rer. nat."). Compliance note kept in all
  languages: Dr. = academic doctorate in bioorganic chemistry, NOT a physician.
- **🔌 Backend phase.** The new **`handover/deliverables/04-Process-and-Automation-
  Blueprint.html`** + `handover/WEBSITE-FINALIZATION.md` define the backend / business-
  flow integration (Stripe, intake, AI report engine). Homepage is considered done;
  next work is wiring these. Stripe needs founder's Payment Links or pk_ key (never sk_).


## 🏥 Portal, Betriebskonsole & Customer Journey (Stand Juli 2026 — AKTUELLE Architektur)
Die frühere Cal.com/Tally/Make-Planung (customer-journey-kit) ist ÜBERHOLT — alles läuft
jetzt eigen gebaut in `portal/` (Flask auf Desirees Mac, Cloudflare-Tunnel
`api.auralisnatura.com`, Konsole `/staff`, Klienten-Portal `/portal`, Buchung `/book`).
**Die Journey (jede Station hat E-Mail + Konsole-Aktion):**
1. `/book` — 4-Schritte-Wizard mit Gesundheits-Vorab-Angaben → Premium-Bestätigung
   **mit echter Kalender-Einladung** (METHOD:REQUEST, Cc team@ → landet automatisch in
   Gmail + Google Calendar). Auto-Lead in der Journey. 🔔 Erinnerungs-Mail per Klick.
2. Erstgespräch → 🎉 Gewonnen → Paket setzen → 🔑 Zugangsdaten-Karte (Portal-Login).
3. Portal-Intake (tief, verschlüsselt) → Auto-Gesprächsvorbereitung → strukturierte
   Notizen (Beobachtungen/Themen/Prioritäten/Vereinbart).
4. KI-Entwurf (Claude CLI auf Pro-Abo, pseudonymisiert, Red-Flag-Enforcement) →
   Freigabe-Gate → **12-Seiten-Premium-PDF** (Cover, Brief, Dashboard mit Radar,
   6 Kapitel mit Wissenschafts-Box + Schritten, Wochenplan, 28-Tage-Tracker) →
   Berichts-Mail als Gmail-Entwurf. Klientin sieht Fortschritts-Tracker im Portal.
5. 💶 Bezahlt/Abgeschlossen → ⭐ Feedback-/Testimonial-Anfrage (Flywheel; nur echte
   Stimmen). Umsatz fließt in Cockpit + Finanzen (GuV/Cashflow/Bilanz/Break-even).
**📅 Programm-Termine (2026-08-10):** Sobald ein Paket gesetzt ist, plant die Konsole die
Programm-Gespräche (Kundinnen-Tab → „Programm-Termine"): Vorschlag = Paket-Plan
(`booking._SESSION_PLANS`; root 90'+45', bloom 1×60'+3×45' wöchentlich, flourish 12 Wochen;
per `config.json packages[].sessions` überschreibbar) über Desirees Verfügbarkeit,
DST-sicher „gleicher Tag, gleiche LOKALE Zeit". Jede Zeile per Dropdown verschiebbar;
Speichern ersetzt künftige Termine (Vergangene bleiben), blockt die Zeiten SOFORT
überlappungsbasiert auf /book (Sessions liegen als kind="session" in der bookings-Tabelle)
und mailt Terminliste + EINE Multi-VEVENT-Einladung. Kalender-Identität ist STABIL
(`UID:{cid}-{key}{n}@…` + SEQUENCE aus dem Payload) — Re-Plan verschiebt Events statt sie
zu doppeln; entfallene/abgesagte Termine gehen als METHOD:CANCEL raus (eigene Route
`/api/session/<id>/cancel`). Kundin sieht „Deine Termine" im Portal. Tests:
`tests/test_sessions.py`. ⚠️ `tests/_sandbox.py` MUSS erster Import jedes Tests sein —
die Suite hat 2026-08-10 einmal live `clients.json` + `auralis.db` zerstört; der Sandbox-
Import (Temp-DB + Config-Schutzschild) verhindert genau das, niemals entfernen.
**Konsole-Tabs:** Cockpit · Customer Journey · Finanzen · Plandaten · Kundinnen ·
Termine (visueller Verfügbarkeits-Editor) · ⚙ Stammdaten/Outbox/System. PWA
(„Office"-App, Login persistent). E-Mail-Modi off/draft/send; alles als .eml-Audit.
**🌐 Sprache pro Kundin (Kundinnen-Tab → Feld „Sprache" de/en/es) ist maßgeblich für
ALLE kundenseitigen Ausgaben:** Zugangsdaten-, Erinnerungs-, Berichts- & Feedback-Mail
UND das Bericht-PDF. `agent.draft_report(..., language=info["language"])` überschreibt
die Intake-Sprache; die Konsole zeigt ein Sprach-Etikett am Bericht + goldene Warnung,
wenn ein Entwurf in veralteter Sprache vorliegt („↻ Neu entwerfen"). Terminerinnerung
bevorzugt die Kundinnen-Sprache vor der Buchungs-Sprache. Test: `tests/test_language.py`.
**Betriebs-Doku:** `handover/auralis-portal/OPERATOR-ONBOARDING.{html,pdf}` (Einarbeitung:
Prozess Station-für-Station, Sprache, Freigabe-Gate, erste-Woche-Checkliste) — ergänzt das
technische `OPERATIONS-MANUAL.{html,pdf}` (Server/Tunnel/Backup-Setup auf dem Mac).

## 📒 Tabs „Buchhaltung" + „Finanzamt" (2026-08-21 — SPANISCHES Recht)
Nach der Paramur-Bauanleitung gebaut, aber vollständig auf Spanien übersetzt (autónoma
Barcelona, estimación directa simplificada). Kern: `lib/buchhaltung.py` — der
Finanzamt-Tab **rechnet nichts Eigenes**, er liest dieselbe `ea()`-Auswertung
(Wächter Nr. 15 erzwingt das). Daten in **eigenen Tabellen der bestehenden SQLite**
(`buch_entries`, `buch_meta`) — symlinkt, stündlich gesichert, vom Reset-Snapshot
erfasst; Beleg-Dateien unter `output_docs/buchhaltung/<id>/`.
- **Spanien-Regeln, die den Aufbau bestimmen:** Zufluss/Abfluss (criterio de cobros y
  pagos — ZAHLdatum bucht); Belege lückenlos `A-<Jahr>-0001`, nie löschen, nur
  stornieren; 6 Jahre Aufbewahrung; IVA 21/10/4/0 und **Coaching ist mit 21 %
  steuerpflichtig** (keine Heilberufe-Befreiung, Art. 20.Uno.3 LIVA — Desiree ist keine
  sanitaria); **atenciones a clientes: IVA NIE abziehbar** (Art. 96 LIVA — die Umkehrung
  der österreichischen Bewirtungsfalle: Gewinn voll, IVA 0); Verpflegung max.
  26,67 €/Tag; **PKW: IVA 50 % vermutet, Gewinnwirkung 0**; Privatanteil kürzt beides;
  **+5 % gastos de difícil justificación (max. 2.000 €)**; Simplificada endet bei
  600.000 € Umsatz (Warnung ab 80 %).
- **Einnahmen kommen automatisch** aus den `paid`-Events (Stripe-Webhook + 💶-Knopf),
  Endpreise inkl. 21 % IVA, virtuell nummeriert `I-<Jahr>-####`; erfasst werden nur
  Ausgaben + sonstige Einnahmen. Neutral-Kategorien (AEAT-IVA, AEAT-IRPF,
  Privatentnahme): Cashflow ja, Gewinn nein, IVA 0.
- **Fristen mit STARTFENSTER** (das macht aus der Deadline-Liste eine Arbeitsliste):
  Modelo **303** + **130** je Quartal (1.–20.4./7./10., Q4 bis 30.1.; Lastschrift endet
  5 Tage früher — steht im `tun`-Text), **390** (1.–30.1.), **Renta/Modelo 100**
  (Kampagne ~6.4.–30.6.). Ort und Handlung getrennt („AEAT Sede Electrónica" +
  Formular-Pfad). Sichtfenster 80 Tage + „+N weitere". Erledigt-Häkchen in `buch_meta`,
  überlebt Neustart, rückholbar. **Ohne Alta-Datum (Modelo 036/037) erscheint KEINE
  Frist** — vor der Gründung gibt es keine Pflichten; das Datum wird im Finanzamt-Tab
  gesetzt (liegt im Store, nicht in der getrackten config).
- **Kennzahlen mit Kopieren-Knopf** (abgetippt = Zahlendreher): 303 je Quartal
  (Basis/repercutido/soportado/Zahllast), 130 (kumuliert, nie negativ, Vorzahlungen
  angerechnet), Renta-Rubriken (Consumos, Servicios profesionales, Suministros, …) —
  der Jahres-Export (PDF via Chromium + CSV) für die Gestoría nutzt DIESELBEN Zeilen.
  Einreichungs-Dossier je Frist als PDF. Rücklagen als Richtwerte (20 %-Logik) klar
  als solche beschriftet.
- Pin: `tests/test_buchhaltung.py` — 17 Wächter, u. a.: offene Belege zählen NIRGENDS,
  Zahlung setzt Buchungsdatum, atenciones/PKW/Privatanteil-Prozente, 130 nie negativ,
  difícil-Deckel, Q4-Fälligkeit 30.1., vor Alta keine Frist, Erledigt übersteht
  Neustart, **Finanzamt == Buchhaltung**, Upload-Sanitisierung, Traversal-Schutz.
- **📷 Beleg-Leser (2026-08-22):** „Beleg fotografieren / hochladen" über dem
  Erfassungsformular → `POST /api/buchhaltung/scan` speichert die Datei IMMER (sie ist
  der Beleg) und liest sie mit der **Claude CLI** (`claude -p`, wie der Bericht-Agent);
  strikte JSON-Antwort, `_sanitize_scan()` verwirft Unbrauchbares (ungültiges Datum,
  negative Beträge, fremde IVA-Sätze, **Neutral-Kategorien nie als Vorschlag**). Die
  Betreiberin **bestätigt jede gelesene Zeile mit ✓** (Bearbeiten bestätigt implizit) —
  ohne alle ✓ ist Speichern gesperrt: der Operator bestätigt, die Maschine bucht nicht.
  **Lernen ohne Training, erklärbar:** (1) Lieferanten-Gedächtnis — die jüngste
  bestätigte Buchung je Lieferant überstimmt die Lese-Vermutung, die Quelle steht an
  der Zeile („aus deinen Buchungen (3× Canva)"); (2) die letzten Korrekturen
  (gelesen ≠ gebucht) wandern als Beispiele in den nächsten Lese-Prompt. Beim Speichern:
  `POST /api/buchhaltung/scan/uebernahme` hängt die Datei an die Buchung und meldet die
  ENDwerte als Feedback (Tabelle `buch_scans`: extracted vs. final = Lernmaterial —
  darum wird `extracted` VOR dem Gedächtnis-Override gespeichert). Ohne CLI oder bei
  Lese-Fehler degradiert der Scan ehrlich: Datei bleibt, Hinweis statt Behauptung.

## 🗺️ Prozess- und Datenkarte: `tools/build_flowmap.py` (2026-08-22)
Ein 13-seitiges PDF im Marken-System, das den ganzen Betrieb als Karte zeigt: sieben
Stationen von der Anfrage bis zur Stimme, dazu Fundament (wo die Daten liegen) und zwei
Querschnitte (Buchhaltung/Finanzamt, „was dich von selbst findet"). Jede Station hat
oben eine Kette (Auslöser → System → ihre Entscheidung → Post), darunter drei Spalten
**⚙ Läuft von selbst · ✋ Du entscheidest · 🗄 Daten & Post** und eine Tabelle mit dem
**exakten Knopf** und seiner Wirkung. Farbsemantik wie überall: Pine automatisch, Clay
ihre Entscheidung, Gold Post, Grau Daten.
- **Als Generator gebaut, nicht als Einmal-Dokument** — der Ablauf ändert sich mit dem
  Code; ein hübsches PDF von letzter Woche wird still falsch. Nach Änderungen neu laufen
  lassen: `python3 tools/build_flowmap.py` (→ `output_docs/Auralis-Prozesskarte.pdf`),
  `--html` für den schnellen Blick.
- Schriften base64 eingebettet (`render._font_css()`), Siegel aus `brand/masters/`,
  gerendert über dieselbe `render.to_pdf`-Kette wie der Kundinnen-Bericht.

## 📣 Social-Media-Modul (Tab 06, 2026-08-14) & Bericht-Redesign
- **Betriebskonsole → „Social Media"** ist das End-to-End-Instagram-Modul (alles kostenlos,
  nur Claude-Pro + bestehender Server): Beobachtungs-**Agenten** (RSS/Web — Instagram wird
  bewusst NICHT gescraped, Wettbewerberinnen via Blogs/Newsletter) → Montag-05:00-Scan
  (`auralis-social-scan.timer`) → deutscher Wochen-**Digest** → chained **Wochenentwurf**
  (Ziel + Digest + hochgeladenes Material → Strategie + Slots mit DE+EN+ES-Caption,
  Hashtags, Alt-Text, Visual-Spec) → Review-Board (editieren, freigeben, einzeln
  regenerieren, Compliance-Lint warnt bei Heil-/Diagnose-Sprache) → **Visual Factory**
  (`lib/socialrender.py`: 7 CI-Templates → Chromium `--screenshot`, exakt 1080×1350/1920;
  Reels via ffmpeg, ohne Audio — Trend-Audio kommt in der IG-App) → Übergabe: ZIP+Mail+
  Checkliste ODER **Auto-Publishing** (`lib/instagram.py`): Freigabe = Queue, 10-Minuten-Timer
  (`auralis-social-publish.timer`) veröffentlicht zur geplanten Madrid-Zeit via Graph API;
  Medien über signierte 4-h-Einmal-URLs (`/pub/social/…`); Token-Auto-Refresh. Einrichtung
  (~40 min, einmalig) als Anleitung im Tab; bis dahin läuft der ZIP-Weg. Secrets NUR in
  `/etc/auralis/portal.env` (`AURALIS_IG_USER_ID/TOKEN/APP_ID/APP_SECRET`). Konfig:
  `config/social.json` (Whitelist, /var/lib-Symlink, Backup); Artefakte unter
  `output_docs/social/`. Prompts extern tunebar: `handover/customer-journey-kit/claude/
  social-{digest,strategy}-prompt.md`. Tests: `tests/test_social_*.py` (immer `_sandbox` zuerst).
- **Kundinnen-Bericht neu (R1+R2, 2026-08-14):** `lib/render.py` komplett neu — benannte
  Seiten-Builder, Marken-Fonts base64-inline (Google-Fonts-CDN entfernt: PDF war offline
  fontlos!), kanonische Tokens aus `design-system/dist/auralis.css`, Cover/Closing mit
  Hairline-Rahmen + Siegel-Wasserzeichen-Anschnitt, neues Inhaltsverzeichnis mit echten
  Seitenzahlen, editoriale Kapitel-Opener (große Ziffer), verfeinerte Radar/Balken-Grafik,
  QR zur Website auf der Schlussseite. **Lange Kapitel clippen nie mehr**: Python-seitiger
  Budget-Splitter erzeugt lokalisierte Fortsetzungsseiten („Kapitel 02 — Fortsetzung").
  Verträge unverändert (`_chrome`/`_CHROME_CANDIDATES`/`to_pdf`-HTML-Fallback, Titel
  wörtlich). Tests: `tests/test_render_contract.py`, `tests/test_render_pagination.py`.

## 🇩🇪 German is the MASTER language (since 2026-08-04)
- Desiree rewrote the homepage copy herself in the in-page editor
  **`www.auralisnatura.com/edit-de.html`** (mirrors the live `index.html` in an iframe,
  autosaves to localStorage, exports JSON). **111 of 236 texts changed.** Workflow from now on:
  she edits German → exports → German is applied to `I18N.de` → **EN (the source text in the
  HTML body) and ES (`I18N.es`) are re-derived from the German**, not patched independently.
- ⚠️ Her export carries `contenteditable` artifacts (`<font color>`, inline `style=`, `<div>`
  wrappers, stray `&nbsp;`, values reduced to a bare `<br>`). **Always clean before importing** —
  see the cleaner used in the 2026-08-04 pass.
- **New positioning:** hero is now *"Verstehe deinen Körper. Verbessere deine Gesundheit
  nachhaltig."* (replaces "Im Einklang mit der Natur…", which survives as the app's brand slogan).
- **Sections removed 2026-08-04** on founder request (redundant / more premium flow):
  the services free-call block (`svc.free.*`), the method footnote (`method.foot`), the logo
  banner (`partners.*`), the differentiators section (`diff.*`) and "Was dich erwartet"
  (`journey.*`). Their i18n keys are gone from all three dictionaries.
- **Credential chips now use emoji** (🔬 🧬 🥗 🌿 🧘) inside the copy itself — an explicit
  founder decision (2026-08-04) replacing the mismatched line-drawn SVGs.
- Key sentences are emphasised with `<strong>` (ink on light sections, amber `--gold-bright`
  on the dark bands via the rule next to `.u-bink`).

## 🎴 CORPORATE ID — the printed work is now the reference (2026-08-09)

Two finished, high-fidelity handoffs were delivered by the founder and live in
`brand/print/`. **They outrank this file's older brand notes where they differ**,
because they are shipped artwork measured against a real print run:

- `brand/print/business-card-and-design-system/` — the **approved business card,
  design 5B "Reine Fläche"**, plus the bound `@auralis/design-system` browser
  bundle (22 components, tokens, self-hosted fonts). The card is described by its
  own handoff as *"the most refined expression of this brand that exists."*
- `brand/print/flyer-a5-a6/` — the **A5 + A6 double-sided flyer, EN/DE/ES,
  12 artboards**, with a CI print-check (`ci/check-print.mjs`).

### The eight decisions the card settled — not re-open questions
1. **Square corners everywhere.** `--r`/`--r-lg` are `0px`. Never add a
   `border-radius`; it is the defining structural decision of the system.
2. **The seal is the recurring mark**, and its signature move is the seal at
   **10 % opacity bleeding off the edge** as a watermark — for large quiet
   surfaces (hero, dark bands, CtaCard), never as loud decoration.
3. **Clay `#A8492A` is the accent, never a field.** Role lines, small marks,
   one primary clay button per view. Large surfaces are paper/cream or the dark
   brown band.
4. **Gold is structural, not shiny.** Hairlines, small caps, the seal — flat
   `--gold`/`--gold-bright`. Mirrored/gradient "chrome" gold was rejected as dated.
5. **Edges are hairlines; shadows are wide and soft.** Never tight, dark shadows.
6. **Restraint is the premium signal.** The card prints at ~4 % ink coverage —
   the paper does the work. Resist filling space.
7. **"Desiree Gruber" never breaks across lines**, at any breakpoint.
8. **Never hyphenate.** `hyphens: none` throughout; German compounds are handled
   by reducing type size, not splitting words. Check every headline at 360 px.
   *(This confirms the pending plan to remove `hyphens:auto` from `index.html` —
   the founder's "GE-SUNDHEITSCOACHING" complaint and the card agree.)*

### Print geometry (flyer) — load-bearing, do not "correct"
- A6 **95 × 148 mm**, A5 **138 × 210 mm** — deliberately **10 mm narrower than
  DIN** at unchanged height, to sit nearer the golden ratio. Not a mistake.
- Every page is a fixed page box with the artboard absolutely positioned at a
  fixed offset. **No page's geometry may depend on its content** — that was the
  root cause of a real registration bug where the back printed ~20 mm higher
  than the front. The CI check asserts it.

### Master assets — use these, they are the best copies that exist
`brand/masters/`: **`seal-1600.png`** (1600 px, clean alpha — now the source for
every generated avatar and cover), `seal-gold-1200.png` (gold-on-dark, the card's
own dark-surface treatment), `seal-brown-1200.png`, `seal-gold-watermark-1200.png`
(for decision 2), `qr-website-1480.png`.
⚠️ `handover/assets/emblem_seal_360.png` is a **different, busier seal** — never
use it for anything customer-facing.

- **⏱️ NEVER state a duration for the free call (2026-08-10).** Founder decision: the
  intro call is a **Kennenlerngespräch / introductory call / llamada de presentación** —
  free and no-obligation, with **no minutes named anywhere**, customer-facing. Removed
  from `/book` (kicker, all 3 langs + the static fallback), the booking-confirmation
  mail, the homepage CTA, the App Store screenshots and the social setup sheets.
  `slot_minutes: 25` in `portal/config/availability.json` STAYS — that is the calendar
  block, not a promise, and it is never shown to a client.

- **🇩🇪 STANDING RULE (restated 2026-08-10): every copy change starts in German.**
  The founder writes/dictates German; EN and ES are **derived from it in the same
  change**, never patched independently and never left behind. This applies to the
  website, `/book`, the staff console, the mails and the App Store metadata alike.
  A change that lands in German only is an unfinished change.

## 🛒 Gastmodus & Verkaufskanal in der App (2026-08-17)
- **Die App öffnet ohne Anmeldung.** Beim ersten Start landet man im Gastmodus:
  Programme, Terminbuchung und veröffentlichte Impulse sind frei zugänglich; Start und
  Profil zeigen ehrliche Gast-Zustände mit einer `LockedCard`, die benennt, was mit
  Zugang aufgeht. Apple verlangt genau das in **5.1.1(v)**. Wer sich auf diesem Gerät
  schon einmal angemeldet hat, kommt weiterhin direkt auf den Login (`an_had_session`).
  ⚠️ **Behobener Fehler:** der alte Gast-Zugang war eine `NavigationLink` in einer auf
  `.frame(height: 46)` geklemmten `NavigationStack` — der Tap schob das Ziel *in* dieses
  46-Punkt-Fenster, sichtbar blieb nur ein nackter Chevron. Die Impulse waren im
  ausgelieferten Build unerreichbar. Nie wieder eine NavigationStack in einem Blatt.
- **⚑ Bezahlen läuft über Stripe, NICHT über In-App-Kauf — und das ist Apples Vorgabe,
  keine Umgehung.** 3.1.3(e): Dienstleistungen, die *außerhalb* der App erbracht werden,
  **müssen** außerhalb des IAP bezahlt werden; 3.1.3(d) erlaubt es ausdrücklich für
  **Echtzeit-Eins-zu-eins-Dienste**. Ersparnis: 15–30 % Provision (bei Balance €135–270).
  ⚠️ **Dauerhafte Grenze:** 3.1.3(d) sagt „one-to-few and one-to-many real-time services
  **must** use in-app purchase" — **Verbindung/Corporate und jedes künftige Gruppen-
  Programm dürfen daher NIE einen Kauf-Button bekommen**, nur den Anfrage-Weg.
- **🔔 Benachrichtigung bei einem Verkauf (2026-08-20):** der Webhook schickte bisher nur
  bei **Fehlern** eine Mail — ein sauberer Kauf lief lautlos durch, obwohl eine Buchung fürs
  kostenlose Gespräch längst im Postfach landet. Jetzt geht **eine** Mail pro Verkauf an
  `team@` (Betreff „💶 Verkauf: Paket · Betrag · Name"), mit Betrag, Paket, AN-Nummer,
  E-Mail, Sprache — und **im selben Mail** dem Hinweis, ob die Zugangsdaten wirklich raus
  sind. Ist `email_mode` nicht `send`, heißt der Betreff „⚠️ Verkauf OHNE Zugang" (sie hat
  bezahlt und kommt nicht rein). Bewusst **eine** Mail statt zweier: die schlechte Nachricht
  darf nicht in einem zweiten „übrigens" untergehen. `mailer.notify_internal()` umgeht
  `email_mode` absichtlich, braucht aber **`AURALIS_SMTP_PASSWORD`** — ohne das Passwort
  wird nur die `.eml` abgelegt und **niemand erfährt etwas**. Pin: `tests/test_stripe_webhook.py`.
- **Der Kreis ist geschlossen:** `POST /api/stripe/webhook` macht aus einer bezahlten
  Checkout-Session eine Klientin mit Zugang — Paket setzen, `paid` setzen (Umsatz landet
  im Cockpit), Journey-Eintrag, Zugangsdaten-Mail. Signaturprüfung mit **stdlib-HMAC**,
  daher **kein `stripe`-Paket und kein `sk_`** — nur das Signing-Secret
  `AURALIS_STRIPE_WEBHOOK_SECRET` in `/etc/auralis/portal.env`.
  ⚠️ **Idempotenz ist tragend:** `_issue_credentials()` rotiert *immer* das Passwort, ein
  Stripe-Retry würde also das gerade gemailte Passwort ungültig machen. Behandelte
  Event-IDs liegen in `config/stripe_events.json`. Paket-Zuordnung: Metadata `package`
  → sonst Betrag → sonst **Eskalations-Mail** (Geld wird nie stillschweigend verworfen).
- **`shop_enabled` steht seit 2026-08-21 auf `true`** — die Kauf-Buttons sind in der
  iOS-App und im Klientinnen-Portal live (neun Payment Links, drei Sprachen, 199/399/899).
  ⚠️ **Der Schalter gehört ins REPO, nicht auf den Server.** `config/config.json` ist
  getrackt und der Server macht alle zwei Minuten `git reset --hard origin/main`; nur
  `auralis.db` und `clients.json` sind aus dem Repo-Baum heraussymlinkt. Ein
  `enable_stripe.sh --shop-on` auf Hetzner hält also **maximal zwei Minuten**, danach ist
  der Shop wieder aus und niemand merkt es — das Skript warnt jetzt genau davor. Umlegen =
  committen und pushen; der Updater zieht + `systemctl restart` (nötig, weil `cfg.config()`
  `lru_cache`d ist). **Offen bleibt nur das Fernabsatz-Recht** (Widerrufsrecht + Verzicht
  bei sofortigem Beginn, vorvertragliche Infos, Rechnung/IVA mit der Gestoría) — kein Code.
- **🚦 `python3 tools/golive_test.py` beweist den Livegang, statt ihn zu behaupten.**
  `console_check.py` und `preflight.py` sind read-only und wären auf einem Host grün, auf
  dem eine Kundin zahlt und nichts passiert — die drei Dinge, die Geld und Vertrauen tragen,
  löst kein GET aus. Dieses Werkzeug fährt sie **echt** und räumt hinterher auf:
  Kauf-Buttons + alle neun Stripe-Links, **eine wirklich versendete** Sofort-Mail (SMTP)
  und **ein wirklich angelegter** Gmail-Entwurf mit Kalender-Einladung (IMAP APPEND),
  ein signierter Kauf durch die ganze Kette (`stripe_rehearsal --auto`), dazu die
  öffentliche Cloudflare-Kante. Läuft auf Hetzner:
  `sudo -u auralis /opt/auralis/venv/bin/python /opt/auralis/app/portal/tools/golive_test.py`
  - Der Mail-Beweis ist die neue **staff-only Route `POST /api/selftest/mail`**: sie spielt
    im **laufenden Prozess** exakt das Mail-Paar einer Buchung nach (`send_now` = sofort,
    `deliver` = nach `email_mode`) an Desirees eigene Adresse, Betreff `[SELBSTTEST]`.
    Legt keine Kundin an, bucht keinen Slot. `/api/status` sagt nur, ob ein Passwort
    *vorhanden* ist — nicht, ob Gmail es akzeptiert; genau darin lag das Livegang-Risiko.
  - **403 von `book.stripe.com` ist eine Warnung, kein Fehler** (Bot-Schutz weist ein
    Skript ab). Nur 404/410 heißt „Link gelöscht". Ein Go-live-Check, der „NOT ready" über
    einen funktionierenden Shop druckt, ist die schlimmste Lüge, die er erzählen kann.
  - Pin: `tests/test_golive.py` (staff-gated, meldet ohne SMTP-Passwort **kein** ok,
    hinterlässt keine Kundin, Standard-Empfänger ist `from_email`).
- **App-Store-Listing korrigiert:** Review-Notes sagen jetzt, dass die App ohne Konto
  nutzbar ist, und nennen 3.1.3(d)/(e); `privacy_url` zeigt auf `impressum.html` statt
  auf die Startseite; die Screenshots zeigen **keinen erfundenen „Wellbeing score 82"**
  mehr (§2: Selbsteinschätzung ist nie ein Score, und Apple 2.3.3 verlangt echte
  Screens), keine Slot-Dauer mehr (2026-08-10) und überall 4 Wochen; `PrivacyInfo.xcprivacy`
  liegt bei (UserDefaults CA92.1, kein Tracking); **iPad abgewählt**
  (`TARGETED_DEVICE_FAMILY = 1`), weil es keine iPad-Screenshots gibt.
  Der Review-Account `barca`/`1234` ist **kein Platzhalter** — `portal/tools/create_review_client.py`
  legt genau diese Zugangsdaten an; er muss nur **einmal auf dem Live-Portal laufen**.
  Pins: `tests/test_ios_contract.py`, `tests/test_stripe_webhook.py`.

## 📊 Selbsteinschätzungs-Skalen: EINE Leserichtung (2026-08-17)
- **Jede Skala ist „höher = besser" — auch Stress.** Die Frage heißt überall
  **„Stressbalance" (1 = niedrig … 5 = sehr gut)**, so wie es die vom Founder
  freigegebene v2-Bericht-Grafik beschriftet und wie die iOS-App schon immer fragte.
- ⚠️ **Behobener Datenfehler:** bis 2026-08-17 hat `render._status()` Stress *invertiert*,
  während die App-Intake bereits nach Balance fragte → eine über die **App** eingereichte
  Intake zeigte eine *gute* Stressbalance als **rote Priorität** im Bericht. Jetzt eine
  einheitliche Leserichtung in `render.py`, `agent.py` (Polarität steht jetzt im Prompt),
  `portal.html` und der App (`ScaleRow`). Pin: `tests/test_render_contract.py`.
- ⚠️ **Für den Founder:** die **Web-Portal-Frage** hieß vorher „Stress (1 = niedrig · 5 = hoch)".
  Intakes, die **vor** dem 2026-08-17 **über das Web-Portal** eingereicht wurden, haben den
  Stress-Wert also in der *alten* Bedeutung gespeichert (5 = viel Stress). Falls es solche
  Datensätze gibt, muss der Stress-Wert dort einmal von Hand gespiegelt werden (6 − Wert)
  oder der Bericht neu entworfen werden. App-Intakes waren immer korrekt.

## 🔒 Schriften selbst gehostet — kein Google-CDN mehr (2026-08-17)
- **Alle kundenseitigen Flächen laden die Marken-Schriften vom eigenen Server**, nicht mehr
  von Googles CDN: `index.html`, `impressum.html`, `/portal`, `/book`, `/staff`.
  Grund: das CDN erhält die **IP jeder Besucherin schon beim Seitenaufruf**, vor jeder
  Einwilligung — für eine Gesundheitspraxis in der EU ein DSGVO-Problem, nicht bloß eine
  Abhängigkeit (LG München I, 3 O 17493/20). Es sind dieselben woff2-Dateien, die Bericht,
  Mails und Social schon einbetten (`design-system/assets/fonts/`).
- **Portal:** Route `/assets/fonts/<name>` (traversal-sicher, 1 Jahr immutable-Cache) liefert
  `fonts.css` (URLs flachgelegt) + die woff2. **CSP erlaubt jetzt gar keine Fremd-Origin mehr**
  (`font-src 'self'`, kein `googleapis`/`gstatic`).
- **Website:** `deploy-pages.yml` stellt `_site/fonts/` bereit **und bricht den Deploy ab**,
  wenn eine veröffentlichte Seite doch wieder ein CDN lädt. Die Datenschutzerklärung sagt
  jetzt korrekt, dass **keine** Drittserver kontaktiert werden (vorher stand dort „It loads
  Google Fonts"). `impressum.html` nutzt außerdem nicht mehr IBM Plex Mono — das Design-System
  hat diese Schrift bewusst abgelegt. Pin: `tests/test_hardening.py`.
- **Eckige Marker:** die letzten runden Formen auf Kundenflächen (Journey-Punkte in App +
  Portal) sind jetzt Quadrate mit **Pine für erledigt** — Radius 0 ist die Struktur der Marke,
  und der Bericht markiert Zustände mit dem gedrehten Quadrat, nie mit einem Kreis.

## 🤝 Engagement: motivierend, nie manipulativ (2026-08-17)
Die Fortschrittsanzeige in App (`ProgressBand`, Components.swift) und Portal (`.pband`)
ist bewusst **ehrlich by construction** — dieselbe Spezifikation auf beiden Flächen:
- Sie zeigt **den echten Server-Stand** (`journeyStep` / `journeyState()`), zählt **Erledigtes**
  (nie Fehlendes) und nennt **genau eine** nächste Handlung. Warten auf Desiree ist ein
  legitimer Zustand und erfindet keine Aufgabe.
- **Verboten und geprüft:** keine Countdowns, keine künstliche Knappheit, kein Streak-Verlust,
  keine Beschämung, keine vorausgewählten Einwilligungen (Consent ist Opt-in und blockierend).
- **Keine Behauptung ohne Beleg:** das App-Badge „AM HÄUFIGSTEN GEWÄHLT / MOST CHOSEN" wurde
  entfernt (vor den ersten Kundinnen war es unbelegt — dieselbe Regel wie §2.7 zu Testimonials)
  und ist jetzt **„UNSERE EMPFEHLUNG / OUR RECOMMENDATION / NUESTRA RECOMENDACIÓN"** —
  Desirees eigene Empfehlung, per Definition wahr. Pin: `tests/test_ios_contract.py`.
- Farbsemantik (aus dem Bericht übernommen): **Pine = stark · Sage = mittel · Clay = Priorität**
  auf hellen Flächen; auf dem dunklen Band macht **Amber** diese Arbeit (Pine verschwindet dort).

## ⚠️ NIEMALS Laufzeit-Dateien ins Git (2026-08-20)
`portal/config/availability.json` (Desirees echte Sprechzeiten, im Termine-Tab bearbeitet)
und `push_tokens.json` waren **getrackt**. Beide Deploy-Wege — der Mac-Launcher und der
Server-Updater — aktualisieren mit **`git reset --hard origin/main`**. Der erste Pull, der
diese Dateien mitbrachte, hätte ihren Kalender durch eine Entwickler-Kopie ersetzt; nur
weil git den Merge wegen einer untracked-Kollision verweigerte, ist es nicht passiert.
Jetzt in `.gitignore`. **Kein Seed nötig:** `booking.get_availability()` schreibt
`DEFAULT_AVAILABILITY`, wenn die Datei fehlt.
**Regel:** was der Portal-Prozess schreibt, gehört nie in den Repo-Baum. Geprüft und
korrekt ungetrackt: `clients.json`, `social.json`, `plan.json`, `stripe_events.json`,
`auralis.db`. Getrackt bleiben nur Dateien, die **ausschließlich** gelesen werden —
`config.json`, `company.json`, `report_engine.json` — denn genau darüber werden Preise,
Pakete und Schalter ausgeliefert.

## 💳 Stripe steht bereit — Korrektur einer falschen Annahme (2026-08-20)
⚠️ **Die Behauptung „die Stripe-Produkte tragen noch alte Namen und Preise" war FALSCH.**
Der Founder hat es mit Screenshots widerlegt: **alle neun Payment Links sind live**
(Clarity/Change/Balance × de/en/es auf `book.stripe.com`), mit den **richtigen Preisen**
199 / 399 / 899 €. Nicht aus Doku schließen, was in einem fremden Dashboard steht — fragen
oder prüfen.
- **`config.json` hinkte hinterher**, nicht Stripe: dort standen zwei *ältere* Links
  (`buy.stripe.com`) und bei Balance **gar keiner**. Jetzt trägt jedes Paket alle drei
  Sprachen als `buy_url: {de,en,es}`; `/api/app/offers` wählt nach `lang` (ein einfacher
  String funktioniert weiter). Die Website hatte die neun Links schon immer.
- ⚠️ **Adaptive Pricing hätte einen echten Verkauf verschluckt.** Stripe zeigt einer
  US-Käuferin **$484 für das 399-€-Programm**, und `amount_total` steht dann in **ihrer**
  Währung — der Abgleich gegen den EUR-Preis fand nichts und der Kauf wäre als „nicht
  zuordenbar" eskaliert. `_package_for_payment()` liest jetzt zuerst
  `currency_conversion.amount_total` (Beträge in **unserer** Währung) und verweigert die
  Zuordnung, wenn die Währung nicht `config.currency` (neu: `"eur"`) ist — lieber eine
  Eskalation als das falsche Programm freischalten. Pin: `tests/test_stripe_webhook.py`.
- **`metadata package=<key>` ist KEIN Blocker**: 199/399/899 sind verschieden, der Betrag
  genügt zur Zuordnung. Nur wenn zwei Pakete je denselben Preis hätten, wäre Metadata Pflicht
  — genau das prüft `preflight.py` jetzt und sagt es, statt Arbeit zu erfinden.
- **Wirklich offen sind nur zwei Umgebungs-Secrets** (beide auf Desirees Rechner, in
  `/etc/auralis/portal.env`): `AURALIS_STRIPE_WEBHOOK_SECRET` (ohne das antwortet der
  Webhook 503 — Geld käme an, das Portal erführe nichts) und `AURALIS_SMTP_PASSWORD`
  (ohne das bekommt die Käuferin keine Zugangsdaten). Dazu der Fernabsatz mit der Gestoría.

## 📨 Anfrage statt Buchung · Mail-Kopf · verlorene Anfragen (2026-08-20)
- **Der Termin wird ANGEFRAGT, nicht gebucht.** Desiree bestätigt ihn. Überall geändert
  (DE Master, EN/ES abgeleitet): `/book` Kicker, Bestätigungs-Button und Schlussbildschirm
  („**Dein Gespräch ist angefragt.**"), die Website-CTAs (`cta.book25`, `form.title`,
  `hero.cta`) und `home.action.book` in der App. Die Mail-Kette passt jetzt dazu: Vorlage 01
  „Deine Anfrage ist angekommen" geht **sofort** raus (`send_now`, ignoriert `email_mode`),
  Vorlage 02 „Termin bestätigt" mit Kalender-Einladung ist der Schritt, den **sie** auslöst.
- ⚠️ **`email_mode` stand auf `off`** — dadurch wurde die Bestätigung samt Einladung nur als
  `.eml` abgelegt und **nie versendet**. Jetzt `draft` (die dokumentierte Produktionsart):
  die Bestätigung liegt in Gmail-Entwürfen, die Eingangsbestätigung geht sofort. ⚠️ Ohne
  **`AURALIS_SMTP_PASSWORD`** in `/etc/auralis/portal.env` geht **gar nichts** raus.
- ⚠️ **Mail-Kopf war unsichtbar.** Das dunkle Band war **nur** ein `linear-gradient`; ein
  Mail-Client, der Gradienten verwirft, malte es nie — cremefarbene Schrift auf Weiß, sichtbar
  blieb nur das blasse Siegel („großes Logo ohne Text"). Alle **11 Vorlagen** haben jetzt
  `bgcolor="#3D2719"` **und** `background-color` vor dem Gradient. Nie wieder helle Schrift auf
  einem Verlauf ohne Vollton darunter.
- ⚠️ **Eine Anfrage konnte spurlos verschwinden:** bucht jemand, die schon über `call` hinaus
  ist, landet der Termin als `followup_bookings` an ihrem Datensatz — **Karte 01 „Offene
  Anfragen" zeigt sie nicht**. Neuer Alert **📨 „Neue Anfrage"** (warn) für jeden bestätigten
  künftigen Termin, dessen Person nicht ohnehin unter lead/call sichtbar ist.
  ⚠️ **Der Alert allein reichte nicht** (Founder-Meldung 2026-08-21: „im Cockpit sehe ich
  es, unter Customer Journey → Offene Anfragen nicht"). Karte 01 filterte auf
  `stage==='lead'` und stand auf **0**, während zwei Termine auf Bestätigung warteten.
  Jetzt liefert `/api/clients` pro Kundin **`next_call`** — den nächsten bestätigten,
  künftigen Nicht-Session-Termin, **über die E-Mail aufgelöst**, weil das die einzige
  Verbindung ist, die beide Fälle trägt (Folge-Buchung *und* Buchung vor Anlage des
  Datensatzes). Karte 01 zeigt sie unter einer Trennzeile „Auch angefragt — bereits
  Kundinnen", zählt sie mit, gibt der Zeile eine **eigene DOM-id (`-req`)** — dieselbe
  Kundin steht ein zweites Mal im Dokument — und nur „Öffnen" als Ghost-Button (die
  Phasen-Aktionen gehören auf ihre eigene Karte). ⚠️ **`booking_slot` ist NICHT der
  Termin**: es hält die *erste* Buchung für immer fest, eine zweite Anfrage zeigte darum
  das alte Datum. Der Ampel-Chip nimmt jetzt `next_call||booking_slot`.
  ⚠️ Beim Testen: die Buchungsroute entscheidet über `won_at`/`intake`, ob ein Datensatz
  als frischer Trichter-Eintrag gilt — eine von Hand gesetzte `stage` ohne Historie wird
  auf `lead` **zurückgestuft** und beweist nichts. Pin: `tests/test_open_requests.py`.
- **⚡ Buchung antwortet sofort (2026-08-22):** `/api/booking/book` wartete auf DREI
  Gmail-Runden (SMTP-Ack, IMAP-Entwurf, SMTP-Briefing) — die Kundin sah zehn Sekunden
  Spinner, was wie ein Fehler aussieht. Die **Buchung** muss vor der Antwort dauerhaft
  sein, die **Mails sind Nachläufer**: sie laufen jetzt in einem Worker-Thread. Tests
  fahren sie inline (`AURALIS_MAIL_SYNC`, von `tests/_sandbox.py` gesetzt), sonst würde
  eine `.eml`-Prüfung gegen den Thread rennen.
- ⚠️ **Das Datums-Ticket in der Eingangsbestätigung war IMMER kaputt:** die Route gab
  `slot_utc=b.get("slot_utc")` weiter, aber `booking.book()` liefert den Slot als
  **`start_utc`** — also immer leer, also immer `_tile_fallback`: ein brauner Block mit
  einem einzelnen Mittelpunkt, darunter das lange Datum, das Outlook dann violett
  verlinkt. Jetzt `b.get("start_utc") or slot`. Merksatz: **ein Fallback, der immer
  feuert, ist kein Fallback, sondern das Design.** Pin: `tests/test_booking_fast.py`.
- **📝 Gesprächsnotizen ab der ersten Anfrage (2026-08-22):** sie standen im Code hinter
  `if(rec.intake)` — also überall außer im Kennenlerngespräch, dem einzigen Moment, in
  dem sie geschrieben werden. Jetzt rendert `notesBlock()` sie **vor** dem Intake-Block,
  „☎ Gespräch geführt" ruft `callDone()` und öffnet die vier Felder als Dialog (leere
  Felder überschreiben nichts), das Detail-Panel hat „✎ Notizen schreiben" (`editNotes`).
  ⚠️ Dabei entschärft: `POST /api/client/<cid>/notes` setzte **immer** `stage="call"` —
  eine Notiz während der offenen Anfrage hätte die Kundin stumm aus „Offene Anfragen"
  geschoben. Der Phasenwechsel braucht jetzt `{"advance": true}`.
- **⛔ Anfrage stornieren (2026-08-22):** Knopf unten im Detail-Panel (rechts abgesetzt,
  Clay-Kontur; nicht bei Phase `lost`). `POST /api/client/<cid>/storno` macht drei Dinge
  in einem Zug: **alle künftigen Termine abgesagt** (Absage-Mail je Termin mit
  METHOD:CANCEL auf derselben UID — `ics_for(..., cancel=True)` für Kennenlern-Termine,
  `sessions_ics(cancel=True)` für Programm-Termine; Slots auf /book sofort wieder frei),
  **Portal-Zugang SOFORT entzogen** (Passwort geleert + Status `disabled` — den prüft
  `client_required` bei JEDEM Request, sonst lebte ein ausgestelltes Token bis zum Ablauf
  weiter; auch Magic-Links prüfen ihn), Phase → `lost`. **Der Datensatz bleibt** (kein
  Löschen — dafür ist die DSGVO-Route). Kopfzeile zeigt „Zugang entzogen"-Chip. Der Weg
  zurück ist bewusst der normale: 🔑 Zugangsdaten senden setzt `disabled` → `active` und
  vergibt ein frisches Passwort. Pin: `tests/test_storno.py` (Live-Token stirbt sofort,
  Slot wird frei, Absage-Mail im Papierpfad, Reaktivierung funktioniert).
- **🗂️ Anfrage-Detail-Panel (2026-08-21):** Klick auf eine Journey-Zeile öffnet rechts die
  strukturierte Detailansicht (Konzeptvorbild Paramur, Gestalt 100 % Auralis: eckig,
  Hairlines, Fraunces, EIN Clay-Hauptknopf). Abschnitte folgen den Journey-Karten und
  **füllen sich mit dem Fortschritt** — Kundin & Kontakt · 01 Anfrage & Vorab-Angaben
  (Termine + Red-Flag-Box + Skalen-Quadrate 1–2 Clay/3 Sage/4–5 Grün, Stress heißt
  **Stressbalance**) · 02 Notizen · 03 Programm & Zahlung (Vorkasse-Chip) · 04 Intake ·
  05 Bericht · Dokumente · Aktivität. **Leere Abschnitte sagen, WANN sie sich füllen**
  (dieselbe Regel wie im Trichter). Aktionen unten = dieselben wie auf der Karte;
  `advance/markPaid/sendCreds/askFeedback` refreshen das offene Panel, `openClient()`
  schließt es. Neuer Endpoint **`GET /api/client/<cid>/documents`**: nur IHRE Unterlagen,
  .eml **nach Subject beschriftet**; Buchungs-Mails liegen unter `bookings/` und werden
  **über die To-Adresse** zugeordnet (im Lead-Stadium ist das der ganze Papierpfad).
  Dateien laufen weiter über `/api/outbox/<path>`. ⚠️ Dabei gefunden: `send_now`/
  `notify_internal` benannten Audit-Kopien mit `int(time.time())` — zwei Buchungen in
  derselben Sekunde **überschrieben sich die Bestätigungs-Kopie**; jetzt `time_ns` wie
  in `deliver()`. Pin: `tests/test_drawer.py`.
- **✉️ E-Mail-Panel „E-Mails an die Kundin" (2026-08-21, Paramur-Konzept):** in der
  Kundinnen-Vollansicht (direkt unter dem Profil) und kompakt im Detail-Panel — jede
  kundenseitige Mail als Ein-Klick-Handlung: 🔑 Zugangsdaten · 🔔 Termin-Erinnerung
  (`remindClient` sucht den nächsten künftigen Termin über Erstbuchung + Folge-Buchungen
  + Programm-Termine) · 📅 Terminliste erneut (**neue Route
  `POST /api/client/<cid>/sessions/notify`** — baut dieselbe Mail wie `sessions_save`
  aus den BESTEHENDEN Terminen, stabile UIDs → Kalender aktualisiert statt doppelt) ·
  ⭐ Feedback · ✉️ **Persönliche Nachricht** (**neue Route
  `POST /api/client/<cid>/personal-mail`** + `mailer.build_personal_email`: Desirees
  Text wortwörtlich in der Newsletter-Hülle, Anrede/Fußzeile/Kicker in IHRER Sprache —
  `render_newsletter` hat dafür einen `kicker`-Parameter). Kopfzeile nennt Empfängerin,
  Sprache und **ehrlich den E-Mail-Modus** (`MAIL_MODE` von `/api/status` beim Boot;
  off = Clay-Warnung „nur .eml-Ablage"). Alles folgt `email_mode`, alles landet im
  Aktivitätsverlauf und im Dokumente-Abschnitt des Panels. Skalen in der Vollansicht
  jetzt via `scaleLine()` (deutsche Namen, kanonische Reihenfolge — nie wieder rohes
  „digestion 5/5"). Pin: `tests/test_client_mails.py`.
- 🚦 **`python3 tools/preflight.py` beantwortet jetzt „was fehlt noch zum Livegang?"** —
  Abschnitt `golive_mail` (SMTP-Passwort, `email_mode`) und `golive_shop` (Payment-Link,
  Webhook-Secret, Produktnamen/Preise, Fernabsatz). Ein Befehl statt einer Doku-Lektüre.
- **Skalen sind selbsterklärend** (Founder: „high stress is great?"): `/book` hatte als
  einzige Fläche noch **„Stresslevel"** unter einer Höher-ist-besser-Skala — eine 5 hieß für
  die Kundin „viel Stress" und wurde als „hervorragende Balance" gespeichert. Jetzt überall
  **Stressbalance**, und statt Schieberegler dieselben fünf Felder wie im Portal und in der
  App, mit Farbrichtung: **1–2 Clay · 3 Sage · 4–5 Pine**, ungewählte Felder mit einem Hauch
  davon, damit die Richtung schon vor der ersten Berührung sichtbar ist — dieselben Farben wie
  im Bericht. Dazu Endbeschriftungen („gerade schwierig" ↔ „richtig gut") und **keine
  Vorauswahl** mehr: ein Regler meldete stillschweigend eine 3, die niemand gewählt hatte.
  ⚠️ Über `/book` **vor dem 2026-08-20** erfasste Stress-Werte können die alte Bedeutung
  tragen — im Zweifel spiegeln (6 − Wert) oder neu erfragen. Pin: `tests/test_render_contract.py`.
- ⚠️ **Tests dürfen nie von der Produktions-Mailart abhängen:** `tests/_sandbox.py` pinnt
  `email_mode="off"`. Der Wechsel auf `draft` ließ sonst `test_e2e` an einem IMAP-Aufruf
  scheitern, den der Test nie gemeint hatte.

## 🖥️ HETZNER IST DER SERVER — der Mac wird stillgelegt (2026-08-21)
⚠️ **Die Migration war bereits Tage vorher erfolgreich** — die Frankfurt-Connectors beweisen
es. Der Mac kam danach zurück (launchd `RunAtLoad`+`KeepAlive` ohne `Disabled`, oder ein
manueller Start) und wurde zum **zweiten Connector**. Daraus folgt die wichtigste Regel:
**niemals `migrate_to_server.sh` erneut laufen lassen, um einen Split zu „reparieren"** —
es würde den Mac-Snapshot über die Server-Daten importieren. Richtig ist: den Mac
persistent stoppen (`launchctl bootout` **und** `disable`, plus `pkill -f 'auralis\.yml'`
— dieses Muster trifft `paramur-api` nicht).
**`python3 tools/console_check.py`** beantwortet danach „läuft die Betriebskonsole auf
Hetzner?": read-only, geht Tab für Tab durch (Cockpit, Journey, Finanzen, Termine, Social,
System, öffentliche Flächen, Stripe-Webhook) und nennt jede kaputte Stelle. `--wipe-clients`
ist der einzige schreibende Pfad, listet vorher auf und verlangt getipptes `ERASE`.

## 🧹 Sauberer Neustart: `tools/factory_reset.py` (2026-08-21)
⚠️ **Alle Kundinnen löschen reicht NICHT — und sieht trotzdem sauber aus.** Eine Buchung
liegt in ihrer **eigenen Tabelle**, nicht am Kundendatensatz: nach `--wipe-clients` blockten
die Termine weiter Zeiten auf `/book`, standen weiter im Termine-Tab und zählten weiter als
Anfragen. Dasselbe gilt für die `events`-Tabelle hinter Cockpit-Umsatz und Trichter.
- **`POST /api/admin/reset`** (staff, verlangt `{"confirm":"RESET"}`) macht beides in einem
  Zug: jede Kundin über **denselben** `_erase_client()` wie die DSGVO-Route (Datensatz +
  Dokumente + Login — die drei Orte dürfen nie auseinanderlaufen), **alle** Buchungen
  (Anfragen *und* Programm-Termine), die Events (`keep_events:true` behält sie),
  `output_docs/{AN-*,bookings,selftest,stripe}` sowie `stripe_events.json` und
  `push_tokens.json`. **Neue Autorität entsteht keine** — der Staff-Key darf ohnehin jede
  Kundin einzeln löschen; die Bestätigungsphrase verhindert nur den Unfall.
- **Es wird IMMER zuerst ein Snapshot geschrieben** (SQLite-Online-Backup + `clients.json`)
  neben die **aufgelöste** DB (`store._DB.resolve().parent` → `/var/lib/auralis`, **nicht**
  neben den Symlink im Repo-Baum, sonst räumt der nächste `git reset --hard` ihn weg).
  Schlägt der Snapshot fehl, wird **nicht** gelöscht. Der Snapshot enthält Gesundheitsdaten
  — nach dem Prüfen löschen.
- **Behalten wird ihre Arbeit:** Impulse-Artikel, Social-Pläne und gerenderte Posts,
  Verfügbarkeit, Stammdaten, Preise/Pakete, alle Schalter (`shop_enabled` bleibt an).
- CLI: `python3 tools/factory_reset.py` listet erst auf, verlangt getipptes `RESET` und
  **prüft danach über die Portal-API** (Kundinnen 0, Termine 0, Umsatz 0, keine
  Kundinnen-Alerts, `/book` bietet wieder Zeiten). Danach beginnt die Nummerierung wieder
  bei **AN-0001**. Kein Neustart nötig. Pin: `tests/test_reset.py`.
- ⚠️ Nicht verwechseln: **Cockpit-Umsatz kommt aus den Kundendatensätzen**, nicht aus den
  Events — `keep_events` zeigt sich also im **Trichter**, nicht am Umsatz.

Founder-Entscheidung, gilt ab sofort für alles: **`api.auralisnatura.com` gehört auf den
Hetzner-Server.** Der MacBook wird abgeschafft und darf in keiner Anleitung mehr als
Betriebsort auftauchen.
- ⚠️ **Aktueller Zustand ist gespalten:** `cloudflared tunnel list` zeigt für den
  `auralis`-Tunnel **8 Verbindungen** — vier aus `bcn01/mad05` (Mac) und vier aus
  `fra03/fra07/fra21` (Hetzner). Beide Maschinen bewerben denselben Hostnamen, Cloudflare
  verteilt die Anfragen zwischen ihnen. Daher dieselbe URL mal `400` (Mac, Secret da) und
  mal `503` (Server, Secret fehlt) — und **Buchungen landen mal in der einen, mal in der
  anderen Datenbank**. Der `paramur-api`-Tunnel auf demselben Mac ist unbeteiligt
  (`api.paramur.at` → :5055), niemals anfassen.
- **Der Weg dorthin ist `portal/deploy/migrate_to_server.sh`** — läuft auf dem Mac, kennt
  genau dieses Problem (Phase B1: launchd `bootout` **und** `disable`, sonst kommt der Mac
  beim nächsten Login als zweiter Connector zurück), stoppt den Mac erst, macht **dann**
  den Snapshot (andersherum verliert man jede Buchung dazwischen), importiert und prüft
  am Ende über die echte Cloudflare-Edge.
- ⚠️ **Neu ergänzt (2026-08-21):** die Migration trug den **Stripe-Signing-Secret nicht
  mit**. Ohne ihn antwortet der Server 503 und ein bezahlter Kauf erreicht das Portal nie.
  `AURALIS_STRIPE_WEBHOOK_SECRET` wird jetzt aus der Mac-`.env` gelesen, geprüft und in
  `/etc/auralis/portal.env` geschrieben; `install_server.sh` warnt laut, wenn er fehlt —
  dieselbe Logik wie beim SMTP-Passwort.

## 🧪 Sandbox UND Live gleichzeitig (2026-08-21)
Eine Stripe-**Sandbox ist ein eigenes Konto**: eigene Produkte, eigene Payment Links,
eigener Webhook-Endpunkt, **eigenes Signing-Secret**. Mit Platz für nur ein Secret hätte
ein Probekauf bedeutet, das Live-Secret zu tauschen — und wer es danach vergisst,
bekommt echtes Geld, von dem das Portal nie erfährt.
- **`stripe_webhook_secret` nimmt jetzt eine Liste** (kommagetrennt, in `.env`:
  `AURALIS_STRIPE_WEBHOOK_SECRET=whsec_live…,whsec_sandbox…`). Beide Endpunkte dürfen
  dauerhaft auf dieselbe URL zeigen. `_stripe_verified()` prüft jeden Kandidaten mit
  `compare_digest` und **ohne Early-Exit**, damit die Laufzeit nicht verrät, welches Secret
  gepasst hat; ein Event ohne passendes Secret bleibt 400.
- **Ein Sandbox-Kauf ist als solcher erkennbar:** `livemode:false` → der Name bekommt
  `[TEST] ` vorangestellt und die Benachrichtigung heißt „🧪 TEST-Verkauf (Sandbox)" mit
  Löschhinweis. Ein Probedatensatz darf nie wie eine zahlende Kundin aussehen.
- Voller Sandbox-Test = Produkt + Payment Link **in der Sandbox** neu anlegen (Live-Links
  existieren dort nicht), Endpunkt anlegen, dessen `whsec_` anhängen, mit
  `4242 4242 4242 4242` zahlen. Pin: `tests/test_stripe_webhook.py`.

## 🎭 Kauf-Generalprobe ohne Karte: `tools/stripe_rehearsal.py` (2026-08-20)
Ein echter Testkauf scheiterte an einer **Karten-Ablehnung** (Stripe/Bank, nicht unser
Code — das Portal war nie beteiligt). Damit die Kette trotzdem beweisbar ist:
**`python3 tools/stripe_rehearsal.py --auto`** ist der Ein-Befehl-Weg: kauft, zeigt die erzeugten Mails (Betreffzeilen über `/api/outbox`), zeigt Cockpit-Umsatz vorher/nachher, Journey-Stufe, Alerts und Trichter — und **löscht den Testdatensatz danach selbst** (`--keep` behält ihn). Ohne `--auto` läuft nur der Kauf.
`python3 tools/stripe_rehearsal.py [--package root|bloom|flourish] [--email …]` baut das
Event, das Stripe schicken würde, **signiert es mit dem echten Signing-Secret** aus
`.env`/`portal.env` und schickt es an den laufenden Portal-Prozess. Kein Mock, kein Bypass:
stimmt die Signatur nicht, lehnt das Portal ab wie bei jeder Fälschung.
- Danach prüft es über die **Portal-API** (`/api/client/<cid>` → `{client, record}`), nicht
  über `lib.store` im eigenen Prozess — ein Prüfer, der die falsche Datenbank liest, ist
  schlimmer als keiner. Geprüft: Datensatz, `login_id`, Paket, Preis aus config, `paid`,
  Stufe `invited`, Stripe-Eintrag im Aktivitätsverlauf.
- ⚠️ **Es entsteht ein ECHTER Kundendatensatz** in den Live-Daten — das ist der Punkt.
  `--cleanup AN-xxxx` löscht ihn über dieselbe GDPR-Route wie die Konsole (verifiziert:
  `db_removed`, `disk_removed`, `login_removed`, danach 404).
- Regel, die dabei wehtat: **niemals Erfolg melden, wenn Prüfungen fehlschlagen.** Die
  erste Fassung druckte „works end to end" über sechs fehlgeschlagenen Zeilen.

## ✉️ E-Mail-Vorlagen: Regeln fürs echte Postfach (2026-08-20)
Der Founder hat die Eingangsbestätigung in Outlook Mobile (Dark Mode) gezeigt: riesiges
verschwommenes Siegel oben, Datum-Kachel unlesbar. Drei Rendering-Regeln, jetzt in allen
11 `mail_v2`-Vorlagen umgesetzt — **nie wieder verletzen:**
- **Kein `position:absolute` in Mail.** Outlook & Co. werfen Positionierung weg, das
  300-px-Wasserzeichen-Siegel wurde INLINE als erstes Element gerendert — „das riesige
  Logo". Wasserzeichen ersatzlos entfernt; die Marke trägt der Mast.
- **Helle Schrift auf dunkler Fläche braucht `-webkit-text-fill-color`** (zusätzlich zu
  `color`). Outlooks Dark-Mode-Transformer schreibt `color` um (die cremefarbene
  Datums-Kachel wurde unsichtbar), lässt fill-color aber stehen — und Outlook Mobile
  rendert mit WebKit, wo fill-color gewinnt. Betroffen: #F6EFE3, #FBF6EB, #D6A84E u. ä.
- **`color-scheme: light` deklarieren** (`<meta name="color-scheme">`,
  `supported-color-schemes`, `:root{color-scheme:light}`) — Apple Mail/Gmail lassen das
  Design dann in Ruhe.
- **Flex nur mit Fallback:** Kachel-Zeilen `display:block`, Kapsel-Nummern als
  `inline-block` mit `line-height`, Caption-Tag mit `float:right` — identisch mit Flex,
  korrekt ohne. Getestet per „degraded client"-Screenshot (alle `display:flex` +
  `position:` entfernt) — dieser Simulations-Schritt gehört zu jeder Vorlagen-Änderung.
- Das Siegel im Mast kommt als `cid:`-Anhang — im Browser-Preview wirkt es „kaputt",
  im Mail-Client nicht. Kein Bug.
- „Untrusted sender"-Banner in Outlook = Empfänger-Heuristik (neuer Absender), kein
  Code-Problem; SPF/DKIM/DMARC prüfen mit `portal/deploy/check_email_dns.py`.

## 💶 VORKASSE: bezahlt wird VOR dem Programmstart (2026-08-20)
Founder-Korrektur — die Konsole war auf „liefern, dann abrechnen" gebaut, das Geschäft
läuft aber auf Vorkasse. Das war kein Wording-Problem, sondern zwei echte Fehler:
- **`markPaid()` sprang zusätzlich auf `done`.** Bei Vorkasse fällt die Zahlung direkt nach
  der Zusage — ein Klick hätte die Kundin also an Intake, Bericht und Programm vorbei ans
  Ende geschoben. Zahlung erfassen und Abschließen sind jetzt **getrennte** Handlungen;
  „✅ Abgeschlossen" liegt auf Karte 06.
- **Der 💶-Button gab es nur auf Stufe `sent`**, der `unpaid`-Alert erst 14 Tage nach
  Auslieferung. Ein Programm konnte also komplett unbezahlt durchlaufen, ohne dass irgendwo
  etwas aufleuchtete.
**Jetzt:** Customer Journey Karte 03 heißt **„Gewonnen · Zahlung & Zugang"** (Karte 06 nur
noch „Bericht geliefert"); der 💶-Button erscheint auf **jeder** Stufe ab `won`, solange Geld
offen ist, und ist dann der Hauptbutton (Zugangsdaten treten zurück — Zahlung zuerst, Zugang
danach). Zwei Alerts statt einem: **Fehler** „Programm läuft ohne Zahlung" (die Arbeit ist im
Gange und wird gerade verschenkt) und **Warnung** „Zahlung ausstehend" (zugesagt, ≥3 Tage
offen). Die Trichter-Stufe heißt **„Bezahlt — Programm startet"**. Beim Direktkauf über die
Website erledigt der Stripe-Webhook beide Schritte in einem Moment, dann sind `won` und
`paid` gleich groß. Kundenseitig ändert sich nichts: die Journey in App und Portal nennt
Zahlung ohnehin nie. Pin: `tests/test_payment_order.py`. Auch die Einarbeitung
(`handover/auralis-portal/build_onboarding.py` → OPERATOR-ONBOARDING.{html,pdf}) ist
korrigiert — dort standen zusätzlich noch die **alten Paketnamen und -preise**
(Root 198 / Bloom 398 / Flourishing 798); jetzt Klarheit 199 · Wandel 399 · Balance 899.
Das Dokument bettet seine Schriften jetzt ein statt sie vom Google-CDN zu laden (sonst wird
das PDF ohne Netz fontlos — derselbe Fehler wie früher beim Bericht).

## 📈 Verkaufstrichter im Cockpit + Website-Zähler (2026-08-19)
- **Cockpit → „Verkaufstrichter"** zeigt sieben Stufen von *Website geöffnet* bis *Bericht
  geliefert*, dazu **Woher die Besucherinnen kommen** und einen **Verlauf**. Umschaltbar
  30 / 90 / 365 Tage. Backend: `lib/analytics.py` (+ `GET /api/funnel`, staff-only, Tage auf
  7…365 geklemmt). Alles wird aus der bestehenden `events`-Tabelle abgeleitet — die trägt
  keine Personendaten und übersteht eine Art.-17-Löschung, die Zahlen bleiben also nach einer
  Löschung wahr.
- **Der Zähler ist cookielos und rein aggregiert** (`POST /api/pulse`, öffentlich, rate-limitiert,
  antwortet immer 204). Kein Cookie, keine Kennung, kein Client-State, **keine IP und kein
  User-Agent gespeichert**. Der Referrer wird **vor** dem Schreiben auf einen Kanal reduziert
  (instagram/google/direct/intern/andere) — ein Google-Suchbegriff, der hier eine
  Gesundheitsfrage sein kann, landet nie in der Datenbank. Genau diese Form braucht **kein
  Cookie-Banner** (nichts wird auf dem Gerät gelesen oder geschrieben, Art. 22.2 LSSI-CE);
  in `impressum.html` steht sie jetzt als „Anonymous reach measurement" (Art. 6(1)(f)).
  ⚠️ `impressum.html` ist **einsprachig Englisch** — DE/ES fehlen dort generell, nicht nur hier.
- **Der Preis, der sichtbar bleiben muss: wir zählen Seitenaufrufe, keine Personen.** Ohne
  Kennung sind zwei Besuche derselben Person zwei Aufrufe. Die Oberfläche sagt das (Hinweis
  unter Stufe 1) und darf **nie** „unique visitors" behaupten. Ein Kanal ist nur bis zum Klick
  verfolgbar, nie bis in eine Buchung.
- **Der Beacon in `index.html` sendet `text/plain`** — bewusst, weil das ein CORS-*simple*
  Request ist. Mit `application/json` verlangt der Browser einen Preflight, den die
  Pages-Origin nicht besteht, und **der Beacon verschwindet spurlos**. Serverseitig wird der
  Body deshalb von Hand geparst (`json.loads(request.get_data())`), Pin in `tests/test_analytics.py`.
  Ebenfalls behoben: der IntersectionObserver stand auf `threshold:.3` — der Programm-Bereich
  ist auf dem Handy 4217 px hoch, 30 % davon sind **nie** gleichzeitig sichtbar, das Ereignis
  wäre nie ausgelöst worden (jetzt `threshold:0` + ≥140 px sichtbar). Und Paket-Buttons tragen
  `data-pkg` **und** `data-soon-href`: die Paket-Prüfung muss zuerst kommen, sonst wird jede
  Kaufabsicht als „Kennenlerngespräch" verbucht.
- **Die Stufe „Auf einen Button geklickt" ist aufgeschlüsselt** (Founder-Wunsch 2026-08-19):
  Kennenlerngespräch · Klarheit · Wandel · Balance · Portal-Login, mit Anteil und Balken,
  eingerückt unter der Stufe. Der Beacon schickt dafür das Paket mit (`p:`), dedupliziert
  **pro Ereignis UND pro Paket** — zwei verschiedene Programme anzuklicken ist ein echtes
  Vergleichsverhalten und zählt zweimal. ⚠️ Die Website nutzt in `data-pkg` die englischen
  Namen (`clarity/change/balance`, weil sie die Stripe-Links steuern), die Firma überall die
  internen Keys — `analytics.PKG_ALIASES` übersetzt **einmal**, serverseitig; ein unbekannter
  Wert wird verworfen, damit ein öffentlicher Endpunkt nie ein viertes Paket erfindet. Die
  Namen kommen aus `config.json packages[]`, ein Rename wirkt also automatisch. Eine Stufe
  ohne Klicks behält ihre Zeile (das ist ein Befund), ein Gleichstand wird als „Gleichauf
  vorn" ausgewiesen statt einen Sieger zu behaupten, und die Fußnote sagt, dass das **Klicks,
  keine Käufe** sind. Die Summe der Zeilen **muss** der Stufe darüber entsprechen — getestet.
- **Der Engpass ist die Stufe mit den meisten verlorenen MENSCHEN, nicht die mit der
  hässlichsten Quote** — 90 % von 10 sind Rauschen neben 40 % von 400. Steht so im Code und im
  Text. Die Richtwerte (35/8/30/30/90/90 %) sind als **Richtwerte gekennzeichnet**, nicht als
  Wahrheit, und färben nur den Balken (Pine/Sage/Clay wie überall).
- **Die Handlungsempfehlungen sind bewusst gegen Manipulation gebaut** (gleiche Regel wie oben):
  keine Countdowns, keine künstliche Knappheit, keine erfundenen Stimmen — das steht als
  Fußnote **in** der Empfehlungskarte, damit es niemand später „vergisst". Empfohlen wird
  stattdessen: Klarheit im ersten Bildschirm, echte Belege früh, Reibung raus, ein
  Hauptbutton pro Fläche, kleine freiwillige Zusagen.
- **Nicht gemessen ≠ null:** solange die Website nichts gemeldet hat, sind die oberen drei
  Stufen **schraffiert** („noch nicht gemessen"), und eine Stufe mit echter 0 bekommt **gar
  keinen Balken** statt eines Strichs. Der Verlauf zeigt dann Text statt einer leeren Achse.
- ⚑ **Ein leerer Zustand muss trotzdem zeigen, WAS er zeigen wird** (gelernt 2026-08-19): die
  Aufschlüsselung rendert ihre fünf Zeilen auch ohne Daten, sonst sieht „noch nichts gezählt"
  genauso aus wie „nicht gebaut" — der Founder hatte zu Recht gemeldet, die Granularität
  funktioniere nicht, obwohl der Code stimmte. Dazu sagt die Karte jetzt, **wann die Website
  zuletzt gemeldet hat** (`funnel.web_last_seen`, ohne Fenster-Grenze) und nennt eine
  30-Sekunden-Probe: Website öffnen, Konsole neu laden. Damit lässt sich „niemand war da" von
  „der Zähler kommt nicht durch" unterscheiden, ohne ein Log zu lesen.
- ⚠️ **Zweimal derselbe CSS-Fehler:** eine Regel `.insight b` bzw. `.nodata b` macht **jede**
  Hervorhebung mitten im Satz zu einem Display-Font-Block und zerreißt den Text. Überschriften
  in diesen Karten sind deshalb explizit ausgezeichnet (`.insight>b`, `.nodata b.hd`) — nie
  wieder über die Element-Position.
- Kleine, aber tragende Details: die Summe der Tageswerte im Verlauf **muss** mit den
  Trichter-Zahlen übereinstimmen (die Achse startet am ersten Tag, den der Server liefert, nicht
  an „heute minus N") — sonst widersprechen sich zwei Zahlen auf demselben Bildschirm.
  Getestet in `tests/test_analytics.py`.

## Website features added at launch
- **Languages EN / DE / ES only** (Italian removed). Toggle in top nav (visible on
  mobile too) + inside mobile menu + footer.
- **Browser-language auto-detect:** first visit picks DE/ES from `navigator.language`,
  else EN; manual choice persisted in `localStorage('an_lang')`. No IP/server geo.
- **i18n engine** uses `data-i18n` keys with English source + DE/ES overrides and
  graceful fallback. Only stable UI chrome (nav, CTAs, tagline) translated so far;
  body copy (~2,080 words) still to be translated once final copy is locked.

## Open / next tasks (launch-specific)
1. Rework Document 02 + §8 financials for the new (lower) prices.
2. Add high-resolution photography to reduce text density (founder providing images).
3. Full DE/ES translation of body copy.
4. (Still from §12) wire booking/lead form to a real backend; real testimonials; gestor/legal/insurance.

-----

# CLAUDE.md — Auralis Natura · Complete Project Handover

> **Read this first.** This file is the full context for the Auralis Natura founder
> package. If you are Claude (in Claude Code or any session) picking this project up,
> everything you need to understand, rebuild, extend, or continue the work is here.
> The real files referenced below live alongside this document in `deliverables/`,
> `source/`, and `assets/`.

---

## 0. ONE-MINUTE ORIENTATION

**Auralis Natura — Holistic Health** is a premium, online holistic-health & nutrition
**coaching** business being launched by **Dr. Desiree Gruber** in Barcelona. This project
delivered a complete, best-in-class founder package: a premium website, three branded
strategy documents, and a reusable client-report template — all sharing one bespoke
brand design system ("Modern Materia Medica") and one set of hard compliance guardrails.

The work was produced as a **founder-consulting engagement**. The tone throughout is
world-class, premium, modern, warm, and scientifically rigorous. The single most
important constraint is **regulatory scope** (see §2): Desiree is a *coach/educator*,
**not** a licensed nutritionist or physician.

**What exists right now (all complete & QA-verified):**
1. `deliverables/index.html` — the public website
2. `deliverables/01-Strategy-and-Market-Research.html`
3. `deliverables/02-Business-Plan.html`
4. `deliverables/03-Operations-and-AI-Workflow.html`
5. `deliverables/Client-Report-TEMPLATE.html` — fill-in-the-browser → print-to-PDF tool

---

## 1. THE CLIENT & THE BUSINESS

### Dr. Desiree Gruber — founder profile
- **PhD in Bioorganic Chemistry.**
- **10+ years in pharmaceutical quality**, most recently working **in global quality
  at Novartis** (Barcelona). ⚠️ CORRECTION (2026): she works **in the global quality
  area, NOT in a leadership/"Lead" role** — do not call her a "Lead"/"Leitung" anywhere.
- Recently **certified in holistic health / nutrition / women's health (Frauenheilkunde)**
  from the **Akademie der Naturheilkunde** (Switzerland) — exam score **97.22%**.
- Also a **certified Yoga & Meditation instructor.**
- Based in **Barcelona, Spain.**
- **Languages: German (native), English, Spanish, Italian.**
- Building this business **alongside her Novartis job** — so the whole model is designed
  for *limited, protected, flexible* founder hours.
  ⚠️ CORRECTION (2026): **Desiree is NOT a mother** — do **not** reference motherhood /
  "becoming a mother" / having a baby anywhere in copy. (The earlier handover text and the
  website About section that implied this have been corrected.)

### Contact / brand facts
- Email: **office@auralisnatura.com**
- Phone: **+34 614 489 656**
- Business name: **Auralis Natura** · descriptor **"Holistic Health"** (preferred — see §3)
- Concept: merge PhD-level scientific rigour with holistic health education
  ("academically-founded"). Convert via a **free introductory call** (Kennenlerngespräch),
then sell
  packages and a membership.

### The business in one line
A premium online practice that converts visitors through a free call, serves them with a
beautifully-produced **personal report** plus a clear ladder of packages, and grows
through **referrals and credibility** — all run on a few protected hours a week.

---

## 2. ⚠️ CRITICAL GUARDRAILS — NON-NEGOTIABLE, APPLY TO EVERYTHING

These govern every word produced for this business. Never relax them, even if asked to
make something punchier.

1. **Scope of practice (Spain — Ley 44/2003, LOPS).** "Dietista-nutricionista" is a
   *legally protected, regulated health profession*. Desiree is **not** a registered
   dietitian or physician. Position Auralis as **holistic health & wellness coaching and
   education** — lifestyle, habits, general nutrition education, accountability,
   wellbeing. **Never** diagnosis, treatment of disease, or prescriptive medical
   nutrition therapy.
2. **"Dr." = PhD in bioorganic chemistry, disclosed transparently.** Never imply a
   medical doctor. This honesty is itself a brand asset.
3. **Complement, never replace, medical care. Refer out.** Build red-flag screening and
   "see your doctor / call 112 in an emergency" guidance into everything. When in doubt,
   refer out.
4. **GDPR & special-category health data.** Intake data is the highest tier of GDPR
   protection: explicit consent, lawful basis, data minimisation, secure (ideally
   EU-hosted, encrypted) storage, defined retention. The AI workflow must handle personal
   data lawfully.
5. **AI is assistive, human-led.** Any AI-drafted client output (e.g. reports) **must** be
   reviewed, edited, and approved by Desiree before it reaches a client. Educational,
   never diagnostic.
6. **Disclaimers everywhere.** Every deliverable carries a scope/medical/GDPR footer (see
   the footer in any built doc for the canonical wording).
7. **Testimonials are real, never fabricated.** The website testimonials are *clearly
   labelled placeholders* to be replaced with genuine client reviews. Never invent reviews
   as if real.
8. **Market/financial figures are directional estimates**, framed for validation — not
   forecasts or fundraising-grade numbers.

---

## 3. BRAND DESIGN SYSTEM — "MODERN MATERIA MEDICA"

Contemporary scientific-herbal: PhD rigour × botanical/holistic warmth. **Deep forest
green is the dominant primary** — a deliberate choice to avoid the "cream + terracotta +
serif" AI-wellness cliché (terracotta/clay is an *accent* only).

### Colour tokens (exact — from `source/doc_base.css` `:root`)
```
--ink:#2A2822;        --ink-soft:#5A5544;     --ink-faint:#857E6C;
--forest:#33422E;     --forest-2:#46583B;     --forest-deep:#27331F;   /* PRIMARY */
--sage:#879675;       --sage-soft:#B7C1A4;    --sage-tint:#D7DECA;
--clay:#AE6745;       --clay-soft:#C58A6B;    --gold:#BB9A52;          /* ACCENTS */
--paper:#F4EEE1;      --paper-2:#ECE4D3;      --paper-3:#E4DAC6;
--cream:#FBF7EE;      --white:#FFFFFF;
--line:rgba(42,40,34,.14);  --line-strong:rgba(42,40,34,.26);  --line-light:rgba(42,40,34,.08);
--shadow:0 1px 2px rgba(42,40,34,.04),0 8px 28px rgba(42,40,34,.06);
--shadow-lg:0 2px 6px rgba(42,40,34,.06),0 24px 60px rgba(42,40,34,.10);
```

### Typography
- **Display / headings:** `Fraunces` (serif) — the editorial, premium voice.
- **Body / UI:** `Hanken Grotesk` (sans).
- **Labels / specimen tags:** `IBM Plex Mono` — used for the "Fig. 0X — Title" section
  labels and small uppercase kickers.
- All loaded via Google Fonts `<link>` in the document `<head>` (see `build_doc.py`).

### Signature elements
- **The botanical seal emblem** — a circular line-drawn botanical crest. This is THE
  recurring brand mark. File: **`assets/seal_320_opt.png`** (transparent PNG8, 320px,
  ~52 KB). It is **base64-injected** into every built file via the `{{SEAL}}` token, so
  outputs are self-contained. It appears as: the cover seal, a faint watermark behind dark
  callouts (`.callout-wm`) and covers (`.cover-wm`), and the small nav/footer dot.
- **"Fig. 0X — Title" specimen labels** in mono on every section head (`.sec-head .fig`).
- **The 3-dot "spark" ornament** — three small dots in clay / sage / gold (`.spark`).
- Generous white space, editorial layout, premium restraint.

### Voice & taglines
Warm, intelligent, calm, precise — "a brilliant friend who happens to be a scientist."
Signature taglines in use: *"Reclaim your energy — with science you can actually trust."*
and *"Where rigorous science meets the wisdom of nature."* Core emotional job the brand
sells: helping a client **"feel like myself again."**

### Naming guidance
Use **"Holistic Health"** as the primary descriptor (broader, more premium, and safely
clear of the protected "nutrition/dietitian" terms). Keep "nutrition" as a *service* word
in copy, never as the headline profession.

---

## 4. WHAT'S IN THIS FOLDER

```
auralis-natura-handover/
├── CLAUDE.md                         ← you are here (full context)
├── deliverables/                     ← the finished, self-contained outputs (open in a browser)
│   ├── index.html                    ← the website
│   ├── 01-Strategy-and-Market-Research.html
│   ├── 02-Business-Plan.html
│   ├── 03-Operations-and-AI-Workflow.html
│   └── Client-Report-TEMPLATE.html   ← edit in browser → print to PDF
├── source/                           ← editable source + the build system
│   ├── doc_base.css                  ← the shared document design system (uses {{SEAL}})
│   ├── build_doc.py                  ← wraps a body fragment → finished HTML (PORTABLE version)
│   ├── shotdoc.py                    ← full-page screenshot QA (needs playwright)
│   ├── shotsec.py                    ← element-level screenshot QA by #id
│   ├── doc1_body.html                ← body fragment for Document 01
│   ├── doc2_body.html                ← body fragment for Document 02
│   ├── doc3_body.html                ← body fragment for Document 03
│   ├── report_body.html              ← body fragment for the client report template
│   ├── auralis_site_raw.html         ← website source (pre-seal-injection)
│   └── main.js                       ← website JS (nav, language toggle, reveal observer)
├── assets/
│   ├── seal_320_opt.png              ← THE brand emblem (base64-injected as {{SEAL}})
│   ├── logo_lockup_600.jpg           ← the full logo lockup (reference)
│   └── emblem_seal_360.png           ← larger seal render (reference)
└── qa-screenshots/                   ← a few sample rendered-output screenshots
```

**Key distinction:** files in `deliverables/` are *generated*. The truth lives in
`source/` (the `*_body.html` fragments + `doc_base.css`). To change a document, edit its
body fragment and **rebuild** (see §6). The website (`index.html`) is built from
`auralis_site_raw.html` + `main.js` with the seal injected.

---

## 5. THE DELIVERABLES — WHAT EACH ONE IS

### Website — `index.html`
Single-file premium site. Sections: fixed nav + mobile menu + **EN/ES/DE language
toggle** + "Book a free call" CTA; **Hero** ("Reclaim your energy — with science you can
actually trust."); credentials ribbon; Problem/JTBD; **Method** (4 movements:
Listen / Analyse / Align / Sustain); **Services/pricing** (see §8); Women's Seasons;
Differentiators (incl. "Alongside your doctor"); About Desiree; the 5-step Journey;
**Testimonials (labelled placeholders — replace with real reviews)**; FAQ (incl.
not-medical, PhD-not-physician, GDPR); booking lead-form (JS demo, **no backend yet**);
full medical/scope/GDPR **footer**. Robustness: content is visible even if JS fails
(progressive enhancement); scroll reveals via IntersectionObserver with fallback.

### Document 01 — Strategy & Market Research
5 C's (Company, Customers, Competitors, Collaborators, Climate); Jobs-to-be-Done;
Problem→Solution; Positioning & Messaging (4 pillars, voice, taglines); **3 personas**
(see §7); the brand identity system; a competitive **positioning map** whose top-right
"high rigour + high warmth" quadrant is empty = Auralis's home; regulatory guardrail box.

### Document 02 — Business Plan
Vision/Mission/Model; the **Offer Ladder & Pricing**; **Unit Economics**; **Financial
Projections** (3 scenarios + P&L + 3-year view); Go-to-Market & Marketing; Operations
summary; Roadmap (staged part-time launch); **Legal, Risk & Compliance** (Ley 44/2003,
GDPR, autónomo/IRPF/IVA, insurance, contracts, risk register); Founder & Time Model;
KPIs. All numbers in §8.

### Document 03 — Operations & AI Workflow
The **five-step client journey**; **Step 1 Intake** (form design); **Step 2 the AI Report
Engine** (the core IP — draft → human review → one-click premium render, with an
illustrative system prompt); the **Safety & Scope Layer** (red-flag triage + refer-out);
Step 3 Deliver & Discuss; Step 4 Invoice; Step 5 the Review loop; the **Technology Stack**;
SOPs/templates & operating rhythm; "putting it together."

### Client Report Template — `Client-Report-TEMPLATE.html`
The practical tool implementing Step 2/Step 4. Open in Chrome → **click the dashed boxes**
to type/paste approved text → **⌘P/Ctrl-P → Save as PDF** (turn ON "Background graphics").
Editable zones use `contenteditable="true"` with a `.edit` highlight; an on-screen
`.howto` banner and `.edithint` labels **auto-hide in print**. Six-section architecture
matching §9. Pre-filled with a worked example (fictional client "Elena") to show tone.

---

## 6. THE BUILD SYSTEM — HOW TO CREATE / EDIT BRANDED DOCUMENTS

All documents share one CSS (`source/doc_base.css`) and are assembled by
`source/build_doc.py`, which: reads the CSS, base64-encodes the seal, wraps a **body
fragment** with the `<head>` (fonts, meta, title) + `<style>…</style>` + `<body>` + foot,
replaces every `{{SEAL}}` token, and writes the finished file.

**The `source/build_doc.py` in this bundle is the PORTABLE version** — it resolves paths
relative to itself (CSS from `source/`, seal from `../assets/`, output to
`../deliverables/`), so it runs anywhere. Usage:

```bash
cd auralis-natura-handover
python3 source/build_doc.py source/doc2_body.html "02-Business-Plan.html" \
    "Business Plan" "Short description for <meta>."
# → writes deliverables/02-Business-Plan.html, reports byte size + leftover-token count (want 0)
```

**To edit a document:** edit the relevant `source/*_body.html`, then rebuild with the same
command. Re-run for all docs if you change `doc_base.css` (it's shared). The exact build
commands used originally:

```bash
python3 source/build_doc.py source/doc1_body.html "01-Strategy-and-Market-Research.html" "Strategy &amp; Market Research" "…"
python3 source/build_doc.py source/doc2_body.html "02-Business-Plan.html"                 "Business Plan" "…"
python3 source/build_doc.py source/doc3_body.html "03-Operations-and-AI-Workflow.html"    "Operations &amp; AI Workflow" "…"
python3 source/build_doc.py source/report_body.html "Client-Report-TEMPLATE.html"         "Client Report Template" "…"
```

**Body-fragment conventions** (so new sections match): wrap each section in
`<section class="block" id="…"><div class="sec-head"><span class="fig">Fig. 0X — …</span>
<h2>…</h2><p class="sub">…</p></div> … </section>`. Useful classes in `doc_base.css`:
`.cover .cover-seal .cover-meta .doc-kicker`, `.sec-head .fig .sub`, `.lead .pull .em`,
`.grid .g2 .g3 .g4`, `.card .ncard (.n)`, `.kpi .kpi-row (.stat .stat-k)`,
`.callout (.callout-wm) .note (.nh)`, `.guard (.gh)`, `.tw table (.tnum)`, `.persona`,
`.tag-row .tag`, `.spark`, `.label`, `.mono`, `.divider`, `.disclaimer`, `.doc-foot .fb`.
Dark callouts: bold text is forced to cream via `.callout strong` (a fix that's already in
the CSS — keep it). Every document ends with the canonical `.disclaimer` footer.

**QA rendering** (optional, needs Playwright):
```bash
pip install playwright Pillow --break-system-packages && playwright install chromium
python3 source/shotdoc.py /abs/path/to/deliverables/02-Business-Plan.html out.png      # full page
python3 source/shotsec.py /abs/path/to/file.html prefix "gtm,legal,kpis"               # by #id
```
Full-page PNGs can exceed the 8000px view limit — crop/resize with Pillow before viewing.

**Self-containment:** outputs embed the seal as base64 and link Google Fonts, so they need
internet only for fonts and otherwise render offline. No build step is needed to *view* a
deliverable — just open it in a browser.

---

## 7. PERSONAS (from Document 01)

- **Elena, 34 — postpartum.** Exhausted, energy/mood/digestion shifted since her baby;
  wants a calm, realistic path. (Beachhead.)
- **Marcus, 45 — depleted high-performer.** Successful, running on empty, wants to feel
  sharp and well again without fads. (Expansion.)
- **Sophie, 48 — perimenopause.** Navigating hormonal change, wants science-literate,
  warm guidance. (Beachhead — women's life-stage transition.)

**Beachhead = ambitious, health-literate women in life-stage transition** (postpartum,
perimenopause). Expansion = depleted high-performers, prevention-minded, expats.

---

## 8. THE FINANCIAL MODEL (computed, internally consistent)

### Pricing (the offer ladder)
| Rung | Offer | Price |
|---|---|---|
| Free | Free first call (conversion engine) | €0 — duration NOT advertised |
| 1 | **Root Session** (deep-dive + report) | **€220** |
| 2 | **The Reset** (6-week guided programme) | **€690** |
| 3 | **The Transformation** (12-week, *featured "most chosen"*) | **€1,290** |
| Sub | **Companion** (ongoing membership) | **€120 / month** |

Instalments offered on programmes (e.g. The Transformation as 3×€450).

### Unit economics — effective €/hour
| Offer | Price | ~Founder hours | €/hour |
|---|---|---|---|
| Root Session | €220 | 3.0 | **€73** |
| The Reset | €690 | 4.5 | **€153** |
| The Transformation | €1,290 | 10.0 | **€129** |
| Companion | €120/mo | 1.25 | **€96** |

### Year-1 scenarios
- **Conservative:** ~**€13,540**
- **Base:** ~**€26,260** — quarterly build Q1 €2,260 / Q2 €5,040 / Q3 €7,960 / Q4 €11,000;
  units sold across the year: Root ×25, Reset ×14, Transformation ×6, Companion-months ×28.
- **Ambitious:** ~**€38,680**

### Base-case Year-1 P&L
Revenue **€26,260** − costs **€6,000** = operating profit **€20,260** (≈ **77% margin**,
before IRPF and self-employed social-security).
Cost lines: Tooling €900 · AI stack €480 · Website/domain €300 · Insurance €420 ·
Accounting/gestoría €900 · Brand (one-time) €600 · Marketing €1,800 · CPD/misc €600.

### Three-year directional view
Y1 ~€26k (Base) → Y2 ~€60–65k → Y3 ~€100–110k+. Growth past Y1 should come from **higher
prices, more memberships, and a one-to-many offer** (group cohort / course) — not just
more 1:1 hours.

---

## 9. OPERATIONS WORKFLOW & GO-LIVE RUNBOOK

### The five-step client journey
1. **Intake** — client completes a secure structured form (history, goals, red-flag
   screen, consent).
2. **AI draft & review** — AI drafts an evidence-informed report; **Desiree reviews,
   edits & approves every word**; one click renders the premium PDF.
3. **Deliver & discuss** — report emailed personally, then walked through in a session.
4. **Invoice** — clean branded invoice, online payment.
5. **Review** — well-timed nudge → five-star review on the site → fuels the next free
   call (the flywheel).

### Recommended tool stack (lean, GDPR-conscious)
Scheduling · Intake forms (**Tally** recommended — EU, free; or **Typeform**, premium) ·
**AI drafting (Claude)** · Report rendering (the HTML→PDF template in this bundle) ·
Email · Payments/invoicing · Reviews · Secure EU-hosted storage · Bookkeeping (gestor-
compatible). Prefer EU data residency + DPA; don't let AI train on/retain client data;
minimise what's sent. Start lean; automate only real bottlenecks.

### The ready-to-use AI report system prompt
Paste into a Claude **Project** ("Auralis Report Engine") as custom instructions; then per
client start a new chat with *"Here is the client's intake — please draft the report:"* +
their answers.

```
You help Dr. Desiree Gruber draft a personalised holistic-health education report for a
client of Auralis Natura. She is a PhD chemist and certified holistic-health coach — NOT a
doctor.

RULES:
• Educational, never diagnostic. Never name a disease as a conclusion, never prescribe or
  adjust medication or medical nutrition therapy, never contradict a doctor.
• Safety first. If the intake shows ANY red flag (unexplained weight loss, chest pain/
  breathlessness, severe pain, fainting, self-harm thoughts, disordered-eating signs,
  pregnancy complications, or a serious condition), OPEN the report by clearly
  recommending they see a physician, and keep all suggestions gentle and general.
• Evidence & honesty. Ground claims in credible science; where evidence is weak or mixed,
  say so plainly. Prefer "may support" to "will fix."
• Voice: warm, intelligent, calm, precise — a brilliant friend who happens to be a
  scientist. Use the client's own words where possible.
• Structure in six parts: (1) Your starting point, (2) What we're seeing, (3) The science,
  simply, (4) Your plan — 2–3 prioritised realistic actions, (5) When to see a doctor,
  (6) Your next steps. Prioritise; never overwhelm.
• You write a FIRST DRAFT for Desiree to review and edit. She approves everything before
  it reaches a client.
```

### The intake question set (paste into the form tool)
Sections A–D: (A) name, age, location/language, main goal in own words, why now, what
they've tried; (B) energy/sleep/stress/digestion scales + notes, typical eating, movement,
life stage, supplements; (C) **safety** — conditions, medications, allergies,
pregnancy/breastfeeding, a **red-flag tick-list** (unexplained weight loss, chest pain/
breathlessness, severe/persistent pain, fainting, self-harm thoughts, unhealthy
relationship with food, "none"), anything the doctor is investigating; (D) **required
consent** — understands it's coaching/education not medical care, and GDPR consent to
process health data. (Full wording is in Document 03 and was provided to the founder.)

### Print-to-PDF (the report)
Open `Client-Report-TEMPLATE.html` in Chrome → click dashed boxes, type/paste approved
text → ⌘P/Ctrl-P → **Save as PDF** → **turn ON "Background graphics"** (critical, or
colours don't print) → Default margins → Save. Editing UI auto-hides in the PDF. Reopen
the fresh template for the next client.

---

## 10. MARKET RESEARCH (key findings, so no re-research needed)

- Global wellness-coaching market ≈ **$20–24B (2025–26), ~7–10% CAGR** → ~$36–40B by
  2030–35. **Nutrition is the largest segment (~34.8%).** Digital nutrition coaching
  ≈ $2.4B (2024), ~12.8% CAGR. Drivers: preventive health, personalisation, AI tools,
  women's health, corporate wellness.
- **Closest competitor/analog:** *Flavia Deuchler* (multilingual functional-medicine
  coach, free initial consult). Others: Functional Self EU, Nutritional Coaching
  (Barcelona). Apps: Noom, HealthifyMe.
- **Design trend 2026:** neo-minimalism, earthy palettes, editorial serif, natural
  textures — *but* "cream + serif + terracotta" is an over-used AI cliché → hence
  **deep forest green primary** here.
- **Pricing benchmarks:** hourly $50–250; 3-mo packages ~$1,200–1,500; monthly $200–500;
  subscriptions $50–200/mo. (Auralis pricing sits comfortably in premium range.)
- **Regulatory (Spain):** see §2 — Ley 44/2003 protects "dietista-nutricionista";
  position as coach/educator.

*(Figures are directional estimates synthesised from public 2024–2026 sources; validate
before external/fundraising use. If asked for fresh numbers, web-search to update.)*

---

## 11. HOW TO CONTINUE IN CLAUDE CODE

### Environment (only needed for rebuilding/QA, not for viewing)
- **Python 3** (for `build_doc.py`).
- For QA screenshots: `pip install playwright Pillow --break-system-packages &&
  playwright install chromium`.
- ImageMagick is **not** needed (the seal is already processed) unless re-processing the
  raw logo.
- Internet is needed only for Google Fonts at view time.

### Common tasks (example asks for a fresh Claude)
- *"Edit Document 02's pricing section"* → edit `source/doc2_body.html`, rebuild.
- *"Make a new branded one-pager / lead magnet / welcome guide"* → write a new
  `source/<name>_body.html` using the section conventions in §6, build with `build_doc.py`.
- *"Build the intake-confirmation email and invoice templates"* (an open item — see §12)
  → same design system; small branded HTML documents.
- *"Update the website copy / add a section"* → edit `source/auralis_site_raw.html`
  (+ `main.js` if behaviour changes), then re-inject the seal. (The site's seal is also
  base64; the original injection replaced a `{{SEAL}}`-style placeholder — match the
  existing pattern, or re-run an injection step that base64-embeds `assets/seal_320_opt.png`.)
- **Always** keep the §2 guardrails and the §3 brand system intact.

### Style of work expected
Premium, thorough, "best-in-class." Build real files (not just chat text). QA-render
before declaring done. Respond in **English**. Keep the warm-but-rigorous voice.

---

## 12. OPEN ITEMS / NEXT STEPS (not yet done)

1. **Replace placeholder testimonials** on the website with genuine client reviews as they
   come in. (Never fabricate.)
2. **Wire up the booking & lead form to a real backend** (e.g. a scheduling tool + email),
   plus connect intake → storage. The site form is currently a front-end demo.
3. **Confirm with a Spanish *gestor*:** autónomo registration, the cuota, IRPF, and —
   importantly — **IVA (VAT) treatment** of the services (coaching is *not* automatically
   exempt). Set up a compliant **invoice format**.
4. **Have a lawyer review** the client contract / terms (scope, payment, cancellation,
   confidentiality, informed-consent/disclaimer) once.
5. **Secure professional liability / civil-liability insurance.**
6. **(Offered, optional)** Build matching **intake-confirmation email** and **invoice**
   templates in the same brand system so all stations share one look.
7. Stand up the Claude **Project** + intake form + report-template flow and run the first
   few founding clients (Phase 1 of the roadmap) to gather proof and reviews.

---

*End of handover. Everything needed to understand, rebuild, and extend Auralis Natura is in
this file and the accompanying `deliverables/`, `source/`, and `assets/` folders. Keep the
guardrails (§2) and the brand system (§3) sacred; everything else is yours to build on.*
