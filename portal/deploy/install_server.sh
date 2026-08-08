#!/usr/bin/env bash
# =============================================================================
#  install_server.sh — RUNS AS ROOT **ON THE HETZNER SERVER** (178.105.10.156)
# =============================================================================
#  Bootstraps the Auralis Natura portal as a permanent systemd service so the
#  MacBook (launchd + start_auralis.command + a hand-started cloudflared) can be
#  switched off for good. It replaces that launcher one-for-one:
#      launchd KeepAlive      -> auralis-portal.service (Restart=always)
#      the 120s git-pull loop -> auralis-update.timer   (every 2 min)
#      the tunnel supervisor  -> cloudflared-auralis.service
#      backup.start_scheduler -> stays in-process, plus auralis-backup.timer
#
#  ⚠ THIS HOST ALSO RUNS ANOTHER COMPANY'S PRODUCTION ERP ("canei-erp").
#  Everything below is namespaced (`auralis*`, `cloudflared-auralis`) and this
#  script writes ONLY inside:
#      /opt/auralis  /var/lib/auralis  /etc/auralis  /var/backups/auralis
#      /etc/cloudflared/auralis*        /etc/systemd/system/auralis-*
#      /etc/systemd/system/cloudflared-auralis.service
#  It never upgrades packages, never edits apt sources, never touches a
#  firewall rule, and never stops/restarts a cloudflared unit it did not create.
#
#  It is INVOKED NON-INTERACTIVELY OVER SSH by portal/deploy/migrate_to_server.sh.
#  Re-running it is safe: every step is idempotent (see "IDEMPOTENCE" below).
#
# -----------------------------------------------------------------------------
#  CONTRACT — 1. ENVIRONMENT VARIABLES CONSUMED
# -----------------------------------------------------------------------------
#  REQUIRED
#    AURALIS_PAYLOAD_DIR   Absolute path of the directory the caller scp'd to
#                          this host (see section 2). Must exist and be readable
#                          by root. Deleted on SUCCESS unless AURALIS_KEEP_PAYLOAD=1
#                          (it contains secrets); ALWAYS kept on failure so the
#                          caller can fix one thing and re-run.
#
#  OPTIONAL — identity / topology (defaults in brackets)
#    AURALIS_REPO_URL      [git@github.com:stefangruber001/AuralisNatura.git]
#                          SSH URL cloned into /opt/auralis/app. An https:// URL
#                          also works but then the repo must be public.
#    AURALIS_BRANCH        [main]
#    AURALIS_PORT          [5056]  Loopback-only listen port.
#    AURALIS_HOSTNAME      [api.auralisnatura.com]  Tunnel ingress hostname.
#    AURALIS_TUNNEL_ID     []      REQUIRED when tunnel.json is in the payload.
#                          Asserted against the credentials file's "TunnelID"
#                          — a guess here is exactly how Cloudflare Error 1033
#                          happened before (Paramur's tunnel was run instead).
#
#  OPTIONAL — behaviour switches (all default "0"; any of 1/yes/true enables)
#    AURALIS_ALLOW_DB_OVERWRITE  Permit replacing an EXISTING, non-empty
#                          /var/lib/auralis/auralis.db (or clients.json) with the
#                          payload copy. Without it, a content mismatch ABORTS
#                          (exit 33). A timestamped copy of the old file is put in
#                          /var/backups/auralis before anything is overwritten.
#    AURALIS_SKIP_DATA     Do not place auralis.db / clients.json / output_docs
#                          at all (code + service refresh only).
#    AURALIS_SKIP_PACKAGES Assume python3/venv/git/curl/chromium/cloudflared are
#                          already installed; run no apt-get at all.
#    AURALIS_SKIP_TUNNEL   Install everything except cloudflared-auralis.service.
#    AURALIS_REQUIRE_VERIFY  Fail (exit 40) if deploy/verify_server.sh is absent,
#                          instead of only warning.
#    AURALIS_REQUIRE_CLAUDE_TOKEN  Fail (exit 15) if the env file carries no
#                          CLAUDE_CODE_OAUTH_TOKEN. Default: loud WARNING only —
#                          the report agent then silently degrades to "stub", so
#                          the warning is deliberately shouted, never whispered.
#    AURALIS_KEEP_PAYLOAD  Keep AURALIS_PAYLOAD_DIR after a successful run.
#
#  OPTIONAL — escape hatches
#    AURALIS_MIN_FREE_MB   [2048] Minimum free MB required on /opt and /var.
#    AURALIS_CHROME        Absolute path to an already-present Chrome/Chromium.
#                          Skips chromium installation; still PDF-tested.
#    AURALIS_CHROME_DEB_URL  If no non-snap chromium can be installed, fetch and
#                          install this .deb instead (official vendor URL only,
#                          e.g. https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb).
#                          Empty by default: we fail loudly rather than let
#                          lib/render.py silently fall back to writing .html.
#
# -----------------------------------------------------------------------------
#  CONTRACT — 2. FILES EXPECTED IN $AURALIS_PAYLOAD_DIR
# -----------------------------------------------------------------------------
#    portal.env          REQUIRED. The COMPLETE environment for the service, in
#                        systemd EnvironmentFile syntax (KEY=VALUE per line, no
#                        `export`, comments on their own line). Must define
#                        AURALIS_API_KEY, AURALIS_SECRET, AURALIS_DATA_KEY — the
#                        exact key the Mac used, or the migrated database cannot
#                        be decrypted. Should also carry AURALIS_SMTP_PASSWORD
#                        and CLAUDE_CODE_OAUTH_TOKEN (from `claude setup-token`
#                        run ON THE MAC — it is interactive/browser-based).
#                        AURALIS_PORT and AURALIS_CHROME are stripped and re-set
#                        by this script; AURALIS_ENV, AURALIS_EMAIL_MODE,
#                        AURALIS_AGENT_PROVIDER, AURALIS_PUBLIC_BASE_URL,
#                        AURALIS_BOOKING_URL and AURALIS_BACKUP_DIR are filled
#                        with the documented defaults if absent (names of the
#                        defaulted keys are logged; values never are).
#    auralis.db          optional. The encrypted backbone from the Mac.
#    clients.json        optional. Client logins/consent (git-ignored at source).
#    output_docs.tar.gz  optional. tar.gz whose members are RELATIVE paths
#                        (e.g. `AN-0001/report/report.pdf`), merged into
#                        /var/lib/auralis/output_docs. Never deletes.
#    tunnel.json         optional. cloudflared credentials JSON for the AURALIS
#                        tunnel. Requires AURALIS_TUNNEL_ID; its "TunnelID" must
#                        match, or we abort (exit 41).
#    tunnel.yml          optional. Pre-rendered ingress config. If absent one is
#                        generated. If present it is ASSERTED (tunnel id,
#                        hostname, and service http://127.0.0.1:$AURALIS_PORT).
#    deploy_key          optional. Existing OpenSSH private key to install as
#                        /opt/auralis/.ssh/id_ed25519 (plus deploy_key.pub, or
#                        it is derived). Absent => a key is generated here.
#
#  Nothing else in the payload dir is read.
#
# -----------------------------------------------------------------------------
#  CONTRACT — 3. EXIT CODES
# -----------------------------------------------------------------------------
#     0  success — install complete AND verify_server.sh passed
#    10  not root
#    11  no systemd (this host cannot run the service)
#    12  unsupported distro / no apt-get and AURALIS_SKIP_PACKAGES not set
#    13  TCP $AURALIS_PORT already held by a FOREIGN process (never killed)
#    14  not enough free disk
#    15  bad invocation: payload dir/file missing, or portal.env malformed /
#        missing a required key
#    20  package installation failed
#    21  no usable Chromium (missing, or snap-only — a snap cannot read the
#        temp HTML lib/render.py writes, so the PDF would silently become .html)
#    22  Chromium found but FAILED the real end-to-end PDF render test
#    30  RETRYABLE: the deploy key is not authorised on GitHub yet. The public
#        key is printed and echoed as AURALIS_DEPLOY_KEY_PUB=<key>; add it as a
#        read-only Deploy Key and re-run this script unchanged.
#    31  git clone/fetch failed for any other reason
#    32  venv creation or pip install failed
#    33  refused to overwrite existing data (see AURALIS_ALLOW_DB_OVERWRITE)
#    34  a data path in the worktree conflicts with the required symlink
#    35  AURALIS_DATA_KEY does NOT open the migrated store (THE failure mode of
#        July 2026 — every staff read would 500). Nothing is started.
#    40  systemd unit install/enable/start failed, or /health never came up
#    41  cloudflared install, tunnel-identity assertion, or tunnel start failed
#    99  unexpected error — the ERR trap prints file:line and the command
#     *  any other code is verify_server.sh's, propagated VERBATIM. The final
#        AURALIS_INSTALL_RESULT / AURALIS_INSTALL_STAGE lines disambiguate.
#
#  Machine-readable trailer, always the last lines on stdout:
#      AURALIS_INSTALL_RESULT=ok|failed
#      AURALIS_INSTALL_STAGE=<stage that ended the run>
#      AURALIS_INSTALL_EXIT=<code>
#      AURALIS_DEPLOY_KEY_PUB=<public key>      (only on exit 30)
#
# -----------------------------------------------------------------------------
#  IDEMPOTENCE
# -----------------------------------------------------------------------------
#  Re-running changes nothing that is already correct: user/dirs are created only
#  when missing, units are compared byte-for-byte before being rewritten (so no
#  gratuitous restarts), the repo is fast-forwarded rather than re-cloned, and
#  data files are checksum-compared — identical payload = no-op, different
#  payload = refuse unless explicitly allowed. The one deliberate exception is
#  the app itself: it is restarted at the end so the freshly pulled code runs.
# =============================================================================
set -Eeuo pipefail
umask 027

