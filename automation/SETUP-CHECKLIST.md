# V2 Setup — step by step (do in this order)

Decisions locked: **Google Apps Script** engine · **free call in Google Calendar + existing Stripe links** · **manual Claude drafting to start**.

## YOU do now (Phase 0–1) — ~45 min
1. **Tell me your Google Workspace tier** (Business Starter / Standard / Plus).
2. **Admin → Account → Data regions → Europe** (GDPR).
3. **Drive:** create a folder **`Auralis — Clients`**, and inside it a subfolder **`_TEMPLATE`**. Copy that folder's **ID** (from the URL).
4. **Sheet:** create **`Auralis CRM`** with these column headers in row 1:
   `Timestamp | Name | Email | Package | Amount | Status | ClientFolder | ReportDoc | Notes`
   (Status values we'll use: Paid → Intake → Drafting → Approved → Delivered → Reviewed.) Copy its **ID**.
5. **Form:** build a Google Form from **`automation/INTAKE-FORM.md`** → Settings: *Collect email*, *Limit to 1 response*, **required* consent*. Link responses to the `Auralis CRM` (or a `Intake` tab). Copy the **public form link**.
6. **Calendar booking (free call):** Google Calendar → **Create → Appointment schedule** → “Free 25‑min discovery call” → turn **Google Meet ON**, add **24h + 1h reminders**, set your availability → **copy the booking page link**.
7. **Send me**: (a) the Calendar booking link, (b) the Form link, (c) the Sheet ID, (d) the `Auralis — Clients` folder ID.

## THEN I do (Phase 2–4)
- Wire every “Book a free call” button on the site → your Calendar link (replaces the contact form).
- Build the **Apps Script** (onboarding + PDF + delivery + review) using your IDs; deploy it as the Stripe **webhook** endpoint (I give you the exact Stripe steps; the signing secret stays in Apps Script).
- Load the **email templates** (EN/DE/ES) into the automation.
- Give you the **Report Google Doc** template + the Claude Project workflow for drafting.

## End state
Desiree only: **approves each report** + **runs the 1:1s on Meet**. Booking, payment, onboarding, intake, PDF, delivery email, invoice, review = automatic.
