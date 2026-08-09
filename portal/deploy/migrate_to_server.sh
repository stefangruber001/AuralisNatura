#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Auralis Natura — move the portal off the Mac and onto the Hetzner server.
#
# WHERE THIS RUNS:  on Desiree's MacBook, inside the repo.  THE one command:
#
#       bash portal/deploy/migrate_to_server.sh
#
# WHAT IT DOES, and why in EXACTLY this order:
#
#   PHASE A — REHEARSAL. The Mac stays live the whole time; nothing a client can
#      see moves. preflight → prove the local DB opens with the key we are about
#      to ship → consistent snapshot → Claude token → assert the tunnel identity
#      → ship a root-only payload → install_server.sh with AURALIS_SKIP_TUNNEL=1
#      → verify WITHOUT --public. The server ends up warm (code, venv, data,
#      chromium, systemd) but its cloudflared is deliberately NOT installed, so
#      the Mac remains the ONLY connector for the tunnel.
#
#   PHASE B — CUTOVER. Only after a typed confirmation, and strictly in this
#      order, because every other order loses data or forks the truth:
#        B1 stop the Mac PERSISTENTLY (bootout **and** disable). A bare `unload`
#           or `bootout` is session-scoped: the agent has RunAtLoad+KeepAlive and
#           no Disabled key, so launchd re-bootstraps it at the next login and
#           the Mac silently becomes a SECOND connector for the same tunnel.
#           Cloudflare load-balances between connectors, so half of the traffic
#           would hit the Mac's now-stale database — and /health answers 200 from
#           either machine, so nobody would notice.
#        B2 POLL until the Mac is really out: no launcher process, no cloudflared
#           holding OUR tunnel, nothing listening on the portal port. On timeout:
#           abort and put the Mac back.
#        B3 ONLY NOW snapshot the database and pack output_docs. Snapshotting
#           before the Mac is stopped strands every booking and intake taken
#           between the snapshot and the stop — silently, because the second
#           installer pass used to skip data.
#        B4 ONE authoritative install run: data imported (overwrite allowed),
#           tunnel installed and started.
#        B5 verify WITH --public, plus one real request through the Cloudflare
#           edge. Failures here are FATAL, not warnings.
#        B6 any failure in B4/B5 (or a crash, or Ctrl-C) → the server's tunnel is
#           stopped and the Mac is automatically re-enabled and restarted. Both
#           sides are never left down, and never both up.
#      No DNS change is needed: the server runs the SAME tunnel id, so the
#      existing api.auralisnatura.com CNAME already points at it.
#
# Re-running is safe at any point. Nothing is imported over existing server data
# unless we are doing the cutover (or --import-data is passed).
#
# SECRETS: the payload (data key, SMTP password, Claude token, the encrypted DB,
# clients.json) is staged in a 0700 dir locally and in /root/.auralis-payload on
# the server — never /tmp, which is world-writable, shared with another company's
# ERP and not aged out by Debian. It is shredded on every exit path and the
# remote copy is VERIFIED gone before this script reports success.
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
LABEL="com.auralis.portal"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

PAYLOAD=""            # local staging dir — CONTAINS SECRETS, shredded on every exit
LWORK=""              # local scratch (install log, probe HOME) — NEVER shipped
# Fixed, root-only remote staging path. Deliberately NOT mktemp in /tmp: /tmp on
# this host is 1777, shared with another company's production ERP, and neither
# Debian nor Ubuntu age it out — a forgotten payload there is the data key
# sitting next to the database it decrypts, forever. /root is 0700 by default.
RDIR="/root/.auralis-payload"
RDIR_STAGED=0         # 1 once we have created/filled it (arms the shred backstop)
MAC_STOPPED=0         # 1 between B1 and either a finished cutover or resume_mac
CUTOVER_DONE=0        # 1 only once the server is verified live
SRV_TUNNEL_UP=0       # 1 once we have ASKED the server to run the tunnel
# Filled in by step 5; pre-declared because `set -u` is on and the helpers above
# are defined before they exist.
TUNNEL_ID=""
TUNNEL_CFG_BASE=""
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
# the cutover adds two steps: the stop-and-hand-over itself, and the public re-verification
if [ "$DO_CUTOVER" = 1 ]; then TOTAL_STEPS=10; fi

# ── SECRET HYGIENE ───────────────────────────────────────────────────────────
# The payload holds the data key, the SMTP password, the Claude token, the
# encrypted client database and clients.json. It must not survive this process —
# not on success, not on failure, not on Ctrl-C, and not on the server.
wipe_local() {
  local d wiped=0
  for d in "$PAYLOAD" "$LWORK"; do
    [ -n "$d" ] || continue
    [ -d "$d" ] || continue
    wiped=1
    chmod -R u+w "$d" 2>/dev/null || true
    # Overwrite before unlinking where we can. macOS has no shred(1); BSD `rm -P`
    # overwrites in place. On APFS/SSD neither guarantees erasure — the real
    # protection is that the directory is 0700 and lives for one run only.
    if command -v shred >/dev/null 2>&1; then
      find "$d" -type f -exec shred -u {} + 2>/dev/null || true
    else
      find "$d" -type f -exec rm -Pf {} + 2>/dev/null || true
    fi
    rm -rf "$d" 2>/dev/null || true
  done
  [ "$wiped" = 1 ] && printf '\n%s· local payload shredded%s\n' "$D" "$N"
  return 0
}

