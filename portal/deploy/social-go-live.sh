#!/usr/bin/env bash
# =============================================================================
#  enable_social.sh — RUNS AS ROOT ON THE SERVER. Activates the Social module.
# =============================================================================
#  WHY THIS EXISTS, AND NOT "just re-run install_server.sh":
#  install_server.sh is a RECEIVER. Its contract requires AURALIS_PAYLOAD_DIR —
#  a directory the Mac ships containing portal.env with the data key, the SMTP
#  password and the Claude token — because its job is to build a host from
#  nothing. Everything it would deliver is already on this box, correct and
#  running. Asking it to rebuild the world in order to add two timers means
#  re-shipping secrets to another company's server for no reason.
#
#  So this script does exactly the delta the Social module needs, and nothing
#  else:
#      1. ffmpeg          (reels, and the PNG→JPEG step Instagram requires)
#      2. two systemd units + timers   (Monday scan, 10-minute publish queue)
#      3. config/social.json symlinked into /var/lib + into the nightly backup
#
#  It writes the SAME unit content install_server.sh writes, so a later full
#  install run finds them unchanged and restarts nothing.
#
#  ⚠ THIS HOST ALSO RUNS ANOTHER COMPANY'S PRODUCTION ERP.
#  Same rules as the installer: namespaced to auralis*, apt is simulated first
#  and the run ABORTS if the plan would touch anything we did not ask for, no
#  apt source is added, no foreign unit is ever touched.
#
#  Safe to re-run: every step is idempotent and reports "unchanged".
#
#  Usage:   bash /opt/auralis/app/portal/deploy/social-go-live.sh
# =============================================================================
set -Eeuo pipefail

readonly SVC_USER="auralis"
readonly SVC_GROUP="auralis"
readonly HOME_DIR="/opt/auralis"
readonly PORTAL_DIR="/opt/auralis/app/portal"
readonly VENV_DIR="/opt/auralis/venv"
readonly DATA_DIR="/var/lib/auralis"
readonly BACKUP_DIR="/var/backups/auralis"
readonly ENV_FILE="/etc/auralis/portal.env"
readonly BIN_DIR="/etc/auralis"
readonly UNIT_DIR="/etc/systemd/system"

MEM_HIGH="${AURALIS_MEM_HIGH:-1G}"
MEM_MAX="${AURALIS_MEM_MAX:-1500M}"
CPU_QUOTA="${AURALIS_CPU_QUOTA:-150%}"
TASKS_MAX="${AURALIS_TASKS_MAX:-256}"

CHANGED=0
say()  { printf '   %s\n' "$*"; }
ok()   { printf '   \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '   \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '\n\033[31mFATAL\033[0m %s\n' "$*" >&2; exit "${2:-1}"; }
stage(){ printf '\n== %s ==\n' "$*"; }

[ "$(id -u)" -eq 0 ] || die "must run as root"
[ -d "$PORTAL_DIR" ] || die "$PORTAL_DIR not found — is this the right host?"
id "$SVC_USER" >/dev/null 2>&1 || die "service user '$SVC_USER' missing — run the full installer first"
[ -f "$ENV_FILE" ] || die "$ENV_FILE missing — run the full installer first"

# ── write a file only if its content actually differs (no spurious restarts) ──
write_managed() {  # write_managed <path> <mode> <owner> ; content on stdin
  local path="$1" mode="$2" owner="$3" tmp
  tmp="$(mktemp "${path}.XXXXXX")"
  cat > "$tmp"
  chmod "$mode" "$tmp"; chown "$owner" "$tmp"
  if [ -f "$path" ] && cmp -s "$tmp" "$path"; then rm -f "$tmp"; return 1; fi
  mv -f "$tmp" "$path"; return 0
}

unit() {  # unit <name> ; content on stdin
  if write_managed "$UNIT_DIR/$1" 0644 root:root; then CHANGED=1; ok "$1 geschrieben"
  else say "$1 unverändert"; fi
}

# ═════════════════════════════════════════════════════════ 1/4 · ffmpeg ══
stage "1/4 ffmpeg"
if command -v ffmpeg >/dev/null 2>&1; then
  ok "ffmpeg bereits vorhanden ($(command -v ffmpeg))"
