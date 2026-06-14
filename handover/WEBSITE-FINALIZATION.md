# WEBSITE-FINALIZATION.md — Make the Auralis Natura site the front door of the engine

> **For Claude Code.** This is a focused build spec. Read `CLAUDE.md` first for full project
> context (brand system, guardrails, file map). Then implement the changes below to turn the
> current beautiful-but-static site into a working booking → payment → automation front end.
> Keep the brand design system and the compliance guardrails in `CLAUDE.md` §2–§3 intact.

## Where the website lives
- **Built, viewable site:** `deliverables/index.html` (self-contained; seal base64-embedded).
- **Editable source:** `source/auralis_site_raw.html` + `source/main.js`.
  `index.html` is produced by injecting the brand seal (base64 of `assets/seal_320_opt.png`)
  into `auralis_site_raw.html` in place of its `{{SEAL}}` placeholders. After editing the
  source, re-inject the seal to regenerate `index.html` (mirror the pattern already in the
  file — every other deliverable uses the same `{{SEAL}}` → base64 substitution).
- `main.js` holds the nav, the **EN/ES/DE language toggle**, the mobile menu, and the
  IntersectionObserver scroll-reveal. The booking lead-form is currently a **front-end demo
  with no backend** — that is the main thing to replace.

## The target architecture (see Document 04 for the full picture)
`Homepage → Cal.com booking (Stripe payment for paid sessions) → webhook to Make →
automated onboarding (welcome + Tally intake + report-session booking + client record)`.
The site owns the **first hop**: capture the booking and fire the trigger.

## The changes to implement

1. **Embed real booking (replaces the demo form).**
   - Replace the demo booking form and wire **all** "Book a free call" CTAs (the `#book`
     targets and any nav/hero/pricing buttons) to an embedded **Cal.com** widget.
   - Use both an **inline embed** in the booking section and a **popup/modal** trigger from
     the header/hero CTAs. Point them at the free-call event type.
   - Keep the existing premium section styling around the embed; the widget should feel native
     to the brand (pass Cal.com theme colours: forest `#33422E`, clay `#AE6745`, cream `#FBF7EE`).

2. **Wire payment for paid sessions.**
   - For the paid offers (Root Session €220, The Reset €690, The Transformation €1,290,
     Companion €120/mo), configure those Cal.com event types to take **Stripe** payment or a
     deposit at booking. (Free call = no payment.)

3. **Fire the automation trigger.**
   - On booking/payment success, send a **webhook to Make** (or enable Cal.com's native
     workflow) so onboarding starts automatically. Leave a clearly-marked config point
     (env var / constant) for the webhook URL — do not hard-code secrets.

4. **Intake hand-off.**
   - Add a private "Next steps" page (or rely on the post-payment email) that links the
     **Tally** intake form. Provide a placeholder URL constant.

5. **Reviews.**
   - Replace the **placeholder testimonials** with a real reviews section (embed or a simple
     data-driven list) and add a review-capture link. Never fabricate reviews.

6. **Legal pages.**
   - Add **Privacy Policy (GDPR)**, **Terms**, and a **cookie notice**. Mirror the
     scope/medical/disclaimer wording from the footer of any built deliverable
     (`deliverables/*.html`) and `CLAUDE.md` §2. Link them in the footer.

7. **Localisation.**
   - Preserve the EN/ES/DE toggle in `main.js`. Ensure the booking widget and any new
     forms localise with the selected language.

8. **Analytics.**
   - Add privacy-first analytics (**Plausible**, EU) and track the **"calls booked"** event —
     the north-star KPI from the Business Plan.

9. **Compliance pass.**
   - Every form (booking, intake link, contact) must be GDPR-compliant: EU data handling and
     an **explicit consent checkbox** with links to the privacy policy. Verify before launch.

## Constraints / acceptance criteria
- ✅ Brand system unchanged (tokens, fonts, seal — `CLAUDE.md` §3).
- ✅ Compliance guardrails intact (coach/educator not medical; "Dr." = PhD; disclaimers — §2).
- ✅ Content still renders if JS fails (keep the progressive-enhancement pattern already in place).
- ✅ No secrets hard-coded; config points are clearly marked.
- ✅ `index.html` regenerated from source with the seal injected; 0 leftover `{{SEAL}}` tokens.
- ✅ All "Book a free call" CTAs open the real booking flow.

## Suggested kickoff prompt
> "Read CLAUDE.md and WEBSITE-FINALIZATION.md. Then implement items 1–3 first (Cal.com booking
> embed, Stripe payment on paid events, and the Make webhook trigger), regenerate index.html
> with the seal injected, and show me the booking section."