# Backstop only: install_server.sh shreds the payload itself on every terminal
# outcome except exit 30 (retryable). We still shred, and then PROVE it is gone —
# "we asked it to be deleted" is not the same statement as "it is deleted".
shred_remote() {
  [ "$RDIR_STAGED" = 1 ] || return 0
  local out=""
  out="$(ssh $SSH_OPTS -o BatchMode=yes "$TARGET" "
      if [ -d '$RDIR' ]; then
        find '$RDIR' -type f -exec shred -u {} + 2>/dev/null || true
        rm -rf '$RDIR'
      fi
      if [ -e '$RDIR' ]; then printf LEFTOVER; else printf GONE; fi" 2>/dev/null || printf 'UNREACHABLE')"
  case "$out" in
    GONE) printf '   %s· remote payload verified gone (%s:%s)%s\n' "$D" "$TARGET" "$RDIR" "$N" ;;
    *)    printf '\n%s! THE REMOTE PAYLOAD MAY STILL EXIST — %s:%s (%s)%s\n' "$Y" "$TARGET" "$RDIR" "$out" "$N" >&2
          printf '  It contains AURALIS_DATA_KEY, the SMTP password, the Claude token and client data.\n' >&2
          printf '  Remove it by hand, now:\n    ssh %s "find %s -type f -exec shred -u {} +; rm -rf %s"\n' \
                 "$TARGET" "$RDIR" "$RDIR" >&2 ;;
  esac
  return 0
}

cleanup() {
  local rc=$?
  trap - EXIT INT TERM ERR; set +e     # a trap must never trip its own traps
  # B6 backstop. Any exit between "the Mac was stopped" and "the server is
  # verified live" — die, ERR, Ctrl-C, SIGTERM — must bring the Mac back.
  if [ "$MAC_STOPPED" = 1 ] && [ "$CUTOVER_DONE" = 0 ]; then resume_mac; fi
  wipe_local
  shred_remote
  ssh $SSH_OPTS -O exit "$TARGET" >/dev/null 2>&1 || true
  rm -f "$SSH_CTL" 2>/dev/null || true
  exit $rc
}
trap cleanup EXIT INT TERM

# ── stopping and restarting the Mac (the cutover's point of no return) ───────
stop_mac() { # B1 — PERSISTENTLY stop the Mac's portal + its tunnel
  local uid; uid="$(id -u)"
  MAC_STOPPED=1          # from here on the EXIT trap owns bringing the Mac back
  if [ -f "$PLIST" ]; then
    # `bootout` (and a bare `unload`) is SESSION-scoped. tools/install_autostart.sh
    # writes the plist with RunAtLoad + KeepAlive and no <Disabled/> key, so
    # launchd re-bootstraps it at the next GUI login — a second connector for the
    # same tunnel, and a silent split brain. `disable` writes the persistent
    # override; on older macOS `unload -w` writes the legacy equivalent.
    launchctl bootout "gui/$uid/$LABEL" >/dev/null 2>&1 || true
    if launchctl disable "gui/$uid/$LABEL" >/dev/null 2>&1; then
      ok "launchd agent booted out AND disabled (survives login and reboot)"
    elif launchctl unload -w "$PLIST" >/dev/null 2>&1; then
      ok "launchd agent unloaded -w (legacy persistent disable)"
    else
      warn "could NOT persistently disable $LABEL. Do it by hand before the next login,"
      warn "or the Mac becomes a second connector:"
      warn "  launchctl bootout gui/$uid/$LABEL ; launchctl disable gui/$uid/$LABEL"
    fi
  else
    warn "no $PLIST — stopping a manually started launcher instead"
  fi
  pkill -f 'start_auralis\.command' >/dev/null 2>&1 || true
}

mac_serving_evidence() { # prints one token per piece of evidence; empty = the Mac is out
  # Never match the bare word "cloudflared": Paramur's tunnel may legitimately be
  # running on this Mac and is none of our business. Only OUR tunnel id and OUR
  # config file name count.
  if pgrep -f 'start_auralis\.command' >/dev/null 2>&1; then printf 'launcher '; fi
  if pgrep -f "cloudflared.*$TUNNEL_ID" >/dev/null 2>&1; then printf 'cloudflared(tunnel-id) '; fi
  if [ -n "$TUNNEL_CFG_BASE" ] && pgrep -f "cloudflared.*$TUNNEL_CFG_BASE" >/dev/null 2>&1; then
    printf 'cloudflared(config) '
  fi
  if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    printf 'listener:%s ' "$PORT"
  fi
  return 0
}

