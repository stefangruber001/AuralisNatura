#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Auralis Natura — move the portal off the Mac and onto the Hetzner server.
#
# WHERE THIS RUNS:  on Desiree's MacBook, inside the repo.  THE one command:
#
#       bash portal/deploy/migrate_to_server.sh
#
# WHAT IT DOES, and why in this order:
#   A) INSTALL (safe, repeatable, Mac keeps serving the whole time)
#      preflight → prove the local DB opens with the local key → consistent
#      snapshot → Claude token → assert the tunnel identity → ship a 0700
#      payload → run install_server.sh with AURALIS_SKIP_TUNNEL=1 → verify.
#      The server's cloudflared is deliberately NOT installed yet, so there is
#      never a moment where BOTH the Mac and the server are connectors for the
#      same tunnel (Cloudflare would load-balance between them and half the
#      traffic would hit the wrong database — a silent split brain).
#   B) CUTOVER (explicit, typed confirmation — the point of no return)
#      re-ship a FRESH snapshot (the Mac kept working during A) → stop the Mac's
#      launchd agent → start the server's tunnel → verify the public URL.
#      No DNS change is needed: the server runs the SAME tunnel id, so the
#      existing api.auralisnatura.com CNAME already points at it.
#
# Re-running is safe at any point. Nothing is imported over existing server data
# unless we are doing the cutover (or --import-data is passed).
#
# Written for the Mac's bash 3.2: no associative arrays, no readarray, no ${x,,}.
# ─────────────────────────────────────────────────────────────────────────────
set -Eeuo pipefail

# ── defaults (every one overridable by flag or env) ──────────────────────────
TARGET="${AURALIS_TARGET:-root@178.105.10.156}"
REPO_URL="${AURALIS_REPO_URL:-git@github.com:stefangruber001/AuralisNatura.git}"
BRANCH="${AURALIS_BRANCH:-main}"
PUB_HOST="${AURALIS_TUNNEL_HOSTNAME:-api.auralisnatura.com}"
PORT="${AURALIS_PORT:-5056}"
TUNNEL_CFG="${AURALIS_TUNNEL_CONFIG:-$HOME/.cloudflared/auralis.yml}"
EMAIL_MODE="${AURALIS_EMAIL_MODE:-draft}"
TOKEN_STORE="$HOME/.auralis/claude_oauth_token"

DO_CUTOVER=0          # --cutover     : offer the cutover at the end of a green install
IMPORT_DATA=0         # --import-data : force-import the snapshot over existing server data
ASSUME_YES=0          # --yes         : skip the soft confirmations (NOT the cutover one)
ALLOW_STUB=0          # --allow-stub  : proceed even though the report agent will be a stub
PREFLIGHT_ONLY=0      # --preflight-only : do everything local, touch nothing remote
TOKEN_PROBE=1         # --no-token-probe : skip the clean-env test of the Claude token
TRUST_TUNNEL=0        # --i-know-the-tunnel : accept a tunnel we could not name-check
SEND_DOCS=1           # --no-docs     : do not carry portal/output_docs (past reports/PDFs)

# ── output helpers (colour only on a terminal; script output stays English) ──
if [ -t 1 ]; then B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; D=$'\033[2m'; N=$'\033[0m'
else B=''; G=''; Y=''; R=''; D=''; N=''; fi
STEP=0
step() { STEP=$((STEP + 1)); printf '\n%s[%d/%s] %s%s\n' "$B" "$STEP" "$TOTAL_STEPS" "$1" "$N"; }
ok()   { printf '   %s✓%s %s\n' "$G" "$N" "$1"; }
info() { printf '   %s·%s %s\n' "$D" "$N" "$1"; }
warn() { printf '   %s!%s %s\n' "$Y" "$N" "$1" >&2; }
die()  { printf '\n%s✗ %s%s\n' "$R" "$1" "$N" >&2; exit "${2:-1}"; }
TOTAL_STEPS=8

on_err() { printf '\n%s✗ migrate_to_server.sh failed at line %s (exit %s)%s\n' "$R" "$1" "$2" "$N" >&2; }
trap 'on_err "$LINENO" "$?"' ERR
# An ERR trap fires even when errexit is off, so a *deliberately* fallible command
# (a probe whose non-zero answer is the information) would print a false alarm.
# soft/hard turn both off and on together.
soft() { trap - ERR; set +e; }
hard() { set -e; trap 'on_err "$LINENO" "$?"' ERR; }

# ── paths ────────────────────────────────────────────────────────────────────
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
PORTAL_DIR="$(cd "$SELF_DIR/.." && pwd)"
REPO_DIR="$(cd "$PORTAL_DIR/.." && pwd)"
ENV_FILE="$PORTAL_DIR/.env"
DB_FILE="$PORTAL_DIR/auralis.db"
CLIENTS_FILE="$PORTAL_DIR/config/clients.json"
PLIST="$HOME/Library/LaunchAgents/com.auralis.portal.plist"

PAYLOAD=""            # local staging dir — CONTAINS SECRETS, wiped on every exit
RDIR=""               # remote staging dir — also contains secrets
SSH_CTL="/tmp/.auralis-migrate-$$.sock"
SSH_OPTS="-o ControlMaster=auto -o ControlPath=$SSH_CTL -o ControlPersist=600 -o ConnectTimeout=15"

usage() {
  cat <<EOF
Usage: bash portal/deploy/migrate_to_server.sh [options]

  --target user@host      SSH target                (default: $TARGET)
  --hostname HOST         public hostname           (default: $PUB_HOST)
  --port N                loopback port             (default: $PORT)
  --tunnel-config FILE    cloudflared config        (default: $TUNNEL_CFG)
  --repo-url URL          git remote the server pulls from
  --branch NAME           branch the server tracks  (default: $BRANCH)
  --email-mode off|draft|send                       (default: $EMAIL_MODE)
  --cutover               after a green install, offer the cutover (typed confirm)
  --import-data           force-import the snapshot over existing server data
  --preflight-only        run every local check, then stop (nothing remote)
  --allow-stub            continue even if the Claude report agent will be a stub
  --no-token-probe        skip the clean-environment test of the Claude token
  --i-know-the-tunnel     accept a tunnel whose NAME could not be verified
  --no-docs               do not carry output_docs/ (past reports and PDFs)
  --yes                   skip soft confirmations (never the cutover confirmation)
  -h, --help              this text
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --target)         TARGET="${2:?}"; shift 2 ;;
    --hostname)       PUB_HOST="${2:?}"; shift 2 ;;
    --port)           PORT="${2:?}"; shift 2 ;;
    --tunnel-config)  TUNNEL_CFG="${2:?}"; shift 2 ;;
    --repo-url)       REPO_URL="${2:?}"; shift 2 ;;
    --branch)         BRANCH="${2:?}"; shift 2 ;;
    --email-mode)     EMAIL_MODE="${2:?}"; shift 2 ;;
    --cutover)        DO_CUTOVER=1; shift ;;
    --import-data)    IMPORT_DATA=1; shift ;;
    --preflight-only) PREFLIGHT_ONLY=1; shift ;;
    --allow-stub)     ALLOW_STUB=1; shift ;;
    --no-token-probe) TOKEN_PROBE=0; shift ;;
    --i-know-the-tunnel) TRUST_TUNNEL=1; shift ;;
    --no-docs)        SEND_DOCS=0; shift ;;
    --yes|-y)         ASSUME_YES=1; shift ;;
    -h|--help)        usage; exit 0 ;;
    *) usage >&2; die "unknown option: $1" ;;
  esac
