#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Auralis Natura — roll the live site back from the server to the Mac.
#
# WHERE THIS RUNS:  on Desiree's MacBook, inside the repo.
#
#       bash portal/deploy/rollback_to_mac.sh
#
# This is the calm undo for migrate_to_server.sh. In order:
#   1. rescue the server's data first (best effort) — a consistent SQLite
#      snapshot pulled into ~/auralis-rollback/<ts>/. It is NEVER promoted over
#      the Mac's database automatically; --adopt-server-data does that, after
#      backing up what the Mac has.
#   2. stop the server's tunnel FIRST, so Cloudflare stops routing there, then
#      the portal + timers. Everything is also `disable`d so a reboot cannot
#      quietly bring the server back and create two live connectors.
#   3. bring the Mac back: reload the launchd agent com.auralis.portal (which
#      starts both the Flask server and the Mac's tunnel).
#   4. verify 127.0.0.1 and then the public URL.
#
# It works even if the server is unreachable: every remote action is best-effort
# and reported, and the Mac is brought back regardless. Nothing on the server is
# deleted — the data stays there for a second attempt at migrating.
#
# ⚠ THE ONE THING THAT CAN LOSE WORK: anything entered through the portal or the
# console WHILE the server was live lives in the SERVER's database. Step 1 pulls
# it down; read the printed path before you carry on working on the Mac.
#
# Written for the Mac's bash 3.2: no associative arrays, no readarray, no ${x,,}.
# ─────────────────────────────────────────────────────────────────────────────
set -Eeuo pipefail

TARGET="${AURALIS_TARGET:-root@178.105.10.156}"
PUB_HOST="${AURALIS_TUNNEL_HOSTNAME:-api.auralisnatura.com}"
PORT="${AURALIS_PORT:-5056}"
ADOPT=0        # --adopt-server-data : promote the server's DB over the Mac's
SKIP_PULL=0    # --no-pull           : do not try to rescue the server's data
ASSUME_YES=0   # --yes

if [ -t 1 ]; then B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; D=$'\033[2m'; N=$'\033[0m'
else B=''; G=''; Y=''; R=''; D=''; N=''; fi
STEP=0
step() { STEP=$((STEP + 1)); printf '\n%s[%d/5] %s%s\n' "$B" "$STEP" "$1" "$N"; }
ok()   { printf '   %s✓%s %s\n' "$G" "$N" "$1"; }
info() { printf '   %s·%s %s\n' "$D" "$N" "$1"; }
warn() { printf '   %s!%s %s\n' "$Y" "$N" "$1" >&2; }
die()  { printf '\n%s✗ %s%s\n' "$R" "$1" "$N" >&2; exit "${2:-1}"; }

trap '_rc=$?; printf "\n%s✗ rollback_to_mac.sh hit an error at line %s (exit %s) — see above%s\n" "$R" "$LINENO" "$_rc" "$N" >&2' ERR

usage() {
  cat <<EOF
Usage: bash portal/deploy/rollback_to_mac.sh [options]

  --target user@host     SSH target                    (default: $TARGET)
  --hostname HOST        public hostname to re-check    (default: $PUB_HOST)
  --port N               loopback port                  (default: $PORT)
  --adopt-server-data    promote the rescued server DB over the Mac's
                         (the Mac's current DB is backed up first)
  --no-pull              skip the data rescue (faster; only if the server never
                         served real traffic)
  --yes                  no questions
  -h, --help             this text
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --target)   TARGET="${2:?}"; shift 2 ;;
    --hostname) PUB_HOST="${2:?}"; shift 2 ;;
    --port)     PORT="${2:?}"; shift 2 ;;
    --adopt-server-data) ADOPT=1; shift ;;
    --no-pull)  SKIP_PULL=1; shift ;;
    --yes|-y)   ASSUME_YES=1; shift ;;
    -h|--help)  usage; exit 0 ;;
    *) usage >&2; die "unknown option: $1" ;;
  esac
done

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
PORTAL_DIR="$(cd "$SELF_DIR/.." && pwd)"
DB_FILE="$PORTAL_DIR/auralis.db"
CLIENTS_FILE="$PORTAL_DIR/config/clients.json"
PLIST="$HOME/Library/LaunchAgents/com.auralis.portal.plist"
LABEL="com.auralis.portal"
TS="$(date -u '+%Y%m%d-%H%M%S')"
# Deliberately OUTSIDE the repo: the self-updating launcher runs `git reset --hard`
# and a stray `git clean -fd` would delete an untracked folder — this one holds
# special-category health data and must not depend on gitignore rules.
RESCUE="$HOME/auralis-rollback/$TS"

