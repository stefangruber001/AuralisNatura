#!/usr/bin/env bash
# =============================================================================
#  uninstall_server.sh — RUNS AS ROOT **ON THE HETZNER SERVER**
# =============================================================================
#  Removes the Auralis portal from this host and nothing else.
#
#      ssh root@178.105.10.156 'bash /opt/auralis/app/portal/deploy/uninstall_server.sh'
#
#  Two reasons this exists:
#    1. an install that failed partway can leave auralis-update.timer and
#       auralis-backup.timer enabled and firing on a host that also runs another
#       company's production ERP. Without an uninstall, the only way back is
#       hand-deleting units, and hand-deleting units on a shared box at speed is
#       how the wrong one gets removed.
#    2. a clean decommission when the portal moves somewhere else.
#
#  ⚠ THIS HOST ALSO RUNS "canei-erp" FOR ANOTHER COMPANY.
#  Every unit and path below is hard-coded and namespaced. There is no glob, no
#  variable expansion into an `rm -rf` target, and nothing outside this list is
#  read, stopped or deleted:
#      units  auralis-portal.service auralis-update.{service,timer}
#             auralis-backup.{service,timer} cloudflared-auralis.service
#      paths  /opt/auralis  /etc/auralis  /run/auralis  /etc/cloudflared/auralis*
#             /var/lib/auralis (data — kept unless --purge-data)
#             /var/backups/auralis (backups — kept unless --purge-data)
#  A pre-existing `cloudflared.service` belonging to the ERP is never touched.
#
#  DATA IS KEPT BY DEFAULT. --purge-data destroys special-category health data
#  and demands a typed confirmation.
#
#  Exit codes: 0 ok · 10 not root · 11 no systemd · 15 bad arguments
# =============================================================================
set -Eeuo pipefail

readonly UNITS="auralis-portal.service auralis-update.timer auralis-update.service auralis-backup.timer auralis-backup.service cloudflared-auralis.service"
readonly UNIT_DIR="/etc/systemd/system"
readonly CODE_PATHS="/opt/auralis /etc/auralis /run/auralis"
readonly DATA_DIR="/var/lib/auralis"
readonly BACKUP_DIR="/var/backups/auralis"
readonly CF_CONF="/etc/cloudflared/auralis.yml"
readonly SVC_USER="auralis"

PURGE=0; ASSUME_YES=0; KEEP_USER=0

if [ -t 1 ]; then B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; D=$'\033[2m'; N=$'\033[0m'
else B=''; G=''; Y=''; R=''; D=''; N=''; fi
say()  { printf '%s\n' "$1"; }
ok()   { printf '   %s✓%s %s\n' "$G" "$N" "$1"; }
info() { printf '   %s·%s %s\n' "$D" "$N" "$1"; }
warn() { printf '   %s!%s %s\n' "$Y" "$N" "$1" >&2; }
die()  { printf '\n%s✗ %s%s\n' "$R" "$2" "$N" >&2; exit "$1"; }
trap '_rc=$?; [ $_rc -eq 0 ] || printf "\n%s✗ uninstall_server.sh failed at line %s (exit %s)%s\n" "$R" "$LINENO" "$_rc" "$N" >&2' ERR

usage() {
  cat <<EOF
Usage: bash uninstall_server.sh [options]

  --purge-data   ALSO delete $DATA_DIR and $BACKUP_DIR.
                 That is the encrypted client backbone, the portal logins and
                 every generated report. Requires typing a confirmation.
  --keep-user    do not remove the '$SVC_USER' system user
  --yes          skip the ordinary confirmation (NOT the --purge-data one)
  -h, --help     this text

Default (no flags): stops and removes the services and the code, and leaves all
data in place, so a later re-install picks it straight back up.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --purge-data) PURGE=1; shift ;;
    --keep-user)  KEEP_USER=1; shift ;;
    --yes|-y)     ASSUME_YES=1; shift ;;
    -h|--help)    usage; exit 0 ;;
    *) usage >&2; die 15 "unknown option: $1" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || die 10 "must run as root"
command -v systemctl >/dev/null 2>&1 || die 11 "no systemd on this host"

printf '%s\nAuralis Natura — uninstall from this server%s\n' "$B" "$N"
info "services + code will be removed"
if [ "$PURGE" = 1 ]; then
  printf '   %s! --purge-data: %s and %s will be DESTROYED%s\n' "$R" "$DATA_DIR" "$BACKUP_DIR" "$N"
else
  info "data kept: $DATA_DIR and $BACKUP_DIR"
fi

if [ "$ASSUME_YES" != 1 ]; then
  printf '   Continue? [y/N] '; read -r a || true
  case "$a" in y|Y|yes|YES) ;; *) say "   Nothing changed."; exit 0 ;; esac