done

case "$EMAIL_MODE" in off|draft|send) ;; *) die "--email-mode must be off, draft or send";; esac
if [ "$DO_CUTOVER" = 1 ]; then TOTAL_STEPS=9; fi   # the cutover adds a public re-verification

# ── the payload holds the data key, the SMTP password and the Claude token.
#    It must not survive this process — not on success, not on failure, not on
#    Ctrl-C. The remote copy goes too (the installer also removes it, belt and
#    braces). ───────────────────────────────────────────────────────────────
cleanup() {
  local rc=$?
  if [ -n "$PAYLOAD" ] && [ -d "$PAYLOAD" ]; then
    chmod -R u+w "$PAYLOAD" 2>/dev/null || true
    rm -rf "$PAYLOAD"
    printf '\n%s· local payload wiped%s\n' "$D" "$N"
  fi
  if [ -n "$RDIR" ]; then
    ssh $SSH_OPTS -o BatchMode=yes "$TARGET" "rm -rf '$RDIR'" >/dev/null 2>&1 || true
  fi
  ssh $SSH_OPTS -O exit "$TARGET" >/dev/null 2>&1 || true
  rm -f "$SSH_CTL" 2>/dev/null || true
  exit $rc
}
trap cleanup EXIT INT TERM

confirm() { # confirm "question"  → 0 yes / 1 no  (honours --yes)
  [ "$ASSUME_YES" = 1 ] && return 0
  [ -t 0 ] || return 1
  local a=""
  printf '   %s%s%s [y/N] ' "$B" "$1" "$N"
  read -r a || true
  case "$a" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

# Read one KEY from portal/.env exactly the way start_auralis.command does:
# comments on their own line, value is everything after the FIRST '=', literal.
env_get() {
  [ -f "$ENV_FILE" ] || return 0
  awk -v k="$1" '
    { line=$0; sub(/^[ \t]+/,"",line)
      if (line ~ /^#/ || line == "") next
      eq = index(line,"="); if (eq == 0) next
      key = substr(line,1,eq-1); gsub(/[ \t]/,"",key)
      if (key == k) { print substr(line,eq+1); exit } }' "$ENV_FILE"
}

yml_get() { # yml_get <key> <file>  — top-level scalar out of the tunnel config
  # `sed -n 1p` rather than `head -1`: head quits early, which under `pipefail`
  # can SIGPIPE the writer and fail the whole substitution.
  sed -n "s/^[[:space:]]*$1:[[:space:]]*//p" "$2" | sed 's/[[:space:]]*#.*$//' | tr -d "\"' " | sed -n '1p'
}

expand_home() { case "$1" in "~/"*) printf '%s\n' "$HOME/${1#\~/}" ;; "~") printf '%s\n' "$HOME" ;; *) printf '%s\n' "$1" ;; esac; }

sha256_of() { python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"; }

remote() { ssh $SSH_OPTS "$TARGET" "$@"; }

printf '%s\n' "$B"
printf 'Auralis Natura — Mac ➜ server migration\n'
printf '%s' "$N"
printf '  repo    %s\n' "$REPO_DIR"
printf '  target  %s\n' "$TARGET"
printf '  public  https://%s  (port %s on the loopback)\n' "$PUB_HOST" "$PORT"

# ═════════════════════════════════════════════════════════════════════════════
# 1 — PREFLIGHT ON THE MAC
# ═════════════════════════════════════════════════════════════════════════════
step "Preflight (this Mac)"

[ -d "$REPO_DIR/.git" ] || die "not a git repo: $REPO_DIR — run this from the checked-out AuralisNatura repo"
ok "repo present"

for t in python3 git ssh tar sed awk curl; do
  command -v "$t" >/dev/null 2>&1 || die "required tool missing: $t"
done
if command -v rsync >/dev/null 2>&1; then XFER=rsync; else XFER=tar; fi
ok "local tools present (transfer via $XFER)"

[ -r "$ENV_FILE" ] || die "cannot read $ENV_FILE — the migration needs the live secrets"
API_KEY="$(env_get AURALIS_API_KEY)"
SECRET="$(env_get AURALIS_SECRET)"
DATA_KEY="$(env_get AURALIS_DATA_KEY)"
SMTP_PW="$(env_get AURALIS_SMTP_PASSWORD)"
for pair in "AURALIS_API_KEY:$API_KEY" "AURALIS_SECRET:$SECRET" "AURALIS_DATA_KEY:$DATA_KEY"; do
  name="${pair%%:*}"; val="${pair#*:}"
  [ -n "$val" ] || die "$name is empty in $ENV_FILE — the server refuses to start in production without it"
  case "$val" in
    change-me*|dev-staff-key-change-me|dev-secret-change-me|REPLACE_WITH_A_LONG_RANDOM_STRING)
      die "$name is still a placeholder in $ENV_FILE — set a real secret first" ;;
  esac
done
[ -n "$SMTP_PW" ] || warn "AURALIS_SMTP_PASSWORD is empty — the server will not be able to send/draft mail"
ok "secrets read from portal/.env (never printed)"

[ -f "$DB_FILE" ] || die "no database at $DB_FILE — nothing to migrate"

# The server pulls its CODE from origin/$BRANCH, not from this Mac. If the Mac
# is ahead, the server would silently run older code than the one just tested.
git -C "$REPO_DIR" fetch origin "$BRANCH" --quiet 2>/dev/null || warn "could not reach GitHub to compare HEAD (offline?)"
# --verify --quiet, or a missing ref makes rev-parse echo the ref name itself and
# every run would cry "out of sync" against the literal string "origin/main".
LOCAL_HEAD="$(git -C "$REPO_DIR" rev-parse --verify --quiet HEAD || echo '')"
REMOTE_HEAD="$(git -C "$REPO_DIR" rev-parse --verify --quiet "origin/$BRANCH" || echo '')"
if [ -z "$REMOTE_HEAD" ]; then
  warn "origin/$BRANCH is unknown here — cannot tell whether the server will run this code"