# ---------------------------------------------------------------- constants --
readonly SVC_USER="auralis"
readonly SVC_GROUP="auralis"
readonly HOME_DIR="/opt/auralis"
readonly APP_DIR="/opt/auralis/app"
readonly PORTAL_DIR="/opt/auralis/app/portal"
readonly VENV_DIR="/opt/auralis/venv"
readonly DATA_DIR="/var/lib/auralis"
readonly ETC_DIR="/etc/auralis"
readonly ENV_FILE="/etc/auralis/portal.env"
readonly BIN_DIR="/etc/auralis"            # root-owned scripts (see note below)
readonly BACKUP_DIR="/var/backups/auralis"
readonly SSH_DIR="/opt/auralis/.ssh"
readonly SSH_KEY="/opt/auralis/.ssh/id_ed25519"
readonly KNOWN_HOSTS="/opt/auralis/.ssh/known_hosts"
readonly CF_DIR="/etc/cloudflared"
readonly CF_CONF="/etc/cloudflared/auralis.yml"
readonly UNIT_DIR="/etc/systemd/system"
readonly WORK_DIR="/var/lib/auralis/.install"   # scratch, service-user readable
# GitHub's published ed25519 host key — pinned so the first clone cannot be
# MITM'd and so ssh never needs to ask an interactive "yes/no" question.
readonly GH_HOSTKEY='github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl'

# ------------------------------------------------------------------ options --
PAYLOAD="${AURALIS_PAYLOAD_DIR:-}"
REPO_URL="${AURALIS_REPO_URL:-git@github.com:stefangruber001/AuralisNatura.git}"
BRANCH="${AURALIS_BRANCH:-main}"
PORT="${AURALIS_PORT:-5056}"
HOSTNAME_ING="${AURALIS_HOSTNAME:-api.auralisnatura.com}"
TUNNEL_ID="${AURALIS_TUNNEL_ID:-}"
MIN_FREE_MB="${AURALIS_MIN_FREE_MB:-2048}"
CHROME="${AURALIS_CHROME:-}"
CHROME_DEB_URL="${AURALIS_CHROME_DEB_URL:-}"

_flag() { case "${1:-0}" in 1|y|Y|yes|YES|true|TRUE|on|ON) return 0 ;; *) return 1 ;; esac; }
ALLOW_DB_OVERWRITE=0; _flag "${AURALIS_ALLOW_DB_OVERWRITE:-0}"     && ALLOW_DB_OVERWRITE=1
SKIP_DATA=0;          _flag "${AURALIS_SKIP_DATA:-0}"              && SKIP_DATA=1
SKIP_PACKAGES=0;      _flag "${AURALIS_SKIP_PACKAGES:-0}"          && SKIP_PACKAGES=1
SKIP_TUNNEL=0;        _flag "${AURALIS_SKIP_TUNNEL:-0}"            && SKIP_TUNNEL=1
REQUIRE_VERIFY=0;     _flag "${AURALIS_REQUIRE_VERIFY:-0}"         && REQUIRE_VERIFY=1
REQUIRE_TOKEN=0;      _flag "${AURALIS_REQUIRE_CLAUDE_TOKEN:-0}"   && REQUIRE_TOKEN=1
KEEP_PAYLOAD=0;       _flag "${AURALIS_KEEP_PAYLOAD:-0}"           && KEEP_PAYLOAD=1

# -------------------------------------------------------------------- output --
# Colour ONLY on a TTY: this normally runs through `ssh host bash -s`, where
# escape codes would just pollute the caller's captured log.
if [ -t 1 ]; then
  C_R=$'\033[31m'; C_G=$'\033[32m'; C_Y=$'\033[33m'; C_B=$'\033[1m'; C_0=$'\033[0m'
else
  C_R=''; C_G=''; C_Y=''; C_B=''; C_0=''
fi
STAGE="init"
DEPLOY_PUB=""          # filled in only for exit 30
WARNINGS=()
CHANGED_UNITS=0

stage() { STAGE="$1"; printf '\n%s== %s ==%s\n' "$C_B" "$1" "$C_0"; }
say()   { printf '   %s\n' "$*"; }
ok()    { printf '   %s✓%s %s\n' "$C_G" "$C_0" "$*"; }
warn()  { printf '   %s!%s %s\n' "$C_Y" "$C_0" "$*"; WARNINGS+=("$*"); }
die()   { local c="$1"; shift; printf '\n%sFATAL [%s] %s%s\n' "$C_R" "$STAGE" "$*" "$C_0" >&2; exit "$c"; }

trap 'rc=$?; printf "\n%sUNEXPECTED ERROR%s stage=%s line=%s cmd=%s rc=%s\n" \
      "$C_R" "$C_0" "$STAGE" "$LINENO" "$BASH_COMMAND" "$rc" >&2; exit 99' ERR
finish() {
  local rc=$?
  set +e; trap - ERR          # never let cleanup itself trip the traps
  # Scratch is removed always; the payload only on success, so a failed run
  # stays retryable (the deploy-key case at exit 30 depends on that).
  rm -rf "$WORK_DIR" 2>/dev/null || true
  if [ "$rc" -eq 0 ] && [ "$KEEP_PAYLOAD" -eq 0 ] && [ -n "$PAYLOAD" ] && [ -d "$PAYLOAD" ]; then
    find "$PAYLOAD" -type f -exec shred -u {} + 2>/dev/null || rm -rf "$PAYLOAD" 2>/dev/null || true
    rm -rf "$PAYLOAD" 2>/dev/null || true
  fi
  printf '\nAURALIS_INSTALL_RESULT=%s\n' "$([ "$rc" -eq 0 ] && echo ok || echo failed)"
  printf 'AURALIS_INSTALL_STAGE=%s\n' "$STAGE"
  printf 'AURALIS_INSTALL_EXIT=%s\n' "$rc"
  if [ -n "$DEPLOY_PUB" ] && [ "$rc" -eq 30 ]; then
    printf 'AURALIS_DEPLOY_KEY_PUB=%s\n' "$DEPLOY_PUB"
  fi
  return 0
}
trap finish EXIT

# ------------------------------------------------------------------ helpers --
as_svc() {  # run a command as the service user, with a sane, minimal environment
  runuser -u "$SVC_USER" -- "$@"
}