SSH_CTL="/tmp/.auralis-rollback-$$.sock"
SSH_OPTS="-o ControlMaster=auto -o ControlPath=$SSH_CTL -o ControlPersist=120 -o ConnectTimeout=8"
cleanup() { local rc=$?; ssh $SSH_OPTS -O exit "$TARGET" >/dev/null 2>&1 || true; rm -f "$SSH_CTL" 2>/dev/null || true; exit $rc; }
trap cleanup EXIT INT TERM

confirm() {
  [ "$ASSUME_YES" = 1 ] && return 0
  [ -t 0 ] || return 1
  local a=""; printf '   %s%s%s [y/N] ' "$B" "$1" "$N"; read -r a || true
  case "$a" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

# ── safety helpers for --adopt-server-data ───────────────────────────────────
# Promoting the server's database over the Mac's is the only destructive act in
# this script, so it is gated three ways: the Mac stops writing, the rescued copy
# is proven readable with THIS Mac's key, and what is about to be replaced is
# copied first — WAL included.

# Read the key the way lib/cfg.py does (env wins, else portal/.env), normalised
# exactly as systemd and install_server.sh normalise it: strip `export `, a
# trailing CR, and ONE surrounding quote pair. Getting this wrong derives a
# DIFFERENT Fernet key and makes a perfectly good database look corrupt.
mac_data_key() {
  if [ -n "${AURALIS_DATA_KEY:-}" ]; then printf '%s' "$AURALIS_DATA_KEY"; return 0; fi
  [ -f "$PORTAL_DIR/.env" ] || return 1
  sed -n 's/^[[:space:]]*\(export[[:space:]][[:space:]]*\)\{0,1\}AURALIS_DATA_KEY=//p' "$PORTAL_DIR/.env" \
    | tail -n 1 | tr -d '\r' | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/"
}

# Does the rescued database actually open with this Mac's key, and does it hold
# anything? store.key_matches_store() is the same probe the server runs at boot,
# so we reuse it rather than re-implementing Fernet. Counting first over a
# read-only URI means the probe cannot create a records table and then cheerfully
# report "match" on an empty file.
# Prints one of: match:<n> | mismatch:<n> | unreadable:<n> | norecords:0
db_opens_with_mac_key() { # <path> → 0 only when it decrypts AND holds records
  local db="$1" key
  key="$(mac_data_key || true)"
  if [ -z "$key" ]; then printf 'nokey:0'; return 1; fi
  AURALIS_DATA_KEY="$key" AURALIS_ENV=production \
  python3 - "$PORTAL_DIR" "$db" <<'PY'
import pathlib, sqlite3, sys
portal, db = sys.argv[1], sys.argv[2]
sys.path.insert(0, portal)
try:
    n = sqlite3.connect(f"file:{db}?mode=ro", uri=True).execute(
        "SELECT COUNT(*) FROM records").fetchone()[0]
except Exception:
    print("norecords:0"); sys.exit(2)
from lib import store
store._DB = pathlib.Path(db)          # probe the rescued copy, never the live one
store._INIT_DONE = False
m = store.key_matches_store()
print(("match" if m is True else "mismatch" if m is False else "unreadable") + f":{n}")
sys.exit(0 if (m is True and n > 0) else 1)
PY
}

# Stop the Mac's portal so nothing is mid-write when the file is swapped.
stop_mac_portal() {
  launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 \
    || launchctl unload "$PLIST" >/dev/null 2>&1 || true
  local i=0
  while [ "$i" -lt 20 ]; do
    pgrep -f 'start_auralis\.command' >/dev/null 2>&1 || return 0
    sleep 0.5; i=$((i + 1))
  done
  pkill -f 'start_auralis\.command' >/dev/null 2>&1 || true
  sleep 1
}

# A `cp` of the .db alone is NOT a backup: a WAL holds committed transactions
# that have not been checkpointed yet, so the most recent bookings would be
# silently dropped. SQLite's online backup API folds the WAL in.
safety_copy_mac_db() { # → prints the path it wrote
  local dest="$PORTAL_DIR/auralis.pre-rollback-$TS.db"
  python3 - "$DB_FILE" "$dest" <<'PY'
import sqlite3, sys
s = sqlite3.connect(sys.argv[1]); d = sqlite3.connect(sys.argv[2])
with d: s.backup(d)
d.close(); s.close()
PY
  chmod 600 "$dest"; printf '%s' "$dest"
}

# Every remote call is best-effort: an unreachable server must NOT stop us from
# bringing the Mac back — that is the whole point of a rollback.
SERVER_UP=0
remote_try() { # remote_try "<remote command>"  → prints output, never aborts
  ssh $SSH_OPTS "$TARGET" "$1" 2>/dev/null || return 1
}

printf '%s\nAuralis Natura — rollback: server ➜ Mac%s\n' "$B" "$N"
printf '  target  %s\n' "$TARGET"
printf '  public  https://%s\n' "$PUB_HOST"

if ! confirm "Roll the live site back to this Mac now?"; then
  printf '   Nothing changed.\n'; exit 0
fi

# ═════════════════════════════════════════════════════════════════════════════
step "Reach the server"
# ═════════════════════════════════════════════════════════════════════════════
# Probe without a prompt first (a rollback must never hang on a passphrase), but
# if that fails and we have a terminal, give SSH one interactive chance — an
# unreachable-looking server we simply skip would keep serving, and once the Mac
# is back BOTH would be connectors for the same tunnel.
if ssh $SSH_OPTS -o BatchMode=yes "$TARGET" true >/dev/null 2>&1; then
  SERVER_UP=1; ok "server reachable"
elif [ -t 0 ] && ssh $SSH_OPTS "$TARGET" true; then
  SERVER_UP=1; ok "server reachable (interactive login)"
else
  SERVER_UP=0
  warn "server $TARGET is NOT reachable."
  warn "Continuing anyway: the Mac will be brought back. Once the server IS"
  warn "reachable, stop its units so it can never become a second connector:"
  warn "  ssh $TARGET 'systemctl disable --now cloudflared-auralis auralis-portal auralis-update.timer auralis-backup.timer'"
fi

# ═════════════════════════════════════════════════════════════════════════════
step "Rescue the server's data (never promoted automatically)"
# ═════════════════════════════════════════════════════════════════════════════
RESCUED=""
if [ "$SKIP_PULL" = 1 ]; then
  info "skipped (--no-pull)"
elif [ "$SERVER_UP" = 0 ]; then
  warn "cannot rescue data from an unreachable server — do it before you rely on the Mac's copy:"
  warn "  ssh $TARGET \"python3 -c \\\"import sqlite3;s=sqlite3.connect('/var/lib/auralis/auralis.db');d=sqlite3.connect('/tmp/an.db');s.backup(d)\\\"\""
else
  mkdir -p "$RESCUE"; chmod 700 "$HOME/auralis-rollback" "$RESCUE"
  # NOT a fixed path in /tmp. This host is shared with another company's ERP, so
  # a predictable name in a world-writable directory is a symlink race that ends
  # with root's sqlite3 writing wherever an attacker points it — and, on a failed
  # scp, leaves the whole client database sitting in /tmp. mktemp -d under /root
  # is unguessable and unreachable by anyone but root.
  RTMP="$(remote_try "umask 077; mktemp -d /root/.auralis-rescue.XXXXXX" | tr -d '\r')" || RTMP=""
  if [ -z "$RTMP" ]; then
    warn "could not create a scratch dir on the server — skipping the data rescue"
  # Online backup API, exactly like lib/backup.py — a raw scp of a WAL database
  # can hand back a torn file that looks fine until the first read fails.
  elif remote_try "umask 077; python3 -c \"
import sqlite3
s=sqlite3.connect('/var/lib/auralis/auralis.db'); d=sqlite3.connect('$RTMP/auralis.db')
s.backup(d); d.close(); s.close()
print('ok')\"" >/dev/null; then
    if scp $SSH_OPTS -q "$TARGET:$RTMP/auralis.db" "$RESCUE/auralis.db" 2>/dev/null; then
      chmod 600 "$RESCUE/auralis.db"; RESCUED="$RESCUE/auralis.db"
      # clients.json is portal logins + consent — PII, so 0600 like the backbone
      if scp $SSH_OPTS -q "$TARGET:/var/lib/auralis/clients.json" "$RESCUE/clients.json" 2>/dev/null; then
        chmod 600 "$RESCUE/clients.json"
      fi
      # output_docs too: the generated report PDFs and the .eml audit trail are
      # part of the delta, and the runbook promises they come back with it.
      if remote_try "tar -czf '$RTMP/output_docs.tar.gz' -C /var/lib/auralis output_docs" >/dev/null \
         && scp $SSH_OPTS -q "$TARGET:$RTMP/output_docs.tar.gz" "$RESCUE/output_docs.tar.gz" 2>/dev/null; then
        chmod 600 "$RESCUE/output_docs.tar.gz"
        ok "reports + .eml audit trail rescued → $RESCUE/output_docs.tar.gz"
      else
        warn "could not rescue output_docs (reports/.eml) — they remain on the server"
      fi
      remote_try "rm -rf -- '$RTMP'" >/dev/null || true
      ok "server data rescued → $RESCUE"
      info "$(python3 -c 'import sqlite3,sys
c=sqlite3.connect(sys.argv[1])
try: n=c.execute("SELECT COUNT(*) FROM records").fetchone()[0]
except Exception: n="?"
print(f"{n} client records in the rescued copy")' "$RESCUE/auralis.db" 2>/dev/null || echo 'rescued copy present')"
    else
      warn "could not copy the snapshot down — continuing with the rollback"
    fi
  else
    warn "could not snapshot the server database — continuing with the rollback"
  fi
fi

# ═════════════════════════════════════════════════════════════════════════════
step "Stop the server (tunnel first, then the app)"
# ═════════════════════════════════════════════════════════════════════════════
if [ "$SERVER_UP" = 1 ]; then
  # Tunnel FIRST: the moment cloudflared-auralis stops, Cloudflare has only the
  # Mac's connector left, so traffic follows the Mac as soon as it is back.
  # ONLY auralis-* units are named here — a pre-existing cloudflared for the
  # other company's ERP is never referenced, let alone restarted.
  for unit in cloudflared-auralis auralis-update.timer auralis-backup.timer auralis-portal; do
    if remote_try "systemctl disable --now '$unit'" >/dev/null; then ok "stopped + disabled $unit"
    else warn "could not stop $unit (may not be installed) — check manually"; fi
  done
  LEFT="$(remote_try "systemctl is-active cloudflared-auralis auralis-portal 2>/dev/null | tr '\n' ' '" || true)"
  info "server unit states now: ${LEFT:-unknown}"
  info "server data left in place at /var/lib/auralis (nothing deleted)"
else
  warn "skipped — server unreachable"
fi

# ═════════════════════════════════════════════════════════════════════════════
step "Bring the Mac back"
# ═════════════════════════════════════════════════════════════════════════════
if [ "$ADOPT" = 1 ] && [ -n "$RESCUED" ]; then
  # 1. Nobody may be writing while we swap the file out from under the app.
  stop_mac_portal
  ok "Mac's portal stopped for the swap"

  # 2. Prove the rescued copy opens with THIS Mac's key BEFORE destroying the
  #    Mac's own. cfg.py accepts a passphrase as well as a real Fernet key, so a
  #    server whose portal.env was ever retyped can hold a database this Mac can
  #    never read — and the old code deleted the original first, which made that
  #    unrecoverable. Refuse rather than warn.
  VERDICT="$(db_opens_with_mac_key "$RESCUED")" || {
    die "the rescued server database is not usable with this Mac's AURALIS_DATA_KEY (${VERDICT:-no verdict}).
   NOTHING has been changed — the Mac still has its own database.
   The rescued copy is kept at: $RESCUED
   Re-run without --adopt-server-data to bring the Mac back on its own data."
  }
  ok "rescued database decrypts with this Mac's key ($VERDICT)"

  # 3. Only now back up what we are about to replace — .db AND its WAL/SHM, via
  #    the online backup API, because a WAL holds committed transactions the main
  #    file does not yet contain.
  if [ -f "$DB_FILE" ]; then
    BK="$(safety_copy_mac_db)"
    ok "Mac's current DB backed up (WAL folded in) → $(basename "$BK")"
  fi
  if [ -f "$CLIENTS_FILE" ]; then
    cp "$CLIENTS_FILE" "$PORTAL_DIR/config/clients.pre-rollback-$TS.json"
    chmod 600 "$PORTAL_DIR/config/clients.pre-rollback-$TS.json"
    ok "Mac's clients.json backed up → config/clients.pre-rollback-$TS.json"
  fi

  # 4. Swap.
  rm -f "$DB_FILE" "$DB_FILE-wal" "$DB_FILE-shm"      # clear stale WAL before swapping
  cp "$RESCUED" "$DB_FILE"; chmod 600 "$DB_FILE"
  # `[ -f x ] && cp` as a bare statement is a set -e landmine: when the file is
  # absent the whole script exits — right here, with the database already
  # swapped and launchd not yet reloaded, i.e. the Mac left offline.
  if [ -f "$RESCUE/clients.json" ]; then cp "$RESCUE/clients.json" "$CLIENTS_FILE"; fi
  ok "server data promoted to the Mac (--adopt-server-data)"
elif [ -n "$RESCUED" ]; then
  info "the Mac keeps its own database; the server's copy waits in $RESCUE"
  info "to promote it later:  bash portal/deploy/rollback_to_mac.sh --adopt-server-data --no-pull"
fi

if ! command -v launchctl >/dev/null 2>&1; then
  die "no launchctl — this script has to run on the Mac that hosts the portal"
fi
if [ ! -f "$PLIST" ]; then
  warn "no $PLIST — installing the autostart agent now"
  bash "$PORTAL_DIR/tools/install_autostart.sh" \
    || warn "install_autostart.sh failed — start the Mac by hand: open portal/start_auralis.command"
else
  # `enable` FIRST and unconditionally. The cutover in migrate_to_server.sh stops
  # the Mac with an explicit `launchctl disable`, and that override SURVIVES a
  # `load -w`/`bootstrap` — without this line the rollback looks like it worked,
  # prints a green tick, and the Mac never actually comes back.
  launchctl enable "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
  launchctl load -w "$PLIST" 2>/dev/null \
    || launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null \
    || true
  launchctl kickstart -k "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
  ok "launchd agent $LABEL loaded (starts Flask + the Mac's tunnel, restarts on crash)"
fi

# ═════════════════════════════════════════════════════════════════════════════
step "Verify the Mac is serving again"
# ═════════════════════════════════════════════════════════════════════════════
LOCAL_OK=0
i=0
while [ $i -lt 40 ]; do            # up to ~2 min: launcher does a git fetch first
  if curl -fsS -m 4 -o /dev/null "http://127.0.0.1:$PORT/" 2>/dev/null; then LOCAL_OK=1; break; fi
  if [ -t 1 ]; then printf '   %s… waiting for 127.0.0.1:%s%s\r' "$D" "$PORT" "$N"; fi
  sleep 3; i=$((i + 1))
done
if [ -t 1 ]; then printf '\r%s\r' "                                                  "; fi
if [ "$LOCAL_OK" = 1 ]; then ok "the Mac's portal answers on 127.0.0.1:$PORT"
else
  warn "127.0.0.1:$PORT is not answering yet."
  warn "Look at:  tail -n 50 $PORTAL_DIR/.logs/portal.err.log"
fi

PUB_OK=0
i=0
while [ $i -lt 20 ]; do            # the tunnel needs a few seconds to register
  CODE="$(curl -fsS -m 6 -o /dev/null -w '%{http_code}' "https://$PUB_HOST/" 2>/dev/null || echo 000)"
  case "$CODE" in 2*|3*) PUB_OK=1; break ;; esac
  if [ -t 1 ]; then printf '   %s… waiting for https://%s (last: %s)%s\r' "$D" "$PUB_HOST" "$CODE" "$N"; fi
  sleep 5; i=$((i + 1))