elif [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
  warn "this Mac is NOT in sync with origin/$BRANCH — the server runs origin/$BRANCH"
  info "local  $LOCAL_HEAD"
  info "origin $REMOTE_HEAD"
  confirm "Continue anyway (the server will run origin/$BRANCH)?" || die "push your commits first, then re-run"
else
  ok "code in sync with origin/$BRANCH"
fi

if [ "$PREFLIGHT_ONLY" = 0 ]; then
  # First SSH also opens the shared control connection, so we authenticate once.
  if ! remote true 2>/dev/null; then
    die "cannot SSH to $TARGET.
   Fix, then re-run:
     ssh-copy-id $TARGET          # install your key
     ssh $TARGET true             # must succeed without a prompt"
  fi
  ok "SSH to $TARGET works (connection shared for the rest of the run)"

  UNAME_R="$(remote 'uname -s' 2>/dev/null || echo '?')"
  [ "$UNAME_R" = "Linux" ] || die "target is not Linux (uname says '$UNAME_R')"
  remote 'command -v systemctl >/dev/null' || die "target has no systemd — this kit installs systemd units"
  [ "$(remote 'id -u')" = "0" ] || die "install_server.sh must run as root — use a root target (default) or a root-equivalent login"
  ok "target is Linux + systemd, and we are root"

  # Port 5056 must be free, OR already held by OUR unit (a re-run). Never kill a
  # foreign listener — another company's ERP lives on this host.
  PORT_HOLDER="$(remote "command -v ss >/dev/null && ss -H -ltn 'sport = :$PORT' | head -1 || echo NO_SS" || true)"
  if [ "$PORT_HOLDER" = "NO_SS" ]; then
    info "no 'ss' on the target — install_server.sh does the authoritative port check"
  elif [ -n "$PORT_HOLDER" ]; then
    if remote "systemctl is-active --quiet auralis-portal" 2>/dev/null; then
      ok "port $PORT is held by our own auralis-portal (re-run)"
    else
      die "TCP $PORT is already in use on $TARGET by something that is NOT auralis-portal.
   Refusing to touch it. Investigate with:  ss -ltnp 'sport = :$PORT'
   Then either free it deliberately or re-run with --port <other>."
    fi
  else
    ok "port $PORT is free on the target"
  fi

  # Read-only observation of the neighbours we must not disturb.
  OTHER_CF="$(remote "systemctl list-units --type=service --all --no-legend 'cloudflared*' 2>/dev/null | awk '{print \$1}' | grep -v '^cloudflared-auralis' | tr '\n' ' '" || true)"
  [ -n "$OTHER_CF" ] && info "pre-existing cloudflared unit(s) noted, will NOT be touched: $OTHER_CF"
  FW="$(remote "(command -v ufw >/dev/null && ufw status | head -1) || (command -v nft >/dev/null && echo 'nftables present') || echo 'no ufw/nft'" 2>/dev/null || true)"
  info "firewall (report only, never changed): ${FW:-unknown}"
fi

# ═════════════════════════════════════════════════════════════════════════════
# 2 — THE LOCAL STORE MUST BE HEALTHY BEFORE ANYTHING ELSE HAPPENS
#     (July's incident: a record encrypted with a throwaway .dev_data.key while
#      the server ran the env key → every staff read 500'd.)
# ═════════════════════════════════════════════════════════════════════════════
step "Local store health (AURALIS_DATA_KEY must open auralis.db)"

PF="$PORTAL_DIR/tools/preflight.py"
if [ -f "$PF" ]; then
  soft
  PF_OUT="$(cd "$PORTAL_DIR" && AURALIS_DATA_KEY="$DATA_KEY" AURALIS_API_KEY="$API_KEY" \
            AURALIS_SECRET="$SECRET" python3 tools/preflight.py --json 2>&1)"
  PF_RC=$?
  hard
  if [ $PF_RC -ne 0 ] && [ -z "$PF_OUT" ]; then die "tools/preflight.py failed to run (exit $PF_RC)"; fi
  # Parse with python (no jq on a stock Mac). Prints one line per check.
  soft
  # NB: the JSON goes in as argv, not stdin — stdin already carries this script.
  PF_SUMMARY="$(python3 - "$PF_OUT" <<'PY'
import json, sys
raw = sys.argv[1]
start = raw.find("{")
if start < 0:
    print("PARSE_FAIL"); print(raw[-400:]); sys.exit(0)
try:
    d = json.loads(raw[start:])
except Exception as e:
    print("PARSE_FAIL"); print(f"{e}: {raw[-400:]}"); sys.exit(0)
print("OK" if d.get("ok") else "NOT_OK")
for c in d.get("checks", []):
    print(("  ok  " if c.get("ok") else "  FAIL") + " " + str(c.get("name","?")) + " — " + str(c.get("detail","")))
PY
)"
  hard
  PF_VERDICT="${PF_SUMMARY%%$'\n'*}"
  printf '%s\n' "$PF_SUMMARY" | sed '1d' | sed 's/^/   /'
  case "$PF_VERDICT" in
    OK)         ok "tools/preflight.py: all checks green" ;;
    NOT_OK)     die "tools/preflight.py reports the local install is NOT healthy — fix that first (see the FAIL lines above)" ;;
    PARSE_FAIL) warn "could not parse preflight JSON — falling back to the direct key check" ;;
  esac
else
  warn "tools/preflight.py not found — running the direct key check instead"
fi

# Independent of preflight.py we prove the invariant that matters most, because
# this is the one that has actually bitten this project.
soft
KEYCHECK="$(cd "$PORTAL_DIR" && AURALIS_DATA_KEY="$DATA_KEY" python3 - <<'PY' 2>&1
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd()))
from lib import store
r = store.key_matches_store()
n = len(store.list_records()) if r is not False else -1
print({True: "MATCH", False: "MISMATCH", None: "UNREADABLE"}[r], n)
PY
)"
KC_RC=$?
hard
[ $KC_RC -eq 0 ] || die "could not probe the local store:
$KEYCHECK"
case "$KEYCHECK" in
  MATCH*)      ok "AURALIS_DATA_KEY opens the live store (${KEYCHECK#MATCH } records)" ;;
  MISMATCH*)   die "AURALIS_DATA_KEY does NOT match auralis.db on this Mac.
   Migrating now would carry the fault to the server. Restore the correct key
   (or the matching backup via tools/restore.py) — do NOT overwrite the store." ;;
  *)           die "the local store could not be read at all: $KEYCHECK" ;;
esac

# ═════════════════════════════════════════════════════════════════════════════
# 3 — CONSISTENT SNAPSHOT (SQLite online backup API — never a raw cp of a WAL DB)
# ═════════════════════════════════════════════════════════════════════════════
step "Snapshot the live database"

