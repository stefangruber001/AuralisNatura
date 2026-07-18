# AppProducer — iOS signing / App Store Connect notes

> **AppBuilder playbook:** the full ship-to-store learnings live in
> [`APPBUILDER-PLAYBOOK.md`](APPBUILDER-PLAYBOOK.md) and the invokable subagent
> [`.claude/agents/appbuilder.md`](../.claude/agents/appbuilder.md). Copy the agent file into
> any repo/template to reuse it.


The iOS TestFlight pipeline (`.github/workflows/ios-testflight.yml` →
`ios-app/fastlane/Fastfile`) authenticates to Apple with an **App Store Connect API
key**.

## Where the key lives (important)
- The private `.p8` is stored **only** as the GitHub Actions secret
  **`ASC_KEY_P8_BASE64`** (Settings → Secrets and variables → Actions), encrypted at
  rest. **It is never committed to this repo.** The Fastfile reads it from the secret
  and fails with a clear message if it is missing.
- Non-secret identifiers are baked into the workflow as defaults (overridable via
  same-named secrets):
  - **Key ID** `JR5U6K9HHB` (`ASC_KEY_ID`) — the `.p8` in `ASC_KEY_P8_BASE64` must belong to this Key ID
  - **Issuer ID** `10347fb1-a3c7-4894-a183-18d98a79a8d0` (`ASC_ISSUER_ID`)
  - **Team ID** `5V62K942X6` (`APPLE_TEAM_ID`)
  - **Bundle ID** `com.auralisnatura.app`

## To rotate the key
Generate a new key in App Store Connect → Users and Access → Integrations, update the
`ASC_KEY_P8_BASE64` secret with the new `.p8` contents, and (if the Key ID changed)
update the `ASC_KEY_ID` default in the workflow or set it as a secret.
