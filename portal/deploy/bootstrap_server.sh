#!/usr/bin/env bash
# =============================================================================
#  bootstrap_server.sh — RUNS AS ROOT **ON THE HETZNER SERVER**, no Mac needed
# =============================================================================
#  migrate_to_server.sh assumes a working Mac to lift the database, the secrets
#  and the tunnel credentials off. This is the path for when there is no Mac:
#  everything is created HERE, and the only other thing you need is a browser
#  (a phone is fine) to approve two logins.
#
#  WHERE THIS RUNS:  in the Hetzner Cloud Console's web terminal, as root, or
#                    over SSH if you have it. Interactive — it asks questions.
#
#      bash /root/auralis-src/portal/deploy/bootstrap_server.sh
#
#  WHAT IT CREATES (nothing is carried over from anywhere):
#    · fresh AURALIS_API_KEY / AURALIS_SECRET / AURALIS_DATA_KEY
#    · a NEW Cloudflare tunnel + its DNS record, via a browser login
#    · a Claude subscription token for the report agent, via a browser login
#    · then it hands all of that to install_server.sh, which does the real work
#
#  ⚠ A FRESH AURALIS_DATA_KEY MEANS A FRESH, EMPTY DATABASE.
#  The old Mac database can only ever be opened by the old key. If the Mac's
#  portal/.env and auralis.db turn up later, §"Adopting the old data" at the
#  bottom of the output explains how to bring them in — but you cannot mix a new
#  key with an old database, and this script will never pretend otherwise.
#
#  ⚠ THIS HOST ALSO RUNS ANOTHER COMPANY'S PRODUCTION ERP ("canei-erp").
#  This script writes only to /root/.auralis-payload and then delegates to
#  install_server.sh, which carries the co-tenant safety rules. It installs
#  cloudflared by unpacking the official .deb — never `dpkg -i`, so no apt
#  source and no root cron are added to the shared host.
#
#  Exit codes: 0 ok · 10 not root · 15 bad environment · 30 deploy key not yet
#  authorised in GitHub (re-run after adding it) · other = install_server.sh's
# =============================================================================
set -Eeuo pipefail

readonly SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
readonly PAYLOAD="/root/.auralis-payload"
readonly CF_BIN_DIR="/opt/auralis/cloudflared"
PUB_HOST="${AURALIS_HOSTNAME:-api.auralisnatura.com}"
TUNNEL_NAME="${AURALIS_TUNNEL_NAME:-auralis}"
# Derived after the Gmail password prompt below, not fixed here: email_mode=draft
# with no password is the silent-no-mail state (mailer just returns "skipped").
EMAIL_MODE="${AURALIS_EMAIL_MODE:-}"

if [ -t 1 ]; then B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; D=$'\033[2m'; N=$'\033[0m'
else B=''; G=''; Y=''; R=''; D=''; N=''; fi
STEP=0
step() { STEP=$((STEP + 1)); printf '\n%s[%d] %s%s\n' "$B" "$STEP" "$1" "$N"; }
ok()   { printf '   %s✓%s %s\n' "$G" "$N" "$1"; }
info() { printf '   %s·%s %s\n' "$D" "$N" "$1"; }
warn() { printf '   %s!%s %s\n' "$Y" "$N" "$1" >&2; }
die()  { printf '\n%s✗ %s%s\n' "$R" "$2" "$N" >&2; exit "$1"; }
trap '_rc=$?; [ $_rc -eq 0 ] || printf "\n%s✗ bootstrap failed at line %s (exit %s)%s\n" "$R" "$LINENO" "$_rc" "$N" >&2' ERR

# The payload holds every secret this server will ever hold. Root-only, and gone
# on every exit path — including a failure — because /root is not a safe place to
# leave a Fernet key lying around either.
cleanup() { local rc=$?; [ -d "$PAYLOAD" ] && rm -rf -- "$PAYLOAD"; exit $rc; }
trap cleanup EXIT INT TERM

