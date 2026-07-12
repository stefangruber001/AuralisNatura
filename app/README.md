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
npm run assets                 # generate all icon/splash sizes from resources/icon.png
npx cap add ios                # create the iOS project
npx cap add android            # create the Android project
npx cap sync                   # copy www/ + install native deps
npx cap open ios               # → Xcode: sign in (your Apple ID), auto-signing, Run
npx cap open android           # → Android Studio: Run
```

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

## Fonts
`www/fonts/fraunces.woff2` + `hanken.woff2` are loaded if present; otherwise the app
falls back to a premium system serif/sans (fully offline-safe). Drop the two `.woff2`
files in for pixel-exact brand type.