umask 077
PAYLOAD="$(mktemp -d "${TMPDIR:-/tmp}/auralis-migrate.XXXXXX")"
chmod 700 "$PAYLOAD"
# Flat layout: install_server.sh reads portal.env, auralis.db, clients.json,
# tunnel.json, output_docs.tar.gz, deploy_key* and nothing else.

snapshot_db() { # snapshot_db  → refreshes $PAYLOAD/auralis.db, prints a one-line summary
  rm -f "$PAYLOAD/auralis.db"
  cd "$PORTAL_DIR" && AURALIS_DATA_KEY="$DATA_KEY" python3 - "$DB_FILE" "$PAYLOAD/auralis.db" <<'PY'
# Mirrors lib/backup.py: sqlite3's online backup API gives a consistent copy even
# while the Mac's Flask server is mid-write (WAL-safe). Then we PROVE the key we
# are about to ship opens the snapshot we are about to ship.
import sqlite3, sys, pathlib
from contextlib import closing
sys.path.insert(0, str(pathlib.Path.cwd()))
src, dst = sys.argv[1], sys.argv[2]
with closing(sqlite3.connect(src)) as s, closing(sqlite3.connect(dst)) as d:
    s.backup(d)
from cryptography.fernet import Fernet
from lib import cfg
key = cfg.data_key()
with closing(sqlite3.connect(dst)) as c:
    rows = c.execute("SELECT blob FROM records").fetchall()
    try:
        ev = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    except Exception:
        ev = 0
if rows:
    Fernet(key).decrypt(rows[0][0])          # raises InvalidToken on a wrong key
print(f"{len(rows)} client records, {ev} funnel events — key verified against the SNAPSHOT")
PY
}
SNAP_INFO="$(snapshot_db)" || die "snapshot failed — the shipped key could not open the shipped database"
ok "$SNAP_INFO"

if [ -f "$CLIENTS_FILE" ]; then
  cp "$CLIENTS_FILE" "$PAYLOAD/clients.json"
  chmod 600 "$PAYLOAD/clients.json"
  ok "clients.json included ($(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1])).get("clients",{})))' "$CLIENTS_FILE") logins)"
else
  warn "no config/clients.json — the server will seed an empty one"
fi

# ═════════════════════════════════════════════════════════════════════════════
# 4 — CLAUDE TOKEN (interactive; must be created here, used on the server)
# ═════════════════════════════════════════════════════════════════════════════
step "Claude report-agent token"

CLAUDE_TOKEN="${CLAUDE_CODE_OAUTH_TOKEN:-}"
TOKEN_SOURCE="environment"
if [ -z "$CLAUDE_TOKEN" ]; then CLAUDE_TOKEN="$(env_get CLAUDE_CODE_OAUTH_TOKEN)"; TOKEN_SOURCE="portal/.env"; fi
if [ -z "$CLAUDE_TOKEN" ] && [ -r "$TOKEN_STORE" ]; then
  CLAUDE_TOKEN="$(cat "$TOKEN_STORE")"; TOKEN_SOURCE="$TOKEN_STORE"
fi

if [ -n "$CLAUDE_TOKEN" ]; then
  ok "reusing the existing token from $TOKEN_SOURCE (never printed)"
elif ! command -v claude >/dev/null 2>&1; then
  warn "the 'claude' CLI is not installed on this Mac, so no token can be created here."
  warn "WITHOUT IT THE REPORT AGENT FALLS BACK TO THE 'stub' PROVIDER — offline"
  warn "boiler-plate drafts instead of real reports. That must never pass unnoticed."
  if [ "$ALLOW_STUB" != 1 ]; then
    confirm "Continue and accept stub reports until a token is added?" \
      || die "install Claude Code, run 'claude setup-token', then re-run (or pass --allow-stub)"
  fi
elif [ ! -t 0 ]; then
  die "'claude setup-token' is interactive (it opens a browser) and stdin is not a terminal.
   Run this script from a normal Terminal window, or export CLAUDE_CODE_OAUTH_TOKEN first."
else
  info "running 'claude setup-token' — a browser window will open; finish the login there."
  RAW="$PAYLOAD/.setup-token.typescript"
  soft
  # `script` gives the CLI a pty (it is a TUI) while we keep a transcript to pull
  # the token out of. The transcript lives inside the 0700 payload and is wiped.
  if [ "$(uname -s)" = "Darwin" ]; then script -q "$RAW" claude setup-token
  else script -q -c "claude setup-token" "$RAW"; fi
  SETUP_RC=$?
  hard
  [ $SETUP_RC -eq 0 ] || warn "'claude setup-token' exited $SETUP_RC — looking for a token anyway"
  # Strip ANSI and pull the last sk-ant-… out of the transcript. Done in python
  # because BSD sed has no \x escapes — the GNU one-liner silently matches nothing.
  soft
  CLAUDE_TOKEN="$(python3 - "$RAW" <<'PY' 2>/dev/null
import re, sys
raw = open(sys.argv[1], "rb").read().decode("utf-8", "replace")
raw = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", raw)
m = re.findall(r"sk-ant-[A-Za-z0-9_-]{20,}", raw)
print(m[-1] if m else "")
PY
)"
  hard
  rm -f "$RAW"
  if [ -z "$CLAUDE_TOKEN" ]; then
    warn "could not read the token from the CLI output — paste it here (input is hidden)."
    printf '   token: '
    read -r -s CLAUDE_TOKEN || true
    printf '\n'
  fi
  [ -n "$CLAUDE_TOKEN" ] || die "no Claude token obtained — re-run, or pass --allow-stub to accept stub reports"
  case "$CLAUDE_TOKEN" in sk-ant-*) ;; *) warn "the token does not start with 'sk-ant-' — shipping it anyway, the server will test it" ;; esac
  ok "token captured (${#CLAUDE_TOKEN} chars, never printed)"
  if confirm "Remember it in $TOKEN_STORE (0600) so re-runs never ask again?"; then
    mkdir -p "$(dirname "$TOKEN_STORE")"; chmod 700 "$(dirname "$TOKEN_STORE")"
    ( umask 077; printf '%s' "$CLAUDE_TOKEN" > "$TOKEN_STORE" )
    ok "stored"
  fi
fi

# CLAUDE_CODE_OAUTH_TOKEN is the documented carrier, but we do not take it on
# faith: probe it in a CLEAN environment with a scratch HOME so the Mac's own
# browser login cannot make a broken token look like a working one.
if [ -n "$CLAUDE_TOKEN" ] && [ "$TOKEN_PROBE" = 1 ] && command -v claude >/dev/null 2>&1; then
  info "testing the token in a clean environment (up to 120s)…"
  soft
  PROBE="$(CLAUDE_TOKEN="$CLAUDE_TOKEN" SCRATCH="$PAYLOAD/probe-home" python3 - <<'PY' 2>&1
