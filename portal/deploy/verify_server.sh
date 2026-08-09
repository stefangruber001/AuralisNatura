#!/usr/bin/env bash
# =============================================================================
#  verify_server.sh — RUNS **ON THE HETZNER SERVER**, no root required
# =============================================================================
#  Answers one question: "is the Auralis portal genuinely live on this host?"
#  It is read-only. It starts nothing, stops nothing, installs nothing and
#  changes no file — so it is safe to run at any moment, as often as you like,
#  on a box that also runs another company's production ERP ("canei-erp").
#
#  It is called twice by portal/deploy/migrate_to_server.sh:
#    1. after install, BEFORE the cutover  ->  bash verify_server.sh
#       the tunnel is installed but deliberately DORMANT, and the Mac still
#       serves api.auralisnatura.com. An inactive cloudflared-auralis and an
#       unreachable public URL are therefore WARNINGS here, not failures.
#    2. after the cutover                  ->  bash verify_server.sh --public
#       now this host IS the live one: the tunnel must be connected and
#       https://api.auralisnatura.com/health must answer. Both become FAILURES.
#  install_server.sh runs it as its own last stage and propagates the exit code.
#
#  It checks what portal/tools/preflight.py structurally cannot see — systemd,
#  the tunnel, ownership, the public edge — and then RUNS preflight.py inside
#  the venv as the `auralis` user and folds its results in, so one command gives
#  one verdict.
#
#  CONTRACT (other scripts code against this — do not break it)
#    • the LAST line is always exactly "VERIFY_RESULT: PASS" or
#      "VERIFY_RESULT: FAIL" (migrate_to_server.sh greps for it)
#    • exit 0 only when nothing FAILED; exit 1 on any FAIL; exit 2 on an
#      internal error (the ERR trap, which also prints VERIFY_RESULT: FAIL)
#    • WARN never changes the exit code — a warning is "look at this", a failure
#      is "do not cut over".
#
#  ENVIRONMENT (all optional; install_server.sh passes the first four)
#    AURALIS_PORT       [5056]                      loopback port
#    AURALIS_HOSTNAME   [api.auralisnatura.com]     public hostname
#    AURALIS_ENV_FILE   [/etc/auralis/portal.env]   systemd EnvironmentFile
#    HOME               [/opt/auralis]              service user's home
#    AURALIS_APP_DIR    [/opt/auralis/app]          git clone
#    AURALIS_VENV       [/opt/auralis/venv]         virtualenv
#    AURALIS_DATA_DIR   [/var/lib/auralis]          live data
#    AURALIS_USER       [auralis]                   service user
#
#  FLAGS
#    --public          require the tunnel + public URL (post-cutover mode)
#    --no-preflight    skip the embedded preflight.py run
#    --quick           skip preflight's slow probes (chromium PDF, claude -p)
#    --allow-stub      report preflight/agent as a WARNING instead of a failure.
#                      The report agent would fall back to the offline "stub"
#                      writer — deliberately accepted for now. Everything else
#                      still has to pass; the warning is never suppressed.
#    -h | --help
# =============================================================================
set -Eeuo pipefail

trap 'rc=$?; printf "\n%s✗ verify_server.sh crashed on line %s (exit %s)%s\n" \
      "${C_R:-}" "$LINENO" "$rc" "${C_0:-}" >&2; echo "VERIFY_RESULT: FAIL"; exit 2' ERR

# ------------------------------------------------------------------ config --
PORT="${AURALIS_PORT:-5056}"
HOSTNAME_ING="${AURALIS_HOSTNAME:-api.auralisnatura.com}"
ENV_FILE="${AURALIS_ENV_FILE:-/etc/auralis/portal.env}"
SVC_USER="${AURALIS_USER:-auralis}"
SVC_HOME="${AURALIS_SVC_HOME:-/opt/auralis}"
APP_DIR="${AURALIS_APP_DIR:-/opt/auralis/app}"
PORTAL_DIR="$APP_DIR/portal"
VENV="${AURALIS_VENV:-/opt/auralis/venv}"
DATA_DIR="${AURALIS_DATA_DIR:-/var/lib/auralis}"
BACKUP_DIR="${AURALIS_SYS_BACKUP_DIR:-/var/backups/auralis}"
# Fixed by the install contract; overridable only so this script can be
# exercised outside a real server (and so a rehearsal host can point elsewhere).
CF_CONF="${AURALIS_CF_CONF:-/etc/cloudflared/auralis.yml}"
# NOTE: this script is scp'd to a staging dir and run from there, so it must
# NEVER locate the portal relative to its own path — only via the absolutes above.

