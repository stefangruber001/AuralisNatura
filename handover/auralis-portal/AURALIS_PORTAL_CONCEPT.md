# Auralis Natura — Portal, Betriebskonsole & Cloud Report Agent
## Complete Concept & Knowledge Base (v1)

> **What this is.** The full blueprint to build, for Auralis Natura, the same kind of
> system Paramur runs — a public website + a **Client Portal** (login → premium health
> intake) + a **Betriebskonsole** (Desiree's back-office cockpit) + a **Cloud Report
> Agent** that drafts the premium holistic-health report, which Desiree reviews and then
> one-click turns into a beautiful PDF that is **auto-placed as a Gmail draft** for her to
> send, with a booking link for the review call.
>
> It reuses ~90 % of the Paramur engine (Flask app, portal auth, ops-console shell,
> Gmail-draft email, Mac/Windows launchers, backup/failover, Cloudflare tunnel + Pages)
> and swaps the top two layers (config/branding + the health-specific flow).
>
> **The one thing that is bigger here than at Paramur:** this system processes
> **special-category health data**. Security, EU data-residency, consent and the
> human-approval gate are first-class, non-negotiable design constraints — see §7 and
> `guides/SECURITY_GDPR.md`.

---

## 0 · TL;DR (the 60-second version)

**Auralis Natura** is Dr. rer. nat. Desiree Gruber's premium, online **holistic-health &
nutrition coaching** practice (Barcelona; worldwide). Coaching & education — **never**
medical diagnosis or treatment. The website already exists (auralisnatura.com). This
project adds the operating system behind it:

```
Client logs into the Client-Portal → fills the premium INTAKE form (history, symptoms,
   goals, lifestyle, consent, red-flag screen) → data lands, encrypted, in the backbone →
   Desiree reviews it in the Betriebskonsole → 1:1 discovery call → she adds her call NOTES →
   she clicks "Draft report" → the CLOUD AGENT (Claude) writes the premium report content →
   it appears in the console for her to REVIEW & EDIT (the approval gate) → she clicks
   "Generate report" → a super-premium branded PDF is rendered, saved to the client's
   folder, and placed as a GMAIL DRAFT (report attached + a booking link for the review
   call) in team@auralisnatura.com → Desiree sends it → client books the review call.
```

Only **two manual touchpoints** (the discovery call, the review call) and **one approval
gate** (Desiree edits every report). Everything else runs itself.

Three human-facing surfaces + one background worker:
1. **Homepage** (public marketing site, `auralisnatura.com`) — already built; we add a
   **"Client Login"** entry.
2. **Client-Portal** (`/portal`) — client login → premium intake form → later, view/
   download their report + book the review call.
3. **Betriebskonsole** (`/staff`) — Desiree's cockpit: review intake, add call notes,
   run the agent, review/approve, generate + draft-email the report.
4. **Cloud Report Agent** — a background engine (Claude API) that turns *intake + notes*
   into the report draft and talks to the Betriebskonsole.

Everything is **config-driven** (a few JSON files) so the Paramur engine re-skins to
Auralis by swapping data + branding.

---

## 1 · The business (context for every screen and word)

- **Company / owner:** Auralis Natura · **Dr. rer. nat. Desiree Gruber** (founder & sole
  practitioner). Academic doctorate in chemistry — **not** a physician, **not** a
  registered "dietista-nutricionista."
- **What it is:** holistic-health & nutrition **coaching and education** — lifestyle,
  habits, general nutrition education, women's health, energy, wellbeing.
- **Contact / brand:** team@auralisnatura.com · +34 614 489 656 · auralisnatura.com ·
  Instagram @auralis_natura · Barcelona, Spain · online worldwide · languages DE / EN / ES.
- **Offers (one-time):** The Root Session €198 · The Bloom €398 (6 weeks) · The
  Flourishing €798 (12 weeks) · The Grove (corporate workshops, bespoke). Free 25-min
  discovery call is the front door.
- **The core IP being automated:** the **personal holistic-health report** — the premium,
  benchmarked, science-led, visually beautiful document that is the heart of the paid
  offers. Today it's a fill-in template; this project makes it an **agent-drafted,
  human-approved, one-click** artefact.

### The compliance guardrails — hard constraints on the whole system
1. **Coaching & education, never medical care.** No diagnosis, no treatment of disease, no
   prescriptive medical nutrition therapy. Every report and page carries the scope footer.
2. **"Dr." = Dr. rer. nat.** (chemistry), stated transparently. Never imply a physician.
3. **Refer out.** A **red-flag screen** in the intake and a "see your doctor / call 112"
   block in every report. The agent is instructed to open with a doctor referral if any
   red flag is present.
4. **Special-category health data (GDPR Art. 9).** Explicit consent, lawful basis, data
   minimisation, EU residency, encryption at rest, defined retention, right to erasure,
   DPAs with every processor. See `guides/SECURITY_GDPR.md`.
5. **Human-approval gate.** The agent only ever produces a **draft**; nothing reaches a
   client until Desiree has reviewed, edited and clicked generate. This is wired into the
   process, not optional.
6. **Real testimonials only.**

---

## 2 · Brand identity (the "corporate identity" to apply everywhere)

Reuse the current website brand ("warm-earth / cozy-campfire" — the same tokens the live
site and the report/invoice templates use):

| Token | Hex | Use |
|---|---|---|
| `--forest` | `#3D2719` | primary (dark cinnamon-brown), dark sections |
| `--forest-deep` | `#27170E` | darkest gradient stop |
| `--clay` | `#A8492A` | accent / CTAs / spark |
| `--gold` | `#AD7A32` | amber accent, emphasis on dark |
| `--sage` | `#927B4A` | warm olive |
| `--sage-soft` | `#DAC79E` | warm sand |
| `--ink` | `#2A211A` | body text |
| `--paper` `--cream` | `#F5EEE0` `#FBF6EB` | backgrounds |

- **Type:** headings **Fraunces** (serif); body/UI **Hanken Grotesk** (sans).
- **Mark:** the botanical **seal emblem** (`assets/seal.png`) — cover, watermark, nav dot.
- **Geometry:** sharp corners (editorial), hairline borders, restrained shadows, optional
  frosted-glass panels — matching the current site.
- **Voice:** warm, intelligent, calm, precise — "a brilliant friend who happens to be a
  scientist." DE (native), plus EN/ES.

Everything the portal, console, report and emails render must read as one premium brand.

---

## 3 · The four surfaces (what we build)

### 3.1 Homepage (public — already live)
`auralisnatura.com` (GitHub Pages today; **recommend migrating to Cloudflare Pages** — see
§8 and `guides/CLOUDFLARE_TUNNEL_AND_DOMAIN.md`). Change needed: add a discreet
**"Client Login"** link (nav + footer) that opens the Client-Portal (`api.auralisnatura.com/portal`
or an in-page overlay, mirroring Paramur's portal button).

### 3.2 Client-Portal (`/portal`)
The client's private space.
- **Login:** Client-ID + password (PBKDF2-hashed), or a magic-link email. Forgot-password
  opens a pre-filled mail to team@. (Same auth engine as Paramur's Partner-Portal.)
- **The premium intake form** (the "predefined premium form"): a beautifully designed,
  multi-step, branded questionnaire — see §5 for the field set. Autosaves; resumable.
  Ends with the **two required consent** checkboxes and the **red-flag screen**.
- **After the report exists:** the client can view/download their report PDF and **book the
  review call** (Cal.com link) from the portal.
- Clients never see anyone else's data; the portal only ever shows their own record.

### 3.3 Betriebskonsole (`/staff`) — Desiree's cockpit
Protected by an API key **and** Cloudflare Access (email-code) — belt and braces for health
data. Tabs (adapted from Paramur's console):
- **Cockpit** — KPIs (calls booked, intakes submitted, reports in draft/sent, review calls).
- **Client Journey** — vertical stage cards per client: *Intake → Discovery call → Draft →
  Review → Report sent → Review call*. Drive each transition; open the client detail.
- **Client detail** (the workhorse) — the intake rendered cleanly + an **auto meeting-prep
  summary** (agent-generated) + a **Call notes** editor (Desiree types during/after the
  1:1) + a **"Draft report"** button → shows the agent's draft, section by section, **fully
  editable** + a **"Generate report"** button (renders PDF + creates the Gmail draft).
- **Templates** — edit the report structure / the agent's system prompt / the email copy.
- **Stammdaten** (⚙) — company.json editor. **Outbox** (⚙) — every generated email as .eml.
- **Clients** — client CRUD, reset password, GDPR tools (export / erase a client's data).

### 3.4 The Cloud Report Agent (the new centrepiece)
A background engine that **communicates with the Betriebskonsole**. When Desiree clicks
"Draft report," the console sends the agent the **structured intake + her call notes**
(and only what's needed — minimised). The agent (Claude, no-training, with the Auralis
Report-Engine system prompt) returns a **structured, six-part, benchmarked, science-led
draft**. The console shows it for review. On "Generate report," the approved content is
poured into the premium **report renderer** (HTML → PDF) and the mail is drafted. The agent
never emails a client and never bypasses the gate. Full design in `guides/REPORT_AGENT.md`.

---

## 4 · The customer journey / business process (the core pipeline)

```
1. DISCOVER   Client books the free 25-min call on the website (Cal.com).           [auto]
2. LOGIN      Client gets portal access (auto-provisioned on booking/payment, or by
              invite) → logs into /portal.                                          [auto]
3. INTAKE     Client fills the premium intake form (history, symptoms, goals,
              lifestyle, consent, red-flag). Saved encrypted to the backbone.       [auto]
4. PREP       The agent writes a short MEETING-PREP summary from the intake so
              Desiree walks in prepared.                                            [auto]
5. CALL 1     Discovery / issues call. Desiree adds her NOTES in the console.       [manual]
6. DRAFT      Desiree clicks "Draft report" → the Cloud Agent writes the premium
              report content from intake + notes.                                   [auto]
7. ★ REVIEW   Desiree reviews & edits every section in the console.        [APPROVAL GATE]
8. GENERATE   One click → premium report PDF rendered → saved to the client's
              folder → placed as a GMAIL DRAFT (report + review-call booking link)
              in team@auralisnatura.com.                                            [auto]
9. SEND       Desiree sends the draft from Gmail.                                   [manual click]
10. REVIEW    Client opens the report, books the review call from the link, they
     CALL     discuss it.                                                           [manual call]
11. (opt.)    Invoice / payment (Stripe) + a well-timed review request.            [auto]
```

Numbering & folders (Paramur-style): every client gets `output_docs/<CLIENT-ID>/<stage>/`
(intake, prep, notes, report, sent). One record per client; documents versioned.

---

## 5 · The premium intake form (field set)

Multi-step, branded, autosaving. Sections A–E. (This is the health analogue of Paramur's
Anfrage.) Keep the **red-flag** and **consent** exactly as safety/GDPR require.

- **A · About you** — name, age, location, preferred language (DE/EN/ES), pronouns
  (optional), main goal in your own words, why now, what you've already tried.
- **B · Your body & everyday life** — energy / sleep / stress / digestion (1–5 scales +
  notes), a typical day of eating, movement, hydration, caffeine/alcohol, life stage
  (cycle, fertility, pregnancy, postpartum, perimenopause), supplements.
- **C · Symptoms & history** — current symptoms (structured multi-select + free text),
  timeline / onset, family history (optional), recent bloodwork or reports the client
  wants to share (secure upload), goals ranked.
- **D · Safety — the red-flag screen** — conditions, medications, allergies, pregnant/
  breastfeeding; **tick-list** (unexplained weight loss · chest pain/breathlessness ·
  severe/persistent pain · fainting · self-harm thoughts · disordered-eating signs ·
  "none"); anything a doctor is currently investigating.
- **E · Consent (required)** — (1) understands this is coaching/education, not medical
  care; (2) GDPR consent to process special-category health data, stored securely in the
  EU, used only for the coaching, never shared without consent, erasable on request
  (links the Privacy Policy).

Design note: this is where "super-premium" starts — the form itself should feel calm,
beautiful and trustworthy (progress bar, one idea per screen, warm microcopy), because it
is the first thing a paying client touches.

---

## 6 · The premium report (what the agent + renderer produce)

Benchmarked against the best holistic/functional-medicine reports, but **compliant**
(education, never diagnosis). Structure (extends the six-part report already designed):

1. **Cover** — client name, date, Auralis seal, one-line framing.
2. **Your starting point** — their story reflected back, in their words.
3. **What we're seeing** — the themes/patterns (educational, not a diagnosis), shown
   **visually**: theme cards, a simple "how it connects" map, energy/sleep/stress mini-charts
   built from the intake scales.
4. **The science, simply** — the "why," with credible, plainly-stated evidence and
   honest uncertainty; tasteful scientific illustration/iconography.
5. **Your plan** — 2–3 prioritised, realistic, sequenced actions (never overwhelming),
   as a visual roadmap.
6. **When to see a doctor** — the safety/refer-out block (always present).
7. **Your next steps** — a warm, unpushy invitation + the review-call booking link.
8. **Footer** — the scope/medical/GDPR disclaimer.

Rendered as a branded **HTML → PDF** (the same route the current report template uses:
Chromium print, background graphics on), so it's visually rich, on-brand, and print-perfect.
"Super-premium, very visual, lots of science" is achieved in the renderer's design system
(charts from the client's own numbers, editorial layout, the seal, Fraunces/Hanken), while
the **content** is the agent's draft that Desiree approved.

---

## 7 · Architecture & tech stack (adapting Paramur)

- **Backend:** Python **Flask** single app, binds `127.0.0.1:5056` (Paramur uses 5055 —
  different port so both can run on one machine). API-key auth on `/api/*` staff routes;
  portal routes use a session cookie or signed bearer token (HMAC, short TTL). CORS
  restricted to configured origins.
- **Data store — CHANGED for health data.** Paramur uses a plain Excel workbook. Auralis
  handles special-category data, so the backbone is an **encrypted store**: SQLite with
  **field-level encryption** for the health fields (or an encrypted disk volume / SQLCipher).
  Never committed; local only; hourly encrypted backup. (Details + choice in
  `guides/SECURITY_GDPR.md`.)
- **The Cloud Report Agent:** the report engine calls the **Claude API** (Anthropic,
  no-training, EU/appropriate region, DPA) with the Auralis Report-Engine system prompt +
  the minimised intake/notes; returns structured JSON sections; the console renders them for
  review. On approve → HTML→PDF render → **Gmail draft** via IMAP `APPEND` (Paramur's
  "draft" email mode — the finished mail with the PDF lands in team@auralisnatura.com Drafts).
- **Config / master data (JSON single sources of truth):** `company.json`, `config.json`,
  `clients.template.json`, `report_engine.json` — see §9 and `config_templates/`.
- **Frontend:** hand-written HTML/CSS/vanilla-JS (no framework), matching the site's brand.
  `portal.html` (client portal + intake), `staff.html` (Betriebskonsole).
- **Rendering / docs:** headless Chromium for HTML→PDF (report, any letters). No heavy PDF
  library needed for the report — the HTML design system is the premium layer.
- **Email:** branded HTML mail with the seal; **draft mode** (IMAP APPEND to Gmail Drafts)
  recommended so Desiree always sends personally. send/off modes as fallback.
- **Hosting & exposure:**
  - **Homepage:** GitHub Pages today → **migrate to Cloudflare Pages** (dev/prod previews).
  - **Portal + Console + API + Agent:** local Flask on the **Mac now → Windows later**,
    exposed via a **Cloudflare named tunnel** at `api.auralisnatura.com`. `/staff` gated by
    **Cloudflare Access** (email code) on top of the API key.
- **Launchers (self-updating):** Mac `.command` / Windows `.ps1` that poll `origin/main`
  every ~2 min and auto-pull+restart — so a `git push` reaches the server with no button.
  Hourly encrypted backup to an EU cloud folder; Mac↔Windows active/passive failover on the
  same tunnel.
- **Code:** GitHub (`stefangruber001/auralisnatura`), same account as the site.

### The three layers (why this is fast to build from Paramur)
```
LAYER 3  Auralis-specific: the intake form, the report renderer + agent, the client
         journey stages.                                                       ← BUILD
LAYER 2  Config + branding: company.json, config.json, clients.json,
         report_engine.json, the seal + palette.                               ← SWAP
LAYER 1  The engine: Flask, portal/console auth, launchers, backup/failover,
         Gmail-draft mailer, Cloudflare tunnel + Pages, self-update.           ← REUSE
```

---

## 8 · Domain, Cloudflare & the Squarespace recommendation

- **Recommendation: move the domain off Squarespace to Cloudflare Registrar.** Squarespace
  domains are comparatively expensive and renew at a premium; **Cloudflare Registrar sells
  at wholesale cost (no markup)** and gives you the tunnel, Access, Pages and DNS in one
  place — which is exactly the stack this system uses. Net: cheaper renewal + one control
  plane + the security tunnel for free.
- **Plan:** (1) unlock the domain at Squarespace, get the EPP/auth code; (2) add the site to
  Cloudflare (Pages) and transfer the domain to Cloudflare Registrar; (3) DNS: `auralisnatura.com`
  → Cloudflare Pages (site), `api.auralisnatura.com` → the named tunnel (portal/console/API),
  keep MX/mail records intact. Full steps in `guides/CLOUDFLARE_TUNNEL_AND_DOMAIN.md`.
- **The tunnel = the safety layer.** The Flask app never opens a port to the internet; the
  Cloudflare tunnel is the only ingress, TLS-terminated at Cloudflare, and `/staff` sits
  behind Cloudflare Access. Health data never rides an exposed port.

---

## 9 · Data model — the JSON single sources of truth

- **`company.json`** — legal + brand master (name, owner "Dr. rer. nat. Desiree Gruber",
  address, email, phone `+34 614 489 656`, web, VAT/NIF placeholders, brand colours, logo
  paths). Appears on the report footer + emails. *(Template provided.)*
- **`config.json`** — runtime (host, port 5056, api_key→env, secret→env, allowed_origins,
  email_mode `draft`, smtp/imap for Gmail, backup, **data_encryption_key→env**). No real
  secrets committed. *(Template provided.)*
- **`clients.template.json`** — client portal accounts (id, name, email, language,
  password PBKDF2 hash, created, consent timestamps, status). Analogue of `partners.json`.
  **Health answers are NOT stored here** — they live in the encrypted backbone. *(Template.)*
- **`report_engine.json`** — the agent config: model id, the system-prompt reference,
  temperature, max tokens, the six-section schema, safety rules, language handling.
  *(Template provided.)*

---

## 10 · Security & GDPR posture (summary — full detail in the guide)

Because we handle Art. 9 health data: EU data residency end-to-end (Cloudflare EU, Gmail
Workspace region, Claude via an appropriate region + DPA + no-training); **encryption at
rest** for the backbone; TLS-only via the tunnel; **Cloudflare Access** on `/staff`;
consent captured with timestamp + version; **data minimisation** (send the agent only what
it needs; never third-party analytics on health pages); a **retention & erasure** policy
(client can request export/erase; console has one-click GDPR export + erase); DPAs on file
with every processor (Cloudflare, Google, Anthropic). This is a genuine obligation, not a
nice-to-have — treat `guides/SECURITY_GDPR.md` as binding.

---

## 11 · Build plan (phases) — see `guides/BUILD_PLAN.md` for the detail

- **Phase 0 — Concept & scaffold (this pack).** Concept, configs, guides, repo layout.
- **Phase 1 — Foundations.** Fork/adapt the Paramur engine → Auralis branding + configs;
  stand up Flask locally on the Mac; Cloudflare tunnel + Access; domain move.
- **Phase 2 — Client-Portal + intake.** Login + the premium multi-step intake form +
  encrypted backbone + consent/red-flag.
- **Phase 3 — Betriebskonsole.** Client journey, client detail, call-notes, meeting-prep.
- **Phase 4 — The Cloud Report Agent + renderer.** Draft → review → generate → premium PDF.
- **Phase 5 — Email draft + booking link + review loop.** Gmail draft, Cal.com link.
- **Phase 6 — Automation glue + hardening.** Auto-provision on booking/payment, backups,
  failover, GDPR tools, go-live.

Each phase is shippable and testable on its own; the system is useful from Phase 3 (manual
agent) and fully automated by Phase 6.

---

## 12 · What we reuse vs build vs must-do differently (Paramur → Auralis map)

| Paramur | Auralis | Action |
|---|---|---|
| Flask engine, portal/console auth, launchers, backup, tunnel, Pages | same | **reuse** |
| `partners.json` (trade logins) | `clients.json` (client logins) | swap/rename |
| Anfrage (walls, m², motifs) | **Health intake** (history, symptoms, consent) | **rewrite** |
| Pricing / Angebot / order-to-cash / Verlegeanweisung / wall-design tool | *removed* | delete |
| PDF/Word doc generators (invoice etc.) | **Report renderer** (HTML→PDF) + optional Stripe invoice | rebuild |
| Excel backbone | **Encrypted store** (health data) | change |
| Gmail draft mailer | same (report + booking link) | reuse |
| — (no AI at Paramur) | **Cloud Report Agent** (Claude) | **new** |
| Betriebskonsole (orders) | Betriebskonsole (**clients + agent review**) | re-skin + extend |

---

*Companion documents in this pack:* `guides/ARCHITECTURE.md`, `guides/SECURITY_GDPR.md`,
`guides/REPORT_AGENT.md`, `guides/DEPLOYMENT_MAC.md`,
`guides/CLOUDFLARE_TUNNEL_AND_DOMAIN.md`, `guides/BUILD_PLAN.md`, and `FOUNDER_TODO.md`
(the concise list of what only you can do). Config templates in `config_templates/`.