done
if [ -t 1 ]; then printf '\r%s\r' "                                                                  "; fi
if [ "$PUB_OK" = 1 ]; then ok "https://$PUB_HOST is served by the Mac again"
else warn "https://$PUB_HOST is not green yet — Error 1033 means no connector is registered; give the Mac's tunnel a minute."; fi

# ── what to check ───────────────────────────────────────────────────────────
if [ "$LOCAL_OK" = 1 ] && [ "$PUB_OK" = 1 ]; then
  printf '\n%s✓ Rolled back. The Mac is live again — leave it switched on.%s\n' "$G" "$N"
else
  printf '\n%s! Rollback finished with warnings — read them above.%s\n' "$Y" "$N"
fi
cat <<EOF

   Check, in this order:
     1. https://$PUB_HOST/staff   — your key works and the client list is COMPLETE
     2. one client → open the record — no 500 (a 500 here means the data key does
        not match the database that is now in place)
     3. the Mac must stay ON and logged in for the site to stay up

   Server state: units stopped AND disabled, data untouched at /var/lib/auralis.
   Nothing was deleted, so a second attempt only needs:
     bash portal/deploy/migrate_to_server.sh --cutover
EOF
if [ -n "$RESCUED" ]; then
  cat <<EOF

   ⚠ Work done while the SERVER was live is in the rescued copy, not on the Mac:
       $RESCUE
     Promote it with:  bash portal/deploy/rollback_to_mac.sh --adopt-server-data --no-pull
     (the Mac's current database is backed up first)
EOF
fi
printf '\n'