PUBLIC=0; DO_PREFLIGHT=1; QUICK=0; ALLOW_STUB=0
while [ $# -gt 0 ]; do
  case "$1" in
    --public)       PUBLIC=1 ;;
    --no-preflight) DO_PREFLIGHT=0 ;;
    --quick)        QUICK=1 ;;
    --allow-stub)   ALLOW_STUB=1 ;;
    -h|--help)      sed -n '2,50p' "$0"; exit 0 ;;
    *) printf 'unknown option: %s (try --help)\n' "$1" >&2; echo "VERIFY_RESULT: FAIL"; exit 2 ;;
  esac
  shift
done

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_G=$'\033[32m'; C_Y=$'\033[33m'; C_R=$'\033[31m'; C_B=$'\033[1m'; C_D=$'\033[2m'; C_0=$'\033[0m'
else
  C_G=""; C_Y=""; C_R=""; C_B=""; C_D=""; C_0=""
fi

N_PASS=0; N_WARN=0; N_FAIL=0
FAILURES=()

ok()   { N_PASS=$((N_PASS+1)); printf ' %sPASS%s  %-20s %s\n' "$C_G" "$C_0" "$1" "$2"; }
warn() { N_WARN=$((N_WARN+1)); printf ' %sWARN%s  %-20s %s\n' "$C_Y" "$C_0" "$1" "$2"; }
bad()  { N_FAIL=$((N_FAIL+1)); FAILURES+=("$1: $2")
         printf ' %sFAIL%s  %-20s %s\n' "$C_R" "$C_0" "$1" "$2"; }
info() { printf ' %s····%s  %-20s %s%s%s\n' "$C_D" "$C_0" "$1" "$C_D" "$2" "$C_0"; }
head2(){ printf '\n%s%s%s\n' "$C_B" "$1" "$C_0"; }

# Severity that depends on the phase: before the cutover the tunnel and the
# public URL are legitimately not live yet.
phase() { if [ "$PUBLIC" -eq 1 ]; then bad "$1" "$2"; else warn "$1" "$2"; fi; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/auralis-verify.XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

# a python we can rely on: the venv first (it is the one the service uses)
PY="$VENV/bin/python3"
[ -x "$PY" ] || PY="$(command -v python3 || true)"

# ------------------------------------------------------------------ helpers --
# fetch <url> <timeout> -> sets FETCH_CODE / FETCH_BODY / FETCH_ERR (never fails)
fetch() {
  FETCH_CODE="000"; FETCH_BODY=""; FETCH_ERR=""
  local url="$1" t="${2:-8}"
  if command -v curl >/dev/null 2>&1; then
    # NB: curl already prints "000" via %{http_code} when it cannot connect, so
    # the failure branch must NOT echo another 000 (that yields "000000").
    FETCH_CODE="$(curl -sS -L --max-redirs 3 -o "$TMP/body" -w '%{http_code}' \
                  --max-time "$t" "$url" 2>"$TMP/err" || true)"
    [ -n "$FETCH_CODE" ] || FETCH_CODE="000"
    FETCH_BODY="$(head -c 4000 "$TMP/body" 2>/dev/null || true)"
    FETCH_ERR="$(tr '\n' ' ' <"$TMP/err" 2>/dev/null | cut -c1-200 || true)"
  elif [ -n "$PY" ]; then
    # curl is not guaranteed on a minimal host; the stdlib always is.
    local out
    out="$("$PY" - "$url" "$t" <<'PY' 2>/dev/null || true
import sys, urllib.request, urllib.error
url, t = sys.argv[1], float(sys.argv[2])
try:
    with urllib.request.urlopen(url, timeout=t) as r:
        print(r.getcode()); print(r.read(4000).decode("utf-8", "replace"))
except urllib.error.HTTPError as e:
    print(e.code); print("")
except Exception as e:
    print("000"); print(f"{type(e).__name__}: {e}")
PY
)"
    FETCH_CODE="$(printf '%s' "$out" | head -n1)"
    FETCH_BODY="$(printf '%s' "$out" | tail -n +2)"
    if [ "$FETCH_CODE" = "000" ]; then FETCH_ERR="$FETCH_BODY"; fi
  else
    FETCH_ERR="neither curl nor python3 available"
  fi
  return 0
}

