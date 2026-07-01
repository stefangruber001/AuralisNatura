# Auralis Natura Portal — Phased Build Plan

> The concrete, phase-by-phase plan to build the Auralis Natura operating system:
> public site (exists) + **Client-Portal** (login → premium health intake) +
> **Betriebskonsole** (Desiree's cockpit) + **Cloud Report Agent** (Claude drafts →
> Desiree approves → one-click premium PDF + Gmail draft + review-call booking link).
>
> Reuses ~90 % of the Paramur engine (Flask, portal/console auth, launchers,
> backup/failover, Cloudflare tunnel + Pages, Gmail-draft mailer). The health-data
> layer (encryption, consent, red-flag, GDPR) and the Cloud Report Agent are the new,
> non-negotiable parts. See `AURALIS_PORTAL_CONCEPT.md` §11/§12, `SECURITY_GDPR.md`,
> `REPORT_AGENT.md`, and `FOUNDER_TODO.md`.
>
> **Reading this plan.** Every phase lists: **Goal** · **Tasks/deliverables** (files &
> modules) · **Acceptance criteria** · **Shippable on its own?** · **Founder inputs
> needed** (numbered against `FOUNDER_TODO.md`). Two rules run through all of it:
> (1) **the human-approval gate is mandatory** — the agent only ever drafts; (2)
> **special-category health data is first-class** — encrypt, minimise, EU-reside.

---

## Guiding principles (apply to every phase)

- **Reuse before rebuild.** Fork the Paramur engine; touch Layer 1 (engine) as little as
  possible, swap Layer 2 (config/branding), build Layer 3 (intake, report, agent).
- **Config-driven.** All brand/legal/runtime facts live in JSON (`company.json`,
  `config.json`, `clients.json`, `report_engine.json`). No hard-coded strings, no secrets
  in code — secrets are env-only.
- **One brand.** Portal, console, report and emails all render as the warm-earth Auralis
  brand (Fraunces / Hanken, seal, palette from concept §2).
- **Ship in slices.** Each phase leaves the system in a working, testable state. The system
  becomes genuinely useful at **Phase 3** (Desiree can run the agent manually) and fully
  automated by **Phase 6**.
- **Test against fake data first.** Nothing waits on the founder; real keys/links slot in
  as they arrive (`FOUNDER_TODO` items 1–9).

---

## Phase 0 — Concept & scaffold  ✅ DONE

**Goal.** Lock the design, data model and guides before writing engine code.

**Delivered.** `AURALIS_PORTAL_CONCEPT.md`; the guides (`ARCHITECTURE`, `SECURITY_GDPR`,
`REPORT_AGENT`, `DEPLOYMENT_MAC`, `CLOUDFLARE_TUNNEL_AND_DOMAIN`, this `BUILD_PLAN`);
config templates in `config_templates/` (`company.json`, `config.json`,
`clients.template.json`, `report_engine.json`); `FOUNDER_TODO.md`; repo layout decided.

**Shippable on its own?** N/A (planning artefact). **Founder inputs:** none.

---

## Phase 1 — Foundations

**Goal.** A branded Auralis Flask app running locally and reachable through a Cloudflare
tunnel with Access on `/staff`. No health features yet — this is the skeleton.

**Tasks / deliverables**
- Fork the Paramur engine into `stefangruber001/auralisnatura` (or a new private repo →
  founder item 5). Strip Paramur-specific Layer-3 code (Anfrage, pricing, Angebot,
  order-to-cash, Verlegeanweisung, wall-design, Excel backbone) per concept §12.
- `app.py` — Flask app binding `127.0.0.1:5056` (Paramur uses 5055; different port so both
  can run on one machine). Routes stubbed: `/portal`, `/staff`, `/api/health`, `/api/*`.
- Auth engine ported: API-key on `/api/*` staff routes (key → env `AURALIS_API_KEY`);
  portal session cookie / signed HMAC bearer (secret → env `AURALIS_SECRET`); CORS locked
  to `allowed_origins`.
- Config loader + templates wired: `company.json`, `config.json` read at boot; secrets
  pulled from env, never files. Fill `company.json` with Auralis brand/contact facts.
- Branding pass: palette + Fraunces/Hanken + seal into a shared `base.css`; `portal.html`
  and `staff.html` shells render the brand with placeholder content.
- Launchers ported: Mac `.command` (self-update: poll `origin/main` ~2 min → pull+restart;
  keep-awake). Windows `.ps1` stub for later.
- Cloudflare named tunnel → `api.auralisnatura.com`; **Cloudflare Access** (email code) in
  front of `/staff`; DNS/domain move per `CLOUDFLARE_TUNNEL_AND_DOMAIN.md`.

