# Auralis Natura — Customer App (iOS + Android)

The client-facing mobile app, built with **Capacitor**. It wraps a bundled web UI
(`www/`) that talks to the existing portal API (`api.auralisnatura.com`). Same brand,
plus native **push notifications**, **Face-ID/fingerprint login**, **offline** access,
and **in-app programme purchase** via Stripe.

Low-cost by design (per the founder's standing preference): open-source plugins,
Firebase free tier for push, and Stripe **Payment Links** for the shop (no extra fees,
no PaymentIntent server, no keys in the app). Over-the-air updates are optional and can
run on a self-hosted Capgo endpoint or OtaKit's free tier — off by default.

## What's here
```
app/
├── capacitor.config.json   native config (bundled webDir=www, splash, status bar)
├── package.json            deps + scripts
├── resources/              icon.png (1024) + splash(-dark).png → source for icon/splash sets
└── www/                    the app itself (no build step — plain HTML/CSS/JS)
    ├── index.html          shell (top bar host + bottom tab bar)
    ├── styles.css          CI v2 design, native-tuned (safe areas, tabs)
    ├── config.js           API base + Stripe Payment Links (offline fallback)
    ├── app.js              router, API client, native bridges, all views + shop
    └── assets/seal.png     brand mark
```
`ios/` and `android/` are **generated on the Mac** (git-ignored) — see below.

## Build it on the Mac (one time)
Prereqs: Node ≥ 18, Xcode (iOS), Android Studio (Android), a paid Apple Developer
account for the store + push.

```bash
cd app
npm install                    # fetch Capacitor + plugins
npx cap add ios                # create the iOS project
npx cap add android            # create the Android project
npm run assets                 # generate icon/splash sets INTO the native projects (needs them to exist first)
npx cap sync                   # copy www/ + install native deps
npx cap open ios               # → Xcode: sign in (your Apple ID), auto-signing, Run
npx cap open android           # → Android Studio: Run
```
> Order matters: `cap add` creates `ios/` and `android/`; `npm run assets` writes the
> generated icons/splashes **into** those projects, so it must run **after** `cap add`.

### Push notifications (Firebase, free)
1. Create a Firebase project → add an **iOS** app (bundle id `com.auralisnatura.app`) and
   an **Android** app (same package). Download `GoogleService-Info.plist` → `ios/App/App/`,
   and `google-services.json` → `android/app/`.
2. Apple Developer → Keys → create an **APNs auth key** (`.p8`) → upload it in the Firebase
   console (Cloud Messaging). Push only works on a **physical iPhone**, not the simulator.

### Shop (Stripe Payment Links)
The shop reads offers live from `GET /api/app/offers` (falls back to `www/config.js`).
Each package's `buy_url` is a **Stripe Payment Link** you create in the Stripe Dashboard.
`root` and `bloom` are pre-filled; paste the **Flourishing** link into
`portal/config/config.json → packages` (or `www/config.js`) when ready. Coaching is a
person-to-person service, so this is compliant and Apple/Google take **no** commission.

### Optional: over-the-air updates (free)
Ship content updates without a store review. In `capacitor.config.json` set
`CapacitorUpdater.autoUpdate: true` and point it at a **self-hosted Capgo** server or
**OtaKit** free tier. Native changes still go through the normal store review.

## Test in a browser (no Mac needed)
```bash
npm run serve      # serves www/ at http://localhost:8100
# open with an API override, e.g.:  http://localhost:8100/?api=http://127.0.0.1:5056
```
Native features (Face ID, push, haptics) no-op gracefully on the web; everything else —
login, home, booking, intake, report, shop — runs exactly as in the app.

## Before you submit — compliance checklist (health app)
This app collects self-reported wellbeing data, so both stores treat it as a health app.
Complete these or the app is auto-rejected:
- **Privacy Policy URL** in both listings, and a **Privacy/Terms link inside the app**
  (already in Profile → points to `impressum.html`). Apple 5.1.1(i) requires the in-app link.
- **Apple App Privacy labels** (App Store Connect → App Privacy): declare *Health & Fitness*
  data, linked to identity, used for "App Functionality" only; encrypted in transit.
- **Google Play Data Safety** form: health data, collected, encrypted in transit, not sold.
- **Google Play Health apps declaration** form (required for health/wellbeing apps).
- **App Review notes (Apple)**: state plainly that purchases are **real-world person-to-person
  coaching services** (human sessions + a personally-delivered report), so external Stripe
  payment is permitted under guideline **3.1.3(d)** — the app does not sell digital content.
  Provide a demo client login for the reviewer.
- Keep the shop wording **service-framed** ("Buchen"/"Book a programme"), never "unlock content".

## Push notifications = opt-in
The app does **not** prompt for notifications on launch. The user enables them in
Profile → "Erinnerungen aktivieren", which then registers the device token. This is the
Apple-preferred contextual opt-in and improves acceptance rates.

## Fonts
`www/fonts/fraunces.woff2` + `hanken.woff2` are loaded if present; otherwise the app
falls back to a premium system serif/sans (fully offline-safe). Drop the two `.woff2`
files in for pixel-exact brand type.
