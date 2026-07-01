# Auralis Natura — Technical Architecture Guide

> **Scope.** How the Auralis Natura portal system is built: its surfaces, layers,
> Flask route map, encrypted data model, request/data flows, repo layout, and ports.
> This is the engineering companion to `AURALIS_PORTAL_CONCEPT.md` — read that first
> for the *why*; this document is the *how*. Terminology and decisions here match the
> concept exactly.
>
> **Compliance is architecture, not decoration.** Auralis Natura is Dr. rer. nat.
> Desiree Gruber's holistic-health **coaching & education** practice — **never** medical
> diagnosis or treatment; "Dr." is an academic doctorate in chemistry, not a physician.
> The system processes **special-category health data (GDPR Art. 9)**, so encryption,
> EU residency, consent and the **human-approval gate** are load-bearing design
> constraints, not add-ons. The Cloud Report Agent only ever produces a *draft*; nothing
> reaches a client until Desiree has reviewed, edited and clicked generate.

Contact / brand facts baked into `company.json`: **team@auralisnatura.com** ·
**+34 614 489 656** · **auralisnatura.com** · Barcelona + online · DE / EN / ES.

---

## 1 · The four surfaces

The system presents three human-facing surfaces plus one background worker:

| # | Surface | Path | Who | Purpose |
|---|---|---|---|---|
| 1 | **Homepage** | `auralisnatura.com` | public | marketing site (already live). We add a discreet **"Client Login"** entry (nav + footer) → opens the Client-Portal. |
| 2 | **Client-Portal** | `/portal` | client | login → premium multi-step **intake form**; later view/download the report PDF + book the review call. |
| 3 | **Betriebskonsole** | `/staff` | Desiree | back-office cockpit: review intake, add call notes, run the agent, review/approve, generate + draft-email the report, GDPR tools. |
| 4 | **Cloud Report Agent** | (internal) | system | background engine (Claude API) that turns *intake + notes* into the report draft; talks only to the Betriebskonsole, never to a client. |

Surfaces 2–4 plus the API are one local **Flask** app; surface 1 is a static site.

---

## 2 · The three layers (why this is fast to build from Paramur)

The Auralis system reuses ~90 % of the Paramur engine and swaps the top two layers.

```
LAYER 3  Auralis-specific: the intake form, the report renderer + Cloud Report
         Agent, the client-journey stages.                                ← BUILD
LAYER 2  Config + branding: company.json, config.json, clients.json,
         report_engine.json, the seal + warm-earth palette.              ← SWAP
LAYER 1  The engine: Flask app, portal/console auth, Mac/Windows launchers,
         backup/failover, Gmail-draft mailer, Cloudflare tunnel + Pages,
         self-update.                                                     ← REUSE
```

The one material change vs Paramur: the **data store**. Paramur uses a plain Excel
workbook; Auralis handles Art. 9 health data, so the backbone is an **encrypted store**
(see §5). Everything else — auth, launchers, tunnel, Gmail-draft email — carries over.

---

## 3 · Backend & auth model

- **Python Flask, single app**, binds **`127.0.0.1:5056`** (Paramur uses 5055 — a
  different port so both can run on one machine; see §8).
- **API-key auth** (`X-Auralis-Key`) on all `/api/*` **staff** routes (the
  Betriebskonsole + agent). Key supplied via env, never committed.
- **Portal routes** use a **session cookie** *or* a **signed HMAC bearer token**
  (short TTL) — the same auth engine as Paramur's Partner-Portal.
- **CORS restricted** to configured origins (`allowed_origins` in `config.json`).
- **Health data never opens a port to the internet.** The Flask app binds to loopback
  only; the sole ingress is the Cloudflare named tunnel (§7), TLS-terminated at
  Cloudflare, with `/staff` additionally behind **Cloudflare Access** (email code) —
  belt and braces on top of the API key.

**Auth markers used in the route table below:**
`[K]` = staff API key (`X-Auralis-Key`) · `[P]` = client portal (session/HMAC bearer) ·
`[–]` = public.

---

## 4 · Flask route table (adapted for Auralis)