import os, subprocess, tempfile, pathlib
home = pathlib.Path(os.environ["SCRATCH"]); home.mkdir(parents=True, exist_ok=True)
env = {"PATH": os.environ.get("PATH",""), "HOME": str(home), "TERM": "dumb",
       "CLAUDE_CODE_OAUTH_TOKEN": os.environ["CLAUDE_TOKEN"]}
try:
    p = subprocess.run(["claude", "-p", "Reply with the single word OK.",
                        "--output-format", "text"],
                       env=env, cwd=str(home), capture_output=True, text=True, timeout=120)
except subprocess.TimeoutExpired:
    print("UNVERIFIED timed out after 120s"); raise SystemExit(0)
except FileNotFoundError:
    print("UNVERIFIED claude not on PATH"); raise SystemExit(0)
if p.returncode == 0 and p.stdout.strip():
    print("PASS " + p.stdout.strip().splitlines()[0][:60])
else:
    print("UNVERIFIED rc=%s %s" % (p.returncode, (p.stderr or p.stdout).strip()[:160]))
PY
)"
  hard
  case "$PROBE" in
    PASS*) ok "CLAUDE_CODE_OAUTH_TOKEN works with a clean HOME → the server will get real drafts" ;;
    *)     warn "token NOT verified here: ${PROBE#UNVERIFIED }"
           warn "this may still be a local quirk — verify_server.sh probes it again on the server"
           warn "and the console must show provider 'claude_cli', never 'stub'." ;;
  esac
fi

# ═════════════════════════════════════════════════════════════════════════════
# 5 — TUNNEL IDENTITY  (Error 1033 came from running Paramur's tunnel — assert,
#     never guess)
# ═════════════════════════════════════════════════════════════════════════════
step "Cloudflare tunnel identity"

[ -f "$TUNNEL_CFG" ] || die "no tunnel config at $TUNNEL_CFG
   Copy portal/deploy/auralis-tunnel.example.yml there and fill in the AURALIS
   tunnel id + credentials, or pass --tunnel-config <file>."

TUNNEL_REF="$(yml_get tunnel "$TUNNEL_CFG")"
CRED_REF="$(yml_get credentials-file "$TUNNEL_CFG")"
[ -n "$TUNNEL_REF" ] || die "no 'tunnel:' line in $TUNNEL_CFG"
[ -n "$CRED_REF" ]   || die "no 'credentials-file:' line in $TUNNEL_CFG"
CRED_FILE="$(expand_home "$CRED_REF")"
[ -r "$CRED_FILE" ] || die "credentials file not readable: $CRED_FILE"

CFG_HOSTS="$(sed -n 's/^[[:space:]]*-\{0,1\}[[:space:]]*hostname:[[:space:]]*//p' "$TUNNEL_CFG" | tr -d "\"' " | tr '\n' ' ')"
case " $CFG_HOSTS " in
  *" $PUB_HOST "*) ok "$TUNNEL_CFG routes $PUB_HOST" ;;
  *) die "$TUNNEL_CFG does not route $PUB_HOST (it routes: ${CFG_HOSTS:-nothing}).
   Refusing to guess which tunnel is the Auralis one." ;;
esac

# The credentials JSON is the ground truth: its TunnelID must equal the config's.
CRED_ID="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("TunnelID",""))' "$CRED_FILE" 2>/dev/null || echo '')"
[ -n "$CRED_ID" ] || die "no TunnelID inside $CRED_FILE — that is not a cloudflared credentials file"

TUNNEL_NAME=""
case "$TUNNEL_REF" in
  ????????-????-????-????-????????????)
    [ "$TUNNEL_REF" = "$CRED_ID" ] || die "TUNNEL MISMATCH — $TUNNEL_CFG says '$TUNNEL_REF' but
   $CRED_FILE belongs to '$CRED_ID'. This exact confusion produced Error 1033
   before (Paramur's tunnel instead of Auralis's). Fix the config; do not guess."
    TUNNEL_ID="$TUNNEL_REF" ;;
  *)
    # config names the tunnel — resolve the name to the id, never assume
    command -v cloudflared >/dev/null 2>&1 \
      || die "$TUNNEL_CFG names the tunnel ('$TUNNEL_REF') instead of its UUID and cloudflared
   is not installed here, so the name cannot be resolved. Put the UUID in the config."
    TUNNEL_ID="$(cloudflared tunnel list 2>/dev/null | awk -v n="$TUNNEL_REF" '$2==n && !f {print $1; f=1}')"
    [ -n "$TUNNEL_ID" ] || die "cloudflared does not know a tunnel named '$TUNNEL_REF'"
    [ "$TUNNEL_ID" = "$CRED_ID" ] || die "tunnel '$TUNNEL_REF' is $TUNNEL_ID but the credentials file is $CRED_ID — refusing"
    TUNNEL_NAME="$TUNNEL_REF" ;;
esac
ok "tunnel id $TUNNEL_ID matches its credentials file"

if command -v cloudflared >/dev/null 2>&1; then
  [ -n "$TUNNEL_NAME" ] || TUNNEL_NAME="$(cloudflared tunnel list 2>/dev/null | awk -v i="$TUNNEL_ID" '$1==i && !f {print $2; f=1}')"
fi
if [ -n "$TUNNEL_NAME" ]; then
  LOWER_NAME="$(printf '%s' "$TUNNEL_NAME" | tr 'A-Z' 'a-z')"    # bash 3.2: no ${x,,}
  case "$LOWER_NAME" in
    *paramur*) die "that tunnel is named '$TUNNEL_NAME' — that is PARAMUR's tunnel, not Auralis's. Refusing." ;;
    *auralis*) ok "tunnel name '$TUNNEL_NAME' confirms this is the Auralis tunnel" ;;
    *) if [ "$TRUST_TUNNEL" = 1 ]; then warn "tunnel name '$TUNNEL_NAME' does not contain 'auralis' — accepted via --i-know-the-tunnel"
       else die "tunnel name '$TUNNEL_NAME' does not contain 'auralis'. Refusing to guess.
   Re-run with --i-know-the-tunnel if this really is the Auralis tunnel."; fi ;;
  esac
else
  warn "cloudflared is not installed here, so the tunnel NAME could not be checked."
  warn "Asserted from files only: config→credentials id match, and $PUB_HOST in ingress."
fi

# The installer re-asserts this file's "TunnelID" against AURALIS_TUNNEL_ID and
# generates the ingress config itself, so the identity is checked on both ends.
cp "$CRED_FILE" "$PAYLOAD/tunnel.json"; chmod 600 "$PAYLOAD/tunnel.json"

if [ "$PREFLIGHT_ONLY" = 1 ]; then
  printf '\n%s✓ preflight only — everything local is green, nothing remote was touched.%s\n' "$G" "$N"
  exit 0
fi

