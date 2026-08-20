#!/usr/bin/env bash
# =============================================================================
#  enable_stripe.sh — close the purchase loop, on the server, in one command
# =============================================================================
#  Runs where the portal runs, and works out which that is:
#
#    • on Desiree's Mac   bash portal/deploy/enable_stripe.sh
#      (secrets live in portal/.env, loaded by start_auralis.command)
#
#    • on the Linux server (as root)
#      bash /opt/auralis/app/portal/deploy/enable_stripe.sh
#      (secrets live in /etc/auralis/portal.env, loaded by systemd)
#
#  Getting this wrong is the whole reason for the detection: writing the secret
#  into the file the running portal does NOT read leaves everything looking
#  correct and nothing working.
#
#  It asks for the webhook SIGNING SECRET (whsec_…), writes it into
#  /etc/auralis/portal.env, restarts the portal, and then PROVES the endpoint
#  now accepts Stripe: it posts a deliberately mis-signed event and requires a
#  400 ("bad signature") instead of the 503 ("not configured") the endpoint
#  answers while the secret is missing. That distinction is the whole point —
#  503 means a real payment would arrive and the portal would never hear of it.
#
#  ⚠️ IT IS NOT AN API KEY. This system has no sk_ secret key and never will:
#  verifying a webhook needs only the signing secret, so there is nothing here
#  that could move money or read a customer. If you are on the "API keys" page
#  you are in the wrong place — the secret lives under Developers → Webhooks,
#  on the endpoint itself, and starts with whsec_.
#
#  ⚠️ TEST MODE AND LIVE MODE HAVE DIFFERENT SECRETS. The payment links being
#  sold are live-mode links, so the endpoint must be created with the dashboard
#  toggle on LIVE. A test-mode secret verifies test events and rejects every
#  real one, which looks exactly like nothing happening.
#
#  FLAGS
#    --check           report what is configured now; change nothing
#    --secret-stdin    read the secret from stdin instead of prompting
#    --shop-on         also set shop_enabled=true in config.json (only once the
#                      distance-selling terms are settled — it is what puts buy
#                      buttons in front of real customers)
#    -h | --help
#
#  Exit codes: 0 ok · 1 usage/precondition · 2 the endpoint did not come up
#  verified · 3 write or restart failed. On a failed restart the previous env
#  file is restored and the service brought back.
# =============================================================================
set -Eeuo pipefail

# Where the portal actually runs. The script is the same either way; only the
# env file it writes and the way it restarts differ.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"     # …/portal
PORT="${AURALIS_PORT:-5056}"

if [ -f /etc/auralis/portal.env ] && command -v systemctl >/dev/null 2>&1; then
  PLATFORM="server"
  ENV_FILE="${AURALIS_ENV_FILE:-/etc/auralis/portal.env}"
  PORTAL_DIR="${AURALIS_APP_DIR:-/opt/auralis/app}/portal"
  VENV="${AURALIS_VENV:-/opt/auralis/venv}"
  SVC_USER="${AURALIS_USER:-auralis}"
  UNIT="auralis-portal.service"
  PY_BIN="$VENV/bin/python"
else
  PLATFORM="mac"
  ENV_FILE="${AURALIS_ENV_FILE:-$HERE/.env}"
  PORTAL_DIR="$HERE"
  VENV=""
  SVC_USER="$(id -un)"
  UNIT="com.auralis.portal"                                  # launchd label
  PY_BIN="$(command -v python3 || echo python3)"
fi

CHECK=0; SECRET_STDIN=0; SHOP_ON=0
while [ $# -gt 0 ]; do
  case "$1" in
    --check)        CHECK=1; shift ;;
    --secret-stdin) SECRET_STDIN=1; shift ;;
    --shop-on)      SHOP_ON=1; shift ;;
    -h|--help)      sed -n '2,40p' "$0"; exit 0 ;;
    *) printf 'unknown flag: %s (try --help)\n' "$1" >&2; exit 1 ;;
  esac
done

C_0=$'\033[0m'; C_G=$'\033[32m'; C_Y=$'\033[33m'; C_R=$'\033[31m'; C_B=$'\033[1m'
step(){ printf '\n%s▸ %s%s\n' "$C_B" "$*" "$C_0"; }
say(){  printf '    %s\n' "$*"; }
ok(){   printf '  %s✔%s %s\n' "$C_G" "$C_0" "$*"; }
warn(){ printf '  %s!%s %s\n' "$C_Y" "$C_0" "$*"; }
die(){  local c="$1"; shift; printf '\n  %s✖ %s%s\n\n' "$C_R" "$*" "$C_0" >&2; exit "$c"; }

[ -d "$PORTAL_DIR" ] || die 1 "$PORTAL_DIR not found — run this from the portal checkout."
if [ "$PLATFORM" = "server" ]; then
  [ "$(id -u)" -eq 0 ] || die 1 "on the server this must run as root: sudo bash $0"
  [ -f "$ENV_FILE" ]   || die 1 "$ENV_FILE not found — is this the portal server?"
