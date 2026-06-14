# Apps Script engine — deployment (do once)

This turns the `Auralis CRM` sheet into the automation hub. ~20 minutes.

## A. Paste the code
1. Open the **Auralis CRM** spreadsheet → **Extensions → Apps Script**.
2. Delete the default `Code.gs` content and paste the contents of `Code.gs` from this folder.
3. **Save** (disk icon). Rename the project (top-left) to `Auralis Engine`.

## B. Fill the remaining config (top of Code.gs)
The folder ID, CRM ID and intake form are already filled. Still to set:
- `BOOKING_URL` — your Calendar booking link (see `../CALENDAR-SETUP.md`).
- `REPORT_TEMPLATE_DOC_ID` — the Google Doc you place in `_TEMPLATE` (see `../REPORT-TEMPLATE.md`).
- `REVIEW_URL` — wherever clients should leave a review (optional for now).
- Check `CRM_TAB` matches your tab name (default `CRM`).

## C. Add the secret webhook token
1. In Apps Script: **Project Settings (gear) → Script properties → Add script property**.
2. Name: `WEBHOOK_TOKEN`  ·  Value: a long random string you invent (e.g. 32+ characters). Keep a copy.

## D. Authorise + set triggers
1. In the editor, choose the function `setupTriggers` from the dropdown → **Run**.
2. Approve the Google permission prompts (Drive, Gmail, Docs, Spreadsheet).
3. This creates the **intake-form → onFormSubmit** trigger. (The form must send responses to THIS spreadsheet.)

## E. Deploy as a Web App (the Stripe endpoint)
1. **Deploy → New deployment → ⚙ → Web app**.
2. Description: `Stripe webhook` · Execute as: **Me** · Who has access: **Anyone**.
3. **Deploy**, authorise, and **copy the Web app URL**.

## F. Connect Stripe
1. Stripe Dashboard (same mode — Sandbox/Test — as your Payment Links) → **Developers → Webhooks → Add endpoint**.
2. Endpoint URL = your Web app URL **plus** `?token=YOUR_WEBHOOK_TOKEN`
   e.g. `https://script.google.com/macros/s/AKfy.../exec?token=YOUR_WEBHOOK_TOKEN`
3. Events to send: **`checkout.session.completed`** → Add endpoint.
4. Make sure your **Payment Links collect the customer's name and email** (Payment Link → after-payment / customer info).

## G. Daily use
- A paid Stripe payment now auto-creates the client folder + report Doc, logs the row (status **Paid**), and emails the welcome + intake links.
- When the client submits intake → status flips to **Intake**, answers are appended to their report Doc, and they get a confirmation.
- Draft & approve the report in their Doc, then in the sheet select that client's row → **Auralis ▸ Deliver report** (sends the PDF, status **Delivered**).
- Later: select the row → **Auralis ▸ Send review request** (status **Reviewed**).

### Note on webhook security
Apps Script web apps can't read HTTP headers, so we authenticate with the secret `?token=` instead of verifying Stripe's signature header. Keep the token private; rotate it by changing the Script property and the Stripe endpoint URL. For a solo, low-volume practice this is a reasonable trade-off.