# ═════════════════════════════════════════════════════════════════════════════
# 6 — BUILD + SHIP THE PAYLOAD, THEN INSTALL
# ═════════════════════════════════════════════════════════════════════════════
step "Ship the payload and install"

[ -f "$SELF_DIR/install_server.sh" ] || die "missing $SELF_DIR/install_server.sh — it is part of this deploy kit"
cp "$SELF_DIR/install_server.sh" "$PAYLOAD/install_server.sh"; chmod 600 "$PAYLOAD/install_server.sh"
# verify_server.sh is NOT shipped: install_server.sh runs the copy that comes with
# the git clone ($PORTAL/deploy/verify_server.sh), so the verifier always matches
# the code that is actually deployed.

# Past reports/PDFs. install_server.sh merges this into /var/lib/auralis/output_docs
# and never deletes, so re-runs are additive.
if [ "$SEND_DOCS" = 1 ] && [ -d "$PORTAL_DIR/output_docs" ]; then
  ( cd "$PORTAL_DIR/output_docs" && tar czf "$PAYLOAD/output_docs.tar.gz" . )
  chmod 600 "$PAYLOAD/output_docs.tar.gz"
  ok "output_docs packed ($(find "$PORTAL_DIR/output_docs" -type f | wc -l | tr -d ' ') files, $(du -h "$PAYLOAD/output_docs.tar.gz" | cut -f1))"
fi

# /etc/auralis/portal.env — the installer normalises this into
# /etc/auralis/portal.env (0640 root:auralis). It OWNS AURALIS_PORT and
# AURALIS_CHROME (it strips and re-sets them), so we deliberately send neither
# a chrome path nor anything it would have to override.
( umask 077
  {
    printf '# generated by migrate_to_server.sh on %s — DO NOT COMMIT\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'AURALIS_API_KEY=%s\n'         "$API_KEY"
    printf 'AURALIS_SECRET=%s\n'          "$SECRET"
    printf 'AURALIS_DATA_KEY=%s\n'        "$DATA_KEY"
    printf 'AURALIS_SMTP_PASSWORD=%s\n'   "$SMTP_PW"
    printf 'AURALIS_EMAIL_MODE=%s\n'      "$EMAIL_MODE"
    printf 'AURALIS_AGENT_PROVIDER=%s\n'  "claude_cli"
    printf 'AURALIS_ENV=production\n'
    printf 'AURALIS_PUBLIC_BASE_URL=https://%s\n' "$PUB_HOST"
    printf 'AURALIS_BOOKING_URL=https://%s/book\n' "$PUB_HOST"
    printf 'AURALIS_BACKUP_DIR=/var/lib/auralis/backups\n'
    printf 'AURALIS_PORT=%s\n'            "$PORT"
    # NB: an `[ … ] && printf` here would make the whole subshell exit 1 under
    # `hard` when the token is absent — hence the explicit if.
    if [ -n "$CLAUDE_TOKEN" ]; then printf 'CLAUDE_CODE_OAUTH_TOKEN=%s\n' "$CLAUDE_TOKEN"; fi
  } > "$PAYLOAD/portal.env" )
chmod 600 "$PAYLOAD/portal.env"

# MANIFEST carries no secrets — it is the audit trail of what was shipped.
{
  printf 'auralis-migration-payload v1\n'
  printf 'created      %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'from         %s (%s)\n' "$(hostname 2>/dev/null || echo mac)" "$(uname -s)"
  printf 'repo-head    %s\n' "${LOCAL_HEAD:-unknown}"
  printf 'target       %s\n' "$TARGET"
  printf 'hostname     %s\n' "$PUB_HOST"
  printf 'tunnel-id    %s\n' "$TUNNEL_ID"
  printf 'tunnel-name  %s\n' "${TUNNEL_NAME:-unverified}"
  printf 'db-sha256    %s\n' "$(sha256_of "$PAYLOAD/auralis.db")"
  printf 'db-summary   %s\n' "$SNAP_INFO"
  printf 'claude-token %s\n' "$([ -n "$CLAUDE_TOKEN" ] && echo present || echo ABSENT-stub-fallback)"
} > "$PAYLOAD/MANIFEST"
chmod 600 "$PAYLOAD/MANIFEST"
ok "payload staged (0700, secrets inside — wiped on exit)"

RDIR="$(remote "umask 077; d=\$(mktemp -d /tmp/auralis-deploy.XXXXXX); chmod 700 \"\$d\"; printf '%s' \"\$d\"")"
[ -n "$RDIR" ] || die "could not create a staging dir on $TARGET"

# rsync when both ends have a capable one, else tar-over-ssh — recent macOS
# ships openrsync, which does not understand --chmod. Either way the remote
# umask keeps every file 0600 inside a 0700 dir.
ship() { # ship <local subdir or "."> — always relative to $PAYLOAD
  local sub="$1"
  if [ "$XFER" = rsync ] && remote 'command -v rsync >/dev/null 2>&1'; then
    if rsync -a --chmod=D700,F600 -e "ssh $SSH_OPTS" "$PAYLOAD/$sub" "$TARGET:$RDIR/" >/dev/null 2>&1; then
      return 0
    fi
    warn "rsync failed — falling back to tar over ssh"
  fi
  ( cd "$PAYLOAD" && tar czf - "$sub" ) | remote "umask 077; tar xzf - -C '$RDIR'"
}
ship .
remote "chmod -R go-rwx '$RDIR'"
ok "payload delivered to $TARGET:$RDIR (0700)"

# Secrets travel in the payload FILES, never on the command line — argv is
# world-readable in `ps` and this host runs another company's production ERP.
# Every name below is install_server.sh's documented contract; AURALIS_KEEP_PAYLOAD
# is on because we call the installer up to three times and it would otherwise
# delete the payload after the first success.
REQUIRE_TOKEN=0
if [ -n "$CLAUDE_TOKEN" ]; then REQUIRE_TOKEN=1; fi
INSTALL_LOG=""
remote_install() { # remote_install <skip_tunnel> <allow_overwrite> <skip_data>
  ssh $SSH_OPTS "$TARGET" \
    "AURALIS_PAYLOAD_DIR='$RDIR' AURALIS_REPO_URL='$REPO_URL' AURALIS_BRANCH='$BRANCH' \
     AURALIS_TUNNEL_ID='$TUNNEL_ID' AURALIS_HOSTNAME='$PUB_HOST' AURALIS_PORT='$PORT' \
     AURALIS_KEEP_PAYLOAD=1 AURALIS_REQUIRE_VERIFY=1 AURALIS_REQUIRE_CLAUDE_TOKEN='$REQUIRE_TOKEN' \
     AURALIS_SKIP_TUNNEL='$1' AURALIS_ALLOW_DB_OVERWRITE='$2' AURALIS_SKIP_DATA='$3' \
     bash '$RDIR/install_server.sh'"
}