# run a command as the service user, whoever we happen to be right now.
# Returns 66 when that is impossible, so the caller can WARN instead of lying.
as_svc() {
  id -u "$SVC_USER" >/dev/null 2>&1 || return 66
  if [ "$(id -un)" = "$SVC_USER" ]; then
    "$@"
  elif [ "$(id -u)" = "0" ] && command -v runuser >/dev/null 2>&1; then
    runuser -u "$SVC_USER" -- "$@"
  elif [ "$(id -u)" = "0" ]; then
    su -s /bin/bash -c "$(printf '%q ' "$@")" "$SVC_USER"
  elif sudo -n true 2>/dev/null; then
    sudo -n -u "$SVC_USER" -- "$@"
  else
    return 66            # cannot become the service user — caller decides
  fi
}

unit_exists() { systemctl cat "$1" >/dev/null 2>&1; }

# check_unit <unit> <required: yes|phase|no>
check_unit() {
  local unit="$1" required="$2" en act sub extra=""
  if ! unit_exists "$unit"; then
    case "$required" in
      yes)   bad   "$unit" "not installed — install_server.sh did not write /etc/systemd/system/$unit" ;;
      phase) phase "$unit" "not installed (expected if the tunnel step was skipped)" ;;
      *)     warn  "$unit" "not installed" ;;
    esac
    return 0
  fi
  en="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
  act="$(systemctl is-active "$unit" 2>/dev/null || true)"
  sub="$(systemctl show "$unit" --property=SubState --value 2>/dev/null || true)"
  case "$unit" in
    auralis-portal.service)
      local nr pid since
      nr="$(systemctl show "$unit" --property=NRestarts --value 2>/dev/null || echo '?')"
      pid="$(systemctl show "$unit" --property=MainPID --value 2>/dev/null || echo '?')"
      since="$(systemctl show "$unit" --property=ActiveEnterTimestamp --value 2>/dev/null || true)"
      extra=" · pid $pid · restarts $nr · up since ${since:-unknown}"
      ;;
  esac
  if [ "$act" = "active" ] && [ "$en" = "enabled" ]; then
    ok "$unit" "enabled + active ($sub)$extra"
  elif [ "$act" = "active" ]; then
    bad "$unit" "active but NOT enabled ($en) — it would not come back after a reboot: systemctl enable $unit"
  elif [ "$en" = "enabled" ]; then
    case "$required" in
      phase) phase "$unit" "enabled but NOT active ($act/$sub)$extra — journalctl -u $unit -n 50" ;;
      *)     bad   "$unit" "enabled but NOT active ($act/$sub)$extra — journalctl -u $unit -n 50" ;;
    esac
  else
    case "$required" in
      phase) phase "$unit" "not enabled and not active ($en/$act)" ;;
      *)     bad   "$unit" "not enabled and not active ($en/$act)" ;;
    esac
  fi
}

# stat_of <path> -> "mode owner group" (empty when the path is missing)
stat_of() { stat -c '%a %U %G' "$1" 2>/dev/null || true; }

printf '%sAuralis verify%s  ·  %s  ·  as %s  ·  %s\n' "$C_B" "$C_0" \
       "$(hostname -f 2>/dev/null || hostname)" "$(id -un)" \
       "$([ "$PUBLIC" -eq 1 ] && echo 'POST-CUTOVER (public required)' || echo 'pre-cutover')"
printf '%s\n' "────────────────────────────────────────────────────────────────────────────"

# =============================================================================
head2 "systemd units"
# =============================================================================
if ! command -v systemctl >/dev/null 2>&1; then
  bad "systemd" "systemctl not found — this script must run ON the server"
