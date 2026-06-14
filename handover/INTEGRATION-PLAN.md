# INTEGRATION-PLAN.md — Wiring the engine behind the homepage

> Turns the static site into the **front door** of the automated practice described in
> `deliverables/04-Process-and-Automation-Blueprint.html`. Private — not published.
> Honours the golden rule (**nothing reaches a client without Desiree's approval**) and the
> §2 compliance guardrails. Uses **current** pricing (Root €199 · Reset €490 · Transformation
> €799 · Companion €120/mo for up to 3 months) — the older docs still show stale numbers.

## The 11-step flow → who owns each step
| # | Step | Lane | Tool | Built where |
|---|------|------|------|-------------|
| 1 | Land on homepage | auto | GitHub Pages site | ✅ done |
| 2 | Book free call | auto | **Cal.com** (embed) | **site — Phase 1** |
| 3 | Discovery call (25 min) | manual | Google Meet / Cal video | founder |
| 4 | Accept & pay (the trigger) | auto | **Stripe** (via Cal.com paid event or Payment Link) | site + Stripe |
| 5 | Onboarding fans out | auto | **Make** (EU) webhook | Make |
| 6 | Secure intake + consent + red-flag screen | auto | **Tally** (EU) | Tally + link on site |
| 7 | AI drafts 6-section report | auto | **Claude** Project (system prompt in §9 of CLAUDE.md) | Make → Claude |
| 8 | ★ Approve / edit (non-negotiable gate) | **approval** | Claude chat + report template | founder |
| 9 | Premium PDF | auto | `Client-Report-TEMPLATE.html` → print-to-PDF | founder one-click |
| 10 | Deliver & discuss | manual | Email + video | founder |
| 11 | Invoice + receipt + books, then review request | auto | **Stripe** (+ Quaderno/gestor for ES VAT) | Stripe/Make |

Only **2 manual steps + 1 approval**; the other 8 are automated. That ratio is the design goal.

## What I build on the site (Phase 1 — the first hop)
1. **Replace the demo/mailto form with a real Cal.com booking.**
   - Inline embed in the `#book` section + popup from every "Book a free call" CTA (nav, hero, mid-page, footer).
   - Free-call event type = no payment. Brand the widget (espresso `#4A3A29`, clay `#AE6745`, cream `#FBF7EE`).
2. **Payment on paid offers** (Root/Reset/Transformation/Companion) — two options (pick one):
   - **A. Cal.com paid event types** (recommended): each paid offer is a Cal.com event that takes Stripe payment/deposit at booking → scheduling + payment + webhook in one. Cleanest, and it fires step 5 natively.
   - **B. Stripe Payment Links/Buy Buttons** on the pricing cards: simplest if you want pay-without-scheduling. Needs the `https://buy.stripe.com/…` URLs or `pk_…` + button IDs.
3. **Fire the automation trigger** — on booking/payment success, Cal.com webhook → **Make**. Webhook URL kept as a clearly-marked config constant (no secrets in the repo).
4. **Consent + privacy** — explicit GDPR consent checkbox on every form, linking the Impressum/Privacy (already live).
5. **Analytics** — add **Plausible** (EU, cookieless) and fire a `call_booked` event (north-star KPI).
6. **Keep** EN/DE/ES localisation on the widget + progressive enhancement (content still renders if JS fails).

## What you (founder) set up — and what I need to wire it
| Need | For | Note |
|------|-----|------|
| **Cal.com** account + event types (free call + paid offers) | steps 2,4 | send me the **event links / embed slugs** |
| **Stripe** connected to Cal.com (Option A) **or** Payment Links / `pk_…` (Option B) | step 4 | 🚫 never send `sk_…` secret keys |
| **Make** scenario + inbound **webhook URL** | step 5 | I add it as a config constant |
| **Tally** intake form (consent + red-flag screen) | step 6 | send the **form URL** |
| **Claude Project** "Auralis Report Engine" (system prompt = CLAUDE.md §9) | step 7 | founder-side |
| **Plausible** site | analytics | send the domain/snippet |
| **Quaderno** or gestor + **NIF/registered address** | step 11 + Impressum | for ES VAT-compliant invoices |

## Sequencing
- **Phase 1 (site):** Cal.com embed + payment route + Make webhook trigger + consent + Plausible. *(I build once you send the Cal.com links + payment choice + webhook URL.)*
- **Phase 2 (Make):** payment → welcome email + Tally link + report-session invite + client record.
- **Phase 3 (AI report):** Tally → Make → Claude draft → **approval gate** → PDF → deliver.
- **Phase 4 (money/loop):** Stripe invoice + Quaderno/gestor; automated review request → real testimonials (replace placeholders; never fabricate).

## Guardrails carried through
- Human-approval gate (step 8) is hard-coded into the process — no auto-send of client output.
- GDPR: EU data residency (Cal.com/Tally/Make EU), explicit consent, data minimisation, DPAs, defined retention; health data = special category.
- Compliance copy unchanged: coaching/education not medical care; Dr. = academic doctorate not physician; refer-out + 112.

## Rough monthly tooling (directional)
Cal.com (free–€12) · Make (free–€9) · Tally (free–€phase) · Stripe (per-txn ~1.5%+€0.25) · Plausible (~€9) · Quaderno (optional). Start on free tiers; upgrade at real bottlenecks.

---
**To start Phase 1 I need:** (1) payment route **A or B**, (2) the **Cal.com** free-call event link (+ paid event links if A), (3) the **Make** webhook URL (can be added later), (4) **Tally** form URL. Send what you have and I'll wire the booking + trigger first.