write_managed() {  # write_managed <path> <mode> <owner:group>  — content on stdin
  # Atomic (temp file in the SAME directory + mv) and change-detecting, so
  # re-running does not touch mtimes and does not trigger pointless restarts.
  local path="$1" mode="$2" own="$3" dir tmp
  dir="$(dirname "$path")"; mkdir -p "$dir"
  tmp="$(mktemp "$dir/.auralis-tmp.XXXXXX")"
  cat > "$tmp"
  chown "$own" "$tmp"; chmod "$mode" "$tmp"
  if [ -e "$path" ] && cmp -s "$tmp" "$path"; then
    rm -f "$tmp"; chown "$own" "$path"; chmod "$mode" "$path"; return 1   # unchanged
  fi
  mv -f "$tmp" "$path"; return 0                                          # changed
}

avail_mb() { local p="$1"; while [ ! -d "$p" ] && [ "$p" != "/" ]; do p="$(dirname "$p")"; done
             df -Pm "$p" 2>/dev/null | awk 'NR==2 {print $4}' || true; }

have() { command -v "$1" >/dev/null 2>&1; }

# =============================================================================
stage "1/12 preflight"
# =============================================================================
[ "$(id -u)" -eq 0 ] || die 10 "must run as root (got uid $(id -u))."
ok "running as root on $(hostname -f 2>/dev/null || hostname)"

[ -d /run/systemd/system ] && have systemctl || die 11 "systemd not detected — this installer only supports systemd hosts."
ok "systemd $(systemctl --version 2>/dev/null | head -1 | awk '{print $2}' || true)"

DISTRO_ID="unknown"; DISTRO_VER=""
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release; DISTRO_ID="${ID:-unknown}"; DISTRO_VER="${VERSION_ID:-}"
fi
say "distro: $DISTRO_ID $DISTRO_VER · kernel $(uname -r) · arch $(uname -m)"
if [ "$SKIP_PACKAGES" -eq 0 ] && ! have apt-get; then
  die 12 "no apt-get. This installer only automates Debian/Ubuntu. Install python3, python3-venv, git, curl, chromium and cloudflared by hand, then re-run with AURALIS_SKIP_PACKAGES=1."
fi

# --- payload ---------------------------------------------------------------
[ -n "$PAYLOAD" ] || die 15 "AURALIS_PAYLOAD_DIR is not set (see the contract at the top of this file)."
[ -d "$PAYLOAD" ] || die 15 "payload directory $PAYLOAD does not exist."
[ -f "$PAYLOAD/portal.env" ] || die 15 "payload is missing the REQUIRED file portal.env."
ok "payload $PAYLOAD ($(find "$PAYLOAD" -maxdepth 1 -type f 2>/dev/null | wc -l || true) files)"

# --- port 5056 -------------------------------------------------------------
# History: a stale process kept the port and answered with the WRONG data while
# every fresh start silently failed to bind. On a shared host we must never kill
# a listener we do not own — so: identify, and abort if it is not ours.
port_pid=""
if have ss; then
  port_pid="$(ss -H -ltnp 2>/dev/null | awk -v p="$PORT" '$4 ~ ("[:.]" p "$")' \
              | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | head -1 || true)"
  ss -H -ltn 2>/dev/null | awk -v p="$PORT" '$4 ~ ("[:.]" p "$")' | grep -q . && port_busy=1 || port_busy=0
elif have lsof; then
  port_pid="$(lsof -ti "tcp:$PORT" -sTCP:LISTEN 2>/dev/null | head -1 || true)"
  [ -n "$port_pid" ] && port_busy=1 || port_busy=0
else
  # last resort: try to connect
  if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then port_busy=1; exec 3>&- 3<&-; else port_busy=0; fi
fi
if [ "${port_busy:-0}" -eq 1 ]; then
  own_pid="$(systemctl show -p MainPID --value auralis-portal.service 2>/dev/null || echo 0)"
  if [ -n "$port_pid" ] && [ "$port_pid" = "$own_pid" ] && [ "$own_pid" != "0" ]; then
    ok "port $PORT held by our own auralis-portal.service (pid $port_pid) — will be restarted"
  else
    exe="$( [ -n "$port_pid" ] && readlink -f "/proc/$port_pid/exe" 2>/dev/null || echo unknown )"
    die 13 "TCP $PORT is already in use by pid ${port_pid:-?} ($exe) which is NOT auralis-portal.service. Refusing to touch a foreign process. Free the port or set AURALIS_PORT to something else (and update the tunnel ingress)."
  fi
else
  ok "TCP $PORT is free"
fi

# --- pre-existing cloudflared (REPORT ONLY — never touch) -------------------
mapfile -t cf_units < <(systemctl list-unit-files --type=service --no-legend 2>/dev/null \
                        | awk '$1 ~ /cloudflared/ {print $1}' || true)
if [ "${#cf_units[@]}" -gt 0 ]; then
  say "existing cloudflared units on this host (NOT modified):"
  for u in "${cf_units[@]}"; do
    if [ "$u" = "cloudflared-auralis.service" ]; then continue; fi
    say "   · $u  [$(systemctl is-enabled "$u" 2>/dev/null || echo ?)/$(systemctl is-active "$u" 2>/dev/null || echo ?)]"
  done
