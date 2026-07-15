#!/usr/bin/env bash
# One-shot: base64-encode the .p8 and push ALL 5 GitHub Actions secrets for the
# Auralis TestFlight pipeline — so you never click through the GitHub Secrets UI.
#
# Prereq: the GitHub CLI, logged in.   brew install gh   &&   gh auth login
# Nothing is sent anywhere except GitHub's encrypted secret store.
#
# Usage (all flags optional — you'll be prompted for anything missing):
#   ./setup-secrets.sh \
#       --key-id ABC123DEF4 \
#       --issuer-id 12345678-aaaa-bbbb-cccc-1234567890ab \
#       --p8 ~/Downloads/AuthKey_ABC123DEF4.p8 \
#       --team-id 1A2B3C4D5E \
#       --repo stefangruber001/auralisnatura
# (MATCH_PASSWORD is prompted for, hidden.)
set -euo pipefail

KEY_ID=""; ISSUER_ID=""; P8=""; TEAM_ID=""; REPO=""; MATCH_PW=""
while [ $# -gt 0 ]; do
  case "$1" in
    --key-id) KEY_ID="$2"; shift 2;;
    --issuer-id) ISSUER_ID="$2"; shift 2;;
    --p8) P8="$2"; shift 2;;
    --team-id) TEAM_ID="$2"; shift 2;;
    --repo) REPO="$2"; shift 2;;
    --match-password) MATCH_PW="$2"; shift 2;;
    *) echo "Unknown option: $1"; exit 1;;
  esac
done

command -v gh >/dev/null || { echo "❌ GitHub CLI not found. Install: brew install gh"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "❌ Not logged in. Run: gh auth login"; exit 1; }

# Repo: use the flag, else the current git remote.
if [ -z "$REPO" ]; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"
fi
[ -z "$REPO" ] && read -r -p "GitHub repo (owner/name): " REPO

prompt() { local v; read -r -p "$1: " v; echo "$v"; }
[ -z "$KEY_ID" ]    && KEY_ID="$(prompt 'App Store Connect Key ID')"
[ -z "$ISSUER_ID" ] && ISSUER_ID="$(prompt 'Issuer ID')"
[ -z "$TEAM_ID" ]   && TEAM_ID="$(prompt 'Apple Team ID (10 chars)')"
if [ -z "$P8" ]; then read -r -p "Path to AuthKey_*.p8: " P8; fi
P8="${P8/#\~/$HOME}"
[ -f "$P8" ] || { echo "❌ .p8 file not found: $P8"; exit 1; }
if [ -z "$MATCH_PW" ]; then
  read -r -s -p "Choose a MATCH_PASSWORD (encrypts your signing certs, save it!): " MATCH_PW; echo
fi
[ -z "$MATCH_PW" ] && { echo "❌ MATCH_PASSWORD cannot be empty"; exit 1; }

# base64 the key WITHOUT line wraps (works on macOS + Linux)
P8_B64="$(base64 < "$P8" | tr -d '\n')"

echo "→ Setting secrets on $REPO …"
gh secret set ASC_KEY_ID        -R "$REPO" -b"$KEY_ID"
gh secret set ASC_ISSUER_ID     -R "$REPO" -b"$ISSUER_ID"
gh secret set APPLE_TEAM_ID     -R "$REPO" -b"$TEAM_ID"
gh secret set ASC_KEY_P8_BASE64 -R "$REPO" -b"$P8_B64"
gh secret set MATCH_PASSWORD    -R "$REPO" -b"$MATCH_PW"

echo "✓ All 5 secrets set on $REPO."
echo "  Next: GitHub → Actions → 'iOS · TestFlight' → Run workflow →"
echo "        'create_app' (once, makes the App Store record), then 'beta' (build → TestFlight)."
