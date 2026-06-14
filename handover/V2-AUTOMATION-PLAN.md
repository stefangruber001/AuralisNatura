# V2 — Full Business Automation Plan

> Goal: automate the **entire** client journey so **Dr. Desiree Gruber only does value‑adding work** —
> (1) **review/approve each AI‑drafted report**, and (2) **run the 1:1 sessions on Google Meet**.
> Everything else (booking, payment, onboarding, intake, report draft, PDF, delivery email,
> invoice, review request) runs automatically. Keep the §2 compliance guardrails: coaching/
> education not medical care; Dr. = academic doctorate (Dr. rer. nat.), not a physician;
> AI **drafts**, human **approves**; GDPR for health data.

## Your stack (what each piece does)
| Tool | Role |
|------|------|
| **Squarespace** | Domain registrar / DNS only (already points www.auralisnatura.com → GitHub Pages; MX → Google) |
| **GitHub Pages** | Hosts the website (the front door) |
| **Stripe** | Takes payments (Payment Links live on the site) + sends receipts/invoices |
| **Google Workspace** | The engine: **Calendar** (booking + Meet), **Forms** (intake), **Gmail** (emails), **Drive/Docs** (reports + storage), **Apps Script** (free automation glue), **Sheets** (simple CRM) |
| **Claude** | Drafts the personalised report (you approve every word) |

## The automated journey (who does what)
```
1  Land on site                         → website (auto)
2  Book FREE 25-min call                 → Google Calendar Appointment Scheduling (auto Meet + reminders)
3  Discovery call                        → ★ DESIREE (Google Meet)
4  Buy a package                         → Stripe Payment Link (auto) ⚡ trigger
5  Onboarding fans out                   → Apps Script: welcome email + intake form + book report-session + client folder + CRM row (auto)
6  Client fills secure intake            → Google Form (consent + red-flag screen) → Sheet (auto)
7  Report drafted                        → Claude (draft into a Google Doc) (auto/assisted)
8  Review, edit & APPROVE                 → ★ DESIREE (the one approval gate)
9  Branded PDF generated                 → Apps Script: Doc → PDF (auto)
10 Deliver + walk-through                 → delivery email auto-prepared; ★ DESIREE runs the Meet session
11 Invoice + receipt, then review request → Stripe + Apps Script (auto)
```
Manual touchpoints = **2 sessions + 1 approval**. Everything else is automated.

---

## Build phases (do in order)

### Phase 0 — Foundations (you, ~30 min)
1. **Confirm Google Workspace plan.** Business Standard or above is ideal (needed for Calendar **Appointment Scheduling with Stripe payments** and EU data region). Tell me your tier.
2. **Set Workspace data region = Europe** (Admin → Data regions) for GDPR.
3. **Create a few Google resources** (I'll give exact names/fields):
   - A Drive folder `Auralis — Clients` (template subfolder inside).
   - A Google Sheet `Auralis CRM`.
   - A Google Doc `Report TEMPLATE` (branded) — I provide the content.
   - A Google Form `Intake` — I provide all questions (consent + red-flag screen).

### Phase 1 — Booking + Meet (you + me)
- **Free 25-min call:** create a Google Calendar **Appointment Schedule** (25 min, Google Meet auto-added, 24h+1h reminders, your real availability). Send me the booking link → I wire every “Book a free call” button to it (replacing the contact form).
- **Paid sessions:** keep the **Stripe Payment Links** already on the site. (Optional upgrade: if your Workspace tier supports it, turn the paid sessions into Calendar appointment types that take Stripe payment at booking — books + pays + Meet in one.)

### Phase 2 — The trigger + onboarding (me, with your access)
- In **Stripe → Developers → Webhooks**, add an endpoint (a **Google Apps Script Web App** URL I deploy) for `checkout.session.completed` / `payment_link` payments.
- **Apps Script** then automatically:
  1. creates the client’s Drive folder (from template),
  2. adds a row to `Auralis CRM`,
  3. sends the **welcome email** (Gmail) with: the **intake form** link + a link to **book the report session** + what happens next.
- You give me: access to the Sheet/Drive (or you paste IDs), and add the webhook in Stripe (I’ll give the exact URL + signing-secret steps; the secret stays in Apps Script, never in the repo).

### Phase 3 — Intake → AI draft → your approval (me)
- **Google Form intake** submission → Apps Script compiles a clean **brief** into the client folder.
- **Report draft:** start simple — you paste the brief into the **Claude Project “Auralis Report Engine”** (system prompt already in CLAUDE.md §9) → paste the draft into the client’s `Report` Google Doc. *(Later upgrade: Apps Script calls the Claude API to auto-draft the Doc and email you “draft ready.”)*
- **Approval gate:** you edit the Doc and tick **Approved** in the CRM Sheet (or move the Doc to an `Approved` folder).

### Phase 4 — Delivery + invoice + review (me)
- On “Approved”, Apps Script: exports the Doc → **branded PDF**, and **drafts the delivery email** in Gmail (PDF attached, warm note, link to book/confirm the walk-through) — ready for you to hit send (or fully auto-send, your choice).
- **Invoice:** Stripe auto-receipt on payment; for ES VAT-compliant invoices use **Stripe Invoicing or Quaderno** (confirm format with your gestor).
- **Review request:** Apps Script schedules a friendly follow-up email a few days after delivery → 5-star review → the flywheel.

### Phase 5 — Emails to prepare (I’ll draft, branded, EN/DE/ES)
1. Booking confirmation (handled by Calendar).
2. **Welcome / onboarding** (after payment) — intake link + next steps.
3. **Intake received** acknowledgement.
4. **Report ready / delivery** email (with PDF).
5. **Session reminder** (handled by Calendar) + a personal pre-session note.
6. **Invoice / receipt** note.
7. **Review request** follow-up.

---

## GDPR / safety (non-negotiable)
- Workspace **EU data region**; intake is **special-category health data** → explicit consent checkbox on the Form, data minimisation, defined retention.
- Red-flag screen in the intake; AI prompt opens with “see a doctor” if any flag; **nothing reaches a client without Desiree’s approval**.
- No secrets (Stripe signing secret, API keys) in the GitHub repo — they live in Apps Script / Stripe only.

## Decisions I need from you to start (3)
1. **Orchestration engine:** **Google Apps Script** (free, native to Workspace, I write the code) — *recommended* — or a no-code tool (**Make/Zapier**, ~€10/mo)?
2. **Booking/payment:** Free call via Google Calendar scheduling + **paid via the existing Stripe links** (simplest) — *recommended* — or upgrade to Calendar appointment types that charge via Stripe at booking (needs Business Standard+)?
3. **AI drafting:** start **manual** (you paste into the Claude Project) — *recommended* — or go straight to **auto** (Apps Script → Claude API, needs an API key + small per-report cost)?

## What I build first (once you answer)
- The **Google Form** intake (all questions, consent, red-flag screen).
- The **branded report Google Doc** template.
- The **Apps Script** onboarding + delivery automation (with clear config slots).
- The **7 email templates** (EN/DE/ES), on-brand.
- Wire the site’s “free call” buttons to your Calendar booking link.