fi
if [ -d "$CF_DIR" ]; then
  for f in "$CF_DIR"/*.yml "$CF_DIR"/*.yaml; do
    [ -e "$f" ] || continue
    case "$(basename "$f")" in auralis.yml) continue ;; esac
    if grep -q -- "$HOSTNAME_ING" "$f" 2>/dev/null; then
      warn "foreign tunnel config $f also mentions $HOSTNAME_ING — two tunnels claiming one hostname is exactly how Error 1033 happened. Check it before going live."
    fi
  done
fi

# --- firewall (REPORT ONLY — never change) ---------------------------------
fw="none detected"
if have ufw;      then fw="ufw: $(ufw status 2>/dev/null | head -1 || true)"; fi
if have firewall-cmd && systemctl is-active --quiet firewalld 2>/dev/null; then fw="firewalld active"; fi
if have nft; then fw="$fw · nftables rules: $(nft list ruleset 2>/dev/null | wc -l || true) lines"; fi
say "firewall: $fw (unchanged — the portal binds 127.0.0.1 only and cloudflared dials OUT, so no inbound rule is needed)"

# --- disk ------------------------------------------------------------------
for p in /opt /var/lib /var/backups; do
  a="$(avail_mb "$p" || true)"; [ -n "$a" ] || continue
  say "free on $p: ${a} MB"
  [ "$a" -ge "$MIN_FREE_MB" ] || die 14 "only ${a} MB free on $p, need ${MIN_FREE_MB} MB (AURALIS_MIN_FREE_MB)."
done
ok "disk ok"

# =============================================================================
stage "2/12 user, group and directory tree"
# =============================================================================
getent group "$SVC_GROUP" >/dev/null || { groupadd --system "$SVC_GROUP"; ok "group $SVC_GROUP created"; }
if ! getent passwd "$SVC_USER" >/dev/null; then
  useradd --system --gid "$SVC_GROUP" --home-dir "$HOME_DIR" --shell /bin/bash \
          --comment "Auralis Natura portal service" "$SVC_USER"
  ok "user $SVC_USER created"
fi
passwd -l "$SVC_USER" >/dev/null 2>&1 || true    # no password login, ever

# $HOME_DIR must be WRITABLE by the service user: the Claude CLI keeps its state
# in ~ (and headless chromium wants a writable HOME too). Root-run helper scripts
# therefore live in $ETC_DIR (root:auralis 0750 — readable, not writable, by us).
mkdir -p "$HOME_DIR" "$APP_DIR" "$SSH_DIR" "$DATA_DIR" "$DATA_DIR/output_docs" \
         "$DATA_DIR/backups" "$WORK_DIR" "$ETC_DIR" "$BACKUP_DIR"
chown "$SVC_USER:$SVC_GROUP" "$HOME_DIR" "$APP_DIR" "$SSH_DIR" "$DATA_DIR" \
      "$DATA_DIR/output_docs" "$DATA_DIR/backups" "$WORK_DIR" "$BACKUP_DIR"
chmod 0750 "$HOME_DIR" "$DATA_DIR" "$DATA_DIR/backups" "$BACKUP_DIR"
chmod 0755 "$APP_DIR" "$DATA_DIR/output_docs"
chmod 0700 "$SSH_DIR" "$WORK_DIR"
chown root:"$SVC_GROUP" "$ETC_DIR"; chmod 0750 "$ETC_DIR"
mkdir -p "$CF_DIR"                                  # created if absent; NEVER chmod'ed
ok "tree ready: $HOME_DIR · $DATA_DIR · $ETC_DIR · $BACKUP_DIR"

# =============================================================================
stage "3/12 packages"
# =============================================================================
APT_OPTS=(-y -o Dpkg::Options::=--force-confold -o Dpkg::Options::=--force-confdef)
export DEBIAN_FRONTEND=noninteractive
apt_update_done=0
apt_install() {  # install ONLY the named packages; never upgrade anything else
  [ "$#" -gt 0 ] || return 0
  if [ "$apt_update_done" -eq 0 ]; then apt-get update -qq || true; apt_update_done=1; fi
  apt-get install "${APT_OPTS[@]}" "$@"
}

if [ "$SKIP_PACKAGES" -eq 1 ]; then
  warn "AURALIS_SKIP_PACKAGES set — no apt-get will run"
else
  missing=()
  for p in python3 python3-venv git curl ca-certificates fonts-liberation; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "ok installed" || missing+=("$p")
  done
  if [ "${#missing[@]}" -gt 0 ]; then
    say "installing: ${missing[*]}"
    apt_install "${missing[@]}" || die 20 "apt-get install failed for: ${missing[*]}"
  fi
  ok "base packages present ($(python3 -V 2>&1), $(git --version))"
fi

# --- chromium: a REAL deb binary, never a snap ------------------------------
# lib/render.py silently writes .html instead of the 12-page PDF when no Chrome
# is found — a degradation nobody notices until a client gets the wrong file.
# A snap chromium is just as bad: its confinement cannot read the temp HTML that
# render.py writes, so --print-to-pdf produces nothing and we fall into the same
# silent path. Hence: detect, refuse, explain.
is_snap_binary() {
  local p; p="$(readlink -f "$1" 2>/dev/null || echo "$1")"
  case "$p" in /snap/*|/var/lib/snapd/*) return 0 ;; esac
  if ! LC_ALL=C head -c 4 "$p" 2>/dev/null | grep -q 'ELF'; then
    # not an ELF binary -> a wrapper script; Ubuntu's transitional deb execs snap
    if LC_ALL=C head -c 4096 "$p" 2>/dev/null | grep -qi 'snap'; then return 0; fi
  fi
  return 1
}
find_chrome() {
  local c
  for c in "$CHROME" /usr/bin/chromium /usr/lib/chromium/chromium /usr/bin/chromium-browser \
           /usr/bin/google-chrome-stable /usr/bin/google-chrome \
           "$(command -v chromium 2>/dev/null || true)" \
           "$(command -v chromium-browser 2>/dev/null || true)" \
           "$(command -v google-chrome 2>/dev/null || true)"; do
    [ -n "$c" ] && [ -x "$c" ] || continue
    if is_snap_binary "$c"; then continue; fi
    printf '%s\n' "$(readlink -f "$c")"; return 0
  done
  return 1
}

if [ -n "$CHROME" ] && [ -x "$CHROME" ] && ! is_snap_binary "$CHROME"; then
  ok "using AURALIS_CHROME=$CHROME"
elif CHROME="$(find_chrome)"; then
  ok "chromium already installed: $CHROME"
elif [ "$SKIP_PACKAGES" -eq 1 ]; then
  die 21 "no usable Chromium found and AURALIS_SKIP_PACKAGES is set."
else
  for pkg in chromium chromium-browser; do
    apt-cache show "$pkg" >/dev/null 2>&1 || continue
    say "installing $pkg"
    apt_install "$pkg" || true
    CHROME="$(find_chrome || true)"
    if [ -n "$CHROME" ]; then break; fi
  done
  if [ -z "$CHROME" ] && [ -n "$CHROME_DEB_URL" ]; then
    say "falling back to AURALIS_CHROME_DEB_URL"
    deb="$WORK_DIR/chrome.deb"
    curl -fsSL --proto '=https' --tlsv1.2 -o "$deb" "$CHROME_DEB_URL" \
      || die 21 "could not download $CHROME_DEB_URL"
    apt_install "$deb" || die 21 "installing $CHROME_DEB_URL failed"
    CHROME="$(find_chrome || true)"
  fi
  [ -n "$CHROME" ] || die 21 "no non-snap Chromium available on $DISTRO_ID $DISTRO_VER.
   A snap build cannot read the temp HTML that lib/render.py writes, so the
   12-page report PDF would silently degrade to .html. Fix one of:
     · apt-get install -y chromium            (Debian, and Ubuntu with a deb source)
     · re-run with AURALIS_CHROME_DEB_URL=https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
     · install Chrome/Chromium yourself and re-run with AURALIS_CHROME=/abs/path"
  ok "chromium installed: $CHROME"
fi

# --- cloudflared: official vendor .deb, NOT an apt source --------------------
# Deliberately NOT adding pkg.cloudflare.com to /etc/apt/sources.list.d: this
# host belongs to another company too, and mutating its apt configuration is out
# of scope. The release artifact below is Cloudflare's own signed download.
if [ "$SKIP_TUNNEL" -eq 1 ]; then
  warn "AURALIS_SKIP_TUNNEL set — cloudflared not installed/configured"
elif have cloudflared; then
  ok "cloudflared present: $(cloudflared --version 2>/dev/null | head -1 || true)"
elif [ "$SKIP_PACKAGES" -eq 1 ]; then
  die 41 "cloudflared missing and AURALIS_SKIP_PACKAGES is set."
else
  arch="$(dpkg --print-architecture)"
  case "$arch" in amd64|arm64|armhf|386) : ;; *) die 41 "unsupported architecture $arch for the cloudflared release deb." ;; esac
  url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${arch}.deb"
  say "downloading cloudflared ($arch) from Cloudflare's official release"
  curl -fsSL --proto '=https' --tlsv1.2 -o "$WORK_DIR/cloudflared.deb" "$url" \
    || die 41 "download failed: $url"
  apt_install "$WORK_DIR/cloudflared.deb" || die 41 "cloudflared package install failed"
  ok "cloudflared installed: $(cloudflared --version 2>/dev/null | head -1 || true)"
fi

# =============================================================================
stage "4/12 deploy key and repository"
# =============================================================================
if [ -f "$PAYLOAD/deploy_key" ] && [ ! -f "$SSH_KEY" ]; then
  install -o "$SVC_USER" -g "$SVC_GROUP" -m 0600 "$PAYLOAD/deploy_key" "$SSH_KEY"
  if [ -f "$PAYLOAD/deploy_key.pub" ]; then
    install -o "$SVC_USER" -g "$SVC_GROUP" -m 0644 "$PAYLOAD/deploy_key.pub" "$SSH_KEY.pub"
  else
    as_svc ssh-keygen -y -f "$SSH_KEY" > "$SSH_KEY.pub"
    chown "$SVC_USER:$SVC_GROUP" "$SSH_KEY.pub"; chmod 0644 "$SSH_KEY.pub"
  fi
  ok "deploy key taken from the payload"
elif [ ! -f "$SSH_KEY" ]; then
  as_svc ssh-keygen -t ed25519 -N '' -C "auralis-deploy@$(hostname -s)" -f "$SSH_KEY" -q
  ok "deploy key generated"
else
  ok "deploy key already present"
fi
chmod 0600 "$SSH_KEY"; chown "$SVC_USER:$SVC_GROUP" "$SSH_KEY" "$SSH_KEY.pub" 2>/dev/null || true
DEPLOY_PUB="$(cat "$SSH_KEY.pub" 2>/dev/null || true)"

printf '%s\n' "$GH_HOSTKEY" | write_managed "$KNOWN_HOSTS" 0644 "$SVC_USER:$SVC_GROUP" >/dev/null || true
GIT_SSH="ssh -i $SSH_KEY -o IdentitiesOnly=yes -o UserKnownHostsFile=$KNOWN_HOSTS -o StrictHostKeyChecking=yes -o BatchMode=yes -o ConnectTimeout=15"

git_svc() { as_svc env HOME="$HOME_DIR" GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND="$GIT_SSH" git "$@"; }

# Can we reach the repo at all? Distinguish "key not authorised yet" (retryable,
# the caller prints instructions and the operator adds the Deploy Key) from
# every other git failure.
ls_err="$WORK_DIR/ls-remote.err"
if ! git_svc ls-remote --heads "$REPO_URL" >/dev/null 2>"$ls_err"; then
  if grep -qiE 'permission denied|could not read from remote|repository not found|access rights' "$ls_err"; then
    printf '\n%s%s%s\n' "$C_Y" "GitHub has not authorised this server's deploy key yet." "$C_0" >&2
    printf '\nAdd it as a READ-ONLY Deploy Key:\n' >&2
    printf '  1. https://github.com/stefangruber001/AuralisNatura/settings/keys/new\n' >&2
    printf '  2. Title: "Hetzner auralis portal"   Allow write access: NO\n' >&2
    printf '  3. Paste exactly this line:\n\n' >&2
    printf '----- BEGIN DEPLOY KEY -----\n%s\n----- END DEPLOY KEY -----\n\n' "$DEPLOY_PUB" >&2
    printf '  4. Re-run this installer unchanged — it will continue from here.\n' >&2
    sed -e 's/^/     git: /' "$ls_err" >&2 || true
    die 30 "deploy key not authorised (retryable)."
  fi
  sed -e 's/^/     git: /' "$ls_err" >&2 || true
  die 31 "cannot reach $REPO_URL."
fi
ok "repository reachable as the deploy key"

if [ -d "$APP_DIR/.git" ]; then
  git_svc -C "$APP_DIR" remote set-url origin "$REPO_URL"
  git_svc -C "$APP_DIR" fetch --quiet origin "$BRANCH" || die 31 "git fetch failed"
  # reset --hard is safe here for exactly the reason the Mac launcher relies on:
  # auralis.db, config/clients.json and output_docs/ are git-ignored (and here
  # they are symlinks into /var/lib/auralis), so no runtime data is in the tree.
  git_svc -C "$APP_DIR" reset --hard --quiet "origin/$BRANCH" || die 31 "git reset failed"
  ok "repo fast-forwarded to origin/$BRANCH"
else
  rmdir "$APP_DIR" 2>/dev/null || true
  git_svc clone --quiet --branch "$BRANCH" "$REPO_URL" "$APP_DIR" || die 31 "git clone failed"
  ok "repo cloned"
fi
[ -f "$PORTAL_DIR/run.py" ] || die 31 "$PORTAL_DIR/run.py missing — wrong branch or repo layout?"
say "HEAD $(git_svc -C "$APP_DIR" rev-parse --short HEAD || true) · $(git_svc -C "$APP_DIR" log -1 --format=%s | cut -c1-60 || true)"

# =============================================================================
stage "5/12 virtualenv and dependencies"
# =============================================================================
if [ ! -x "$VENV_DIR/bin/python" ]; then
  as_svc python3 -m venv "$VENV_DIR" || die 32 "python3 -m venv failed (is python3-venv installed?)"
  ok "venv created"
else
  ok "venv present"
fi
# Only flask + cryptography — deliberately tiny; see portal/requirements.txt.
as_svc "$VENV_DIR/bin/pip" install --quiet --disable-pip-version-check --no-input \
       -r "$PORTAL_DIR/requirements.txt" || die 32 "pip install -r requirements.txt failed"
ok "deps: $(as_svc "$VENV_DIR/bin/pip" list --format=freeze 2>/dev/null | grep -iE '^(flask|cryptography)=' | tr '\n' ' ' || true)"

# =============================================================================
stage "6/12 environment file"
# =============================================================================
# Values are NEVER printed — only key names. Validate first so a mangled file
# fails here instead of as a cryptic systemd "Failed to parse environment file".
norm="$WORK_DIR/portal.env.norm"
sed -e 's/\r$//' -e 's/^[[:space:]]*export[[:space:]]\+//' "$PAYLOAD/portal.env" > "$norm"
bad_line="$(awk '!/^[[:space:]]*(#|$)/ && !/^[A-Za-z_][A-Za-z0-9_]*=/ {print NR; exit}' "$norm")"
[ -z "$bad_line" ] || die 15 "portal.env line $bad_line is not KEY=VALUE (comments must be on their own line)."

for k in AURALIS_API_KEY AURALIS_SECRET AURALIS_DATA_KEY; do
  grep -qE "^$k=.+" "$norm" || die 15 "portal.env is missing a non-empty $k."
done
# cfg.validate_secrets() refuses these at startup — catch them now, not after a
# failed service start.
if grep -qE '^AURALIS_(API_KEY|SECRET)=(dev-staff-key-change-me|dev-secret-change-me|change-me|REPLACE_WITH_A_LONG_RANDOM_STRING)$' "$norm"; then
  die 15 "portal.env still carries a dev placeholder secret — the app refuses to start in production with those."
fi
if ! grep -qE '^CLAUDE_CODE_OAUTH_TOKEN=.+' "$norm"; then
  if [ "$REQUIRE_TOKEN" -eq 1 ]; then
    die 15 "no CLAUDE_CODE_OAUTH_TOKEN in portal.env and AURALIS_REQUIRE_CLAUDE_TOKEN is set."
  fi
  warn "NO CLAUDE_CODE_OAUTH_TOKEN — lib/agent.py will fall back to the offline \"stub\" report writer. Run \`claude setup-token\` ON THE MAC (it is interactive), add the token to portal.env and re-run. verify_server.sh probes the CLI at runtime."
fi

defaulted=()
add_default() { grep -qE "^$1=" "$norm" || { printf '%s=%s\n' "$1" "$2" >> "$norm"; defaulted+=("$1"); }; }
add_default AURALIS_ENV               production
add_default AURALIS_EMAIL_MODE        draft
add_default AURALIS_AGENT_PROVIDER    claude_cli
add_default AURALIS_PUBLIC_BASE_URL   "https://$HOSTNAME_ING"
add_default AURALIS_BOOKING_URL       "https://$HOSTNAME_ING/book"
add_default AURALIS_BACKUP_DIR        "$DATA_DIR/backups"
if [ "${#defaulted[@]}" -gt 0 ]; then say "defaulted keys: ${defaulted[*]}"; fi

{
  # AURALIS_PORT / AURALIS_CHROME are OWNED by this installer: the port must
  # match the unit + tunnel ingress, and the chromium path is whatever survived
  # the render test below.
  awk '!/^[[:space:]]*(AURALIS_PORT|AURALIS_CHROME)=/' "$norm"
  printf '\n# --- set by portal/deploy/install_server.sh on %s ---\n' "$(date -u +%FT%TZ)"
  printf 'AURALIS_PORT=%s\n' "$PORT"
  printf 'AURALIS_CHROME=%s\n' "$CHROME"
} | write_managed "$ENV_FILE" 0640 "root:$SVC_GROUP" >/dev/null || true
ok "$ENV_FILE written 0640 root:$SVC_GROUP ($(grep -cE '^[A-Za-z_]' "$ENV_FILE" || true) keys, values not logged)"

# =============================================================================
stage "7/12 data placement"
# =============================================================================
# The server may already be live. Stop it before touching the store so no writer
# is racing us; it is started again in stage 10.
if systemctl is-active --quiet auralis-portal.service 2>/dev/null; then
  systemctl stop auralis-portal.service; say "auralis-portal stopped for data placement"
fi

place_data() {  # place_data <payload-file> <target> <mode>
  local src="$1" dst="$2" mode="$3" ts
  [ -f "$src" ] || { say "$(basename "$dst"): not in payload — keeping what is on the server"; return 0; }
  if [ -s "$dst" ]; then
    if cmp -s "$src" "$dst"; then ok "$(basename "$dst"): already identical (no-op)"; return 0; fi
    if [ "$ALLOW_DB_OVERWRITE" -eq 0 ]; then
      die 33 "$dst already exists with DIFFERENT content than the payload copy.
   Refusing to clobber live data. Either drop $(basename "$src") from the payload
   (server data wins) or re-run with AURALIS_ALLOW_DB_OVERWRITE=1 (payload wins;
   the current file is copied to $BACKUP_DIR first)."
    fi
    ts="$(date -u +%Y%m%d-%H%M%S)"
    # Back the old file up WITH its -wal/-shm sidecars: a WAL holds committed
    # transactions that are not in the main .db yet, so copying the .db alone
    # would silently drop the most recent records.
    for sc in "" "-wal" "-shm"; do
      if [ -e "$dst$sc" ]; then cp -a "$dst$sc" "$BACKUP_DIR/preinstall-$ts-$(basename "$dst")$sc"; fi
    done
    warn "$(basename "$dst") overwritten; previous file (+WAL) saved as $BACKUP_DIR/preinstall-$ts-$(basename "$dst")*"
  fi
  # Only now, once we are certain we are writing: the new file must never
  # inherit the previous database's sidecars. (Doing this earlier would have
  # destroyed WAL contents even on the refuse-to-overwrite path.)
  rm -f "$dst-wal" "$dst-shm"
  install -o "$SVC_USER" -g "$SVC_GROUP" -m "$mode" "$src" "$dst"
  ok "$(basename "$dst") placed"
}

if [ "$SKIP_DATA" -eq 1 ]; then
  warn "AURALIS_SKIP_DATA set — no data files placed"
else
  # WAL/SHM handling lives inside place_data — it must happen only once the
  # overwrite is actually going ahead. See the comment there.
  place_data "$PAYLOAD/auralis.db"   "$DATA_DIR/auralis.db"   0640
  place_data "$PAYLOAD/clients.json" "$DATA_DIR/clients.json" 0640
  if [ -f "$PAYLOAD/output_docs.tar.gz" ]; then
    tar -xzf "$PAYLOAD/output_docs.tar.gz" -C "$DATA_DIR/output_docs" --no-same-owner \
      || die 33 "could not extract output_docs.tar.gz"
    chown -R "$SVC_USER:$SVC_GROUP" "$DATA_DIR/output_docs"
    ok "output_docs merged ($(find "$DATA_DIR/output_docs" -type f 2>/dev/null | wc -l || true) files)"
  fi
fi
# clients.json must exist for cfg.clients(); an absent one is seeded from the
# committed example on first read, so only fix ownership when it is there.
if [ -e "$DATA_DIR/clients.json" ]; then chown "$SVC_USER:$SVC_GROUP" "$DATA_DIR/clients.json"; fi
if [ -e "$DATA_DIR/auralis.db" ];   then chown "$SVC_USER:$SVC_GROUP" "$DATA_DIR/auralis.db"; fi

# =============================================================================
stage "8/12 symlinks into the worktree"
# =============================================================================
# lib/cfg.py computes ROOT = the portal dir, so the app finds its data through
# these three links without knowing anything about /var/lib/auralis. All three
# repo paths are git-ignored, so `git reset --hard` in the updater leaves them.
link_data() {  # link_data <link-path> <target>
  local link="$1" target="$2" ts
  if [ -L "$link" ]; then
    if [ "$(readlink -f "$link" || true)" = "$(readlink -f "$target" || true)" ]; then
      ok "$(basename "$link") -> $target"; return 0
    fi
    rm -f "$link"
  elif [ -d "$link" ] && [ ! -L "$link" ]; then
    # a real directory (cfg.py creates output_docs/ on import) — merge, never lose
    cp -an "$link/." "$target/" 2>/dev/null || true
    rm -rf "$link"
  elif [ -e "$link" ]; then
    ts="$(date -u +%Y%m%d-%H%M%S)"
    mv "$link" "$BACKUP_DIR/worktree-$ts-$(basename "$link")" \
      || die 34 "$link is a real file and could not be moved aside."
    warn "$link was a real file; moved to $BACKUP_DIR/worktree-$ts-$(basename "$link")"
  fi
  as_svc ln -sfn "$target" "$link" || die 34 "could not create symlink $link"
  ok "$(basename "$link") -> $target"
}
link_data "$PORTAL_DIR/auralis.db"          "$DATA_DIR/auralis.db"
link_data "$PORTAL_DIR/config/clients.json" "$DATA_DIR/clients.json"
link_data "$PORTAL_DIR/output_docs"         "$DATA_DIR/output_docs"

# =============================================================================
stage "9/12 chromium PDF render test + data-key check"
# =============================================================================
# Not `--version`: the exact command line lib/render.py runs, end to end, and
# the output is checked for a real %PDF header. This is the only way to catch
# the silent .html fallback before a client receives the wrong file.
cat > "$WORK_DIR/render-probe.html" <<'HTML'
<!doctype html><html><head><meta charset="utf-8"><title>Auralis render probe</title>
<style>@page{size:A4;margin:0}body{font-family:serif;padding:40mm}h1{color:#3D2719}</style>
</head><body><h1>Auralis Natura — render probe</h1><p>If this became a PDF, the
12-page report will render too.</p></body></html>
HTML
chown "$SVC_USER:$SVC_GROUP" "$WORK_DIR/render-probe.html"
rm -f "$WORK_DIR/render-probe.pdf"
if ! as_svc env HOME="$HOME_DIR" timeout 120 "$CHROME" --headless --disable-gpu --no-sandbox \
       --no-pdf-header-footer "--print-to-pdf=$WORK_DIR/render-probe.pdf" \
       "file://$WORK_DIR/render-probe.html" >"$WORK_DIR/chrome.log" 2>&1; then
  sed -e 's/^/     chrome: /' "$WORK_DIR/chrome.log" | tail -20 >&2 || true
  die 22 "chromium exited non-zero on the render probe ($CHROME)."
fi
if [ ! -s "$WORK_DIR/render-probe.pdf" ] || [ "$(LC_ALL=C head -c 5 "$WORK_DIR/render-probe.pdf")" != "%PDF-" ]; then
  sed -e 's/^/     chrome: /' "$WORK_DIR/chrome.log" | tail -20 >&2 || true
  die 22 "chromium produced no valid PDF — lib/render.py would silently write .html instead of the 12-page report."
fi
ok "PDF render verified ($(stat -c%s "$WORK_DIR/render-probe.pdf") bytes) via $CHROME"

# --- THE data-key check ------------------------------------------------------
# July 2026: the console started 500-ing because a record had been encrypted
# with a throwaway .dev_data.key while the server ran with the env key. Probe it
# BEFORE anything is started or the tunnel is pointed here.
cat > "$WORK_DIR/keycheck.py" <<'PY'
import os, sys
env_file, portal_dir = sys.argv[1], sys.argv[2]
# Parse the EnvironmentFile exactly the way systemd will: LITERALLY. Sourcing it
# in a shell instead would expand $... and backticks inside values, which for a
# passphrase-style AURALIS_DATA_KEY yields a DIFFERENT key than the service gets
# and turns this probe into a false alarm on a perfectly good migration.
with open(env_file, encoding="utf-8") as fh:
    for raw in fh:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]                     # systemd strips matched quotes
        os.environ[k.strip()] = v
sys.path.insert(0, portal_dir)
try:
    from lib import store
    r = store.key_matches_store()
except Exception as e:                      # missing key, unreadable file, ...
    print("ERROR:%s: %s" % (e.__class__.__name__, str(e)[:200])); raise SystemExit(0)
print("MATCH" if r is True else ("MISMATCH" if r is False else "UNREADABLE"))
PY
chown "$SVC_USER:$SVC_GROUP" "$WORK_DIR/keycheck.py"
# Values never pass through this shell — the child reads the env file itself.
keyres="$(as_svc "$VENV_DIR/bin/python" "$WORK_DIR/keycheck.py" "$ENV_FILE" "$PORTAL_DIR" 2>&1 | tail -1 || true)"
case "$keyres" in
  MATCH)      ok "AURALIS_DATA_KEY opens the store" ;;
  MISMATCH)   die 35 "AURALIS_DATA_KEY does NOT decrypt $DATA_DIR/auralis.db.
   This is the exact July-2026 failure: every staff read would 500. Do NOT
   overwrite the store — put the ORIGINAL key from the Mac into portal.env
   (portal/.env on the Mac, AURALIS_DATA_KEY) and re-run." ;;
  UNREADABLE) die 35 "the store at $DATA_DIR/auralis.db could not be read at all (permissions? corrupt file?)." ;;
  *)          die 35 "data-key probe failed: $keyres" ;;
esac

# =============================================================================
stage "10/12 systemd units"
# =============================================================================
# Helper scripts live in $ETC_DIR: root-owned 0750 root:auralis, so the service
# user can execute but never rewrite a script that systemd runs as root.
write_managed "$BIN_DIR/update.sh" 0750 "root:$SVC_GROUP" <<UPDATE || true
#!/usr/bin/env bash
# Managed by portal/deploy/install_server.sh — do not edit by hand.
# Replaces the Mac launcher's 120s self-update loop: fetch, and only if origin
# moved, hard-reset + reinstall deps + restart. Runs as root; all git/pip work
# is done as $SVC_USER so file ownership stays correct.
set -Eeuo pipefail
export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND="$GIT_SSH"
cd "$APP_DIR"
# A failed fetch (network blip, key revoked) must NOT take the running app down:
# log it and wait for the next tick. Everything after this point is deliberate.
runuser -u $SVC_USER -- env HOME=$HOME_DIR GIT_SSH_COMMAND="\$GIT_SSH_COMMAND" git fetch --quiet origin $BRANCH \\
  || { echo "git fetch failed (network or deploy key?) — retrying next tick"; exit 0; }
local_head="\$(runuser -u $SVC_USER -- git -C $APP_DIR rev-parse HEAD)"
remote_head="\$(runuser -u $SVC_USER -- git -C $APP_DIR rev-parse origin/$BRANCH)"
# NB: \`[ x = y ] && exit 0\` would abort this script under \`set -e\` on the
# NOT-equal branch, i.e. exactly when there IS an update. Use a real if.
if [ "\$local_head" = "\$remote_head" ]; then exit 0; fi
echo "updating \$local_head -> \$remote_head"
runuser -u $SVC_USER -- git -C $APP_DIR reset --hard --quiet "origin/$BRANCH"
runuser -u $SVC_USER -- $VENV_DIR/bin/pip install --quiet --disable-pip-version-check --no-input -r $PORTAL_DIR/requirements.txt || echo "pip install failed — restarting with the old deps"
# re-assert the data symlinks (cheap; protects against a bad tree state)
runuser -u $SVC_USER -- ln -sfn $DATA_DIR/auralis.db   $PORTAL_DIR/auralis.db
runuser -u $SVC_USER -- ln -sfn $DATA_DIR/clients.json $PORTAL_DIR/config/clients.json
runuser -u $SVC_USER -- ln -sfn $DATA_DIR/output_docs  $PORTAL_DIR/output_docs
systemctl restart auralis-portal.service
UPDATE

write_managed "$BIN_DIR/backup.sh" 0750 "root:$SVC_GROUP" <<BACKUP || true
#!/usr/bin/env bash
# Managed by portal/deploy/install_server.sh — do not edit by hand.
# Daily tar.gz of $DATA_DIR into $BACKUP_DIR, newest 14 kept. The DB is snapshotted
# with SQLite's online backup API (WAL-safe, consistent while the server writes),
# exactly like lib/backup.py does. The rolling in-app snapshots under
# $DATA_DIR/backups are excluded — they are derived data and would double the size.
set -Eeuo pipefail
ts="\$(date -u +%Y%m%d-%H%M%S)"
stage="\$(mktemp -d $DATA_DIR/.bk.XXXXXX)"
trap 'rm -rf "\$stage"' EXIT
if [ -f $DATA_DIR/auralis.db ]; then
  $VENV_DIR/bin/python - "\$stage/auralis.db" <<'PY'
import sqlite3, sys
src = sqlite3.connect("$DATA_DIR/auralis.db")
dst = sqlite3.connect(sys.argv[1])
src.backup(dst); dst.close(); src.close()
PY
fi
if [ -f $DATA_DIR/clients.json ]; then cp -a $DATA_DIR/clients.json "\$stage/"; fi
tar -czf $BACKUP_DIR/auralis-\$ts.tar.gz -C "\$stage" . -C $DATA_DIR ./output_docs
# keep the newest 14 (|| true: an unmatched glob must not fail the unit)
ls -1t $BACKUP_DIR/auralis-*.tar.gz 2>/dev/null | tail -n +15 | xargs -r rm -f || true
echo "backup written: $BACKUP_DIR/auralis-\$ts.tar.gz"
BACKUP

unit() {  # unit <name> ; content on stdin
  if write_managed "$UNIT_DIR/$1" 0644 root:root; then CHANGED_UNITS=1; say "$1 written"; else say "$1 unchanged"; fi
}

unit auralis-portal.service <<PORTALUNIT
# Managed by portal/deploy/install_server.sh — replaces launchd KeepAlive.
[Unit]
Description=Auralis Natura portal (Flask, 127.0.0.1:$PORT)
Documentation=file://$PORTAL_DIR/deploy/SERVER-RUNBOOK.md
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SVC_USER
Group=$SVC_GROUP
WorkingDirectory=$PORTAL_DIR
EnvironmentFile=$ENV_FILE
Environment=PYTHONUNBUFFERED=1
Environment=HOME=$HOME_DIR
# HOME must be real and writable: the \`claude\` CLI keeps its state there and
# headless chromium wants a profile dir. PATH includes the user-local bins so a
# \`claude\` installed under ~/.local/bin is found by shutil.which("claude").
Environment=PATH=$HOME_DIR/.local/bin:$HOME_DIR/bin:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin
ExecStart=$VENV_DIR/bin/python $PORTAL_DIR/run.py
Restart=always
RestartSec=3
TimeoutStopSec=20
StandardOutput=journal
StandardError=journal
SyslogIdentifier=auralis-portal
# Containment — this box also runs another company's production ERP.
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
ProtectHome=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
ReadWritePaths=$DATA_DIR $BACKUP_DIR $HOME_DIR

[Install]
WantedBy=multi-user.target
PORTALUNIT

unit auralis-update.service <<'UPDATEUNIT'
# Managed by portal/deploy/install_server.sh
[Unit]
Description=Auralis portal self-update from GitHub main
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/etc/auralis/update.sh
SyslogIdentifier=auralis-update
UPDATEUNIT

unit auralis-update.timer <<'UPDATETIMER'
# Managed by portal/deploy/install_server.sh — the Mac launcher polled every 120s.
[Unit]
Description=Check GitHub main for portal updates every 2 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=2min
AccuracySec=30s
Unit=auralis-update.service

[Install]
WantedBy=timers.target
UPDATETIMER

unit auralis-backup.service <<BACKUPUNIT
# Managed by portal/deploy/install_server.sh
[Unit]
Description=Auralis daily encrypted-store backup

[Service]
Type=oneshot
User=$SVC_USER
Group=$SVC_GROUP
Environment=HOME=$HOME_DIR
ExecStart=$BIN_DIR/backup.sh
SyslogIdentifier=auralis-backup
BACKUPUNIT

unit auralis-backup.timer <<'BACKUPTIMER'
# Managed by portal/deploy/install_server.sh
[Unit]
Description=Daily Auralis backup

[Timer]
OnCalendar=*-*-* 03:20:00
RandomizedDelaySec=20min
Persistent=true
Unit=auralis-backup.service

[Install]
WantedBy=timers.target
BACKUPTIMER

systemctl daemon-reload
systemctl enable --quiet auralis-portal.service auralis-update.timer auralis-backup.timer \
  || die 40 "systemctl enable failed"
systemctl restart auralis-portal.service || die 40 "auralis-portal.service failed to start — journalctl -u auralis-portal -n 50"
systemctl start auralis-update.timer auralis-backup.timer || die 40 "timers failed to start"
ok "units installed, enabled and started"

# --- health gate -------------------------------------------------------------
healthy=0
for i in $(seq 1 30); do
  if curl -fsS -m 3 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then healthy=1; break; fi
  systemctl is-active --quiet auralis-portal.service || break
  sleep 1
done
if [ "$healthy" -ne 1 ]; then
  journalctl -u auralis-portal.service -n 40 --no-pager 2>/dev/null | sed -e 's/^/     /' >&2 || true
  die 40 "the portal never answered http://127.0.0.1:$PORT/health"
fi
ok "portal healthy on http://127.0.0.1:$PORT/health"

# =============================================================================
stage "11/12 cloudflared tunnel"
# =============================================================================
if [ "$SKIP_TUNNEL" -eq 1 ]; then
  warn "tunnel skipped (AURALIS_SKIP_TUNNEL) — https://$HOSTNAME_ING stays on the Mac"
elif [ ! -f "$PAYLOAD/tunnel.json" ]; then
  warn "no tunnel.json in the payload — cloudflared-auralis.service NOT installed. Copy ~/.cloudflared/<AURALIS_TUNNEL_ID>.json from the Mac into the payload and re-run."
else
  [ -n "$TUNNEL_ID" ] || die 41 "tunnel.json supplied but AURALIS_TUNNEL_ID is empty. Identity must be asserted, never guessed — running Paramur's tunnel instead of the Auralis one is what produced Error 1033."
  creds_id="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("TunnelID",""))' "$PAYLOAD/tunnel.json" 2>/dev/null || true)"
  [ -n "$creds_id" ] || die 41 "tunnel.json has no TunnelID field — is that really a cloudflared credentials file?"
  [ "$creds_id" = "$TUNNEL_ID" ] || die 41 "tunnel identity mismatch: AURALIS_TUNNEL_ID=$TUNNEL_ID but tunnel.json belongs to $creds_id. Refusing to run the wrong tunnel."
  ok "tunnel identity asserted: $TUNNEL_ID"

  CF_CRED="$CF_DIR/auralis-$TUNNEL_ID.json"
  install -o root -g "$SVC_GROUP" -m 0640 "$PAYLOAD/tunnel.json" "$CF_CRED"

  if [ -f "$PAYLOAD/tunnel.yml" ]; then
    # Trust but assert: the three facts that decide whether traffic lands here.
    grep -qE "^tunnel:[[:space:]]*$TUNNEL_ID[[:space:]]*$" "$PAYLOAD/tunnel.yml" || die 41 "payload tunnel.yml does not declare tunnel: $TUNNEL_ID"
    grep -q "$HOSTNAME_ING" "$PAYLOAD/tunnel.yml" || die 41 "payload tunnel.yml has no ingress for $HOSTNAME_ING"
    grep -q "127.0.0.1:$PORT" "$PAYLOAD/tunnel.yml" || die 41 "payload tunnel.yml does not route to http://127.0.0.1:$PORT"
    sed -e "s#^credentials-file:.*#credentials-file: $CF_CRED#" "$PAYLOAD/tunnel.yml" \
      | write_managed "$CF_CONF" 0644 root:root >/dev/null || true
  else
    write_managed "$CF_CONF" 0644 root:root <<CFYML >/dev/null || true
# Managed by portal/deploy/install_server.sh — the AURALIS tunnel ONLY.
# Any other cloudflared instance on this host is none of our business and is
# never read, written or restarted by us.
tunnel: $TUNNEL_ID
credentials-file: $CF_CRED
no-autoupdate: true

ingress:
  - hostname: $HOSTNAME_ING
    service: http://127.0.0.1:$PORT
  - service: http_status:404
CFYML
  fi
  ok "$CF_CONF -> $HOSTNAME_ING => http://127.0.0.1:$PORT"

  CFBIN="$(command -v cloudflared)"
  unit cloudflared-auralis.service <<CFUNIT
# Managed by portal/deploy/install_server.sh.
# Deliberately NOT named cloudflared.service: this host already runs another
# company's tunnel and that unit must never be touched.
[Unit]
Description=Cloudflare Tunnel (Auralis) $HOSTNAME_ING -> 127.0.0.1:$PORT
After=network-online.target auralis-portal.service
Wants=network-online.target

[Service]
Type=simple
User=$SVC_USER
Group=$SVC_GROUP
Environment=HOME=$HOME_DIR
# --no-autoupdate is mandatory here: an auto-update would replace the shared
# /usr/bin/cloudflared binary underneath the OTHER company's tunnel too.
ExecStart=$CFBIN --no-autoupdate --config $CF_CONF tunnel run
Restart=always
RestartSec=5
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
ProtectHome=yes
SyslogIdentifier=cloudflared-auralis

[Install]
WantedBy=multi-user.target
CFUNIT

  systemctl daemon-reload
  systemctl enable --quiet cloudflared-auralis.service || die 41 "could not enable cloudflared-auralis.service"
  systemctl restart cloudflared-auralis.service || die 41 "cloudflared-auralis.service failed to start — journalctl -u cloudflared-auralis -n 50"
  sleep 4
  systemctl is-active --quiet cloudflared-auralis.service || {
    journalctl -u cloudflared-auralis.service -n 30 --no-pager 2>/dev/null | sed -e 's/^/     /' >&2 || true
    die 41 "cloudflared-auralis.service did not stay up"
  }
  ok "cloudflared-auralis.service running (own instance, own config)"
fi

# =============================================================================
stage "12/12 verify"
# =============================================================================
VERIFY="$PORTAL_DIR/deploy/verify_server.sh"
verify_rc=0
if [ -f "$VERIFY" ]; then
  say "running $VERIFY as $SVC_USER"
  set +e
  as_svc env HOME="$HOME_DIR" AURALIS_PORT="$PORT" AURALIS_HOSTNAME="$HOSTNAME_ING" \
         AURALIS_ENV_FILE="$ENV_FILE" bash "$VERIFY"
  verify_rc=$?
  set -e
elif [ "$REQUIRE_VERIFY" -eq 1 ]; then
  die 40 "$VERIFY is missing and AURALIS_REQUIRE_VERIFY is set."
else
  warn "$VERIFY not present in this revision — post-install verification SKIPPED. Merge portal/deploy/verify_server.sh and re-run, or run it by hand."
fi

# ------------------------------------------------------------------ summary --
printf '\n%s================ AURALIS INSTALL SUMMARY ================%s\n' "$C_B" "$C_0"
printf '  code      %s @ %s (%s)\n' "$APP_DIR" "$BRANCH" "$(git_svc -C "$APP_DIR" rev-parse --short HEAD || true)"
printf '  data      %s (db %s · output_docs %s files)\n' "$DATA_DIR" \
       "$( [ -f "$DATA_DIR/auralis.db" ] && stat -c%s "$DATA_DIR/auralis.db" || echo 0 )B" \
       "$(find "$DATA_DIR/output_docs" -type f 2>/dev/null | wc -l || true)"
printf '  env       %s (0640 root:%s)\n' "$ENV_FILE" "$SVC_GROUP"
printf '  chromium  %s (PDF verified)\n' "$CHROME"
printf '  listen    http://127.0.0.1:%s   (loopback only)\n' "$PORT"
printf '  services  %s auralis-portal · %s update.timer · %s backup.timer\n' \
       "$(systemctl is-active auralis-portal.service || true)" \
       "$(systemctl is-active auralis-update.timer || true)" \
       "$(systemctl is-active auralis-backup.timer || true)"
if [ "$SKIP_TUNNEL" -eq 0 ] && [ -f "$CF_CONF" ]; then
  # a re-run without tunnel.json leaves TUNNEL_ID empty — read it back from the
  # installed config so the summary always names the tunnel actually in use
  shown_id="${TUNNEL_ID:-$(awk '/^tunnel:/ {print $2; exit}' "$CF_CONF" || true)}"
  printf '  tunnel    %s -> %s [%s]\n' "$HOSTNAME_ING" "$shown_id" "$(systemctl is-active cloudflared-auralis.service || true)"
else
  printf '  tunnel    NOT installed — %s still serves %s\n' "the Mac" "$HOSTNAME_ING"
fi
printf '  logs      journalctl -u auralis-portal -f\n'
if [ "${#WARNINGS[@]}" -gt 0 ]; then
  printf '\n%s  %d WARNING(S):%s\n' "$C_Y" "${#WARNINGS[@]}" "$C_0"
  for w in "${WARNINGS[@]}"; do printf '   ! %s\n' "$w"; done
fi
if [ "$verify_rc" -ne 0 ]; then
  printf '\n%s  verify_server.sh FAILED (exit %s) — propagating its exit code.%s\n' "$C_R" "$verify_rc" "$C_0"
  STAGE="verify"
  exit "$verify_rc"
fi
printf '\n%s  INSTALL COMPLETE.%s\n' "$C_G" "$C_0"
STAGE="done"
exit 0