else
  check_unit auralis-portal.service yes
  check_unit auralis-update.timer   yes
  check_unit auralis-backup.timer   yes
  # The oneshot services behind the timers are inactive between runs — that is
  # correct, so we only assert they EXIST and report their last result.
  for u in auralis-update.service auralis-backup.service; do
    if unit_exists "$u"; then
      res="$(systemctl show "$u" --property=Result --value 2>/dev/null || true)"
      last="$(systemctl show "$u" --property=ExecMainExitTimestamp --value 2>/dev/null || true)"
      if [ "$res" = "success" ] || [ -z "$res" ]; then
        info "$u" "oneshot · last result: ${res:-never run} ${last:+(${last})}"
      else
        warn "$u" "last run did NOT succeed (Result=$res ${last:-}) — journalctl -u $u -n 50"
      fi
    else
      bad "$u" "not installed — the timer has nothing to trigger"
    fi
  done
  check_unit cloudflared-auralis.service phase

  # Timers must actually be scheduled; an enabled timer with no next elapse is
  # a real (and quiet) failure mode.
  # The column layout of `list-timers` is not stable across systemd versions, so
  # we pick the unit name out of whichever column it sits in and then ask
  # systemd itself for the next elapse rather than parsing the pretty table.
  while read -r unit; do
    [ -n "$unit" ] || continue
    nxt="$(systemctl show "$unit" --property=NextElapseUSecRealtime --value 2>/dev/null || true)"
    if [ -z "$nxt" ] || [ "$nxt" = "0" ]; then
      # a monotonic timer (OnBootSec/OnUnitActiveSec) has no wall-clock elapse
      nxt="$(systemctl show "$unit" --property=NextElapseUSecMonotonic --value 2>/dev/null || true)"
      [ -z "$nxt" ] || [ "$nxt" = "0" ] || nxt="$nxt after boot"
    fi
    if [ -z "$nxt" ] || [ "$nxt" = "0" ] || [ "$nxt" = "n/a" ]; then
      warn "schedule" "$unit is enabled but has NO next run scheduled — systemctl list-timers --all"
    else
      ok "schedule" "$unit next run: $nxt"
    fi
  done < <(systemctl list-timers --all --no-pager 'auralis-*' 2>/dev/null \
           | awk '{for (i=1;i<=NF;i++) if ($i ~ /^auralis-[A-Za-z0-9_.-]*\.timer$/) print $i}' \
           | sort -u || true)
fi

# =============================================================================
head2 "the portal itself (127.0.0.1:$PORT)"
# =============================================================================
# Loopback-only is a hard invariant on a shared host: the portal must be
# reachable ONLY through the tunnel, never from the internet directly.
if command -v ss >/dev/null 2>&1; then
  LISTEN="$(ss -ltnH 2>/dev/null | awk -v p=":$PORT" '$4 ~ p {print $4}' | tr '\n' ' ' || true)"
  if [ -z "$LISTEN" ]; then
    bad "listen" "nothing is listening on port $PORT"
  elif printf '%s' "$LISTEN" | grep -qE '(^|[[:space:]])(0\.0\.0\.0|\*|\[::\]):'"$PORT"; then
    bad "listen" "port $PORT is bound to ALL interfaces ($LISTEN) — it must be 127.0.0.1 only; the portal is exposed to the internet"
  else
    ok "listen" "bound loopback-only: $LISTEN"
  fi
else
  warn "listen" "ss not available — cannot confirm the socket is loopback-only"
fi

fetch "http://127.0.0.1:$PORT/health" 8
if [ "$FETCH_CODE" = "200" ] && printf '%s' "$FETCH_BODY" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
  ok "health" "GET /health -> 200 ok:true $(printf '%s' "$FETCH_BODY" | cut -c1-90)"
elif [ "$FETCH_CODE" = "000" ]; then
  bad "health" "GET /health did not connect (${FETCH_ERR:-no response}) — the portal is not answering on 127.0.0.1:$PORT"
else
  bad "health" "GET /health -> HTTP $FETCH_CODE, body $(printf '%s' "$FETCH_BODY" | cut -c1-120)"
fi

# /staff and /book are plain pages (the API behind them needs the key); a 200
# with real HTML proves the templates and static assets were deployed too.
for page in staff book portal; do
  fetch "http://127.0.0.1:$PORT/$page" 10
  if [ "$FETCH_CODE" = "200" ] && printf '%s' "$FETCH_BODY" | grep -qi '<html\|<!doctype'; then
    ok "/$page" "200 · $(printf '%s' "$FETCH_BODY" | wc -c | tr -d ' ') bytes of HTML"
  elif [ "$FETCH_CODE" = "200" ]; then
    warn "/$page" "200 but the body does not look like HTML — check portal/web/$page.html"
  else
    bad "/$page" "HTTP $FETCH_CODE ${FETCH_ERR:-}"
  fi
