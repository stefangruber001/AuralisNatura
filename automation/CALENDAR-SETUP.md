# Calendar — free 25-min discovery call (booking link)

Goal: a public page where anyone can book your free call; it auto-creates a Google Meet and sends reminders. Then paste the link into `apps-script/Code.gs` as `BOOKING_URL` and into the website.

> Requires Google Workspace (you have Business Starter, which includes **Appointment schedules**).

## Steps
1. Open **calendar.google.com** (on desktop).
2. Top-left **Create** (the + button) → **Appointment schedule**.
   - If you don't see it: top-right ⚙ **Settings → Appointment schedules**, or click any empty slot in the grid and pick the **Appointment schedule** tab.
3. **Title:** `Free 25-min discovery call`.
4. **Appointment duration:** 25 minutes.
5. **General availability:** set the windows you want to offer (e.g. Tue & Thu 18:00–20:00). You can add multiple windows.
6. **Booked appointment settings** (scroll down):
   - **Booking window:** e.g. can book up to 60 days ahead, must book at least 4 hours before.
   - **Buffer time:** e.g. 15 min between appointments (optional).
   - **Maximum bookings per day:** optional cap to protect your hours.
7. **Add Google Meet:** turn ON **"Add video conferencing — Google Meet"** so every booking gets a Meet link automatically.
8. **Booking form:** keep Name + Email (required). Optionally add one question: "In one line, what would you like help with?"
9. **Email reminders:** add reminders, e.g. **24 hours** and **1 hour** before.
10. Click **Save**.
11. Click the schedule again → **Open booking page** (or **Share → Copy link**). **Copy that link.**

## Then send me
Paste the booking link in the chat. I'll:
- set it as `BOOKING_URL` in the Apps Script, and
- wire every **"Book a free call"** button on the website to it.

### Optional: paid-session booking
If you also want clients to self-book their *paid* package sessions, create a second Appointment schedule (e.g. `Auralis session — 60 min`) the same way and send me that link too. Otherwise the welcome email's booking link can point to the same page.