| Method & path | Auth | Purpose |
|---|---|---|
| GET `/health` | – | liveness probe |
| GET `/api/version` | – | build number (commit count) |
| POST `/api/login` · `/api/logout` · GET `/api/me` | – / P | **client auth** (portal login / logout / whoami) |
| POST `/api/portal/change-password` | P | self-service password change |
| POST `/api/intake` | P | **submit the intake form** → encrypted backbone (see §6) |
| GET `/api/intake/draft` · POST `/api/intake/draft` | P | autosave / resume the multi-step form |
| POST `/api/upload` | P | secure upload (bloodwork / prior reports) — stored encrypted |
| GET `/api/clients/open` · GET `/api/client/<id>` | K | staff: **list open clients** + **client detail** (rendered intake) |
| POST `/api/client/<id>/notes` | K | save Desiree's **call notes** |
| GET `/api/client/<id>/prep` | K | agent-generated **meeting-prep** summary |
| POST `/api/agent/draft` | K | **run the Cloud Report Agent** → returns structured six-part draft for review |
| POST `/api/report/generate` | K | ★ **generate report** → renders PDF + creates the **Gmail draft** (approval gate — draft must be approved) |
| GET `/api/report/<id>` | K/P | fetch a generated report (staff any; client only their own) |
| POST `/api/client/<id>/stage` | K | drive a journey transition (Intake → Discovery → Draft → Review → Sent → Review-call) |
| GET `/api/dashboard` · `/api/journey` | K | cockpit KPIs + client-journey board |
| POST `/api/gdpr/export/<id>` · POST `/api/gdpr/erase/<id>` | K | **GDPR** one-click export / right-to-erasure for a client |
| GET/POST `/api/company` | K | **Stammdaten** (company.json editor) |
| GET/POST `/api/clients` · DELETE `/api/clients/<id>` · `/reset-password` | K | client CRUD + password reset |
| GET/POST `/api/report-engine` | K | edit report structure / agent system prompt / email copy |
| GET `/api/outbox` · GET `/api/outbox/<file>` | K | every generated email as `.eml`, re-openable |
| GET `/api/docs/<file>` | K/P | fetch generated documents from `output_docs/` |
| GET `/api/update` · POST `/api/update` | K | in-app **self-update** (poll `origin/main`, pull + restart) |
| GET `/` `/staff` `/portal` | – | page shells |

**Robustness note (carried from Paramur):** body-optional POST routes tolerate an empty
body (return `{}` rather than 500).

The **★ approval gate** lives at `POST /api/report/generate`: it refuses to run unless the
draft it renders is the founder-approved content submitted from the console. The agent
route (`/api/agent/draft`) can *only* produce a draft — it has no path to a client.

---

## 5 · The encrypted data model

Paramur's Excel backbone is replaced by an **encrypted store** because Auralis holds
special-category health data. Two clear zones:

**A · `clients.json` (logins only — NOT health data).**
Portal accounts, analogue of Paramur's `partners.json`. Per client:

```
id · name · email · language (DE/EN/ES) · password (PBKDF2 hash) ·
created · consent_scope_ts · consent_gdpr_ts · consent_version · status
```

Health answers are **never** stored here. This file holds only what's needed to log in
and to prove consent was captured (timestamp + version).

**B · The encrypted backbone (health data).**
An **encrypted SQLite / SQLCipher** database with **field-level encryption** for the
health fields, keyed by `data_encryption_key` (from env, never committed; local only;
hourly encrypted backup). Illustrative tables:

| Table | Key fields | Encrypted? |
|---|---|---|
| `intake` | `client_id`, `submitted_at`, `language`, section A–E answers, red-flag flags, consent snapshot | **health fields encrypted** (symptoms, history, medications, red-flags, free text) |
| `uploads` | `client_id`, `filename`, `stored_path`, `sha256` | file bytes encrypted at rest |
| `notes` | `client_id`, `author`, `updated_at`, call-notes body | **encrypted** |
| `prep` | `client_id`, agent meeting-prep summary | **encrypted** |
| `report` | `client_id`, `version`, approved section JSON, `pdf_path`, `generated_at`, `approved_by` | **encrypted** |
| `journey` | `client_id`, `stage`, `transitioned_at` | not sensitive (stage labels only) |
| `audit` | `ts`, `actor`, `action`, `client_id` | append-only access/consent log |

Design rules: **data minimisation** (only the minimised intake + notes are ever sent to
the agent — never third-party analytics on health pages); one record per client;
documents versioned under `output_docs/<CLIENT-ID>/<stage>/`; the whole store is
git-ignored and encrypted at rest. Full policy in `guides/SECURITY_GDPR.md`.