fi
# The Mac keeps its secrets in portal/.env. Do NOT create it here: a rejected
# secret must leave the filesystem exactly as it found it, and a stray empty
# .env next to a typo'd path is a puzzle for later. It is created at write time.
say "detected: $PLATFORM · env file $ENV_FILE · restart via ${UNIT}"

# ── what is true right now ───────────────────────────────────────────────────
probe() {   # prints: the HTTP status the webhook gives a deliberately bad signature
  curl -s -o /dev/null -w '%{http_code}' -m 8 \
    -X POST "http://127.0.0.1:$PORT/api/stripe/webhook" \
    -H 'Content-Type: application/json' \
    -H 'Stripe-Signature: t=1,v1=0000000000000000000000000000000000000000000000000000000000000000' \
    -d '{"id":"evt_probe","type":"checkout.session.completed","data":{"object":{}}}' 2>/dev/null
}

describe() {
  local code="$1"
  case "$code" in
    400) ok  "the webhook is CONFIGURED — it refused a forged signature (400), which is
       exactly right. A genuine Stripe event will be accepted." ;;
    503) warn "the webhook is NOT configured — it answers 503. Money would arrive in Stripe
       and the portal would never hear about it." ;;
    000) if [ "$PLATFORM" = "server" ]; then
           warn "no answer on 127.0.0.1:$PORT — is the portal running? (systemctl status $UNIT)"
         else
           warn "no answer on 127.0.0.1:$PORT — is the portal running? Start it with
       $PORTAL_DIR/start_auralis.command, or launchctl list | grep $UNIT"
         fi ;;
    *)   warn "unexpected status $code from the webhook endpoint" ;;
  esac
}

if [ "$CHECK" -eq 1 ]; then
  step "Checking the purchase loop"
  if grep -qE '^[[:space:]]*AURALIS_STRIPE_WEBHOOK_SECRET=..' "$ENV_FILE"; then
    ok "AURALIS_STRIPE_WEBHOOK_SECRET is present in $ENV_FILE"
  else
    warn "AURALIS_STRIPE_WEBHOOK_SECRET is NOT in $ENV_FILE"
  fi
  describe "$(probe)"
  say ""
  if [ "$PLATFORM" = "server" ]; then
    say "Full picture:  sudo -u $SVC_USER $PY_BIN $PORTAL_DIR/tools/preflight.py --no-agent --no-pdf"
  else
    say "Full picture:  cd $PORTAL_DIR && python3 tools/preflight.py --no-agent --no-pdf"
  fi
  exit 0
fi

# ── the secret ───────────────────────────────────────────────────────────────
step "The webhook signing secret"
say "Stripe Dashboard → Developers → Webhooks → your endpoint → 'Signing secret'."
say "It starts with whsec_ . It is NOT an API key and NOT an sk_ key."
say "Make sure the dashboard is in LIVE mode — test mode has a different secret."
say ""
if [ "$SECRET_STDIN" -eq 1 ]; then
  IFS= read -r SECRET || true
else
  printf '    Paste it (hidden): '
  IFS= read -rs SECRET || true
  printf '\n'
fi
SECRET="$(printf '%s' "$SECRET" | tr -d '[:space:]')"

[ -n "$SECRET" ] || die 1 "nothing entered — $ENV_FILE is untouched."
case "$SECRET" in
  whsec_*) ;;
  sk_*|rk_*|pk_*)
    die 1 "that is an API key, not a webhook secret. This system must never hold an
     sk_ key. Go to Developers → Webhooks → your endpoint → Signing secret (whsec_…)." ;;
  *) die 1 "a signing secret starts with whsec_ — that does not. Nothing was written." ;;
esac
[ "${#SECRET}" -ge 24 ] || die 1 "that secret looks too short to be real. Nothing was written."
ok "shape looks right (whsec_…, ${#SECRET} characters)"

# ── write it ─────────────────────────────────────────────────────────────────
step "Writing $ENV_FILE"
if [ -f "$ENV_FILE" ]; then
  BACKUP="$ENV_FILE.bak-$(date +%Y%m%d-%H%M%S)"
  cp -p "$ENV_FILE" "$BACKUP" && chmod 0600 "$BACKUP"
  say "previous file kept at $BACKUP (0600, owner-only)"
else
  : > "$ENV_FILE"; chmod 0600 "$ENV_FILE"
  BACKUP="$ENV_FILE.bak-$(date +%Y%m%d-%H%M%S)"; : > "$BACKUP"; chmod 0600 "$BACKUP"
  say "created $ENV_FILE (this is its first secret)"
fi