**Acceptance criteria**
- `python app.py` boots; `GET /api/health` returns 200 locally.
- `/staff` unreachable without both a valid API key **and** passing Cloudflare Access;
  `/portal` loads a branded (empty) shell.
- A `git push` to `main` reaches the running server within ~2 min via the launcher.
- `api.auralisnatura.com` resolves through the tunnel; no port is exposed to the internet.

**Shippable on its own?** Yes — an internal skeleton (branded shell, secure ingress),
demoable to the founder even with no client features.

**Founder inputs.** #1 Cloudflare account · #5 repo confirmation · #6 domain-transfer OK
(can defer the actual move; tunnel works on a Cloudflare-managed hostname meanwhile).
Gmail/Anthropic/Cal.com not needed yet.

---

## Phase 2 — Client-Portal + premium intake + encrypted backbone

**Goal.** A client can log in, complete the beautiful multi-step intake, and have it saved
**encrypted**, with consent and red-flag screening captured correctly.

**Tasks / deliverables**
- **Encrypted backbone** (concept §7, `SECURITY_GDPR.md`): SQLite with field-level
  encryption for health fields (or SQLCipher / encrypted volume). Key → env
  `AURALIS_DATA_KEY`. DB never committed; local only. Per-client folders
  `output_docs/<CLIENT-ID>/{intake,prep,notes,report,sent}/`.
- **Client auth** (`clients.json` model): Client-ID + PBKDF2 password, plus magic-link
  email option; forgot-password opens a pre-filled mail to team@. Health answers are **not**
  in `clients.json` — only account metadata + consent timestamps.
- **Premium intake form** (`portal.html` + JS), concept §5, Sections A–E: About you · Body
  & everyday life (1–5 scales) · Symptoms & history (+ secure upload for bloodwork) · **the
  red-flag screen** · **the two required consents**. Multi-step, progress bar, one idea per
  screen, autosave + resumable, warm microcopy, DE/EN/ES.
- **Intake API**: `POST /api/intake/save` (autosave draft) and `/submit` (finalise) →
  encrypted store; consent captured with **timestamp + version**; upload handling scoped &
  size-limited.
- **Red-flag handling**: any tick (other than "none") is stored as a flag on the record so
  the console and agent can surface it.

**Acceptance criteria**
- A test client logs in, completes all 5 sections, refreshes mid-way and resumes from
  autosave, submits; the record appears **encrypted** on disk (health fields unreadable
  without the key).
- Submit is **blocked** unless both consent boxes are ticked; consent version + timestamp
  are recorded.
- A red-flag tick is persisted and visibly flagged on the stored record.
- A client can only ever load their own record (authz test with two accounts).