fi

# ── 1. stop + disable, one unit at a time, by exact name ─────────────────────
say ""
say "${B}Stopping Auralis units${N}"
for u in $UNITS; do
  if systemctl list-unit-files "$u" >/dev/null 2>&1 && [ -e "$UNIT_DIR/$u" ]; then
    systemctl disable --now "$u" >/dev/null 2>&1 || warn "could not disable $u"
    ok "stopped + disabled $u"
  else
    info "$u not installed"
  fi
done

# Anything still holding the port after this is NOT ours — say so, never kill it.
PORT="$(sed -n 's/^AURALIS_PORT=//p' /etc/auralis/portal.env 2>/dev/null | tail -n1 | tr -d '"'"'"'\r')"
PORT="${PORT:-5056}"
if command -v ss >/dev/null 2>&1 && ss -ltnp 2>/dev/null | grep -q ":$PORT "; then
  warn "something is still listening on 127.0.0.1:$PORT after our units stopped."
  warn "It is NOT an Auralis unit — inspect it, do not assume it is stale:"
  warn "  ss -ltnp | grep :$PORT"
fi

# ── 2. remove the unit files ─────────────────────────────────────────────────
say ""
say "${B}Removing unit files${N}"
for u in $UNITS; do
  if [ -e "$UNIT_DIR/$u" ]; then rm -f "$UNIT_DIR/$u"; ok "removed $UNIT_DIR/$u"; fi
done
systemctl daemon-reload
systemctl reset-failed 2>/dev/null || true
ok "systemd reloaded"

# ── 3. code, config and the tunnel config ────────────────────────────────────
# Fixed literals only. $CODE_PATHS is a readonly constant, never derived from
# input, so there is no way for an empty variable to turn this into `rm -rf /`.
say ""
say "${B}Removing code and configuration${N}"
for p in $CODE_PATHS; do
  if [ -e "$p" ]; then rm -rf -- "$p"; ok "removed $p"; else info "$p absent"; fi
done
if [ -e "$CF_CONF" ]; then rm -f -- "$CF_CONF"; ok "removed $CF_CONF"; fi
# Only OUR credentials file, matched by our own naming convention. A bare
# /etc/cloudflared/*.json glob would take the ERP's tunnel credentials with it.
for f in /etc/cloudflared/auralis-*.json; do
  [ -e "$f" ] || continue
  rm -f -- "$f"; ok "removed $f"
done
if [ -d /etc/cloudflared ] && [ -z "$(ls -A /etc/cloudflared 2>/dev/null)" ]; then
  rmdir /etc/cloudflared 2>/dev/null && ok "removed the now-empty /etc/cloudflared" || true
else
  info "/etc/cloudflared kept — it still holds files (very likely the ERP's tunnel)"
fi

# ── 4. data (only on --purge-data) ───────────────────────────────────────────
say ""
if [ "$PURGE" = 1 ]; then
  printf '   %sType DELETE to destroy the encrypted health data and all backups:%s ' "$R" "$N"
  read -r confirm_word || true
  if [ "${confirm_word:-}" = "DELETE" ]; then
    for p in "$DATA_DIR" "$BACKUP_DIR"; do
      if [ -e "$p" ]; then rm -rf -- "$p"; ok "DESTROYED $p"; fi
    done
  else
    warn "not confirmed — data kept at $DATA_DIR and $BACKUP_DIR"
  fi
else
  say "${B}Data${N}"
  info "kept: $DATA_DIR (encrypted backbone, logins, reports)"
  info "kept: $BACKUP_DIR"
  info "re-running install_server.sh later picks these up unchanged"
fi

# ── 5. the service user ──────────────────────────────────────────────────────
say ""
if [ "$KEEP_USER" = 1 ]; then
  info "keeping the '$SVC_USER' user (--keep-user)"
elif id "$SVC_USER" >/dev/null 2>&1; then
  if [ "$PURGE" = 1 ]; then
    userdel "$SVC_USER" >/dev/null 2>&1 && ok "removed the '$SVC_USER' user" \
      || warn "could not remove the '$SVC_USER' user — do it by hand if you care"
  else
    # Keeping data but deleting its owner would leave files owned by a bare uid,
    # and a later useradd could hand that uid to somebody else.
    info "keeping the '$SVC_USER' user because $DATA_DIR still belongs to it"
  fi
fi

say ""
printf '%s✓ Auralis removed from this host.%s\n' "$G" "$N"
info "nothing belonging to canei-erp was stopped, changed or deleted"
[ "$PURGE" = 1 ] || info "data is still at $DATA_DIR — re-install or delete it deliberately"
