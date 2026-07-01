# Auralis Natura — Security & GDPR Guide (BINDING)

> **Status: binding.** The Auralis Portal system (Client-Portal, Betriebskonsole, Cloud
> Report Agent, encrypted backbone) collects and processes **special-category health data**
> under **GDPR Article 9** — a client's history, symptoms, goals and a red-flag screen. This
> is the highest tier of data-protection obligation, not a nice-to-have. Every rule here is
> a design constraint on the build and an operating rule for Desiree. If a feature would
> break a rule in this guide, the feature does not ship.
>
> **Scope recap (from the Concept, §1 guardrails):** Auralis Natura is Dr. rer. nat.
> Desiree Gruber's holistic-health & nutrition **coaching and education** practice
> (Barcelona; online worldwide). **Dr. = academic doctorate in chemistry, not a physician.**
> Coaching, never medical diagnosis or treatment. This scope is itself a safety control and
> is referenced below.

---

## 0 · The controller, the data, the processors

- **Data controller:** Auralis Natura / Dr. rer. nat. Desiree Gruber, Barcelona, Spain (EU).
  Supervisory authority: **AEPD** (Agencia Española de Protección de Datos).
- **Data subjects:** prospective and active coaching clients.
- **The special-category data (Art. 9):** the whole premium intake — Section B lifestyle
  scales, Section C symptoms & history, Section D safety & red-flag screen, plus any
  bloodwork the client uploads. Treat the **entire intake record** as Art. 9 health data.
- **Ordinary personal data (Art. 6):** name, email, language, Client-ID, booking metadata,
  consent timestamps. Lives in `clients.json`. Still protected — just not Art. 9.