deploy_key_authorised() {
  remote "GIT_SSH_COMMAND='ssh -i /opt/auralis/.ssh/id_ed25519 -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o BatchMode=yes' \
          git ls-remote '$REPO_URL' HEAD >/dev/null 2>&1"
}

github_keys_url() { # git@github.com:owner/repo.git → https://github.com/owner/repo/settings/keys/new
  printf '%s' "$REPO_URL" | sed -e 's#^git@github.com:#https://github.com/#' \
                                -e 's#^https\{0,1\}://github.com/#https://github.com/#' \
                                -e 's#\.git$##' -e 's#$#/settings/keys/new#'
}

run_install() { # run_install <skip_tunnel> <allow_overwrite> <skip_data> → 0 green, else dies
  local rc=0 pub=""
  INSTALL_LOG="$PAYLOAD/install.log"
  # tee so the operator watches it live AND we can read the machine-readable
  # trailer (AURALIS_DEPLOY_KEY_PUB=… on exit 30) back out of it afterwards.
  soft; remote_install "$1" "$2" "$3" 2>&1 | tee "$INSTALL_LOG"; rc=${PIPESTATUS[0]}; hard
  if [ $rc -eq 30 ]; then
    pub="$(sed -n 's/^AURALIS_DEPLOY_KEY_PUB=//p' "$INSTALL_LOG" | sed -n '1p')"
    if [ -z "$pub" ]; then
      pub="$(remote "cat /opt/auralis/.ssh/id_ed25519.pub 2>/dev/null" || true)"
    fi
    printf '\n%s──────── the server needs read access to the repo ────────%s\n' "$B" "$N"
    printf '%s\n' "$pub"
    printf '%s\n' "$B"
    printf 'Paste that ONE line here:  %s\n' "$(github_keys_url)"
    printf '  Title:  auralis-server (hetzner)\n'
    printf '  Allow write access:  LEAVE OFF — the server only ever reads.\n'
    printf '%s\nWaiting… I check every 15s and continue by myself. (Enter = check now, Ctrl-C = abort)\n' "$N"
    local deadline; deadline=$(( $(date +%s) + 1800 ))
    while :; do
      if deploy_key_authorised; then printf '\n'; ok "deploy key accepted by GitHub — continuing"; break; fi
      if [ "$(date +%s)" -ge "$deadline" ]; then
        die "still no repo access after 30 minutes. Add the key, then simply re-run this script."
      fi
      if [ -t 1 ]; then printf '   %s… waiting for the deploy key%s\r' "$D" "$N"; fi
      if [ -t 0 ]; then read -r -t 15 _ >/dev/null 2>&1 || true; else sleep 15; fi
    done
    soft; remote_install "$1" "$2" "$3" 2>&1 | tee "$INSTALL_LOG"; rc=${PIPESTATUS[0]}; hard
  fi
  # install_server.sh's documented exit codes. Everything that is not 0 leaves
  # the Mac serving, so the recovery advice is always "nothing was cut over".
  case $rc in
    0)  return 0 ;;
    30) die "install_server.sh still says the deploy key is not authorised (exit 30)" ;;
    10) die "install_server.sh must run as root on the server (exit 10) — use a root target" ;;
    11) die "the target has no systemd (exit 11) — this kit installs systemd units" ;;
    12) die "unsupported distro / no apt-get on the target (exit 12)" ;;
    13) die "install aborted: TCP $PORT is held by a FOREIGN process (exit 13).
   Nothing was killed — another company's ERP runs on this host.
   Investigate:  ssh $TARGET \"ss -ltnp 'sport = :$PORT'\"" ;;
    14) die "not enough free disk on the server (exit 14)" ;;
    15) die "bad payload or portal.env (exit 15) — a required key is missing.
   If it names CLAUDE_CODE_OAUTH_TOKEN, re-run with --allow-stub to accept stub reports." ;;
    20) die "package installation failed on the server (exit 20)" ;;
    21) die "no usable Chromium (exit 21). Without it lib/render.py silently writes
   .html instead of the 12-page PDF, so the install refused to finish." ;;
    22) die "Chromium is present but FAILED the real PDF render test (exit 22) — same
   consequence: no premium PDF. Fix Chromium on the server, then re-run." ;;
    31) die "git clone/fetch failed on the server (exit 31)" ;;
    32) die "venv creation or pip install failed on the server (exit 32)" ;;
    33) die "install refused to overwrite existing server data (exit 33).
   The server already holds a DIFFERENT auralis.db/clients.json than this Mac.
   Decide deliberately:
     • server data is the newer one → do NOT re-import; just re-run without --import-data
     • this Mac is authoritative     → re-run with --import-data (the server file is
       backed up to /var/backups/auralis first)" ;;
    34) die "a data path in the worktree collides with the required symlink (exit 34)" ;;
    35) die "AURALIS_DATA_KEY does NOT open the MIGRATED store on the server (exit 35).
   This is the July failure mode caught before it could go live: nothing was
   started and your Mac is untouched. Do NOT overwrite the store." ;;
    40) die "systemd unit install/start failed, /health never came up, or
   deploy/verify_server.sh is missing from this revision (exit 40)." ;;
    41) die "cloudflared install / tunnel-identity assertion / tunnel start failed (exit 41).
   A pre-existing cloudflared for the other app was left untouched, as designed." ;;
    99) die "unexpected error inside install_server.sh (exit 99) — its ERR trap printed file:line above" ;;
    *)  die "verify_server.sh failed on the server (exit $rc propagated through the installer).
   The install is on disk but NOT trusted. Read the verifier output above.
   Nothing was cut over — the Mac is still serving." ;;
  esac
}

# Default: import data only if the server has none yet (the installer decides).
# --import-data forces it. The cutover always re-imports a fresh snapshot.
# Phase A: skip_tunnel=1 (dormant), allow_overwrite=$IMPORT_DATA, skip_data=0.
# The installer places data only if the server has none yet; a DIFFERENT existing
# file makes it exit 33 rather than clobber live records.
run_install 1 "$IMPORT_DATA" 0
ok "install_server.sh finished green — portal on 127.0.0.1:$PORT, tunnel NOT installed yet"
info "the installer ran deploy/verify_server.sh itself; exit 0 means it passed"

# ═════════════════════════════════════════════════════════════════════════════
# 7 — VERIFY (again, independently of the installer's own run)
# ═════════════════════════════════════════════════════════════════════════════
step "Verify the server"

