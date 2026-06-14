# Report template (Google Doc)

The Apps Script copies one master Google Doc for each client and (after intake) appends their answers to it. Create it once.

## Create it
1. In Drive, open your `Auralis — Clients/_TEMPLATE` folder.
2. **New → Google Docs**. Name it `Report — TEMPLATE`.
3. **Insert → Image → the logo** (`logo-lockup.png` — download from the repo `images/` or the live site) at the top, centered.
4. Paste the structure below and style headings with the Docs heading styles (Title / Heading 1).
5. Copy the Doc's **ID** from its URL (between `/d/` and `/edit`) and set it as `REPORT_TEMPLATE_DOC_ID` in `apps-script/Code.gs`.

## Suggested structure (the 6-part report)
```
[logo]
Your Personalised Holistic-Health Report
Prepared by Dr. rer. nat. Desiree Gruber · Auralis Natura
For: «Client name»          Date: «date»

1 · Your starting point
   A warm summary of where the client is now, in their own words.

2 · What we're seeing
   The themes/patterns from the intake — observations, not diagnoses.

3 · The science, simply
   The relevant evidence explained plainly. "May support", not "will fix".

4 · Your plan — 2 to 3 prioritised, realistic actions
   Action 1 — …
   Action 2 — …
   Action 3 — …

5 · When to see a doctor
   Clear red-flag guidance; in an emergency call 112.

6 · Your next steps
   What happens now, how to book the walk-through, encouragement.

— — —
This report is holistic-health education to complement, never replace, your medical
care. Auralis Natura provides coaching & education, not diagnosis or treatment.
Dr. rer. nat. = academic doctorate in bioorganic chemistry, not a physician.
Your data is handled under GDPR; see the Privacy Policy.
```

> Drafting workflow: paste the client's intake into your Claude "Auralis Report Engine" project (system prompt in CLAUDE.md §9), review & edit every word, then paste the approved text into this client's copied Doc — and use **Auralis ▸ Deliver report** in the sheet.