- **The processors we rely on (each needs a DPA on file — see §5):**
  - **Cloudflare** — tunnel, Access, Pages, DNS (network ingress; TLS termination).
  - **Google (Workspace / Gmail)** — email + report-draft delivery (`team@auralisnatura.com`).
  - **Anthropic (Claude, via Claude Code on Desiree's Pro/Max subscription)** — the Cloud
    Report Agent drafts report content from **pseudonymised** inputs only (no client identity).
  - **The EU backup destination** — encrypted off-machine backup (see §11).

**Golden separation (from the Concept §9):** health answers live **only** in the encrypted
backbone. `clients.json` holds logins + consent metadata, **never** health answers.

---

## 1 · Lawful basis & explicit consent (Art. 9)

For Art. 9 health data the lawful basis is the data subject's **explicit consent**
(Art. 9(2)(a)) resting on **Art. 6(1)(a)/(b)** for the coaching relationship. There is **no**
legitimate-interest shortcut for health data — consent must be explicit, informed, freely
given, specific and **recorded**.

**How consent is captured (Concept §5, Section E — the two required checkboxes):**

1. **Coaching-not-medical** — the client confirms they understand Auralis Natura is
   **holistic-health coaching and education, not medical care**, no diagnosis or treatment,
   and that "Dr." is an academic doctorate in chemistry (not a physician).
2. **GDPR health-data** — the client gives **explicit consent** to process their
   special-category health data for the coaching, stored securely **in the EU**, used only
   for their coaching, **never shared without consent**, and **erasable on request** (links
   the Privacy Notice, §9).

**Recording rules (build these into the intake submit handler):**
- Both boxes are **required** — the intake cannot be submitted with either unticked. No
  pre-ticked boxes (pre-ticked consent is invalid under GDPR).
- On submit, store a **consent record** per client: `consent_coaching=true`,
  `consent_gdpr=true`, **UTC timestamp**, the **privacy-notice version string** (e.g.
  `privacy_v1.2`) and the **consent-text version** the client actually saw. Store these
  timestamps + versions in `clients.json` (ordinary data), not with the health answers.
- Consent is **withdrawable** at any time; withdrawal triggers stop-processing + the erase
  flow (§8). Withdrawal must be as easy as giving consent — a line in the Privacy Notice
  pointing to `team@auralisnatura.com` plus the console erase tool satisfies this.

---

## 2 · Data minimisation — send the agent (and everyone) only what's needed

Minimisation is a **hard rule**, not a preference, because every extra copy of health data
is extra breach surface and extra obligation.

- **To the Cloud Report Agent (Claude API):** send **only** the structured intake fields +
  Desiree's call notes that the report actually needs. Strip direct identifiers where they
  add nothing: the agent can draft from **age, life stage, scales, symptoms, goals, notes**
  without the client's full name, email, address or Client-ID. Where a name is needed for
  warmth, first name only. **Never** send raw uploaded lab PDFs to the agent unless a section
  genuinely requires it.
- **Prefer IDs over payloads across tool boundaries.** When surfaces talk to each other
  (console ↔ backbone ↔ mailer, or any future automation), pass a **Client-ID / record
  reference**, not the raw health blob. The health payload is dereferenced only inside the
  encrypted backbone at the moment of use.
- **No third-party analytics or trackers on the portal or intake pages — none.** No Google
  Analytics, no ad pixels, no third-party fonts that phone home, no session-replay, no
  embedded chat widgets. The health-data surfaces (`/portal`, the intake form) load only
  first-party assets. (Privacy-first, cookieless analytics such as Plausible may run on the
  **public marketing site only**, never on portal/intake.)
- **Collect only what the coaching needs.** The intake field set in Concept §5 is the ceiling,
  not a starting point — don't add fields "in case." The report goes out as a Gmail **draft**
  (Concept §3.4/§7) that attaches the PDF and need not restate raw intake answers.

---

## 3 · EU data residency, end to end

Health data must stay in the **EU/EEA** across every hop. Configure each processor for EU
residency and verify it:

- **Cloudflare** — enable EU data-localisation (Data Localization Suite / EU region for
  processing where offered); the tunnel TLS-terminates at Cloudflare. Cloudflare sees
  encrypted transit metadata, not decrypted health payloads at rest.
- **Google Workspace** — set the **Workspace data region to Europe** (Admin console → Data
  regions) so mail/report drafts are stored in the EU.
- **Anthropic (Claude, via the Claude Code subscription)** — the agent runs on Desiree's
  **Pro/Max subscription** (no per-token API cost). A consumer subscription does **not** carry
  a commercial DPA, so we compensate with two controls that are mandatory here: **(1)** turn
  **OFF** “use my data to improve Claude / model training” in the account settings, and
  **(2)** send the agent **pseudonymised** data only — a client reference plus the health
  content and notes, never the name, email or other direct identifiers (the mapping stays in
  the encrypted backbone, never leaves the server). **Optional stricter footing:** move the
  agent to a commercial **Claude Team/API plan with a signed DPA + EU-eligible region + no
  training**; the agent code is written so this is a one-line provider switch. Do not send any
  real (even pseudonymised) client data until training is confirmed off.
- **The server** runs locally on Desiree's **Mac (→ Windows later)** in Spain — EU by
  definition. The **encrypted backbone and all backups stay in the EU** (§11). No US-hosted
  analytics, form tools or trackers touch health data.

Document the chosen region for each processor in the ROPA (§9). If a processor cannot
guarantee EU residency for health data, it is not used for health data.

---

## 4 · Encryption — at rest and in transit

**At rest (the backbone + backups):**
- The backbone is an **encrypted SQLite store using SQLCipher** with **field-level
  encryption** on the health fields (Concept §7). Both the DB-level and field-level layers
  stay on; the field-level layer means even a copied DB file is opaque without the key.
- The **encryption key comes from an environment variable — `AURALIS_DATA_KEY`** — resolved
  at runtime via `config.json`'s `data_encryption_key→env`. **The key is never committed**,
  never written to the repo, never printed to logs. It lives in the OS environment / a
  secrets file outside the repo tree.
- **Backups are encrypted too** (§11) — an unencrypted backup would defeat the entire scheme.
- Uploaded files (bloodwork/reports) are stored encrypted in the client's
  `output_docs/<CLIENT-ID>/` area, under the same key regime.

**In transit:**
- **TLS only, via the Cloudflare tunnel.** The **Flask app binds `127.0.0.1:5056` and never
  opens a public port** (Concept §7/§8). The Cloudflare **named tunnel is the only ingress**;
  there is no other route to the app from the internet. Health data never rides an exposed
  port.
- Internal calls to the Claude API and Gmail (IMAP/SMTP) use TLS.
- HSTS on the public hostnames; no mixed content on portal/intake.

---

## 5 · Data Processing Agreements — the checklist

Under Art. 28 every processor that touches personal data must be under a **signed DPA** with
appropriate safeguards. **Get each on file before real client data flows**, then keep copies.

- [ ] **Cloudflare DPA** — signed / accepted; EU data-localisation confirmed; SCCs where
      relevant.
- [ ] **Google (Workspace) DPA** — Workspace Data Processing Amendment accepted; **data
      region = Europe** set in Admin console.
- [ ] **Claude account** — training/“improve Claude” **turned OFF**; agent inputs
      **pseudonymised** (no direct identifiers). *(Optional: commercial Claude Team/API plan
      with a signed DPA + EU region for the strictest footing.)*
- [ ] **Backup provider DPA** — signed; EU storage region confirmed.
- [ ] (If ever used) any form/scheduling/analytics tool touching PII — DPA + EU residency,
      else not used for health data.

Keep signed DPAs in a dedicated, access-controlled folder. Note each processor + purpose +
region + DPA date in the ROPA (§9).

---

## 6 · Access control & authentication

Least privilege everywhere; belt-and-braces on the staff surface because it exposes all
health data.

- **`/staff` (Betriebskonsole) — two independent gates (Concept §3.3):**
  1. **Cloudflare Access** with **email one-time-code** in front of the whole `/staff` path.
  2. The application **API key** on `/api/*` staff routes (key from env, never committed).
- **`/portal` (Client-Portal):** Client-ID + **PBKDF2-hashed** password (or magic-link email),
  session cookie / short-TTL signed bearer token (HMAC). **A client only ever sees their own
  record** — enforce the record scope server-side on every portal route; never trust a
  client-supplied ID.
- **Strong, unique passwords / passkeys with 2FA/MFA on** for Desiree's Mac login,
  Cloudflare, Google Workspace, GitHub and the Anthropic console. A password manager is
  mandatory.
- **Least privilege:** only Desiree has console access; no shared logins. If a helper is ever
  added, scope them narrowly and log it in the ROPA.
- **CORS** restricted to configured origins; no wildcard on health routes. **Lock the Mac**
  (FileVault full-disk encryption ON, auto-lock short) — it is the physical home of the backbone.

---

## 7 · The human-approval gate as a safety & compliance control

The Cloud Report Agent (Claude) only ever produces a **draft**. **Nothing reaches a client
until Desiree has reviewed, edited and clicked "Generate report"** (Concept §1.5, §3.4, §4
step 7). This gate is wired into the process, not optional, and it is simultaneously:

- a **clinical-safety** control (a human checks every word against the coaching-not-medical
  scope and the refer-out rules), and
- a **data-accuracy** control (Art. 5(1)(d) — personal data must be accurate; the human catches
  and corrects errors before anything is sent).

**Coaching-not-medical / refer-out / red-flag guardrails (safety, from Concept §1):**
- Every report and page carries the **scope footer** (coaching & education, not medical care;
  "Dr." = Dr. rer. nat.).
- The intake includes the **red-flag screen** (Section D); the report always contains a
  **"When to see a doctor" / call-112** block.
- The agent's system prompt instructs it to **open with a doctor referral if any red flag is
  present** and to keep suggestions gentle and general. Desiree confirms this at the gate.
- **Never** diagnosis, treatment of disease, or prescriptive medical nutrition therapy.

---

## 8 · Retention, erasure & data-subject rights

**Retention:**
- Default retention window: **3 years** from last client activity, **configurable** in
  `config.json` (e.g. a `retention_years` setting). After the window, records are purged (or
  irreversibly anonymised) unless the client is still active or a legal duty requires keeping
  something (e.g. invoices/tax records — keep those separately for the statutory period, not
  in the health backbone).
- Retention is stated plainly in the Privacy Notice (§9) and logged in the ROPA.

**Data-subject rights (respond within one month; free of charge):**
- **Access** (Art. 15) — the client can get a copy of their data.
- **Rectification** (Art. 16) — correct wrong data.
- **Erasure / "right to be forgotten"** (Art. 17) — delete on request or on consent withdrawal.
- **Portability** (Art. 20) — a machine-readable export of their data.
- **Restriction / objection / withdraw consent** — stop processing.

**The console tools that make this real (Concept §3.3 "Clients" tab):**
- **One-click GDPR EXPORT** per client → a machine-readable bundle (JSON + the report PDFs)
  covering access + portability.
- **One-click ERASE** per client → removes the encrypted backbone record **and** the
  `output_docs/<CLIENT-ID>/` files **and** the `clients.json` entry, and flags any Gmail
  drafts for manual deletion. Erasure must reach **backups too** (document that the next
  backup rotation removes the erased record, or run a targeted purge).
- Log every export/erase (who, when, which client) for accountability — but keep the log
  minimal (no health content in the log).

---

## 9 · Records of processing (ROPA) & the privacy notice

**ROPA (Art. 30) — a simple maintained document, kept with this guide.** Record, in one table:
purpose (coaching + report drafting), categories of data (Art. 9 health + ordinary),
categories of data subjects (clients), recipients/**processors** (Cloudflare, Google,
Anthropic, backup provider — with region + DPA date), **retention** window, and the
**technical & organisational measures** (encryption at rest + in transit, access control,
approval gate). Update it whenever a processor or a data flow changes.

**Privacy Notice (Arts. 13/14) — shown to the client BEFORE they consent.** Plain-language,
linked from the intake consent step and the site footer. It states: who the controller is
and how to reach them (`team@auralisnatura.com`); that this is **coaching, not medical care**;
what data is collected and why; the **lawful basis (explicit consent)**; the **EU processors**
and EU storage; the **retention** window; the client's **rights** and how to exercise them;
how to **withdraw consent**; and the right to complain to the **AEPD**. Version it (a version
string) and record which version each client accepted (§1).

---

## 10 · Breach response plan (the 72-hour duty)

Under Art. 33, a personal-data breach likely to risk individuals' rights must be reported to
the **AEPD within 72 hours** of becoming aware; high-risk breaches must also be communicated
to affected clients (Art. 34) **without undue delay**. Health data raises the stakes.

**If you suspect a breach (lost/stolen Mac, leaked key, unauthorised access, misdirected
report, processor incident):**
1. **Contain** — revoke/rotate the affected credentials immediately (rotate `AURALIS_DATA_KEY`
   and API keys, force-logout, disable the tunnel/Access if needed). Isolate the machine.
2. **Assess** — what data, whose, how much, is it encrypted (a stolen but fully-encrypted
   backbone with the key held separately is materially lower risk — note this).
3. **Record** — start an incident log: time discovered, facts, actions, decisions.
4. **Notify AEPD within 72h** if there is a risk to individuals (via the AEPD breach form).
   If unsure, involve the gestor/lawyer and lean toward notifying.
5. **Notify affected clients** promptly if the risk to them is high, in plain language, with
   what happened and what they should do.
6. **Remediate & learn** — fix the root cause; update this guide and the ROPA.

Keep the AEPD breach-form URL and the gestor/lawyer contacts in `FOUNDER_TODO.md`.

---

## 11 · Backups — encrypted, EU, hourly, tested

- **Encrypted, hourly, EU-hosted** backups of the backbone (Concept §7). The backup is
  encrypted **before** it leaves the machine (same key regime / a dedicated backup key from
  env — never plaintext to the cloud).
- **EU storage region** only; backup provider under DPA (§5).
- **Test the restore** — a backup you have never restored is not a backup. Do a restore drill
  at go-live and periodically; confirm the restored backbone decrypts and opens.
- **Erasure reaches backups** — an erased client must not silently survive in backups (§8).
- Keep the backup key **separate** from where the backups are stored, so a compromise of the
  backup destination alone does not yield plaintext.

---

## 12 · Secrets hygiene

- **All secrets come from environment variables** and are referenced by `config.json` via
  `→env` (Concept §9): `AURALIS_DATA_KEY` (backbone/field encryption), the staff **API key**,
  the portal HMAC **secret**, Gmail IMAP/SMTP credentials (app password), Cloudflare tunnel
  token, backup credentials. *(The Cloud Report Agent uses **no** API key — it runs via Claude
  Code signed into the Pro/Max subscription on the server.)*
- **Never commit a real secret.** `config.json` in the repo holds **placeholders/`env`
  references only**. Add secrets files and `*.key` to `.gitignore`; if a secret is ever
  committed, treat it as compromised and **rotate immediately**.
- **Rotate on a schedule** and on any suspicion (see §10). Rotating `AURALIS_DATA_KEY` implies
  a re-encrypt migration — document the procedure.
- **No secrets in logs, screenshots, error messages, or the Outbox `.eml` files.**
- Enable **GitHub secret scanning / push protection** on the repo.

---

## 13 · Pre-go-live compliance checklist (Desiree ticks each)

- [ ] Intake has **both consent checkboxes** (coaching-not-medical + GDPR health-data),
      neither pre-ticked, both required; consent **timestamp + version** stored per client.
- [ ] **Privacy Notice** written, versioned, linked at the consent step and site footer;
      names controller, explicit-consent basis, EU processors, retention, rights, AEPD.
- [ ] **ROPA** written and current (processors, regions, retention, TOMs).
- [ ] **DPAs signed & on file:** Cloudflare, Google (region = Europe), **Anthropic (EU
      region + no-training)**, backup provider.
- [ ] Backbone is **SQLCipher + field-level encryption**; key is **`AURALIS_DATA_KEY` from
      env**, not in the repo.
- [ ] Flask binds **127.0.0.1 only**; **Cloudflare tunnel is the only ingress**; TLS only.
- [ ] `/staff` behind **Cloudflare Access (email code) + API key**; `/portal` PBKDF2 + own-
      record scoping.
- [ ] **No third-party analytics/trackers on `/portal` or intake**; agent receives
      **minimised** data (IDs/first-name, not full identifiers or raw uploads).
- [ ] **Backups** encrypted, EU, hourly; **restore tested**; erasure reaches backups.
- [ ] **GDPR export + erase** buttons work end-to-end in the console (backbone + files +
      `clients.json`).
- [ ] **Retention window** set in `config.json` and stated in the Privacy Notice.
- [ ] **Secrets** all from env, `.gitignore`d, MFA on all accounts, secret scanning on.
- [ ] **Breach plan** to hand (AEPD form URL + gestor/lawyer contacts); incident log ready.
- [ ] **Human-approval gate** enforced in code — the agent cannot send; report scope footer,
      red-flag screen and "when to see a doctor" block present.
- [ ] Mac **FileVault ON**, auto-lock short, strong login.

---

*Binding companion to `AURALIS_PORTAL_CONCEPT.md` (§1 guardrails, §7 architecture, §10
security summary). If in doubt, minimise data, keep it in the EU, encrypt it, get consent,
and let no report reach a client without Desiree's approval. Have the Privacy Notice, ROPA,
and client contract reviewed once by a Spanish lawyer/gestor before go-live.*
