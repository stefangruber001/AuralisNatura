# The Cloud Report Agent — Design Guide

> Companion to `AURALIS_PORTAL_CONCEPT.md` (esp. §4, §6, §7) and
> `config_templates/report_engine.json`. This guide is the complete, self-contained
> design of the **Cloud Report Agent** — the background engine that drafts Auralis
> Natura's premium holistic-health report. It is written for whoever builds Phase 4.

---

## 0 · What the agent is (in one paragraph)

The Cloud Report Agent is a **background worker** that lives inside the Auralis backbone
and **communicates with the Betriebskonsole** (Desiree's cockpit). It is not a chat
window and it is not client-facing. When Desiree clicks **"Draft report"** in a client's
detail view, the console hands the agent a **minimised structured intake + her 1:1 call
notes + the target language**. The agent calls the **Claude API** (model
`claude-opus-4-8`, no-training + signed DPA) with the Auralis Report-Engine system prompt
and returns a **structured, six-part, benchmarked, science-led DRAFT** as JSON. The
console renders that draft section by section for Desiree to **review and edit** — the
human approval gate. Only when she clicks **"Generate report"** does the *approved*
content flow into the premium HTML→PDF renderer and land as a **Gmail draft** (report +
review-call booking link). The agent produces text; a human decides what a client sees.

---

## 1 · Role & the golden rule

**Role.** Turn `intake + call notes` into *draft report content* (and, earlier, a short
meeting-prep summary). Nothing more. It does not render PDFs, does not send email, does
not write to the client record, and does not talk to the client.

**★ THE GOLDEN RULE — the human approval gate.**
The agent **only ever produces a DRAFT.** Nothing it writes reaches a client until
Dr. Gruber has read it, edited it, and clicked **Generate report**. This is wired into
the process, not a setting that can be turned off:

- The "Draft report" endpoint returns JSON to the console — it **cannot** trigger a send.
- The renderer + Gmail-draft step is a **separate** action gated behind the console's
  "Generate report" button, and even that only creates a *Gmail draft* — Desiree still
  presses Send herself.
- The agent never receives credentials for email, the client record, or the renderer.

Every other rule in this guide serves that one.

---

## 2 · Where it sits in the pipeline

```
INTAKE (portal) ──► [minimise] ──► ┌─────────────────────┐
                                   │  Cloud Report Agent │  (Claude API, background)
CALL NOTES (console) ─────────────►│  system prompt +    │
                                   │  payload → JSON out │
                                   └─────────┬───────────┘
                                             │  six-section DRAFT
                                             ▼
                 Betriebskonsole ── REVIEW & EDIT (★ approval gate) ──►
                                             │  approved sections
                                             ▼
                 HTML→PDF renderer ──► client folder + GMAIL DRAFT (report + booking link)
```

Two agent calls exist per client:
1. **Meeting-prep** — automatically, right after intake, before the discovery call (§6).
2. **Report draft** — on demand, after the call, when Desiree clicks "Draft report" (§4).

Both are stateless single-shot API calls. The agent keeps no memory between clients.

---

## 3 · Model & configuration (`report_engine.json`)

| Key | Value | Why |
|---|---|---|
| `provider` | `claude-code-subscription` | Claude via Claude Code on the Pro/Max subscription — no per-token cost |
| `model` | `claude-opus-4-8` | strongest reasoning + safety for health-adjacent copy |
| `temperature` | `0.4` | warm but disciplined; low enough to stay factual and on-brand |
| `max_tokens` | `6000` | fits a full six-section report with structured extras |
| `system_prompt_ref` | `claude/report-engine-system-prompt.md` | the Auralis Report-Engine prompt (see §5) |
| `output_language` | `match_intake` | write in the client's DE / EN / ES |
| `sections` | cover · starting_point · what_were_seeing · the_science_simply · your_plan · when_to_see_a_doctor · next_steps | the fixed schema |
| `safety_rules.*` | see §7 | open-with-referral if red flag; never diagnose; "may support"; always include the doctor section |
| `human_gate.required` | `true` | draft only |
| `data_minimisation` | send only needed fields; strip direct identifiers | see §8 |

No API key: the agent runs through **Claude Code** authenticated with Desiree's Claude **Pro/Max** subscription (`claude login` on the server) — no per-token charges, subject to the plan's usage limits. Inputs are **pseudonymised** and account **training is OFF**. Region: an
EU/appropriate region with a signed DPA and **data-not-used-for-training** enabled.

---

## 4 · The request/response contract (console ⇄ agent)

The console builds the payload; the agent returns JSON only (no prose outside the object).

### 4.1 Request IN — `POST /api/agent/draft`

```json
{
  "task": "draft_report",
  "client_ref": "AN-2026-041",            // opaque record id, NOT a name
  "language": "de",                        // de | en | es (from intake)
  "intake": {
    "age": 34,
    "life_stage": "postpartum",
    "main_goal": "Ich moechte mich wieder wie ich selbst fuehlen.",
    "why_now": "Seit der Geburt keine Energie mehr.",
    "already_tried": ["mehr Schlaf", "Vitamin D"],
    "scales": { "energy": 2, "sleep": 2, "stress": 4, "digestion": 3 },   // 1-5
    "notes": { "energy": "Nachmittagstief ab 15 Uhr", "digestion": "Blaehungen abends" },
    "typical_day_eating": "Kaffee, Brot, spaetes Abendessen",
    "movement": "Spaziergaenge, kein Sport",
    "caffeine_alcohol": "3 Kaffee/Tag, selten Alkohol",
    "symptoms": ["Erschoepfung", "Brain fog", "Blaehungen"],
    "supplements": ["Vitamin D"],
    "goals_ranked": ["Energie", "Verdauung", "Schlaf"],
    "red_flags": [],                        // empty = none ticked
    "conditions": [], "medications": [], "allergies": [],
    "pregnant_or_breastfeeding": "breastfeeding"
  },
  "call_notes": "Discovery-Call: sehr motiviert. Kind schlaeft schlecht -> ihr Schlaf leidet. Will keine Crash-Diaet. Fokus: Fruehstueck + Nachmittagstief.",
  "sections": ["cover","starting_point","what_were_seeing","the_science_simply","your_plan","when_to_see_a_doctor","next_steps"]
}
```

Notes on the payload:
- `client_ref` is an **opaque id**, not a full name (§8). A first name may be included
  only if Desiree wants it echoed in the copy; otherwise the renderer inserts the name
  locally after drafting.
- Only intake fields the report actually uses are sent. Free-text uploads/bloodwork are
  summarised or omitted, never raw-forwarded.

### 4.2 Response OUT — the six-section draft

The agent returns one object. Each section carries a `title` + `body` (markdown-lite
paragraphs) plus **structured bits** the renderer turns into charts / cards. `charts`
echoes the client's own numbers so the report visualises *their* data, not stock values.

```json
{
  "language": "de",
  "meta": { "red_flag_open": false, "tone_check": "warm-scientific" },
  "sections": {
    "cover": {
      "title": "Ihr persoenlicher Auralis-Bericht",
      "one_line": "Ein ruhiger, wissenschaftlich fundierter Weg zurueck zu Ihrer Energie."
    },
    "starting_point": {
      "title": "Ihr Ausgangspunkt",
      "body": "Sie sind seit der Geburt Ihres Kindes erschoepft ..."   // their story, their words
    },
    "what_were_seeing": {
      "title": "Was wir beobachten",
      "body": "Drei Muster verbinden sich hier ...",
      "theme_cards": [
        { "label": "Energie-Rhythmus", "note": "Nachmittagstief deutet auf Blutzucker-Schwankungen hin (Bildung, keine Diagnose)." },
        { "label": "Schlafdruck", "note": "Unterbrochener Schlaf senkt die Regeneration." },
        { "label": "Verdauung", "note": "Abendliche Blaehungen, moegliche Zusammenhaenge mit Timing der Mahlzeiten." }
      ],
      "charts": { "energy": 2, "sleep": 2, "stress": 4, "digestion": 3, "scale_max": 5 }
    },
    "the_science_simply": {
      "title": "Die Wissenschaft, einfach erklaert",
      "body": "Warum ein proteinreiches Fruehstueck den Nachmittag stabilisieren *kann* ...",
      "evidence_notes": ["Belege moderat", "Individuelle Reaktion variiert"]
    },
    "your_plan": {
      "title": "Ihr Plan",
      "body": "Drei priorisierte, realistische Schritte - nicht mehr.",
      "steps": [
        { "n": 1, "action": "Proteinreiches Fruehstueck", "why": "stabilisiert Energie am Nachmittag" },
        { "n": 2, "action": "Feste Essenszeiten am Abend", "why": "unterstuetzt Verdauung & Schlaf" },
        { "n": 3, "action": "10-Min-Atemuebung vor dem Schlafen", "why": "senkt Stress-Score" }
      ]
    },
    "when_to_see_a_doctor": {
      "title": "Wann Sie eine Aerztin/einen Arzt aufsuchen sollten",
      "body": "Diese Begleitung ist Bildung, kein Ersatz fuer medizinische Versorgung ... Notfall: 112."
    },
    "next_steps": {
      "title": "Ihre naechsten Schritte",
      "body": "Buchen Sie Ihren Review-Call, wenn Sie bereit sind - ohne Druck.",
      "booking_placeholder": "{{REVIEW_CALL_LINK}}"   // console injects the real Cal.com link
    }
  }
}
```

The console validates the object against the `sections` schema; a missing or malformed
section fails soft (see §9). `booking_placeholder` is a **token** — the agent never gets
or writes real links.

---

## 5 · The system prompt (reference & summary)

The agent is initialised with the existing prompt at
`claude/report-engine-system-prompt.md` (the same one Desiree can paste into a Claude
Project). **Do not fork it — reference the single source.** Its rules, in brief:

- **Educational, never diagnostic.** Never name a disease as a conclusion, never
  prescribe or adjust medication or medical nutrition therapy, never contradict a doctor.
  Dr. Gruber is a **Dr. rer. nat.** (chemistry) — framed as an academic doctorate, never
  a physician.
- **Safety first.** If the intake shows **any** red flag (unexplained weight loss, chest
  pain/breathlessness, severe/persistent pain, fainting, self-harm thoughts,
  disordered-eating signs, pregnancy complications, serious condition), **open** the
  report by clearly recommending the client see a physician and keep everything gentle
  and general.
- **Evidence & honesty.** Ground claims in credible science; where evidence is weak or
  mixed, say so. Prefer **"may support"** to **"will fix."**
- **Voice.** Warm, intelligent, calm, precise — "a brilliant friend who happens to be a
  scientist." Use the client's own words where possible.
- **Structure.** The six parts, prioritised, never overwhelming (2-3 plan actions max).
- **Language.** Write in the client's language — German, English or Spanish — matching
  the intake.
- **Draft only.** Explicitly a first draft for Desiree to review, edit and approve.

For the API, the JSON-output contract in §4.2 is appended to this prompt as an
**output-format instruction** ("Return only a JSON object with these keys ..."), so the
prose rules and the machine format live together.

---

## 6 · The meeting-prep summary (the earlier agent call)

Before the discovery call, right after intake lands, the agent produces a **short
meeting-prep brief** so Desiree walks in prepared. Same model/config, a `task:
"meeting_prep"` payload (intake only, **no** call notes — they don't exist yet), lower
`max_tokens` (~1200).

Output is a compact JSON the console renders at the top of the client detail:

```json
{
  "headline": "34, postpartum, main goal: 'feel like myself again'. Energy 2/5, stress 4/5.",
  "watch_points": ["Sleep disrupted by baby", "Afternoon energy crash", "Evening bloating"],
  "red_flag_check": "None ticked - proceed as coaching. Breastfeeding: keep suggestions gentle.",
  "suggested_focus": ["Breakfast composition", "Meal timing", "One calming evening habit"],
  "open_questions": ["What does a realistic week look like with the baby?"]
}
```

Same golden rule applies: it's an internal aid for Desiree, never client-facing. If a red
flag *is* present, `red_flag_check` says so plainly so she can lead the call safely.

---

## 7 · Safety rules (from `report_engine.json.safety_rules`)

1. **`open_with_doctor_referral_if_red_flag: true`** — any red flag => the report opens
   with a clear "please see a physician" and all suggestions stay gentle and general.
   The response `meta.red_flag_open` flag lets the console double-check this happened.
2. **`never_diagnose_or_prescribe: true`** — no disease as a conclusion; no medication or
   medical-nutrition-therapy changes; theme cards are framed as *education, not diagnosis*.
3. **`prefer_may_support_over_will_fix: true`** — honest, hedged language throughout.
4. **`always_include_when_to_see_a_doctor: true`** — the doctor/refer-out section and the
   "emergency: 112" line are present in **every** report, red flag or not.

These are enforced by the prompt AND re-checked by the console before "Generate report"
is enabled (e.g. reject a draft missing `when_to_see_a_doctor`). Belt and braces.

---

## 8 · Data minimisation (GDPR Art. 9)

Health data is special-category. The console **minimises before it sends**:

- **Strip direct identifiers.** Send `client_ref` (opaque id), not full name/email/exact
  address. Send `age`, not date of birth. The renderer re-attaches the name **locally**
  after the draft returns.
- **Send only what the report needs.** Fields the report doesn't use (raw uploads, phone,
  billing) are never forwarded. Free-text bloodwork is summarised, not raw-pasted.
- **No retention at the model.** No-training DPA region; the agent keeps no state; the
  API call is transient. Nothing is logged with identifiers on our side beyond the
  encrypted backbone.
- **One purpose only.** The payload is used solely to draft this client's report. No
  analytics, no reuse.

See `guides/SECURITY_GDPR.md` for the binding detail; this section is the agent's slice.

---

## 9 · Failure, timeout & retries

The console owns robustness; the agent call is wrapped defensively:

- **Timeout.** 90 s per call. On timeout, show "Draft is taking longer than usual -
  retry?" and do **not** block the console.
- **Retries.** Up to **2** automatic retries with exponential backoff (2 s, 8 s) on
  network errors, 429 (rate limit) and 5xx. **No** retry on 4xx auth/validation — surface
  it.
- **Malformed JSON.** If the response isn't valid JSON or fails schema validation, retry
  once with a stricter "return JSON only" reminder; if it still fails, present the raw
  text to Desiree as an *unstructured* draft she can edit manually (never auto-discard her
  potential content).
- **Missing safety section.** If `when_to_see_a_doctor` is absent, the console **blocks**
  "Generate report" and flags it — the report cannot ship without it.
- **Partial draft.** Sections render independently; a good section shows even if a sibling
  failed, so Desiree can regenerate just what's missing.
- **Cost/limit guard.** A per-day call cap prevents runaway spend; over-cap requests queue
  with a notice.

Errors are logged **without** health content (record ref + error code only).

---

## 10 · Rough per-report cost

Model `claude-opus-4-8`. A typical run: system prompt + minimised payload ~= 2-4k input
tokens; a full six-section draft ~= 3-5k output tokens (within the 6000 cap). Meeting-prep
is far smaller (~1-2k in, <1k out). At Opus pricing this lands on the order of **~EUR 0.15-
0.40 per report** (prep call a few cents), i.e. **cents, not euros** — negligible against
a EUR 198-798 offer. Confirm current Opus rates before go-live and set the per-day cap
accordingly. (Verify pricing via the `claude-api` reference; do not hardcode stale rates.)

---

## 11 · Example run (end-to-end walkthrough)

1. **Intake.** Elena (postpartum, DE) submits the portal form. Energy 2, sleep 2,
   stress 4, digestion 3; no red flags; breastfeeding.
2. **Prep.** The console auto-fires `task: meeting_prep` (intake only). The agent returns
   the brief in §6; it renders at the top of Elena's client detail.
3. **Discovery call.** Desiree runs the 25-min call, types **call notes** in the console:
   *"sehr motiviert ... Fokus: Fruehstueck + Nachmittagstief."*
4. **Draft.** She clicks **"Draft report."** The console minimises (opaque `client_ref`,
   age not DOB, only report-relevant fields), builds the §4.1 payload with `language:"de"`
   + the notes, and calls the agent.
5. **Agent.** Claude drafts the six sections in German, warm-scientific, "may support"
   language, theme cards + a chart object echoing 2/2/4/3, a 3-step plan, the always-on
   doctor section, and a `{{REVIEW_CALL_LINK}}` token. Returns JSON (§4.2). No red flag,
   so `meta.red_flag_open:false`.
6. **★ Review gate.** The console shows each section, **fully editable**. Desiree softens
   one science paragraph, tweaks step 2, and approves. The console confirms
   `when_to_see_a_doctor` is present.
7. **Generate.** She clicks **"Generate report."** The approved content pours into the
   premium HTML->PDF renderer — Fraunces/Hanken, the seal, editorial layout, the
   energy/sleep/stress **charts built from Elena's own numbers**, the theme cards, the
   plan roadmap. The PDF saves to `output_docs/AN-2026-041/report/` and a **Gmail draft**
   (report attached + the real Cal.com review-call link swapped in for the token) appears
   in team@auralisnatura.com.
8. **Send.** Desiree reviews the draft email and presses **Send** herself. The agent never
   touched the client.

---

## 12 · Build checklist (Phase 4)

- [ ] `report_engine.json` wired; Claude Code logged in (Pro/Max) on the server; inputs pseudonymised; account training OFF. (Commercial API/Team + DPA = optional upgrade.)
- [ ] `/api/agent/draft` and `/api/agent/prep` endpoints (staff-key protected, behind the tunnel + Access).
- [ ] Payload **minimiser** (opaque ref, drop identifiers, select fields) before every call.
- [ ] JSON schema validation of responses; safety-section presence check.
- [ ] Section-by-section **editable** review UI in the console (the approval gate).
- [ ] Renderer receives only **approved** content; charts fed the client's own scale values.
- [ ] Gmail-draft step separate & gated behind "Generate report"; booking token -> real link.
- [ ] Timeout/retry/failure handling (§9); per-day cost cap; identifier-free error logs.

---

*The agent writes. Dr. Gruber decides. A client only ever sees what she approved and sent.*