wait_mac_gone() { # B2 — 0 when the Mac is provably out, 1 on timeout
  local start el ev termed=0 killed=0
  start="$(date +%s)"
  while :; do
    ev="$(mac_serving_evidence)"
    if [ -z "$ev" ]; then
      if [ -t 1 ]; then printf '\r%s\r' "                                                                  "; fi
      return 0
    fi
    el=$(( $(date +%s) - start ))
    if [ "$el" -ge 120 ]; then
      if [ -t 1 ]; then printf '\n'; fi
      warn "the Mac is STILL serving after 120s: $ev"
      return 1
    fi
    # Escalate on our own patterns only. TERM first: the launcher's own EXIT trap
    # kills the cloudflared child it started, which is cleaner than killing it.
    # NB: every pkill ends in `|| true` — a pkill that matches nothing exits 1,
    # and under errexit that would abort the cutover at the best possible moment.
    if [ "$el" -ge 10 ] && [ "$termed" = 0 ]; then
      pkill -f 'start_auralis\.command' >/dev/null 2>&1 || true
      pkill -f "cloudflared.*$TUNNEL_ID" >/dev/null 2>&1 || true
      if [ -n "$TUNNEL_CFG_BASE" ]; then pkill -f "cloudflared.*$TUNNEL_CFG_BASE" >/dev/null 2>&1 || true; fi
      termed=1
    fi
    if [ "$el" -ge 60 ] && [ "$killed" = 0 ]; then
      pkill -9 -f 'start_auralis\.command' >/dev/null 2>&1 || true
      pkill -9 -f "cloudflared.*$TUNNEL_ID" >/dev/null 2>&1 || true
      if [ -n "$TUNNEL_CFG_BASE" ]; then pkill -9 -f "cloudflared.*$TUNNEL_CFG_BASE" >/dev/null 2>&1 || true; fi
      killed=1
    fi
    if [ -t 1 ]; then printf '   %s… waiting for the Mac to let go (%ss): %s%s\r' "$D" "$el" "$ev" "$N"; fi
    sleep 2
  done
}

resume_mac() { # B6 — bring the Mac back, but NEVER as a second connector
  local tun="down" code=""
  printf '\n%s──────── restoring the Mac ────────%s\n' "$B" "$N" >&2
  if [ "$SRV_TUNNEL_UP" = 1 ]; then
    # The server may already BE a connector. Starting the Mac now would put two
    # connectors on one tunnel — exactly the split brain this script exists to
    # prevent. So: server tunnel down first, and if we cannot prove it is down,
    # do NOT start the Mac.
    if ssh $SSH_OPTS -o BatchMode=yes "$TARGET" true >/dev/null 2>&1; then
      ssh $SSH_OPTS "$TARGET" "systemctl disable --now cloudflared-auralis" >/dev/null 2>&1 || true
      if ssh $SSH_OPTS "$TARGET" "systemctl is-active --quiet cloudflared-auralis" >/dev/null 2>&1; then
        tun="up"
      fi
    else
      # Cannot ask the server; ask the public edge instead. A 2xx/3xx means
      # SOMETHING is still serving the hostname, and it is not the Mac.
      code="$(curl -sS -m 8 -o /dev/null -w '%{http_code}' "https://$PUB_HOST/" 2>/dev/null || echo 000)"
      case "$code" in 2*|3*) tun="up" ;; esac
    fi
  fi
  if [ "$tun" = "up" ]; then
    printf '%s! NOT starting the Mac: the server still serves https://%s.%s\n' "$R" "$PUB_HOST" "$N" >&2
    printf '  Two connectors on one tunnel = half the traffic on a stale database.\n' >&2
    printf '  Stop the server first, then start the Mac:\n' >&2
    printf '    ssh %s "systemctl disable --now cloudflared-auralis auralis-portal"\n' "$TARGET" >&2
    printf '    bash portal/deploy/rollback_to_mac.sh\n' >&2
    return 1
  fi
  local uid; uid="$(id -u)"
  # `enable` FIRST: an explicit `launchctl disable` survives `load -w`/`bootstrap`,
  # so without it the agent silently refuses to come back.
  launchctl enable "gui/$uid/$LABEL" >/dev/null 2>&1 || true
  if [ -f "$PLIST" ]; then
    launchctl bootstrap "gui/$uid" "$PLIST" >/dev/null 2>&1 \
      || launchctl load -w "$PLIST" >/dev/null 2>&1 || true
    launchctl kickstart -k "gui/$uid/$LABEL" >/dev/null 2>&1 || true
    printf '%s✓ launchd agent %s enabled and loaded again — the Mac serves https://%s%s\n' \
           "$G" "$LABEL" "$PUB_HOST" "$N" >&2
  else
    printf '%s! no %s — start the Mac by hand: open portal/start_auralis.command%s\n' "$Y" "$PLIST" "$N" >&2
  fi
  MAC_STOPPED=0
  return 0
}

