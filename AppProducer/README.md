# AppProducer — App Store Connect signing key

This folder holds the **App Store Connect API key** used by the iOS TestFlight
pipeline (`.github/workflows/ios-testflight.yml` → `ios-app/fastlane/Fastfile`).

- **`AuthKey_5695PLUZS2.p8`** — the account-wide "Paramur CI" API key (App Manager).
  One App Store Connect API key is **account/Team-wide, not per-app**, so this same
  key signs *every* app on the team (Auralis Natura and Paramur alike). Key ID
  `5695PLUZS2`, Issuer ID `10347fb1-a3c7-4894-a183-18d98a79a8d0`, Team ID `5V62K942X6`.

The Fastfile reads the key from a GitHub Actions **secret** (`ASC_KEY_P8_BASE64`)
if one is set; otherwise it falls back to this file. The key is kept here at the
founder's explicit request so no secret has to be re-entered each session.

## Security notes
- This is a **private** repository. The GitHub Pages deploy (`deploy-pages.yml`)
  publishes a strict allow-list (`index.html`, `impressum.html`, a few text files,
  `images/`) into `_site/` — it never copies `AppProducer/`, so this key is **not**
  exposed on the public website.
- Because the key is account-wide, treat it as sensitive: if it is ever exposed
  outside this repo, revoke it in App Store Connect → Users and Access →
  Integrations and generate a new one (then update this file or the secret).
- The more locked-down alternative is to store the key **only** as the encrypted
  `ASC_KEY_P8_BASE64` GitHub Actions secret and delete this file; the pipeline
  supports that with no other change.