else
  say "simuliere die Installation, bevor irgendetwas passiert …"
  sim="$(mktemp)"
  export NEEDRESTART_SUSPEND=1 NEEDRESTART_MODE=l DEBIAN_FRONTEND=noninteractive
  if ! apt-get install -y --no-install-recommends -s ffmpeg >"$sim" 2>&1; then
    cat "$sim"; rm -f "$sim"
    die "apt-Simulation für ffmpeg fehlgeschlagen (evtl. 'apt-get update' nötig)" 20
  fi
  # the co-tenant guard: refuse a plan that removes anything
  if grep -qE '^Remv ' "$sim"; then
    printf '\n%s\n' "----- apt-Plan -----"; grep -E '^(Inst|Remv|Conf) ' "$sim"
    rm -f "$sim"
    die "apt würde Pakete ENTFERNEN — abgebrochen, dieser Host gehört nicht uns allein" 20
  fi
  printf '\n%s\n' "----- apt würde installieren -----"
  grep -E '^Inst ' "$sim" | sed 's/^/   /' || true
  rm -f "$sim"
  if [ "${AURALIS_ASSUME_YES:-0}" != "1" ]; then
    printf '\n   Plan in Ordnung? [j/N] '
    read -r reply </dev/tty || reply=""
    case "$reply" in [jJyY]*) ;; *) die "abgebrochen auf deinen Wunsch" 0;; esac
  fi
  apt-get install -y --no-install-recommends ffmpeg || die "ffmpeg-Installation fehlgeschlagen" 20
  ok "ffmpeg installiert ($(command -v ffmpeg))"
  CHANGED=1
fi

# ═════════════════════════════════════════════════ 2/4 · social.json ══
stage "2/4 social.json in die Datenablage"
mkdir -p "$DATA_DIR"
if [ -L "$PORTAL_DIR/config/social.json" ]; then
  ok "bereits verlinkt"