confirm() { # confirm "question"  → 0 yes / 1 no  (honours --yes)
  [ "$ASSUME_YES" = 1 ] && return 0
  [ -t 0 ] || return 1
  local a=""
  printf '   %s%s%s [y/N] ' "$B" "$1" "$N"
  read -r a || true
  case "$a" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

# Read one KEY from portal/.env the way start_auralis.command does — comments on
# their own line, value is everything after the FIRST '=' — plus the two
# line-level artifacts that side does not handle: a UTF-8 BOM on line 1 (Windows
# editors) and a leading `export ` (which would otherwise become part of the KEY
# and make the lookup silently miss).
env_get() {
  [ -f "$ENV_FILE" ] || return 0
  awk -v k="$1" '
    { line=$0
      if (NR == 1) sub(/^\357\273\277/, "", line)      # UTF-8 BOM
      sub(/^[ \t]+/,"",line)
      sub(/^export[ \t]+/,"",line)
      if (line ~ /^#/ || line == "") next
      eq = index(line,"="); if (eq == 0) next
      key = substr(line,1,eq-1); gsub(/[ \t]/,"",key)
      if (key == k) { print substr(line,eq+1); exit } }' "$ENV_FILE"
}

# ── D8: ENV VALUE NORMALISATION — the same semantics on both sides ───────────
# The Mac's launcher exports .env values LITERALLY (start_auralis.command:
# val="${line#*=}"). systemd's EnvironmentFile — and install_server.sh's keycheck,
# which deliberately mirrors it — strips exactly one matched pair of surrounding
# quotes and a trailing CR. If the two disagree, cfg._derive() hashes a DIFFERENT
# string on each machine and the migrated store cannot be decrypted at all.
# So: normalise ONCE, here, exactly the way the reader will, ship the normalised
# form, and then PROVE (step 2) that the normalised key still opens the store.
# Nothing is expanded, ever — a passphrase is a literal string.
env_norm() {
  local v="$1"
  v="${v#$'\xef\xbb\xbf'}"                     # UTF-8 BOM
  v="${v%$'\r'}"                               # trailing CR from a CRLF file
  case "$v" in
    \"*\") v="${v#\"}"; v="${v%\"}" ;;         # exactly ONE matched pair
    \'*\') v="${v#\'}"; v="${v%\'}" ;;
  esac
  printf '%s' "$v"
}

# systemd does not expand $VAR or `cmd` in an EnvironmentFile, but a shell that
# sources the file (a human debugging, or a future tool) does — and a value that
# means two different things on two machines is the same failure as a mis-quoted
# key. Refuse it here rather than debug it after the cutover.
assert_no_expansion() { # assert_no_expansion <NAME> <value>
  case "$2" in
    *'$'*|*'`'*)
      die "$1 in $ENV_FILE contains a \$ or a backtick.
   Some readers expand those and some do not, so the value would differ between
   the Mac and the server — for AURALIS_DATA_KEY that silently bricks the store.
   Change the secret to one without \$ or \` (and re-key the store if it is the
   data key), then re-run." ;;
  esac
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
# *_RAW is what the Mac's launcher exports today; the unsuffixed name is what the
# server will see. They differ only when the .env value is quoted or CRLF — and
# for AURALIS_DATA_KEY that difference is fatal, so step 2 proves it.
API_KEY_RAW="$(env_get AURALIS_API_KEY)";        API_KEY="$(env_norm "$API_KEY_RAW")"
SECRET_RAW="$(env_get AURALIS_SECRET)";          SECRET="$(env_norm "$SECRET_RAW")"
DATA_KEY_RAW="$(env_get AURALIS_DATA_KEY)";      DATA_KEY="$(env_norm "$DATA_KEY_RAW")"
SMTP_PW_RAW="$(env_get AURALIS_SMTP_PASSWORD)";  SMTP_PW="$(env_norm "$SMTP_PW_RAW")"
for pair in "AURALIS_API_KEY:$API_KEY" "AURALIS_SECRET:$SECRET" "AURALIS_DATA_KEY:$DATA_KEY"; do
  name="${pair%%:*}"; val="${pair#*:}"
  [ -n "$val" ] || die "$name is empty in $ENV_FILE — the server refuses to start in production without it"
  case "$val" in
    change-me*|dev-staff-key-change-me|dev-secret-change-me|REPLACE_WITH_A_LONG_RANDOM_STRING)
      die "$name is still a placeholder in $ENV_FILE — set a real secret first" ;;
  esac
  assert_no_expansion "$name" "$val"
done
assert_no_expansion AURALIS_SMTP_PASSWORD "$SMTP_PW"
[ -n "$SMTP_PW" ] || warn "AURALIS_SMTP_PASSWORD is empty — the server will not be able to send/draft mail"
if [ "$API_KEY" != "$API_KEY_RAW" ] || [ "$SECRET" != "$SECRET_RAW" ] || [ "$SMTP_PW" != "$SMTP_PW_RAW" ]; then
  warn "some .env values are quoted or CRLF-terminated; the quotes/CR are NOT part of"
  warn "the secret on the server (systemd strips them) — normalised before shipping."
fi
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
# this is the one that has actually bitten this project. The key we probe with is
# the NORMALISED one — i.e. exactly the bytes the server's cfg.data_key() will
# see — so a quoting problem is caught here, on the Mac, with nothing shipped.
probe_key() { # probe_key <key> → "MATCH <n>" | "MISMATCH -1" | "UNREADABLE -1"
  cd "$PORTAL_DIR" && AURALIS_DATA_KEY="$1" python3 - <<'PY' 2>&1
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd()))
from lib import store
r = store.key_matches_store()
n = len(store.list_records()) if r is not False else -1
print({True: "MATCH", False: "MISMATCH", None: "UNREADABLE"}[r], n)
PY
}

soft; KEYCHECK="$(probe_key "$DATA_KEY")"; KC_RC=$?; hard
[ $KC_RC -eq 0 ] || die "could not probe the local store:
$KEYCHECK"
case "$KEYCHECK" in
  MATCH*)      ok "AURALIS_DATA_KEY opens the live store (${KEYCHECK#MATCH } records)" ;;
  MISMATCH*)
    # Before blaming the key, check whether the RAW .env value opens it. If it
    # does, the quotes are part of the key on this Mac and stripping them (which
    # systemd does whether we like it or not) would leave the server unable to
    # read a single record.
    if [ "$DATA_KEY" != "$DATA_KEY_RAW" ]; then
      soft; RAWCHECK="$(probe_key "$DATA_KEY_RAW")"; hard
      case "$RAWCHECK" in
        MATCH*) die "AURALIS_DATA_KEY in $ENV_FILE is QUOTED, and this Mac's store is
   encrypted with the quotes included. systemd strips one matched pair of quotes
   from an EnvironmentFile value, so the server would derive a different key and
   every staff read would 500 — the July failure, in slow motion.
   Fix it deliberately, on the Mac, BEFORE migrating:
     · decrypt/re-encrypt the store with the unquoted key, or
     · restore a backup that was written with the unquoted key (tools/restore.py)
   Then remove the quotes from $ENV_FILE and re-run." ;;
      esac
    fi
    die "AURALIS_DATA_KEY does NOT match auralis.db on this Mac.
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
# Scratch that must NEVER reach the server: the installer log and the throwaway
# HOME the Claude CLI probe writes its state (and possibly cached credentials)
# into. Keeping it out of $PAYLOAD is what makes "the payload is exactly the
# documented contract files" a true statement instead of a hopeful one.
LWORK="$(mktemp -d "${TMPDIR:-/tmp}/auralis-work.XXXXXX")"
chmod 700 "$LWORK"
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
else:
    # Say what actually happened. An empty store makes key_matches_store() return
    # True as well, so two green lines could otherwise be read as proof that the
    # key is right when nothing was decrypted at all.
    print(f"0 client records, {ev} funnel events — store is EMPTY, the key was NOT exercised")
PY
}

announce_snapshot() { # print the snapshot summary and shout if it proved nothing
  ok "$SNAP_INFO"
  case "$SNAP_INFO" in
    *EMPTY*) warn "the snapshot contains NO client records. If this Mac is supposed to hold"
             warn "live clients, STOP: something restored or truncated the store." ;;
  esac
}
SNAP_INFO="$(snapshot_db)" || die "snapshot failed — the shipped key could not open the shipped database"
announce_snapshot

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

# Scrub whitespace out of whatever we were handed. `claude setup-token` prints
# the token hard-wrapped across two lines, so copying it out of the terminal and
# pasting it into CLAUDE_CODE_OAUTH_TOKEN='…' very easily carries the newline
# inside the quotes. The result is a token that is correct apart from a \n in the
# middle, and the only symptom is a baffling
#     API Error: Header 'Authorization' has invalid value
# because an HTTP header cannot contain a line break. Tokens are strictly
# [A-Za-z0-9_-], so deleting every whitespace character is always safe and
# always right — there is no legitimate token with a space in it.
if [ -n "$CLAUDE_TOKEN" ]; then
  _tok_raw_len=${#CLAUDE_TOKEN}
  CLAUDE_TOKEN="$(printf '%s' "$CLAUDE_TOKEN" | tr -d '[:space:]')"
  if [ "${#CLAUDE_TOKEN}" -ne "$_tok_raw_len" ]; then
    warn "the token from $TOKEN_SOURCE contained $(( _tok_raw_len - ${#CLAUDE_TOKEN} )) whitespace character(s) — stripped"
    warn "  (that is the terminal's line-wrap sneaking into the paste; harmless now)"
  fi
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
  RAW="$LWORK/.setup-token.typescript"     # scratch, not payload: never shipped
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
# This text came from `script`, i.e. from a PTY, so every line ends "\r\n" — not
# "\n". Strip the carriage returns FIRST or the de-wrap below cannot match: the
# character before the newline is \r, never a token character. (Learned the hard
# way — a de-wrap tested against plain \n looked correct and still returned 98
# characters of a 108-character token in the real thing.)
raw = raw.replace("\r", "")
# Cut the prose off FIRST. The CLI prints, after the token, "Store this token
# securely…" and "Use this token by setting…". The de-wrap below joins a line
# ending in token characters to the next line starting with one, and if the
# blank line between them is missing or padded it happily welds "Store" onto the
# end of the token — 108 characters became 113, still a 401. Everything from
# those markers on is prose, never token, so drop it before joining anything.
for marker in ("Store this token", "Use this token", "You won't be able"):
    i = raw.find(marker)
    if i != -1:
        raw = raw[:i]
# The CLI HARD-WRAPS the token at the terminal width, so a ~108-char token
# arrives as two lines and `\n` is not in the character class below — matching
# without rejoining returns only the first line. Rejoin a line that ENDS in
# token characters with the next line that BEGINS with one.
raw = re.sub(r"([A-Za-z0-9_-])\n[ \t]*([A-Za-z0-9_-])", r"\1\2", raw)
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
TOKEN_RETRIED=0
while [ -n "$CLAUDE_TOKEN" ] && [ "$TOKEN_PROBE" = 1 ] && command -v claude >/dev/null 2>&1; do
  info "testing the token in a clean environment (up to 120s)…"
  soft
  # HOME for the probe lives in $LWORK, never in $PAYLOAD: the CLI writes .claude/
  # state, session transcripts and possibly cached credentials there, and the
  # payload is copied to a server that belongs to somebody else too.
  PROBE="$(CLAUDE_TOKEN="$CLAUDE_TOKEN" SCRATCH="$LWORK/probe-home" python3 - <<'PY' 2>&1
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
    PASS*) ok "CLAUDE_CODE_OAUTH_TOKEN works with a clean HOME → the server will get real drafts"
           break ;;
    # A 401 here is almost never a "local quirk": it means the token we are about
    # to ship does not authenticate, so lib/agent.py falls back to the stub
    # provider and every client report becomes obvious placeholder text. That is
    # the same class of silent degradation as chromium falling back to .html, and
    # it gets the same treatment — stop, rather than discover it in a client's
    # report. The commonest cause was the CLI hard-wrapping the token across two
    # lines and the capture above taking only the first (see the de-wrap there).
    "UNVERIFIED claude not on PATH")
           warn "could not probe the token: the claude CLI is not on PATH here."
           warn "verify_server.sh probes it again on the server; the console must"
           warn "show provider 'claude_cli', never 'stub'."
           break ;;
    *)     printf '\n'
           warn "token NOT verified: ${PROBE#UNVERIFIED }"
           if [ "${#CLAUDE_TOKEN}" -lt 100 ]; then
             warn "the captured token is only ${#CLAUDE_TOKEN} characters — these are normally ~108."
             warn "That is the signature of a token truncated at a terminal line wrap."
           fi
           # A bad token that got remembered would be picked up by the NEXT run in
           # preference to minting a fresh one, turning one failure into a loop
           # that no amount of re-running escapes. Forget it here so the retry
           # starts clean.
           if [ -f "$TOKEN_STORE" ]; then
             rm -f "$TOKEN_STORE"
             warn "removed the remembered copy at $TOKEN_STORE so the next run re-mints"
           fi
           # Reading the token back out of a terminal transcript has now failed
           # three ways (character class, CRLF, welded prose). Rather than send
           # the operator round the loop a fourth time, ask for it directly —
           # the token is still on screen right above, the paste is scrubbed of
           # whitespace, and we re-probe immediately. One retry only.
           if [ "$TOKEN_RETRIED" -eq 0 ] && [ -t 0 ]; then
             TOKEN_RETRIED=1
             printf '\n'
             warn "reading it from the CLI output did not give a working token."
             say "   The token is printed above. Select it — BOTH lines if it wrapped —"
             say "   copy, and paste it here. Any line breaks or spaces are stripped."
             printf '   token (hidden): '
             stty -echo 2>/dev/null || true
             read -r _PASTED || true
             # A WRAPPED paste arrives as two lines and `read` stops at the first
             # newline, leaving the rest in the buffer — which would reproduce
             # exactly the truncation this retry exists to escape. Drain anything
             # else that arrived (a paste lands all at once) and glue it on.
             while read -r -t 1 _more; do _PASTED="$_PASTED$_more"; done
             stty echo 2>/dev/null || true
             printf '\n'
             _PASTED="$(printf '%s' "$_PASTED" | tr -d '[:space:]')"
             if [ -n "$_PASTED" ]; then
               CLAUDE_TOKEN="$_PASTED"; TOKEN_SOURCE="pasted"
               ok "got ${#CLAUDE_TOKEN} characters — re-testing"
               continue
             fi
             warn "nothing pasted"
           fi
           die "refusing to ship a token that does not authenticate — the report agent
   would silently fall back to 'stub' and every client draft would be placeholder text.
   Fix it one of these ways, then re-run:
     · mint a fresh one and pass it in explicitly (most reliable):
         claude setup-token
         CLAUDE_CODE_OAUTH_TOKEN='<paste the WHOLE token>' bash portal/deploy/MIGRATE.command
     · or accept stub reports deliberately for now:  --allow-stub
     · or skip only this check if you know the token is good:  --no-token-probe" ;;
  esac
done

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
# Used by the cutover to recognise OUR cloudflared process (and only ours) —
# basename, because the full path may contain spaces and lands in a pgrep regex.
TUNNEL_CFG_BASE="$(basename "$TUNNEL_CFG")"

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
# and never deletes, so re-runs are additive. Re-packed at the cutover, because
# the Mac keeps generating PDFs during the rehearsal phase.
pack_docs() {
  [ "$SEND_DOCS" = 1 ] || return 0
  [ -d "$PORTAL_DIR/output_docs" ] || return 0
  rm -f "$PAYLOAD/output_docs.tar.gz"
  # COPYFILE_DISABLE + the excludes: macOS bsdtar otherwise serialises extended
  # attributes and resource forks as AppleDouble `._name` members, and GNU tar on
  # the server extracts those as REAL files into the live report store, where
  # they are counted by preflight, backed up nightly and never cleaned up.
  ( cd "$PORTAL_DIR/output_docs" \
    && COPYFILE_DISABLE=1 tar czf "$PAYLOAD/output_docs.tar.gz" \
         --exclude '._*' --exclude '.DS_Store' . )
  chmod 600 "$PAYLOAD/output_docs.tar.gz"
  ok "output_docs packed ($(find "$PORTAL_DIR/output_docs" -type f | wc -l | tr -d ' ') files, $(du -h "$PAYLOAD/output_docs.tar.gz" | cut -f1 | tr -d ' '))"
}
pack_docs

# /etc/auralis/portal.env — the installer normalises this into
# /etc/auralis/portal.env (0640 root:auralis). It OWNS AURALIS_PORT and
# AURALIS_CHROME (it strips and re-sets them), so we deliberately send neither
# a chrome path nor anything it would have to override.
# EVERY value written here is the D8-normalised one: what systemd will hand the
# service must be byte-identical to what this Mac's store was encrypted with.
if [ -n "$CLAUDE_TOKEN" ]; then assert_no_expansion CLAUDE_CODE_OAUTH_TOKEN "$CLAUDE_TOKEN"; fi
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

# MANIFEST carries no secrets — it is the audit trail of what was shipped. It is
# rewritten at the cutover so db-sha256 always describes the database that is
# actually in the payload. (No key fingerprint: this file lands on a shared host,
# and a hash of a passphrase is a brute-force oracle.)
write_manifest() {
  {
    printf 'auralis-migration-payload v1\n'
    printf 'created      %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'phase        %s\n' "$1"
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
}
write_manifest rehearsal
ok "payload staged (0700, secrets inside — shredded on exit)"

# rsync when both ends have a capable one, else tar-over-ssh — recent macOS
# ships openrsync, which does not understand --chmod. Either way the remote
# umask keeps every file 0600 inside a 0700 dir.
ship_payload() {
  # EXPLICIT include list, not `.`: the contract in install_server.sh names these
  # files and nothing else, and an explicit list is the only way to guarantee that
  # a scratch file created later cannot ride along to a host we do not own.
  local f list=""
  for f in portal.env auralis.db clients.json tunnel.json output_docs.tar.gz install_server.sh MANIFEST; do
    if [ -f "$PAYLOAD/$f" ]; then list="$list $f"; fi
  done
  [ -n "$list" ] || die "internal error: nothing to ship"
  # $list is deliberately unquoted — it is a fixed set of literal, space-free names.
  if [ "$XFER" = rsync ] && remote 'command -v rsync >/dev/null 2>&1'; then
    if ( cd "$PAYLOAD" && rsync -a --chmod=D700,F600 -e "ssh $SSH_OPTS" $list "$TARGET:$RDIR/" ) >/dev/null 2>&1; then
      return 0
    fi
    warn "rsync failed — falling back to tar over ssh"
  fi
  ( cd "$PAYLOAD" && tar czf - $list ) | remote "umask 077; tar xzf - -C '$RDIR'"
}

stage_remote() { # (re)create the root-only payload dir and deliver the payload
  # Root-only, fixed path. The installer shreds it when it finishes (except on
  # the retryable exit 30), so the cutover re-stages instead of leaving secrets
  # lying around between phases.
  remote "umask 077
          mkdir -p '$RDIR'
          chown root:root '$RDIR'
          chmod 700 '$RDIR'
          find '$RDIR' -mindepth 1 -type f -exec shred -u {} + 2>/dev/null || true
          rm -rf '$RDIR'/* '$RDIR'/.[!.]* 2>/dev/null || true" \
    || die "could not create the payload directory $RDIR on $TARGET"
  RDIR_STAGED=1        # arms the shred-and-verify backstop in cleanup()
  ship_payload
  remote "chmod 700 '$RDIR'; find '$RDIR' -type f -exec chmod 600 {} +"
  ok "payload delivered to $TARGET:$RDIR (0700 root:root, files 0600)"
}
stage_remote

# Secrets travel in the payload FILES, never on the command line — argv is
# world-readable in `ps` and this host runs another company's production ERP.
# Every name below is install_server.sh's documented contract. AURALIS_KEEP_PAYLOAD
# is deliberately NOT set: the installer must shred the payload itself on every
# terminal outcome except exit 30, so the secrets' lifetime never depends on this
# laptop keeping its Wi-Fi long enough to run a trap.
REQUIRE_TOKEN=0
if [ -n "$CLAUDE_TOKEN" ]; then REQUIRE_TOKEN=1; fi
INSTALL_LOG=""
remote_install() { # remote_install <skip_tunnel> <allow_overwrite> <skip_data>
  ssh $SSH_OPTS "$TARGET" \
    "AURALIS_PAYLOAD_DIR='$RDIR' AURALIS_REPO_URL='$REPO_URL' AURALIS_BRANCH='$BRANCH' \
     AURALIS_TUNNEL_ID='$TUNNEL_ID' AURALIS_HOSTNAME='$PUB_HOST' AURALIS_PORT='$PORT' \
     AURALIS_REQUIRE_VERIFY=1 AURALIS_REQUIRE_CLAUDE_TOKEN='$REQUIRE_TOKEN' \
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
  INSTALL_LOG="$LWORK/install.log"      # scratch, never shipped
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

# PHASE A — rehearsal: skip_tunnel=1 (dormant), allow_overwrite=$IMPORT_DATA,
# skip_data=0. The server ends up warm and holding a copy of the data, but it is
# not a connector, so the Mac is still the only machine serving the hostname.
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
# `runuser`, never `sudo`: the whole kit drops privileges with runuser (the
# installer, update.sh, verify's own as_svc) and sudo is NOT in the installer's
# package list — a Debian netinst without sudo would fail this step with exit 127
# on a perfectly good install. `su -s /bin/bash` is the fallback for the same
# reason. Every value interpolated below is space-free (port, hostname, paths),
# which is what makes the inner `su -c` string safe.
verify_remote() { # verify_remote [--public]
  local flag="${1:-}"
  remote "V=/opt/auralis/app/portal/deploy/verify_server.sh
    E=\"HOME=/opt/auralis AURALIS_PORT=$PORT AURALIS_HOSTNAME=$PUB_HOST AURALIS_ENV_FILE=/etc/auralis/portal.env\"
    if command -v runuser >/dev/null 2>&1; then
      exec runuser -u auralis -- env \$E bash \"\$V\" $flag
    else
      exec su -s /bin/bash auralis -c \"env \$E bash \$V $flag\"
    fi"
}
# Pre-cutover: NO --public. The tunnel is deliberately dormant and the Mac still
# owns the hostname, so tunnel/public findings are warnings here (verify's own
# phase() mechanism), not failures.
soft; VOUT="$(verify_remote 2>&1)"; VRC=$?; hard
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

   The cutover, in this exact order (nothing else is safe):
     1. stop the Mac PERSISTENTLY (bootout + disable, survives login/reboot) and
        WAIT until no launcher, no cloudflared of ours and no listener on port
        $PORT is left        ← point of no return for "the Mac must stay on"
     2. only then snapshot the database and re-pack output_docs — with no writers
        alive, so nothing entered in the last minutes can be stranded
     3. one authoritative install run on the server: import the data AND start
        cloudflared-auralis
     4. verify with --public, and fetch https://$PUB_HOST through Cloudflare

   There is a short outage between 1 and 3 (roughly the length of one install
   run, a minute or two). That is deliberate: an outage is recoverable, a booking
   written to a machine that is about to be abandoned is not.

   If anything fails after step 1, the server's tunnel is stopped and the Mac is
   automatically re-enabled and restarted — you are never left with both down.

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

step "Cutover — stop the Mac, then hand the tunnel over"

# ── B1: stop the Mac, persistently ───────────────────────────────────────────
info "stopping the Mac's launchd agent ($LABEL)…"
stop_mac

# ── B2: prove it. Nothing may be shipped while a writer can still be alive ───
info "waiting until the Mac has really let go (launcher, tunnel, port $PORT)…"
if ! wait_mac_gone; then
  # cleanup() will re-enable and restart the Mac on the way out.
  die "the Mac did not stop within 120s, so a second writer may still be live.
   Nothing was shipped and the server is still dormant; the Mac is being
   restarted. Find what is holding on:
     pgrep -fl 'start_auralis.command|cloudflared'
     lsof -nP -iTCP:$PORT -sTCP:LISTEN"
fi
ok "the Mac is out: no launcher, no Auralis cloudflared, nothing on port $PORT"

# ── B3: NOW take the snapshot. No writers ⇒ nothing can be stranded ──────────
info "snapshot with no writers alive…"
SNAP_INFO="$(snapshot_db)" || die "snapshot failed after the Mac was stopped — the Mac is being restarted"
announce_snapshot
if [ -f "$CLIENTS_FILE" ]; then
  cp "$CLIENTS_FILE" "$PAYLOAD/clients.json"; chmod 600 "$PAYLOAD/clients.json"
fi
pack_docs                     # PDFs generated during the rehearsal come too
write_manifest cutover
stage_remote                  # the installer shredded the rehearsal payload

# ── B4: ONE authoritative install run — data AND tunnel ──────────────────────
# skip_tunnel=0, allow_overwrite=1, skip_data=0. Doing data and tunnel in the
# same pass is what closes the old gap: there is no second run that "skips data"
# and no window in which the Mac serves while a stale snapshot travels.
info "importing the final data and starting the server's tunnel…"
SRV_TUNNEL_UP=1               # from here resume_mac must stop the server first
run_install 0 1 0
ok "final data imported, accepted by the server's key, cloudflared-auralis running"

step "Final verification (through the public URL)"
# --public: post-cutover this host IS the live one, so an inactive tunnel, an
# unregistered connector or an unreachable https://$PUB_HOST are FAILURES, not
# warnings. Without the flag verify would print PASS over a dead tunnel.
soft; VOUT="$(verify_remote --public 2>&1)"; VRC=$?; hard
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
  CUTOVER_DONE=1          # disarms the automatic "put the Mac back" in cleanup()
  printf '\n%s✓ Live on the server. The Mac can be switched off.%s\n\n' "$G" "$N"
  printf '   Check yourself, in this order:\n'
  printf '     1. https://%s/book       — the booking wizard loads\n' "$PUB_HOST"
  printf '     2. https://%s/staff      — your key works and the client list is COMPLETE\n' "$PUB_HOST"
  printf '     3. one client → draft a report — the console must say provider "claude_cli", never "stub"\n'
  printf '     4. generate a PDF — it must be the 12-page PDF, not an .html fallback\n'
  printf '\n   The Mac'"'"'s launchd agent is booted out AND disabled, so switching the Mac\n'
  printf '   on again cannot turn it into a second connector. rollback_to_mac.sh\n'
  printf '   re-enables it when you want it back.\n'
  printf '\n   Day to day from now on: just `git push` — auralis-update.timer deploys\n'
  printf '   within ~2 minutes. Logs:  ssh %s journalctl -u auralis-portal -f\n' "$TARGET"
  printf '\n   Something wrong?  bash portal/deploy/rollback_to_mac.sh   (back on the Mac in ~1 min)\n\n'
else
  # B6: do NOT leave both sides down. cleanup() stops the server's tunnel and
  # brings the Mac back on the way out; say so loudly here so the operator knows
  # which machine is serving by the time the prompt returns.
  warn "final verification did NOT pass — rolling the cutover back automatically:"
  warn "the server's tunnel is being stopped and the Mac restarted."
  printf '\n   %sIf the Mac does not come back:%s  bash portal/deploy/rollback_to_mac.sh\n\n' "$B" "$N"
  exit 1
fi
