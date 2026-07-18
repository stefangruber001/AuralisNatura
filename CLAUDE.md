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
- **💶 Pricing (overrides §8 ladder).** Three one-time individual products, ordered cheapest→most expensive: **The Root Session €198 · The Bloom €398 (6-week) · The Flourishing €798 (12-week)** — single payments, no instalments. Stripe (Sandbox) products created with these exact names/prices. **Offer 04 (added 2026-06-19): "The Grove" — a corporate/teams offer** (science-led nutrition & wellbeing workshops: lunch-&-learn talks, half-day workshops, multi-session series). Priced bespoke ("Tailored · request a quote"); CTA is a `mailto:` enquiry (NOT Stripe/booking — it stays active during the pre-launch gate). Lives as a distinct dark espresso band at the end of the Services section (`#corporate`, `.corp`). ⚠️ **OPEN TASK:** Document 02 financials + §8 below still show OLD prices/offers and must be reworked to match. Treat §8 numbers as stale.
- **🧘 Yoga & Meditation (added 2026-06-19).** Desiree is a **certified Yoga & Meditation teacher** (200-hr Ashtanga, Elemental Yoga & the Mind Arts, 2021, under maiden name Pressnitz). Integrated on the homepage as: a credentials-ribbon chip (`creds.5`), a 4th certificate slide (`cert-yoga.jpg`, `cert.c4`), a bio line (`about.p3`), programme features (Bloom `svc.reset.f5`, Flourishing `svc.trans.f6`) and the method footer. Education **and** service.
- **🖼️ Photos (2026-06-19).** Real photos of Desiree: solo desk portrait = `images/desiree-portrait.jpg` (HERO); consultation-with-client = `images/desiree-consult.jpg` (ABOUT). `about-evidence.jpg` is now orphaned/unused.
- **🎠 Certificates carousel** now infinite-loops (wraps last→first) with gentle 6s autoplay that stops once the user navigates; respects reduced-motion.
- **✍️ Wording decision (2026-07-01):** "12+ Jahre / 12+ years / 12+ años" is the approved
  MASTER wording for the pharma-experience credential (supersedes the Word master's
  "Fast 12 Jahre"). Applied in creds.2 and diff.1.p in all three languages.
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
  ("academically-founded"). Convert via a **free 25-minute first session**, then sell
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
| Free | Free first call (conversion engine) | 25 min, €0 |
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