# install_server.sh already ran deploy/verify_server.sh and propagated its exit
# code, so reaching here means it passed once. We run it again by hand, exactly
# as the installer does (service user, same env), because the operator should
# SEE the health of the machine they are about to hand the business to.
verify_remote() {
  remote "sudo -u auralis env HOME=/opt/auralis AURALIS_PORT='$PORT' AURALIS_HOSTNAME='$PUB_HOST' \
          AURALIS_ENV_FILE=/etc/auralis/portal.env bash /opt/auralis/app/portal/deploy/verify_server.sh $1"
}
soft; VOUT="$(verify_remote "" 2>&1)"; VRC=$?; hard
printf '%s\n' "$VOUT" | sed 's/^/   /'
if [ $VRC -ne 0 ]; then
  die "verify_server.sh did not pass (exit $VRC).
   The Mac is still serving https://$PUB_HOST — nothing was cut over.
   Fix what is red above and re-run this script."
fi
ok "verify_server.sh: PASS"
case "$VOUT" in
  *stub*|*STUB*) warn "the verifier mentions the STUB provider — reports would be boiler-plate,"
                 warn "not real drafts. Fix the Claude token before you send anything to a client." ;;
esac

# ═════════════════════════════════════════════════════════════════════════════
# 8 — CUTOVER (offered, never silent)
# ═════════════════════════════════════════════════════════════════════════════
step "Cutover"

cat <<EOF

   The server is installed, healthy and idle. Right now:
     • the Mac still serves https://$PUB_HOST  (its launchd agent + its tunnel)
     • the server runs the portal on 127.0.0.1:$PORT with a copy of the data
     • the server has NO cloudflared yet — deliberately, so the two machines
       can never both be connectors for tunnel $TUNNEL_ID (Cloudflare
       would balance between them and half the requests would hit the wrong
       database)

   The cutover, in one move:
     1. take a FRESH snapshot (the Mac kept working during the install) and
        import it on the server
     2. stop the Mac's launchd agent com.auralis.portal  ← point of no return
        for "the Mac must stay on": the Mac stops serving and stops its tunnel
     3. install and start cloudflared-auralis on the server
     4. re-verify, this time through https://$PUB_HOST

   No DNS change is needed — the server uses the SAME tunnel id, so the existing
   $PUB_HOST record already points at it.
   Undo at any time:  bash portal/deploy/rollback_to_mac.sh

EOF

if [ "$DO_CUTOVER" != 1 ]; then
  printf '   %sInstall-only run.%s Re-run with --cutover when you are ready to switch.\n' "$B" "$N"
  printf '   Until then nothing changes for your clients.\n\n'
  exit 0
fi

CONFIRM_WORD="${AURALIS_CONFIRM_CUTOVER:-}"
if [ -z "$CONFIRM_WORD" ]; then
  [ -t 0 ] || die "cutover needs a typed confirmation; run interactively or set AURALIS_CONFIRM_CUTOVER=CUTOVER"
  printf '   %sType CUTOVER to switch the live site to the server:%s ' "$B" "$N"
  read -r CONFIRM_WORD || true
fi
[ "$CONFIRM_WORD" = "CUTOVER" ] || { printf '   Not confirmed — nothing changed.\n'; exit 0; }

info "fresh snapshot…"
SNAP_INFO="$(snapshot_db)" || die "fresh snapshot failed — cutover aborted, the Mac is untouched"
if [ -f "$CLIENTS_FILE" ]; then
  cp "$CLIENTS_FILE" "$PAYLOAD/clients.json"; chmod 600 "$PAYLOAD/clients.json"
fi
ok "$SNAP_INFO"
ship auralis.db
if [ -f "$PAYLOAD/clients.json" ]; then ship clients.json; fi

# Import BEFORE stopping the Mac: if the key refuses the fresh DB (exit 35), or
# the server has diverged (exit 33), the Mac is still live and nothing is lost.
# allow_overwrite=1 here is the whole point of the cutover — and the installer
# still copies the file it replaces into /var/backups/auralis first.
run_install 1 1 0
ok "fresh data imported and accepted by the server's key"

info "stopping the Mac's launchd agent (com.auralis.portal)…"
if [ -f "$PLIST" ]; then
  launchctl unload "$PLIST" 2>/dev/null || launchctl bootout "gui/$(id -u)/com.auralis.portal" 2>/dev/null || true
  ok "launchd agent unloaded — the Mac no longer serves or tunnels"
else
  warn "no $PLIST — was the agent ever installed? Stopping any manual launcher instead."
  pkill -f start_auralis.command 2>/dev/null || true
fi

info "installing and starting the server's tunnel…"
# skip_tunnel=0 now; skip_data=1 because the data we just imported is already in
# place and must not be re-examined.
run_install 0 0 1
ok "cloudflared-auralis is running (enabled at boot)"

step "Final verification (through the public URL)"
soft; VOUT="$(verify_remote "" 2>&1)"; VRC=$?; hard
printf '%s\n' "$VOUT" | sed 's/^/   /'

# The server verifying itself over the loopback cannot prove that Cloudflare
# reaches it. This one request travels the whole path the client takes:
# Mac → Cloudflare edge → tunnel → server. It is the only honest cutover proof.
PUB_CODE=000
i=0
while [ $i -lt 24 ]; do
  PUB_CODE="$(curl -sS -m 8 -o /dev/null -w '%{http_code}' "https://$PUB_HOST/" 2>/dev/null || echo 000)"
  case "$PUB_CODE" in 2*|3*) break ;; esac
  if [ -t 1 ]; then printf '   %s… waiting for https://%s through Cloudflare (last: %s)%s\r' "$D" "$PUB_HOST" "$PUB_CODE" "$N"; fi
  sleep 5; i=$((i + 1))
done
if [ -t 1 ]; then printf '\r%s\r' "                                                                            "; fi

case "$PUB_CODE" in
  2*|3*) ok "https://$PUB_HOST answers $PUB_CODE from the public internet" ;;
  *)     VRC=1; warn "https://$PUB_HOST returned '$PUB_CODE' — Error 1033 means no connector is registered" ;;
esac

if [ $VRC -eq 0 ]; then
  printf '\n%s✓ Live on the server. The Mac can be switched off.%s\n\n' "$G" "$N"
  printf '   Check yourself, in this order:\n'
  printf '     1. https://%s/book       — the booking wizard loads\n' "$PUB_HOST"
  printf '     2. https://%s/staff      — your key works and the client list is COMPLETE\n' "$PUB_HOST"
  printf '     3. one client → draft a report — the console must say provider "claude_cli", never "stub"\n'
  printf '     4. generate a PDF — it must be the 12-page PDF, not an .html fallback\n'
  printf '\n   Day to day from now on: just `git push` — auralis-update.timer deploys\n'
  printf '   within ~2 minutes. Logs:  ssh %s journalctl -u auralis-portal -f\n' "$TARGET"
  printf '\n   Something wrong?  bash portal/deploy/rollback_to_mac.sh   (back on the Mac in ~1 min)\n\n'
else
  warn "final verification did NOT pass."
  printf '\n   %sRoll back now — one command:%s  bash portal/deploy/rollback_to_mac.sh\n\n' "$B" "$N"
  exit 1
fi