TMP="$(mktemp "$(dirname "$ENV_FILE")/.portal.env.XXXXXX")"
if [ "$PLATFORM" = "server" ]; then chmod 0640 "$TMP"; chown "root:$SVC_USER" "$TMP"
else chmod 0600 "$TMP"; fi
{
  # drop only the key we own; everything else stays byte-for-byte
  grep -vE '^[[:space:]]*AURALIS_STRIPE_WEBHOOK_SECRET=' "$ENV_FILE" || true
  # no quotes: systemd keeps them literally, and a quoted secret is a different secret
  printf 'AURALIS_STRIPE_WEBHOOK_SECRET=%s\n' "$SECRET"
} > "$TMP"
mv -f "$TMP" "$ENV_FILE"
ok "$ENV_FILE updated"

# ── optionally open the shop ─────────────────────────────────────────────────
CFG="$PORTAL_DIR/config/config.json"
if [ "$SHOP_ON" -eq 1 ]; then
  step "Turning the shop on"
  [ -f "$CFG" ] || die 3 "$CFG not found"
  cp -p "$CFG" "$CFG.bak-$(date +%Y%m%d-%H%M%S)"
  "$VENV/bin/python" - "$CFG" <<'PY' || die 3 "could not update config.json"
import json, sys, pathlib
p = pathlib.Path(sys.argv[1]); c = json.loads(p.read_text(encoding="utf-8"))
c["shop_enabled"] = True
p.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
  ok "shop_enabled=true — buy buttons will appear in the app and the portal"
  warn "only correct once the distance-selling terms (withdrawal right, pre-contractual
       information, invoice/IVA) are settled with the gestoría."
fi

# ── restart and PROVE it ─────────────────────────────────────────────────────
step "Restarting the portal"
restore_and_die() {
  printf '\n%s  Restoring %s from %s%s\n' "$C_Y" "$ENV_FILE" "$BACKUP" "$C_0" >&2
  cp -p "$BACKUP" "$ENV_FILE"
  [ "$PLATFORM" = "server" ] && { chmod 0640 "$ENV_FILE"; chown "root:$SVC_USER" "$ENV_FILE"; systemctl restart "$UNIT" >/dev/null 2>&1 || true; }
  die 3 "$1"
}
if [ "$PLATFORM" = "server" ]; then
  systemctl restart "$UNIT" || die 3 "systemctl restart $UNIT failed — journalctl -u $UNIT -n 50"
  sleep 3
  systemctl is-active --quiet "$UNIT" || {
    journalctl -u "$UNIT" -n 30 --no-pager 2>/dev/null | sed -e 's/^/     /' >&2 || true
    restore_and_die "$UNIT did not stay up with the new env file — rolled back."
  }
else
  # launchd has KeepAlive on, so stopping the job is enough to bring it back with
  # the new .env; kickstart -k does both in one step where it is available.
  launchctl kickstart -k "gui/$(id -u)/$UNIT" 2>/dev/null \
    || { launchctl unload "$HOME/Library/LaunchAgents/$UNIT.plist" 2>/dev/null || true
         launchctl load -w "$HOME/Library/LaunchAgents/$UNIT.plist" 2>/dev/null \
         || warn "no launchd job found — restart start_auralis.command by hand"; }
  sleep 5
fi
ok "portal restarted"

step "Proving the endpoint is live"
# A forged signature must now be REFUSED (400). While the secret was missing the
# same request got 503, so this single status tells us the secret was loaded —
# without needing a real payment to find out.
CODE="$(probe)"
describe "$CODE"
[ "$CODE" = "400" ] || die 2 "the webhook did not come up configured (status $CODE).
     The secret is written; check journalctl -u $UNIT -n 50."

step "What is still open"
if [ "$PLATFORM" = "server" ]; then
  sudo -u "$SVC_USER" "$PY_BIN" "$PORTAL_DIR/tools/preflight.py" --no-agent --no-pdf 2>/dev/null \
    | grep -E 'golive_(mail|shop)' -A 6 || true
else
  ( cd "$PORTAL_DIR" && "$PY_BIN" tools/preflight.py --no-agent --no-pdf 2>/dev/null ) \
    | grep -E 'golive_(mail|shop)' -A 6 || true
fi

cat <<EOF

  ${C_G}${C_B}Done.${C_0}

  Test it for real, once:
    1. Stripe → Developers → Webhooks → your endpoint → "Send test webhook"
       → checkout.session.completed. It should show a 200.
    2. Or buy the cheapest programme with a real card and refund yourself:
       within seconds the Betriebskonsole shows her under Customer Journey
       card 03, paid, with access sent — and you get a "💶 Verkauf" mail.

  Turn the shop off again:
    ${VENV}/bin/python - <<'PY'
import json,pathlib
p=pathlib.Path("$CFG"); c=json.loads(p.read_text()); c["shop_enabled"]=False
p.write_text(json.dumps(c,ensure_ascii=False,indent=2)+"\n")
PY
    restart the portal (launchctl kickstart -k gui/$(id -u)/com.auralis.portal, or systemctl restart auralis-portal)

EOF