done

# =============================================================================
head2 "cloudflare tunnel (our OWN instance only)"
# =============================================================================
# Error 1033 in this project came from running the WRONG tunnel (Paramur's).
# So the identity is asserted from the config, never assumed.
if [ -r "$CF_CONF" ]; then
  T_ID="$(awk '/^tunnel:/ {print $2; exit}' "$CF_CONF" 2>/dev/null || true)"
  T_CRED="$(awk '/credentials-file:/ {print $2; exit}' "$CF_CONF" 2>/dev/null || true)"
  T_HOST="$(awk '/hostname:/ {print $3; exit}' "$CF_CONF" 2>/dev/null || true)"
  T_SVC="$(awk '/service:[[:space:]]*http/ {print $2; exit}' "$CF_CONF" 2>/dev/null || true)"
  if [ -z "$T_ID" ]; then
    bad "tunnel.config" "$CF_CONF has no 'tunnel:' id — cloudflared cannot know which tunnel to run"
  elif [ -n "$T_CRED" ] && [ "$T_CRED" != "/etc/cloudflared/auralis-$T_ID.json" ]; then
    bad "tunnel.config" "identity mismatch: tunnel id $T_ID but credentials-file is $T_CRED — this is exactly how Error 1033 happened before"
  elif [ -n "$T_CRED" ] && [ ! -e "$T_CRED" ]; then
    bad "tunnel.config" "credentials file $T_CRED does not exist"
  else
    ok "tunnel.config" "tunnel $T_ID · creds $(basename "${T_CRED:-unset}") · $T_HOST -> ${T_SVC:-?}"
  fi
  if [ -n "$T_HOST" ] && [ "$T_HOST" != "$HOSTNAME_ING" ]; then
    warn "tunnel.ingress" "config routes '$T_HOST' but this run expects '$HOSTNAME_ING'"
  fi
  if [ -n "$T_SVC" ] && ! printf '%s' "$T_SVC" | grep -q ":$PORT"; then
    bad "tunnel.ingress" "ingress points at $T_SVC but the portal listens on 127.0.0.1:$PORT"
  fi
elif [ -e "$CF_CONF" ]; then
  warn "tunnel.config" "$CF_CONF exists but is not readable as $(id -un) — cannot assert the tunnel identity"
else
  phase "tunnel.config" "$CF_CONF does not exist — the tunnel is not installed on this host"
fi

# Journal parsing is deliberately forgiving: cloudflared's log wording changes
# between releases, and a regex miss must never fail a healthy deployment.
if unit_exists cloudflared-auralis.service; then
  CF_ACTIVE="$(systemctl is-active cloudflared-auralis.service 2>/dev/null || true)"
  CF_LOG="$(journalctl -u cloudflared-auralis.service --since '-15 min' --no-pager 2>/dev/null || true)"
  if [ -z "$CF_LOG" ]; then
    if [ "$CF_ACTIVE" = "active" ]; then
      warn "tunnel.connected" "unit is active but its journal is empty or unreadable as $(id -un) — falling back to the unit state (add yourself to the systemd-journal group to see more)"
    else
      phase "tunnel.connected" "unit is $CF_ACTIVE and no journal is readable"
    fi
  elif printf '%s' "$CF_LOG" | grep -qiE 'registered tunnel connection|connection [0-9a-f-]+ registered|connIndex=[0-9]+.*(registered|connected)'; then
    CONNS="$(printf '%s' "$CF_LOG" | grep -ciE 'registered tunnel connection|connection [0-9a-f-]+ registered' || true)"
    ok "tunnel.connected" "$CONNS connection registration(s) in the last 15 min · unit $CF_ACTIVE"
  elif printf '%s' "$CF_LOG" | grep -qiE 'error|failed|unauthorized|1033'; then
    LASTERR="$(printf '%s' "$CF_LOG" | grep -iE 'error|failed|unauthorized|1033' | tail -n1 | cut -c1-170 || true)"
    phase "tunnel.connected" "no healthy connection line, and the journal shows: $LASTERR"
  elif [ "$CF_ACTIVE" = "active" ]; then
    # Log format changed, or the connection predates our 15-minute window.
    warn "tunnel.connected" "no recognised connection line in the last 15 min, but the unit is active — treating as up (cloudflared's log format may have changed; check: journalctl -u cloudflared-auralis -n 40)"
  else
    phase "tunnel.connected" "unit is $CF_ACTIVE and no connection line was found"
  fi
