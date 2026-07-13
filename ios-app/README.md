# Auralis Natura — native iOS app (SwiftUI)

Premium, brand-first customer app on the proven Paramur architecture: hand-written
Xcode 16 project (`objectVersion 77`, `PBXFileSystemSynchronizedRootGroup` — new Swift
files are picked up automatically, no project-file edits per file), SwiftUI, iOS 17+,
**no third-party dependencies**, bundled brand fonts, light mode only.

## What's inside
- **5 tabs** — Start (journey KPIs + Balance score hero, action cards), Programme
  (webshop with lifestyle photos, detail views, sticky checkout via Stripe Payment
  Links in Safari), Termin (embedded /book web tool with floating menu + share bridge),
  Mein Weg (journey timeline, native 4-step intake sheet, documents, PDF report viewer
  with fit→4× zoom), Profil (language de/en/es, Face ID, change password, documents,
  links, delete-data request, logout).
- **Auth**: 24h token in Keychain only; Face ID via `SecAccessControl(.biometryCurrentSet)`;
  401 anywhere → session expiry with a friendly toast.
- **L10n**: code-table `L10n` enum, de/en/es with full key parity (audited).
- **Design system**: `Theme.swift` (CI v2 tokens, ANFont with Dynamic Type, sharp
  radius-0 cards) + `Components.swift` (brand bar with slogan, Fig.-tag section headers,
  pills, KPI tiles, skeletons, toasts, journey timeline).

## Build on the Mac
```bash
open ios-app/AuralisNatura.xcodeproj   # Xcode 16+
# Xcode → Signing & Capabilities → select your team (bundle id com.auralisnatura.app)
# Run on a device or simulator (Face ID: Simulator → Features → Face ID → Enrolled)
```
No packages to resolve, nothing to configure — fonts register at runtime.

## Quality loop (no Swift compiler needed here)
```bash
python3 ios-app/audit.py                       # L10n parity/coverage, brace balance,
                                               # asset+font refs, API paths vs server
python3 portal/tests/test_ios_contract.py      # 25-check server contract e2e (isolated)
```
Both green as of the last commit.

## First-build checklist (things only Xcode can verify)
1. All 18 Swift files compile as one module (synchronized group should pick them up).
2. Runtime font registration logs no CTFontManager errors; Fraunces renders in headlines.
3. Home KPI tiles: the ✓/– glyphs render acceptably in Fraunces (else swap to SF symbols).
4. Face ID on device (simulator needs Face ID enrolled).
5. App icon + launch screen (new emblem on warm paper) appear correctly.

## Server contract
Uses only live endpoints: login, me, intake, app/offers, my/documents,
my/report-token → my/report, my/change-password, my/delete-request, app/push-token.
Contract locked by `portal/tests/test_ios_contract.py`.