ask() { # ask <prompt> <default>  → echoes the answer
  local p="$1" d="${2:-}" a=""
  if [ -n "$d" ]; then printf '   %s [%s]: ' "$p" "$d" >&2; else printf '   %s: ' "$p" >&2; fi
  read -r a || true
  printf '%s' "${a:-$d}"
}
ask_secret() { # never echoed, never defaulted
  local p="$1" a=""
  printf '   %s (input hidden, Enter to skip): ' "$p" >&2
  stty -echo 2>/dev/null || true; read -r a || true; stty echo 2>/dev/null || true
  printf '\n' >&2; printf '%s' "$a"
}
confirm() {
  local a=""; printf '   %s%s%s [y/N] ' "$B" "$1" "$N"; read -r a || true
  case "$a" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

[ "$(id -u)" -eq 0 ] || die 10 "must run as root (use the Hetzner console's root shell)"
[ -f "$SELF_DIR/install_server.sh" ] || die 15 "install_server.sh is not next to this script — is the clone complete?"

printf '%s\nAuralis Natura — build the portal on this server (no Mac required)%s\n' "$B" "$N"
info "hostname : $PUB_HOST"
info "tunnel   : $TUNNEL_NAME (created fresh)"
info "data     : a NEW empty encrypted database with a NEW key"
printf '\n'
warn "If the old Mac database still exists somewhere, STOP and read the warning"
warn "at the top of this file first — a new key can never open the old database."
confirm "Continue with a fresh install?" || { printf '   Nothing changed.\n'; exit 0; }

mkdir -p "$PAYLOAD"; chmod 700 "$PAYLOAD"

# ── 1. secrets ───────────────────────────────────────────────────────────────
step "Generate the secrets"
command -v python3 >/dev/null 2>&1 || { apt-get update -qq || true; DEBIAN_FRONTEND=noninteractive apt-get install -y python3 >/dev/null; }
# cryptography may not be present yet; Fernet keys are just 32 random bytes in
# urlsafe-base64, so generate them without adding a dependency at this stage.
gen_key() { python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"; }
gen_hex() { python3 -c "import secrets;print(secrets.token_urlsafe(48))"; }
API_KEY="$(gen_hex)"; SECRET="$(gen_hex)"; DATA_KEY="$(gen_key)"
ok "AURALIS_API_KEY, AURALIS_SECRET, AURALIS_DATA_KEY generated (never printed)"
info "the staff-console key is shown once at the very end — write it down then"

# ── 2. Gmail app password (optional) ─────────────────────────────────────────
step "Email (optional — you can add this later)"
info "The portal writes client mails as Gmail DRAFTS by default; nothing is sent"
info "automatically. It needs the app password for team@auralisnatura.com."
SMTP_PW="$(ask_secret 'Gmail app password')"
if [ -n "$SMTP_PW" ]; then
  [ -n "$EMAIL_MODE" ] || EMAIL_MODE=draft
  ok "stored — AURALIS_EMAIL_MODE=$EMAIL_MODE"
else
  # `off` rather than `draft`: with no password mailer._imap_draft() quietly
  # returns "skipped — no AURALIS_SMTP_PASSWORD set" and nothing raises or logs,
  # so draft-without-password looks configured and produces no client mail at
  # all. `off` is the same behaviour, said out loud.
  [ -n "$EMAIL_MODE" ] || EMAIL_MODE=off
  warn "skipped — AURALIS_EMAIL_MODE=$EMAIL_MODE. NO client mail (access details,"
  warn "reminders, reports, feedback) until you add AURALIS_SMTP_PASSWORD to"
  warn "/etc/auralis/portal.env, set AURALIS_EMAIL_MODE=draft and restart auralis-portal."
fi

# ── 3. Claude token for the report agent ─────────────────────────────────────
step "Claude report agent"
info "lib/agent.py shells out to \`claude -p\`. On a server that needs a"
info "long-lived token from \`claude setup-token\`, which prints a URL you open"
info "in ANY browser (your phone is fine) and approve with your Claude account."
CLAUDE_TOKEN="${CLAUDE_CODE_OAUTH_TOKEN:-}"
if [ -z "$CLAUDE_TOKEN" ] && confirm "Run \`claude setup-token\` now?"; then
  if ! command -v claude >/dev/null 2>&1; then
    info "installing the Claude CLI…"
    curl -fsSL https://claude.ai/install.sh | bash >/dev/null 2>&1 || warn "install script failed"
    export PATH="$HOME/.local/bin:$PATH"
  fi
  if command -v claude >/dev/null 2>&1; then
    printf '\n'; claude setup-token || warn "setup-token did not complete"
    printf '\n'
    CLAUDE_TOKEN="$(ask_secret 'paste the token it printed')"
  else
    warn "no claude binary — skipping"
  fi
fi
if [ -n "$CLAUDE_TOKEN" ]; then ok "token stored"
else warn "no token — the report agent falls back to the offline 'stub' provider."
     warn "That is SAFE (drafts are obviously placeholder text) but not useful."
fi

# ── 4. Cloudflare tunnel ─────────────────────────────────────────────────────
step "Cloudflare tunnel"
# Unpacked, not dpkg-installed: a vendor .deb's postinst would add an apt source
# and a systemd unit to a host that belongs to another company's ERP as well.
if ! command -v cloudflared >/dev/null 2>&1 && [ ! -x "$CF_BIN_DIR/usr/bin/cloudflared" ]; then
  info "fetching cloudflared (unpacked, nothing registered with dpkg/apt)…"
  mkdir -p "$CF_BIN_DIR"
  arch="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
  curl -fsSL -o /root/cf.deb \
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${arch}.deb" \
    || die 15 "could not download cloudflared"
  dpkg-deb -x /root/cf.deb "$CF_BIN_DIR"; rm -f /root/cf.deb
fi
CF="$(command -v cloudflared || echo "$CF_BIN_DIR/usr/bin/cloudflared")"
[ -x "$CF" ] || die 15 "cloudflared is not executable at $CF"
ok "cloudflared: $CF"

if [ ! -f /root/.cloudflared/cert.pem ]; then
  printf '\n'
  info "A browser login follows. cloudflared prints a URL — open it on any"
  info "device, pick the auralisnatura.com zone, and approve."
  printf '\n'
  "$CF" tunnel login || die 15 "cloudflared login did not complete"
fi
ok "Cloudflare account authorised"

# Reuse a tunnel of this name if one already exists (re-runs must be safe), else
# create it. Never touch a tunnel belonging to the ERP or to Paramur — we only
# ever address the one named "$TUNNEL_NAME".
TUNNEL_ID="$("$CF" tunnel list --output json 2>/dev/null \
  | python3 -c "
import json,sys
try: rows = json.load(sys.stdin)
except Exception: rows = []
print(next((r['id'] for r in rows if r.get('name') == '$TUNNEL_NAME' and not r.get('deleted_at')), ''))" || true)"
if [ -z "$TUNNEL_ID" ]; then
  "$CF" tunnel create "$TUNNEL_NAME" >/dev/null || die 15 "could not create the tunnel"
  TUNNEL_ID="$("$CF" tunnel list --output json | python3 -c "
import json,sys
print(next((r['id'] for r in json.load(sys.stdin) if r.get('name')=='$TUNNEL_NAME'),''))")"
  ok "tunnel '$TUNNEL_NAME' created: $TUNNEL_ID"
else
  ok "reusing existing tunnel '$TUNNEL_NAME': $TUNNEL_ID"
fi
[ -n "$TUNNEL_ID" ] || die 15 "could not determine the tunnel id"

CREDS="/root/.cloudflared/$TUNNEL_ID.json"
[ -f "$CREDS" ] || die 15 "tunnel credentials not found at $CREDS"
install -m 0600 "$CREDS" "$PAYLOAD/tunnel.json"
ok "credentials captured"

# DNS: point the hostname at this tunnel. Idempotent; an existing record that
# already points here is left alone, and one pointing elsewhere is reported
# rather than silently stolen.
if "$CF" tunnel route dns "$TUNNEL_NAME" "$PUB_HOST" >/dev/null 2>&1; then
  ok "DNS: $PUB_HOST → this tunnel"
else
  warn "could not create the DNS route automatically."
  warn "In the Cloudflare dashboard add a CNAME:"
  warn "    $PUB_HOST  →  $TUNNEL_ID.cfargotunnel.com   (proxied)"
  confirm "Continue anyway?" || die 15 "stopped so you can fix DNS first"
fi

# ── 5. the deploy key ────────────────────────────────────────────────────────
step "GitHub deploy key"
# Hand the installer the key this clone already used, so there is ONE key to
# authorise rather than two.
BOOT_KEY="${AURALIS_BOOT_KEY:-/root/.ssh/auralis_deploy}"
if [ -f "$BOOT_KEY" ]; then
  install -m 0600 "$BOOT_KEY" "$PAYLOAD/deploy_key"
  [ -f "$BOOT_KEY.pub" ] && install -m 0644 "$BOOT_KEY.pub" "$PAYLOAD/deploy_key.pub"
  ok "reusing the key this clone was made with (nothing new to paste)"
else
  info "no bootstrap key found — install_server.sh will generate one and print it"
fi

# ── 6. write portal.env ──────────────────────────────────────────────────────
step "Assemble the environment"
# No quotes around values: systemd's EnvironmentFile keeps them literally, and a
# quoted AURALIS_DATA_KEY derives a DIFFERENT Fernet key from the same string.
{
  printf 'AURALIS_API_KEY=%s\n' "$API_KEY"
  printf 'AURALIS_SECRET=%s\n'  "$SECRET"
  printf 'AURALIS_DATA_KEY=%s\n' "$DATA_KEY"
  [ -n "$SMTP_PW" ]      && printf 'AURALIS_SMTP_PASSWORD=%s\n' "$SMTP_PW"
  [ -n "$CLAUDE_TOKEN" ] && printf 'CLAUDE_CODE_OAUTH_TOKEN=%s\n' "$CLAUDE_TOKEN"
  printf 'AURALIS_ENV=production\n'
  printf 'AURALIS_EMAIL_MODE=%s\n' "$EMAIL_MODE"
  printf 'AURALIS_AGENT_PROVIDER=%s\n' "$([ -n "$CLAUDE_TOKEN" ] && echo claude_cli || echo stub)"
  printf 'AURALIS_PUBLIC_BASE_URL=https://%s\n' "$PUB_HOST"
  printf 'AURALIS_BOOKING_URL=https://%s/book\n' "$PUB_HOST"
  printf 'AURALIS_BACKUP_DIR=/var/lib/auralis/backups\n'
} > "$PAYLOAD/portal.env"
chmod 600 "$PAYLOAD/portal.env"
ok "portal.env written (0600, root-only, values never printed)"

# ── 7. hand over to the installer ────────────────────────────────────────────
step "Install"
info "everything from here is install_server.sh — the co-tenant safety rules,"
info "the systemd units, the hardening and the verification live there."
printf '\n'
# `|| RC=$?`, not `set +e`: with set -E the ERR trap still fires with errexit
# off, and here that would print a spurious "bootstrap failed at line 257" over
# the installer's own, accurate diagnosis. Exit 30 in particular is a normal,
# expected outcome handled just below.
RC=0
AURALIS_PAYLOAD_DIR="$PAYLOAD" \
AURALIS_TUNNEL_ID="$TUNNEL_ID" \
AURALIS_HOSTNAME="$PUB_HOST" \
AURALIS_KEEP_PAYLOAD=1 \
AURALIS_REQUIRE_VERIFY=1 \
AURALIS_VERIFY_PUBLIC=1 \
  bash "$SELF_DIR/install_server.sh" || RC=$?

if [ "$RC" -eq 30 ]; then
  printf '\n%s──────────────────────────────────────────────────────────────%s\n' "$B" "$N"
  printf '%sOne thing left: authorise the deploy key%s\n' "$B" "$N"
  printf '  1. copy the key printed above\n'
  printf '  2. open  https://github.com/stefangruber001/AuralisNatura/settings/keys/new\n'
  printf '  3. title "auralis server", leave write access OFF, Add key\n'
  printf '  4. run this script again — it picks up exactly where it stopped\n'
  exit 30
fi
[ "$RC" -eq 0 ] || die "$RC" "install_server.sh failed with exit $RC — see above"

printf '\n%s══════════════════════════════════════════════════════════════%s\n' "$G" "$N"
printf '%s Auralis Natura is running on this server.%s\n' "$G" "$N"
printf '   console   https://%s/staff\n' "$PUB_HOST"
printf '   portal    https://%s/portal\n' "$PUB_HOST"
printf '\n   %sSTAFF CONSOLE KEY — copy it now, it is not shown again:%s\n' "$B" "$N"
printf '   %s\n' "$API_KEY"
printf '\n   Store it in a password manager. It is also in /etc/auralis/portal.env\n'
printf '   (root-only) if you lose it.\n'
printf '\n%sAdopting the old Mac data, if it ever turns up%s\n' "$B" "$N"
printf '   You need BOTH the old auralis.db AND the old AURALIS_DATA_KEY — the\n'
printf '   new key cannot open the old database, and there is no way around that.\n'
printf '   With both in hand:\n'
printf '     1. systemctl stop auralis-portal\n'
printf '     2. cp <old-auralis.db> /var/lib/auralis/auralis.db\n'
printf '     3. edit /etc/auralis/portal.env → AURALIS_DATA_KEY=<the OLD key>\n'
printf '     4. runuser -u auralis -- /opt/auralis/venv/bin/python \\\n'
printf '          /opt/auralis/app/portal/tools/preflight.py    # must say key matches\n'
printf '     5. systemctl start auralis-portal\n'
printf '   Anything created on this server in the meantime is in the NEW database\n'
printf '   and would be replaced by step 2 — back it up first.\n'