fi

# Read-only neighbourhood report: prove we left the other company's tunnel alone.
OTHER="$(systemctl list-units --type=service --all --no-legend 'cloudflared*' 2>/dev/null \
         | awk '{print $1}' | grep -v '^cloudflared-auralis.service$' | tr '\n' ' ' || true)"
if [ -n "$OTHER" ]; then
  info "tunnel.neighbours" "untouched, still running their own units: $OTHER"
fi

# =============================================================================
head2 "public edge (https://$HOSTNAME_ING)"
# =============================================================================
fetch "https://$HOSTNAME_ING/health" 15
if [ "$FETCH_CODE" = "200" ] && printf '%s' "$FETCH_BODY" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
  if [ "$PUBLIC" -eq 1 ]; then
    ok "public" "https://$HOSTNAME_ING/health -> 200 ok:true (served through this host's tunnel)"
  else
    ok "public" "https://$HOSTNAME_ING/health -> 200 ok:true — NOTE: pre-cutover this is still the Mac answering; /health cannot tell the two apart"
  fi
elif [ "$FETCH_CODE" = "000" ]; then
  if [ "$PUBLIC" -eq 1 ]; then
    phase "public" "https://$HOSTNAME_ING/health unreachable (${FETCH_ERR:-no response}) — the cutover has happened, so this is OUR outage: check cloudflared-auralis and the DNS CNAME for $HOSTNAME_ING"
  else
    phase "public" "https://$HOSTNAME_ING/health unreachable (${FETCH_ERR:-no response}) — expected while the Mac still serves it only if the Mac is off; otherwise check DNS"
  fi
else
  phase "public" "https://$HOSTNAME_ING/health -> HTTP $FETCH_CODE $(printf '%s' "$FETCH_BODY" | cut -c1-110)$([ "$FETCH_CODE" = "530" ] && printf ' (Cloudflare 1033: no tunnel is serving this hostname)' || true)"
fi

# =============================================================================
head2 "files, ownership and symlinks"
# =============================================================================
S="$(stat_of "$ENV_FILE")"
if [ -z "$S" ]; then
  bad "env.file" "$ENV_FILE does not exist — the service has no secrets at all"
else
  set -- $S; MODE="$1"; OWNER="$2"; GROUP="$3"
  WORLD="${MODE: -1}"
  if [ "$WORLD" != "0" ]; then
    bad "env.file" "$ENV_FILE is $MODE $OWNER:$GROUP — WORLD-READABLE secrets on a host shared with another company. chmod 640 '$ENV_FILE'"
  elif [ "$MODE" = "640" ] && [ "$OWNER" = "root" ] && [ "$GROUP" = "$SVC_USER" ]; then
    ok "env.file" "$ENV_FILE 0640 root:$SVC_USER"
  elif [ "$GROUP" != "$SVC_USER" ]; then
    warn "env.file" "$ENV_FILE is $MODE $OWNER:$GROUP — systemd still reads it as root, but $SVC_USER cannot (chown root:$SVC_USER, chmod 640)"
  else
    warn "env.file" "$ENV_FILE is $MODE $OWNER:$GROUP — expected 0640 root:$SVC_USER"
  fi
  # Never print values: only assert the keys the service cannot start without.
  if [ -r "$ENV_FILE" ]; then
    MISSING=""
    for k in AURALIS_API_KEY AURALIS_SECRET AURALIS_DATA_KEY AURALIS_ENV AURALIS_PORT; do
      grep -qE "^[[:space:]]*(export[[:space:]]+)?$k=." "$ENV_FILE" || MISSING="$MISSING $k"
    done
    if [ -n "$MISSING" ]; then
      bad "env.keys" "missing from $ENV_FILE:$MISSING"
    else
      ok "env.keys" "all required keys present (values never read or printed)"
    fi
    grep -qE '^[[:space:]]*(export[[:space:]]+)?CLAUDE_CODE_OAUTH_TOKEN=.' "$ENV_FILE" \
      || warn "env.keys" "no CLAUDE_CODE_OAUTH_TOKEN in $ENV_FILE — the report agent falls back to the offline STUB writer (run 'claude setup-token' ON THE MAC)"
  fi
