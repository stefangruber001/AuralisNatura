# Auralis Natura → App Store / TestFlight — Mac-free pipeline

The whole build runs in the cloud on GitHub's macOS runner (latest Xcode = latest
iOS SDK), signs itself with `fastlane match`, and uploads to TestFlight. **You only
need a browser.** I (Claude) set up the pipeline; you do only the steps Apple insists
be personal. Mirrors the Paramur playbook.

## The 6 steps
| # | Who | Step |
|---|---|---|
| 1 | **You** | Apple Developer Program — enrol (99 €/yr) at developer.apple.com |
| 2 | Claude ✓ | Pipeline — GitHub Actions + Fastlane + match (done, in this repo) |
| 3 | **You** | Create the App Store Connect **API key** + the **app record** + add **5 GitHub Secrets** (below) |
| 4 | Claude ✓ | Build — trigger the workflow, read logs, fix errors → TestFlight |
| 5 | Claude ✓ | Assets — screenshots + store texts (see `STORE-LISTING.md`) |
| 6 | **You** | Upload assets, add demo login to review notes, **Submit for Review** |

## Step 3 — the one-time setup (browser only)

### a) App Store Connect API key  (App Store Connect → **Users and Access → Integrations → App Store Connect API**)
1. Click **+** to generate a key with the **App Manager** role. Give it a name (e.g. "CI").
2. Note the **Key ID** and the **Issuer ID** (shown at the top of the page).
3. **Download the `AuthKey_XXXXXX.p8` file** — Apple lets you download it *once*. Keep it safe.

### b) Base64-encode the .p8  (so it can live in a secret)
On any Mac/Linux terminal (e.g. Desiree's Mac):
```bash
base64 -i AuthKey_XXXXXX.p8 | tr -d '\n'        # macOS
base64 -w0 AuthKey_XXXXXX.p8                     # Linux
```
Copy the **single long line** it prints — that's the value for `ASC_KEY_P8_BASE64`.

### c) Create the app record  (App Store Connect → **Apps → +**)
- Platform **iOS**, Name **Auralis Natura**, Primary language **German**,
  Bundle ID **`com.auralisnatura.app`** (must match exactly), SKU e.g. `auralis-app`.

### d) Add the 5 GitHub Secrets  (GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**)
| Secret name | Value | Where to find it |
|---|---|---|
| `ASC_KEY_ID` | the Key ID | App Store Connect → Integrations (the key you made) |
| `ASC_ISSUER_ID` | the Issuer ID | App Store Connect → Integrations (top of page) |
| `ASC_KEY_P8_BASE64` | the long base64 line | from step (b) |
| `APPLE_TEAM_ID` | your 10-char Team ID | developer.apple.com → Membership details |
| `MATCH_PASSWORD` | a passphrase **you invent** | anything strong — it encrypts the signing certs. Save it in your password manager. |

That's it — no Apple ID, no password, no certificates by hand. `match` creates the
distribution certificate + provisioning profile on the first run and stores them
**encrypted** in a `match-storage` branch of this repo (git auth uses the built-in
`GITHUB_TOKEN`, so nothing extra to configure).

## Step 4 — run the build
GitHub repo → **Actions** tab → **iOS · TestFlight** → **Run workflow** → lane `beta` → **Run**.

- First run: creates the signing cert/profile, builds, and uploads to TestFlight
  (build number auto-derives from the latest TestFlight build, always increments).
- ~8–12 minutes. When it's green, the build appears in **App Store Connect → TestFlight**
  after Apple finishes processing (a few minutes more).
- If it fails, open the run log — send it to me and I'll fix it in the repo, then you
  just re-run. (The `signing` lane is available separately if you ever need to reset certs.)

## For every future update
Bump nothing by hand — just **Run workflow → beta** again. The build number climbs on
its own and the new build lands in TestFlight. (To submit a new version for public
release, raise `MARKETING_VERSION` in the project and Submit for Review in App Store Connect.)

## Notes
- **Health-app compliance** (required before public release, not for TestFlight): App
  Privacy labels, Google-style data handling, the privacy-policy URL, and the review
  demo-login — all covered in `STORE-LISTING.md` and the app's `README.md` checklist.
- Runner is `macos-15` (Xcode 16) because the project uses `objectVersion 77`.