---

## 6 · Data-flow diagrams

### 6.1 · Intake → encrypted backbone

```
Client (/portal, authed [P])
   │  fills multi-step intake form (A About you · B Body & everyday life ·
   │  C Symptoms & history · D Red-flag screen · E Consent ×2)  — autosaves
   ▼
POST /api/intake  ── HMAC/session verified · CORS-checked ──►  Flask (127.0.0.1:5056)
   │
   ├─► clients.json      : write consent timestamps + version (login zone only)
   │
   └─► encrypted backbone: INSERT intake row
         · health fields FIELD-LEVEL ENCRYPTED (SQLCipher + per-field key from env)
         · red_flag flags set → surfaced to console for refer-out handling
         · audit row appended
   ▼
Cloud Report Agent writes MEETING-PREP summary (minimised) → prep table
   ▼
Console shows the client under "Intake submitted" on the Client-Journey board
```

### 6.2 · Draft → review → generate → Gmail draft (the approval gate)

```
Desiree (/staff, authed [K] + Cloudflare Access)
   │  reads rendered intake + adds Call notes (POST /api/client/<id>/notes)
   │  clicks "Draft report"
   ▼
POST /api/agent/draft
   │  console sends MINIMISED intake + notes only (record IDs/values needed, no more)
   ▼
Cloud Report Agent  →  Claude API  (no-training, DPA, appropriate EU region)
   │  system prompt = report_engine.json (six-part schema + safety/red-flag rules)
   │  returns STRUCTURED JSON: (1) starting point (2) what we're seeing
   │  (3) the science, simply (4) your plan (5) when to see a doctor (6) next steps
   ▼
Console renders the draft, section by section, FULLY EDITABLE
   ▼
★ APPROVAL GATE — Desiree reviews & edits every section, then clicks "Generate report"
   ▼
POST /api/report/generate
   ├─► HTML → PDF via headless Chromium (print_background on, Fraunces/Hanken, the seal,
   │        charts built from the client's own intake scales) → output_docs/<ID>/report/
   ├─► store approved section JSON + pdf_path in encrypted `report` table (approved_by set)
   └─► Mailer: build branded HTML email (report attached + review-call booking link) and
            IMAP APPEND it to team@auralisnatura.com **Drafts** (draft mode)
   ▼
Desiree opens Gmail, sends the draft personally → client books the review call
```

The agent never emails a client and never bypasses the gate. The renderer is the "premium
visual" layer; the *content* is always the founder-approved draft.

---

## 7 · Hosting & exposure

- **Homepage:** static site on **Cloudflare Pages** (dev/prod previews per branch).
- **Portal + Console + API + Agent:** the local Flask app (Mac now → Windows later),
  exposed via a **Cloudflare named tunnel** at **`api.auralisnatura.com`**. The Flask
  process never opens an internet-facing port; the tunnel is the only ingress, TLS
  terminated at Cloudflare.
- **`/staff` behind Cloudflare Access** (email-code) on top of the `X-Auralis-Key`.
- **Launchers (self-updating):** Mac `.command` / Windows `.ps1` poll `origin/main`
  every ~2 min and auto-pull + restart, so a `git push` reaches the server with no
  button. Hourly **encrypted** backup to an EU cloud folder; Mac↔Windows active/passive
  failover on the same tunnel.
- **Code:** GitHub — **`stefangruber001/auralisnatura`** (same account as the site).

DNS: `auralisnatura.com` → Cloudflare Pages; `api.auralisnatura.com` → the named tunnel;
MX/mail records left intact. Details in `guides/CLOUDFLARE_TUNNEL_AND_DOMAIN.md`.

---

## 8 · Ports (coexistence on one machine)

| App | Bind | Port |
|---|---|---|
| **Auralis Natura** portal/console/API/agent | `127.0.0.1` | **5056** |
| Paramur (if co-hosted) | `127.0.0.1` | 5055 |

Distinct ports let both systems run on the same Mac/Windows box without collision. Each
app is fronted by its **own** Cloudflare tunnel + hostname, so there is no shared ingress.
Change the port in `config.json` (`host` / `port`) if 5056 is taken locally.

---

## 9 · Config JSON — the single sources of truth

Four JSON files drive the whole system (no real secrets committed; secrets via env):