**Shippable on its own?** Yes — the founder can invite a real client to fill the intake;
data lands safely even before the console exists (she'd read it in the DB tool meanwhile).

**Founder inputs.** #8 client access mode (recommended: **invite-only** at first) · #6/#1
domain+Cloudflare for the live portal URL · #9 NIF/address for footer (nice-to-have here).

---

## Phase 3 — Betriebskonsole (the cockpit)  ← system becomes useful here

**Goal.** Desiree can see every client's journey, read the intake cleanly, get an
auto meeting-prep summary, and record call notes — the full manual workflow, minus the
agent draft (which arrives Phase 4).

**Tasks / deliverables**
- `staff.html` console shell with tabs (adapted from Paramur): **Cockpit** (KPIs: calls
  booked, intakes submitted, reports in draft/sent, review calls) · **Client Journey** ·
  **Client detail** · **Templates** · **Stammdaten (⚙)** · **Outbox (⚙)** · **Clients**.
- **Client Journey** view: vertical stage cards per client — *Intake → Discovery call →
  Draft → Review → Report sent → Review call* — with buttons to advance stage and open the
  detail. Backed by `GET /api/clients` + stage state on the record.
- **Client detail** (the workhorse): the intake rendered cleanly & on-brand (red-flags
  highlighted); a **Call-notes** editor autosaving to `notes/`; an **auto meeting-prep
  summary** (short, agent-generated from the intake — first, minimal use of the Claude API;
  the full report agent is Phase 4).
- **Clients** tab: client CRUD, reset password, create/invite account (aligned with
  founder item #8). GDPR export/erase buttons stubbed (built out in Phase 6).
- APIs: `/api/client/<id>` (detail), `/api/notes/save`, `/api/prep/generate`,
  `/api/journey/advance`.

**Acceptance criteria**
- The console lists all clients with correct stages; opening one shows the full intake and
  any red-flags, calling out consent status.
- Call notes save and reload; meeting-prep generates a sensible, on-brand summary from a
  test intake and never invents medical claims.
- Console is reachable only through Access + API key (re-verify from Phase 1).

**Shippable on its own?** **Yes — this is the first genuinely useful release.** Desiree can
run the whole practice manually: read intake, prep, take the call, keep notes. The report is
still produced with the existing fill-in template until Phase 4.

**Founder inputs.** #2 Claude Code signed into the Pro/Max subscription on the server (for the meeting-prep summary; if not yet
supplied, prep is a manual/stub step and everything else works) · #7 report/summary
language default (recommended: follow intake language).

---

## Phase 4 — Cloud Report Agent + premium HTML→PDF renderer

**Goal.** From the client detail, Desiree clicks **Draft report** → the agent writes the
structured premium report → she **reviews & edits every section (the approval gate)** →
**Generate report** renders a super-premium branded PDF into the client's folder.

**Tasks / deliverables**
- **Report Agent module** (`report_agent.py`, `report_engine.json`) per `REPORT_AGENT.md`:
  calls the **Claude API** (no-training, appropriate region, DPA) with the Auralis
  Report-Engine system prompt + **minimised** intake + notes. Returns **structured JSON**
  for the six/seven-part report (concept §6). Safety rule enforced: if a red-flag is
  present, the draft **opens with a doctor referral**.
- **Draft/review UI** in client detail: each section shown **fully editable**; "regenerate
  section" optional; an explicit **approve** action gates generation. The agent output is
  always a *draft* — never emailed, never rendered until Desiree clicks generate.
- **Premium report renderer** (`report_render.py` + `report.css` + `report_template.html`):
  HTML → PDF via headless Chromium (`print_background=True`), reusing the existing
  brand/print system. Very visual: theme cards, a "how it connects" map, energy/sleep/
  stress **mini-charts built from the client's own intake scales**, the seal, editorial
  layout, and the always-present **When to see a doctor** + scope/GDPR footer.
- APIs: `/api/report/draft` (call agent), `/api/report/save` (edited content),
  `/api/report/generate` (render PDF → `report/`, mark stage).

**Acceptance criteria**
- "Draft report" returns a complete, compliant six/seven-part draft (educational, no
  diagnosis; red-flag path verified with a red-flagged test intake).
- Every section is editable; **generate is impossible without an explicit approve step.**
- "Generate report" produces an on-brand, print-perfect PDF with correct charts from the
  test client's numbers, saved to `output_docs/<id>/report/`.
- No client data beyond the minimised payload leaves for the API (verify the request body).

**Shippable on its own?** Yes — end-to-end *report production* works even before email
automation (Desiree attaches the PDF by hand in Phase 4). This is the core IP live.

**Founder inputs.** #2 Claude Code logged in on the server (Pro/Max subscription — no API key; required now) · #7 language default · #9
NIF/address for the report footer.

---

## Phase 5 — Email draft + booking link + review loop

**Goal.** One click after generate also drops a finished, on-brand email — report attached
+ review-call booking link — into **team@auralisnatura.com Drafts**, ready for Desiree to
send personally.

**Tasks / deliverables**
- **Gmail-draft mailer** (ported from Paramur): IMAP `APPEND` to Gmail Drafts (`email_mode:
  draft`); branded HTML mail with the seal; the report PDF attached; the **Cal.com review-
  call link** embedded. Fallbacks: send / off modes.
- Wire generate → draft: `/api/report/generate` (or a follow-on `/api/report/mail`) creates
  the .eml, saves a copy to **Outbox**, and appends to Drafts.
- **Portal review loop**: once a report exists, the client's `/portal` shows **view/download
  report** + **book the review call** (Cal.com link) — concept §3.2.
- Cockpit KPI: reports sent / review calls booked.

**Acceptance criteria**
- After generate, a correctly-addressed draft with the PDF + booking link appears in Gmail
  Drafts and as an .eml in Outbox; **nothing is auto-sent** (Desiree sends manually).
- The client can download their report and open the booking link from the portal.
- Email renders on-brand in Gmail (seal, fonts fall back gracefully).

**Shippable on its own?** Yes — completes the "produce → deliver" half of the pipeline;
provisioning is still manual (invite), which Phase 6 automates.

**Founder inputs.** #3 Gmail App Password (`AURALIS_SMTP_PASSWORD`) · #4 Cal.com review-call
event link.

---

## Phase 6 — Automation glue + hardening + go-live

**Goal.** Close the loop: portal logins auto-provision on booking/payment; backups &
failover run; GDPR export/erase tools are real; the system goes live.

**Tasks / deliverables**
- **Auto-provision**: webhook endpoints for Cal.com booking and Stripe payment → create the
  `clients.json` account + send the portal invite/magic link (respects founder item #8 —
  can stay invite-only, toggle in config).
- **Backups**: hourly **encrypted** backup of the backbone to an EU cloud folder; restore
  drill documented.
- **Failover**: Mac↔Windows active/passive on the same tunnel (Windows `.ps1` finished);
  one-double-click switch, per `DEPLOYMENT_MAC.md`.
- **GDPR tools** (make Phase-3 stubs real): one-click **export** (all of a client's data as a
  bundle) and **erase** (crypto-erase / delete + audit log entry); retention policy job.
- **Hardening**: rate-limit auth, security headers, dependency/secret audit, log review;
  confirm DPAs on file (Cloudflare, Google, Anthropic) per `SECURITY_GDPR.md`.
- **Go-live checklist** run (below); domain fully on Cloudflare; add the discreet
  **"Client Login"** link to the public site (nav + footer).

**Acceptance criteria**
- A test booking/payment auto-creates an account and sends a working invite (or queues it
  for approval if invite-only).
- Kill the Mac process → Windows serves the tunnel; backups restore cleanly in a drill.
- GDPR export produces a complete bundle; erase removes the client from store + folders and
  logs the action.
- Full go-live checklist passes.

**Shippable on its own?** Yes — this is the **fully automated** production system.

**Founder inputs.** #1 Cloudflare · #3 Gmail · #4 Cal.com · #6 domain move (must be done for
go-live) · #9 NIF/address + gestor IVA confirmation · Stripe keys (for payment-triggered
provisioning) · the hardware note (server on & awake).

