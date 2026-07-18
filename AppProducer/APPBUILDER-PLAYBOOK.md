# AppBuilder — iOS ship-to-TestFlight/App-Store playbook

**Canonical source:** [`.claude/agents/appbuilder.md`](../.claude/agents/appbuilder.md) — the
invokable **AppBuilder** subagent. Its system prompt is the full playbook; copy that file
into any repo/template to carry the learnings forward. This doc mirrors the essentials for
humans.

Mac-free pipeline: GitHub Actions (`macos-26`) + Fastlane + `match` → TestFlight/App Store.
Lanes in `.github/workflows/ios-testflight.yml`: `create_app · beta · internal_testers ·
tf_status · release · signing`.

## The only human inputs
- Secrets: **`ASC_KEY_P8_BASE64`** (private `.p8`, never committed) + **`MATCH_PASSWORD`**.
- Baked defaults: `ASC_KEY_ID`, `APPLE_TEAM_ID`, `ASC_ISSUER_ID`.
- One ASC API key is **account-wide** (signs all apps). The `.p8` and its Key ID must be the
  **same key** or auth fails. `.p8` won't download in an iPhone browser — use a computer.

## Gotchas (each cost a real CI failure)
1. `produce` is unusable on CI (needs Apple ID username) → register Bundle ID + verify app
   record via `Spaceship::ConnectAPI` directly.
2. `BundleId.create` needs `platform: "IOS"`.
3. Apple's API **cannot create the app record** — make it once in the UI, or match the build's
   bundle id to an existing record (mismatch → upload "Couldn't find app").
4. pbxproj (objectVersion 77): `SWIFT_VERSION` in **both** Debug + Release.
5. Synchronized groups auto-add `Info.plist` to resources → add a
   `PBXFileSystemSynchronizedBuildFileExceptionSet` excluding it.
6. App Store requires the **iOS 26 SDK** → `macos-26` + **newest** `Xcode_26*.app` (never pin
   26.0 — actool simulator-runtime mismatch).
7. `Info.plist` → `ITSAppUsesNonExemptEncryption = false` (skips the compliance gate).
8. `match`: distribution cert account-wide; profile per-app (auto-created). Use an **Admin** key.
9. Internal group with `has_access_to_all_builds` (pass `public_link_*: nil`); add testers in
   the UI (API blocked); each tester accepts the email invite once — then all builds auto-flow.
10. `deliver` = metadata + screenshots only. Privacy labels, age rating, pricing, demo login,
    **Submit** are UI-only. Keep `submit_for_review: false`.
11. Screenshots: HTML→PNG (Playwright) at 1320×2868, localized — not a UITest/simulator target.
    Generator: `ios-app/scripts/gen_screenshots.py`.
12. **Match locales to the app's real ASC localizations** — `deliver` fills only the locale
    folders you provide. If the primary is **English (U.K.) `en-GB`** but you only gave `en-US`,
    the listing shows empty (and blocks submission). Mirror en-US→en-GB. "Didn't upload?" →
    first switch the ASC language dropdown; the content is usually under another locale.
13. **Split deliver lanes** — fast `release` (metadata + review info, `skip_screenshots:true`)
    vs a separate `screenshots` lane (`skip_metadata:true`, `overwrite_screenshots:true`). A
    full screenshot overwrite can hang deliver for many minutes; don't couple it with metadata.
14. **Review demo login**: login is **client_id + password**. Provision a fixed-credential
    account on the host with `portal/tools/create_review_client.py`, and put the creds in
    `metadata/review_information/demo_user.txt` + `demo_password.txt` (and/or the ASC UI).

## Go-live order
`create_app` → `beta` → `internal_testers` (+ add members/accept invites) → `release` →
founder does UI items (privacy, age rating, pricing, demo login, attach build) → **Submit**.

## Verify before "done"
`python3 ios-app/audit.py` · `python3 portal/tests/test_ios_contract.py` · and **read the job
log** — a `success` conclusion can hide a rescued error; a ~3s fast-fail = missing/mismatched key.