| File | Holds |
|---|---|
| **`company.json`** | legal + brand master: name, owner "Dr. rer. nat. Desiree Gruber", address, `team@auralisnatura.com`, `+34 614 489 656`, `auralisnatura.com`, VAT/NIF placeholders, brand colours, seal/logo paths. Appears on the report footer + emails. |
| **`config.json`** | runtime: `host`, `port` (5056), `api_key`→env, `secret`→env, `allowed_origins[]`, `email_mode` (`draft`), Gmail SMTP/IMAP, backup settings, **`data_encryption_key`→env**. |
| **`clients.json`** | client portal accounts (§5 A) — logins + consent only; **no health answers**. |
| **`report_engine.json`** | agent config: Claude model id, system-prompt reference, temperature, max tokens, the six-section schema, safety/red-flag rules, language handling. |

---

## 10 · Repository / folder layout

```
auralisnatura/                       (GitHub: stefangruber001/auralisnatura)
├── server/
│   └── server_app.py                Flask app — binds 127.0.0.1:5056, all /api/* routes
├── auralis_lib.py                   shared lib: config/paths, hashing, HMAC tokens, SOT loaders
├── portal.html                      Client-Portal UI + the premium multi-step intake form
├── staff.html                       Betriebskonsole (client journey, detail, agent review, GDPR)
├── agent/
│   └── report_agent.py              Cloud Report Agent — Claude API call, six-part draft
├── render/
│   └── report_renderer.py           HTML → PDF via headless Chromium (background graphics on)
├── mailer/
│   └── email_sender.py              branded HTML mail + Gmail-draft mode (IMAP APPEND)
├── store/
│   └── backbone.py                  encrypted SQLite/SQLCipher + field-level encryption
├── company.json config.json clients.json report_engine.json          (SOT — §9)
├── assets/                          seal.png, brand assets
├── output_docs/<CLIENT-ID>/<stage>/ generated docs: intake · prep · notes · report · sent
├── config_templates/                *.template.json (committed; real values via env/local)
├── tools/                           backup / restore / GDPR export helpers
├── start_auralis.command            macOS launcher (auto-update poll + backup)
├── start_auralis.ps1                Windows launcher (auto-update poll + backup)
└── Notfall_Mac_Start.command        Mac failover / standby launcher
```

Frontend is **hand-written HTML/CSS/vanilla-JS** (no framework), matching the site's
warm-earth brand: `--forest #3D2719`, `--clay #A8492A`, `--gold #AD7A32`,
`--sage #927B4A`, `--ink #2A211A`, `--paper #F5EEE0`, `--cream #FBF6EB`; headings
**Fraunces**, body/UI **Hanken Grotesk**; the botanical **seal** as cover/watermark/nav
dot. Every report and page carries the scope/medical/GDPR footer.

---

## 11 · Compliance guardrails wired into the architecture

These are enforced in code, not just in copy:

1. **Coaching & education, never medical care.** No diagnosis/treatment; the scope footer
   is rendered on every report (`company.json`) and page.
2. **"Dr." = Dr. rer. nat. (chemistry)**, stated transparently — never "physician".
3. **Refer out.** The intake **red-flag screen** (section D) sets flags on the `intake`
   row; the agent's `report_engine.json` rules make it open with a doctor referral if any
   flag is present; every report carries the "see your doctor / call 112" block.
4. **Art. 9 health data.** Field-level encryption at rest, EU residency end-to-end,
   explicit consent (timestamp + version in `clients.json`), data minimisation to the
   agent, one-click GDPR export/erase (`/api/gdpr/*`), DPAs with Cloudflare, Google and
   Anthropic. See `guides/SECURITY_GDPR.md`.
5. **Human-approval gate.** `POST /api/report/generate` only renders founder-approved
   content; the agent has no route to a client. Draft mode (IMAP APPEND) means Desiree
   always sends personally.
6. **Real testimonials only.**

---

*Companion docs: `AURALIS_PORTAL_CONCEPT.md` (the master concept), `guides/SECURITY_GDPR.md`,
`guides/REPORT_AGENT.md`, `guides/DEPLOYMENT_MAC.md`,
`guides/CLOUDFLARE_TUNNEL_AND_DOMAIN.md`, `guides/BUILD_PLAN.md`. Config templates in
`config_templates/`.*