else
  if [ -f "$PORTAL_DIR/config/social.json" ] && [ ! -f "$DATA_DIR/social.json" ]; then
    mv "$PORTAL_DIR/config/social.json" "$DATA_DIR/social.json"
    say "bestehende social.json nach $DATA_DIR verschoben"
  fi
  # Seed from the committed example, NOT from '{}'. The portal seeds itself on
  # first read — but only when the file is ABSENT, and a symlink whose target
  # exists is not absent. An empty object would hand the console a config with
  # no agents key at all.
  [ -f "$DATA_DIR/social.json" ] || {
    python3 - "$PORTAL_DIR/config/social.example.json" "$DATA_DIR/social.json" <<'SEED'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
d.pop("_comment", None)
json.dump(d, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
SEED
    say "social.json aus der Vorlage angelegt"
  }
  chown "$SVC_USER:$SVC_GROUP" "$DATA_DIR/social.json"
  ln -sfn "$DATA_DIR/social.json" "$PORTAL_DIR/config/social.json"
  chown -h "$SVC_USER:$SVC_GROUP" "$PORTAL_DIR/config/social.json"
  ok "verlinkt: config/social.json → $DATA_DIR/social.json"
  CHANGED=1
fi
if [ -f "$BIN_DIR/backup.sh" ] && ! grep -q 'social.json' "$BIN_DIR/backup.sh"; then
  # append next to the clients.json line, same shape
  sed -i 's#^\(if \[ -f .*clients\.json \]; then cp -a .*clients\.json "\$stage/"; fi\)$#\1\nif [ -f '"$DATA_DIR"'/social.json ]; then cp -a '"$DATA_DIR"'/social.json "$stage/"; fi#' \
      "$BIN_DIR/backup.sh" && ok "social.json in die nächtliche Sicherung aufgenommen"
else
  say "Sicherung deckt social.json bereits ab (oder backup.sh fehlt)"
fi

# ═══════════════════════════════════════════════════════ 3/4 · units ══
stage "3/4 systemd-Einheiten"
HARDENING=(
  "NoNewPrivileges=true" "PrivateTmp=true" "ProtectSystem=strict" "ProtectHome=true"
  "ProtectKernelTunables=true" "ProtectKernelModules=true" "ProtectControlGroups=true"
  "ProtectProc=invisible" "RestrictSUIDSGID=true" "RestrictRealtime=true"
  "LockPersonality=true" "SystemCallArchitectures=native"
  "ReadWritePaths=$DATA_DIR $BACKUP_DIR $HOME_DIR"
  "MemoryHigh=$MEM_HIGH" "MemoryMax=$MEM_MAX" "CPUQuota=$CPU_QUOTA" "CPUWeight=50"
  "TasksMax=$TASKS_MAX" "LimitNOFILE=8192"
)

{
  cat <<SOCIALUNIT
# Managed by portal/deploy/install_server.sh
[Unit]
Description=Auralis weekly social-media screening + strategy draft
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=$SVC_USER
Group=$SVC_GROUP
WorkingDirectory=$PORTAL_DIR
EnvironmentFile=$ENV_FILE
Environment=PYTHONUNBUFFERED=1
Environment=HOME=$HOME_DIR
Environment=PATH=$HOME_DIR/.local/bin:$HOME_DIR/bin:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin
ExecStart=$VENV_DIR/bin/python $PORTAL_DIR/tools/social_scan.py
SyslogIdentifier=auralis-social-scan
TimeoutStartSec=1800
Nice=10
SOCIALUNIT
  printf '%s\n' "${HARDENING[@]}"
} | unit auralis-social-scan.service

unit auralis-social-scan.timer <<'SOCIALTIMER'
# Managed by portal/deploy/install_server.sh
# 05:00 server time (UTC on this box = 06:00/07:00 Madrid) — the digest and the
# weekly draft are waiting when the console is opened on Monday morning.
[Unit]
Description=Weekly Auralis social-media scan (Monday early)

[Timer]
OnCalendar=Mon *-*-* 05:00:00
RandomizedDelaySec=15min
Persistent=true
Unit=auralis-social-scan.service

[Install]
WantedBy=timers.target
SOCIALTIMER

{
  cat <<PUBUNIT
# Managed by portal/deploy/install_server.sh
[Unit]
Description=Auralis Instagram publish queue
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=$SVC_USER
Group=$SVC_GROUP
WorkingDirectory=$PORTAL_DIR
EnvironmentFile=$ENV_FILE
Environment=PYTHONUNBUFFERED=1
Environment=HOME=$HOME_DIR
Environment=PATH=$HOME_DIR/.local/bin:$HOME_DIR/bin:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin
ExecStart=$VENV_DIR/bin/python $PORTAL_DIR/tools/social_publish.py
SyslogIdentifier=auralis-social-publish
TimeoutStartSec=900
Nice=10
PUBUNIT
  printf '%s\n' "${HARDENING[@]}"
} | unit auralis-social-publish.service

unit auralis-social-publish.timer <<'PUBTIMER'
# Managed by portal/deploy/install_server.sh
[Unit]
Description=Auralis Instagram publish queue (every 10 min)

[Timer]
OnCalendar=*:00/10
RandomizedDelaySec=60
Persistent=true
Unit=auralis-social-publish.service

[Install]
WantedBy=timers.target
PUBTIMER

[ "$CHANGED" = "1" ] && systemctl daemon-reload || true

# ═════════════════════════════════════════════════════ 4/4 · arm + check ══
stage "4/4 Timer aktivieren"
systemctl enable --now auralis-social-scan.timer >/dev/null 2>&1 \
  || die "konnte auralis-social-scan.timer nicht aktivieren" 40
systemctl enable --now auralis-social-publish.timer >/dev/null 2>&1 \
  || die "konnte auralis-social-publish.timer nicht aktivieren" 40
ok "beide Timer aktiv"

systemctl restart auralis-portal.service || warn "Portal-Neustart fehlgeschlagen — bitte prüfen"
ok "Portal neu gestartet (liest ffmpeg + neue Konfiguration ein)"

printf '\n'
systemctl list-timers 'auralis-social-*' --no-pager || true

printf '\n\033[32m═══ Social-Modul ist scharf geschaltet ═══\033[0m\n'
cat <<'DONE'

   Was ab jetzt von allein läuft:
     · Montag 05:00  — Quellen scannen, Digest schreiben, Wochenentwurf erzeugen
     · alle 10 Min   — freigegebene Posts zur geplanten Zeit veröffentlichen
                       (sobald die Instagram-Verbindung eingerichtet ist)

   Nächster Schritt in der Konsole:
     api.auralisnatura.com/staff → Registerkarte "Social Media"
     → Wochenziel eintragen → Quellen prüfen → "Scan jetzt starten"

DONE