---

## Milestones & rough sequencing

| Milestone | Phases | What's true at this point |
|---|---|---|
| **M0 — Scaffold** ✅ | 0 | Concept, configs, guides locked. |
| **M1 — Secure skeleton** | 1 | Branded Flask app live behind the tunnel + Access. |
| **M2 — Intake live** | 2 | Real clients can submit the encrypted premium intake. |
| **M3 — Practice runs manually** | 3 | Desiree works the whole journey in the console. **First useful release.** |
| **M4 — Core IP live** | 4 | Agent drafts → she approves → premium PDF renders. |
| **M5 — Deliver loop** | 5 | One click → Gmail draft + booking link; portal shows the report. |
| **M6 — Fully automated** | 6 | Auto-provision, backups, failover, GDPR tools, go-live. |

Rough shape for a solo build with a human approval gate: Phases 1–3 are the heaviest lift
(engine adaptation + two full UIs); Phases 4–5 are focused feature builds on top; Phase 6 is
integration + hardening. Founder inputs are only *blocking* from Phase 4 (Anthropic key) and
Phase 5–6 (Gmail, Cal.com, domain, Stripe) — Phases 1–3 proceed against test data. Sequence
strictly 1→6; each phase merges to `main` and reaches the server via the self-update
launcher.

---

## Definition of done / go-live checklist

**Security & GDPR (binding — `SECURITY_GDPR.md`)**
- [ ] Health backbone encrypted at rest; key in env only; DB never committed.
- [ ] EU data residency end-to-end (Cloudflare EU, Gmail Workspace region, Claude region).
- [ ] Tunnel-only ingress; no exposed port; `/staff` behind Cloudflare Access + API key.
- [ ] Consent captured with version + timestamp; two required boxes enforced at submit.
- [ ] Data minimisation to the agent verified (only what's needed leaves the machine).
- [ ] DPAs on file: Cloudflare, Google, Anthropic. No third-party analytics on health pages.
- [ ] GDPR export + erase tools work; retention/erasure policy documented.
- [ ] Hourly encrypted backups running; restore drill passed.

**Function & safety**
- [ ] Client can register/login, complete + resume + submit the intake (DE/EN/ES).
- [ ] Red-flag path: draft opens with a doctor referral; "When to see a doctor" always present.
- [ ] **Approval gate enforced:** no PDF/email is producible without Desiree's explicit approve.
- [ ] Report renders on-brand, print-perfect, with charts from the client's own numbers.
- [ ] Generate → Gmail draft (report + booking link) in team@ Drafts; nothing auto-sent.
- [ ] Scope/medical/GDPR footer on every report and page; "Dr." shown as Dr. rer. nat.

**Ops & resilience**
- [ ] Self-update launcher pulls `main` and restarts within ~2 min.
- [ ] Mac↔Windows failover verified on the same tunnel.
- [ ] `company.json` carries correct NIF + registered address; gestor confirmed IVA treatment.
- [ ] Public site has the discreet "Client Login" link (nav + footer); domain on Cloudflare.
- [ ] Auto-provision on booking/payment works (or invite-only toggle set as the founder chose).

When every box is ticked, the system is **live and fully automated** with the human
approval gate intact — exactly the Paramur-equivalent, tuned for special-category health data.
