# V2 Setup — status & remaining steps

Decisions locked: **Google Apps Script** engine · **free call in Google Calendar + existing Stripe links** · **manual Claude drafting to start**.

## ✅ Done
- Workspace tier: **Business Starter** · Data region: **Europe**
- Drive `Auralis — Clients` folder → ID `10awEfYBCt308Ap_3ksk6QTmKpoAN2KM1`
- `Auralis CRM` sheet → ID `1-YZW1wjQUy4b0GTcQGoqZ9Ief_MplqXYIRB5QT7U034`
- Intake Google Form → linked
- New brand logo live on the website (emblem, favicon, og-image)
- Built: Apps Script engine (`apps-script/Code.gs`), deployment guide, email templates, intake form spec, report-template spec, Calendar guide

## ⏳ Your remaining steps
1. **Calendar booking link** — follow `automation/CALENDAR-SETUP.md`, then send me the link.
2. **Report template Doc** — follow `automation/REPORT-TEMPLATE.md` (create the Google Doc in `_TEMPLATE`), then send me its **Doc ID**.
3. **Deploy the Apps Script** — follow `automation/apps-script/README.md` (paste code, set `WEBHOOK_TOKEN`, run `setupTriggers`, deploy web app).
4. **Connect Stripe** — add the webhook endpoint (README §F) using the web-app URL + `?token=`.
5. *(optional)* a **review link** for `REVIEW_URL`.

## THEN I finish
- Set `BOOKING_URL` + wire every “Book a free call” button on the site → your Calendar link.
- Final end-to-end test of the payment → onboarding → intake → deliver flow.

## End state
Desiree only: **approves each report** + **runs the 1:1s on Meet**. Booking, payment, onboarding, intake, PDF, delivery email, review = automatic.

---
### Captured config (for reference)
| Item | Value |
|---|---|
| Clients folder ID | `10awEfYBCt308Ap_3ksk6QTmKpoAN2KM1` |
| CRM sheet ID | `1-YZW1wjQUy4b0GTcQGoqZ9Ief_MplqXYIRB5QT7U034` |
| Intake form | `https://docs.google.com/forms/d/e/1FAIpQLSfOsX0hj1k_oI_mltKPxZ4wC2DAJKQWJiu-ZMMgvgbWzs3GSQ/viewform` |
| Calendar booking link | _pending_ |
| Report template Doc ID | _pending_ |