fi

for pair in "data.dir:$DATA_DIR:required" "backup.dir:$BACKUP_DIR:optional"; do
  label="${pair%%:*}"; rest="${pair#*:}"; d="${rest%%:*}"; need="${rest#*:}"
  S="$(stat_of "$d")"
  if [ -z "$S" ]; then
    if [ "$need" = "required" ]; then
      bad "$label" "$d does not exist — the live data has nowhere to live"
    else
      warn "$label" "$d does not exist yet (created by the first auralis-backup run)"
    fi
    continue
  fi
  set -- $S; MODE="$1"; OWNER="$2"; GROUP="$3"
  if [ "$OWNER" != "$SVC_USER" ]; then
    bad "$label" "$d is owned by $OWNER:$GROUP ($MODE) — the service runs as $SVC_USER and cannot write its own data"
  elif [ "${MODE: -1}" != "0" ]; then
    warn "$label" "$d is $MODE $OWNER:$GROUP — special-category health data should not be world-accessible (chmod 750 '$d')"
  else
    ok "$label" "$d $MODE $OWNER:$GROUP"
  fi
done

# The symlinks are what let `git reset --hard` in auralis-update.service run
# without ever touching live data. A broken one is silent and catastrophic.
link_ok=1
for pair in "auralis.db:$DATA_DIR/auralis.db" \
            "config/clients.json:$DATA_DIR/clients.json" \
            "output_docs:$DATA_DIR/output_docs"; do
  rel="${pair%%:*}"; want="${pair#*:}"; src="$PORTAL_DIR/$rel"
  if [ ! -e "$src" ] && [ ! -L "$src" ]; then
    bad "symlink" "$src is missing entirely"; link_ok=0
  elif [ ! -L "$src" ]; then
    bad "symlink" "$src is a REAL file/dir, not a symlink to $want — live data inside the worktree is destroyed by the update timer's git reset --hard"; link_ok=0
  elif [ ! -e "$src" ]; then
    bad "symlink" "$src -> $(readlink "$src") is BROKEN (target missing)"; link_ok=0
  elif [ "$(readlink "$src")" != "$want" ]; then
    warn "symlink" "$src -> $(readlink "$src") (expected $want)"
  fi
done
if [ "$link_ok" -eq 1 ]; then
  ok "symlinks" "auralis.db, config/clients.json and output_docs all resolve into $DATA_DIR"
fi

# Informational: is the checkout current? The update timer fixes drift by itself
# within ~2 minutes, so this is never a failure.
if [ -d "$APP_DIR/.git" ] && command -v git >/dev/null 2>&1; then
  GH="$(git -c safe.directory='*' -C "$APP_DIR" rev-parse --short HEAD 2>/dev/null || true)"
  GB="$(git -c safe.directory='*' -C "$APP_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  GD="$(git -c safe.directory='*' -C "$APP_DIR" status --porcelain 2>/dev/null | wc -l | tr -d ' ' || true)"
  if [ -n "$GH" ]; then
    if [ "${GD:-0}" != "0" ]; then
      warn "git" "$APP_DIR at $GB@$GH with $GD local change(s) — auralis-update.service will git reset --hard over them"
    else
      info "git" "$APP_DIR at $GB@$GH (clean)"
    fi
  fi
fi

# =============================================================================
head2 "preflight.py (inside the venv, as $SVC_USER)"
# =============================================================================
PF="$PORTAL_DIR/tools/preflight.py"
if [ "$DO_PREFLIGHT" -eq 0 ]; then
  warn "preflight" "skipped (--no-preflight) — the app-level checks did NOT run"
elif [ ! -f "$PF" ]; then
  bad "preflight" "$PF is missing from this revision — the app-level checks cannot run"
elif [ ! -x "$VENV/bin/python3" ]; then
  bad "preflight" "$VENV/bin/python3 is missing — the service's virtualenv is not installed"
else
  PF_ARGS=(--json --env-file "$ENV_FILE" --timeout 30)
  if [ "$QUICK" -eq 1 ]; then PF_ARGS+=(--no-pdf --no-agent); fi
  # NB: preflight.py exits 1 whenever it reports a FAIL — an expected outcome we
  # want to READ, not die on. `set +e` would NOT help: bash executes an ERR trap
  # regardless of errexit. Only an explicit ||-list suppresses it.
  PF_RC=0
  PF_OUT="$(as_svc env HOME="$SVC_HOME" "$VENV/bin/python3" "$PF" "${PF_ARGS[@]}" 2>&1)" \
    || PF_RC=$?
  if [ "$PF_RC" -eq 66 ]; then
    if id -u "$SVC_USER" >/dev/null 2>&1; then
      warn "preflight" "cannot become $SVC_USER as $(id -un) (no sudo/runuser) — run it by hand: sudo -u $SVC_USER $VENV/bin/python3 $PF --env-file $ENV_FILE"
    else
      bad "preflight" "the service user '$SVC_USER' does not exist on this host — install_server.sh never completed"
    fi
  elif [ -z "$PF_OUT" ]; then
    bad "preflight" "produced no output at all (exit $PF_RC)"
  else
    # Fold every preflight check in as one of our own lines, so the operator
    # gets a single list and a single verdict.
    PF_LINES="$("$PY" - "$PF_OUT" <<'PY' 2>&1 || true
import json, sys
raw = sys.argv[1]
i = raw.find("{")
if i < 0:
    print("fail|preflight|no JSON in output: " + " ".join(raw.split())[-300:]); sys.exit(0)
try:
    d = json.loads(raw[i:])
except Exception as e:
    print(f"fail|preflight|unparseable JSON ({e}): " + " ".join(raw[i:].split())[:300]); sys.exit(0)
for c in d.get("checks", []):
    sev = str(c.get("severity", "fail"))
    if sev not in ("ok", "warn", "fail"):
        sev = "fail" if not c.get("ok") else "warn"
    print(f'{sev}|{c.get("name","?")}|{" ".join(str(c.get("detail","")).split())}')
PY
)"
    if [ -z "$PF_LINES" ]; then
      bad "preflight" "returned $PF_RC but no parseable checks: $(printf '%s' "$PF_OUT" | tr '\n' ' ' | cut -c1-240)"
    else
      while IFS='|' read -r sev nm det; do
        [ -n "${nm:-}" ] || continue
        # --allow-stub downgrades exactly ONE check, and says so in the line it
        # prints. Nothing is hidden: the operator still sees that reports would
        # be offline boiler-plate, it simply stops blocking the run.
        if [ "$ALLOW_STUB" -eq 1 ] && [ "$nm" = "agent" ] && [ "$sev" != "ok" ]; then
          sev="warn"; det="[--allow-stub: accepted, NOT fixed] $det"
        fi
        case "$sev" in
          ok)   ok   "preflight/$nm" "$det" ;;
          warn) warn "preflight/$nm" "$det" ;;
          *)    bad  "preflight/$nm" "$det" ;;
        esac
      done <<EOF
$PF_LINES
EOF
    fi
  fi
fi

# =============================================================================
# verdict
# =============================================================================
printf '%s\n' "────────────────────────────────────────────────────────────────────────────"
printf ' %d pass · %d warn · %d fail\n' "$N_PASS" "$N_WARN" "$N_FAIL"
if [ "$N_FAIL" -gt 0 ]; then
  printf '\n%sMust be fixed before this host serves clients:%s\n' "$C_R" "$C_0"
  for f in "${FAILURES[@]}"; do printf '   ✗ %s\n' "$f"; done
  printf '\n   Logs: journalctl -u auralis-portal -n 80 · journalctl -u cloudflared-auralis -n 40\n'
  echo "VERIFY_RESULT: FAIL"
  exit 1
fi
if [ "$N_WARN" -gt 0 ]; then
  printf '\n%s%d warning(s) above — read them, none of them blocks the cutover.%s\n' "$C_Y" "$N_WARN" "$C_0"
fi
if [ "$PUBLIC" -eq 1 ]; then
  printf '\n%s✓ The server is live on https://%s — the Mac can be switched off.%s\n' "$C_G" "$HOSTNAME_ING" "$C_0"
else
  printf '\n%s✓ The server is ready. The tunnel is installed but dormant; the Mac still serves %s.%s\n' \
         "$C_G" "$HOSTNAME_ING" "$C_0"
fi
echo "VERIFY_RESULT: PASS"
exit 0
