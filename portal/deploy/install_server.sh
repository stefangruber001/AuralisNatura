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
#      /run/auralis  /etc/cloudflared/auralis*  /etc/systemd/system/auralis-*
#      /etc/systemd/system/cloudflared-auralis.service
#      + a root-only scratch dir under root's home, removed on exit
#
#  WHAT IT DOES TO THE SHARED PACKAGE MANAGER — the honest version:
#    · It runs `apt-get update` (this refreshes the host's shared package lists)
#      and installs distro packages BY NAME only.
#    · Before every install it runs the SAME command with `-s` and ABORTS
#      (exit 20) if apt's own simulation would remove anything, or upgrade any
#      package that is already installed and was not asked for. The simulated
#      plan is printed, so it can be shown to the other owner.
#    · needrestart is suppressed (NEEDRESTART_SUSPEND / MODE=l) so installing a
#      library can never auto-restart the co-tenant's services mid-run.
#    · It NEVER adds an apt source, NEVER installs a vendor .deb through
#      dpkg/apt (Chrome and cloudflared are UNPACKED with `dpkg-deb -x` into
#      /opt/auralis, so no maintainer script runs, nothing is registered with
#      dpkg, no repo file and no root cron job are created, and the shared
#      /usr/bin/cloudflared the other tenant may be running is never replaced),
#      NEVER touches a firewall rule, and NEVER stops, restarts or removes a
#      unit it did not create.
#
#  It is INVOKED NON-INTERACTIVELY OVER SSH by portal/deploy/migrate_to_server.sh.
#  Re-running it is safe: every step is idempotent (see "IDEMPOTENCE" below).
#
# -----------------------------------------------------------------------------
#  CONTRACT — 1. ENVIRONMENT VARIABLES CONSUMED
# -----------------------------------------------------------------------------
#  REQUIRED
#    AURALIS_PAYLOAD_DIR   Absolute path of the directory the caller scp'd to
#                          this host (see section 2). Must exist, be root-owned
#                          and 0700 (we re-assert that). Expected location:
#                          /root/.auralis-payload — NEVER /tmp on a shared box.
#                          ⚠ IT IS SHREDDED ON EVERY TERMINAL OUTCOME EXCEPT
#                          EXIT 30 (the retryable deploy-key case). It carries
#                          the data key, the SMTP password and the Claude token;
#                          leaving it on another company's host between runs is
#                          not acceptable. THE CALLER MUST RE-SHIP THE FULL
#                          PAYLOAD BEFORE EVERY INSTALL RUN.
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
#                          (exit 33). A timestamped copy of the old file (+WAL)
#                          is put in /var/backups/auralis before anything is
#                          overwritten.
#    AURALIS_SKIP_DATA     Do not place auralis.db / clients.json / output_docs
#                          at all (code + service refresh only). Use this for a
#                          re-run that must not touch a live store.
#    AURALIS_SKIP_PACKAGES Assume python3/venv/git/curl/chromium/cloudflared are
#                          already installed; run no apt-get at all.
#    AURALIS_SKIP_TUNNEL   Install everything except cloudflared-auralis.service.
#    AURALIS_REQUIRE_VERIFY  Fail (exit 40) if deploy/verify_server.sh is absent,
#                          instead of only warning.
#    AURALIS_REQUIRE_CLAUDE_TOKEN  Fail (exit 15) if the env file carries no
#                          CLAUDE_CODE_OAUTH_TOKEN. Default: loud WARNING only —
#                          the report agent then silently degrades to "stub", so
#                          the warning is deliberately shouted, never whispered.
#    AURALIS_ALLOW_APT_CHANGES  Accept an apt plan that upgrades or removes
#                          packages this script did not ask for. OFF by default;
#                          only ever set it after agreeing the printed plan with
#                          the OTHER company that shares this host.
#    AURALIS_SKIP_HARDENED_PROBE  Run the chromium PDF probe as a plain process
#                          instead of inside a transient unit carrying the real
#                          service sandbox + memory limits. Only as a last
#                          resort: the hardened probe is what proves the limits
#                          in auralis-portal.service are not too tight.
#    AURALIS_VERIFY_PUBLIC  Force the final verify_server.sh run into (1) or out
#                          of (0) --public mode. Default: --public exactly when
#                          our own tunnel is up, i.e. after the cutover.
#    AURALIS_SKIP_CLAUDE_CLI  Do not install the Claude Code CLI for the service
#                          user. Only useful when it is already present by some
#                          other route; otherwise reports become offline stubs.
#    AURALIS_ALLOW_STUB    Accept a report agent that would fall back to the
#                          offline "stub" writer: verify_server.sh is then run
#                          with --allow-stub, which downgrades preflight/agent
#                          from a failure to a warning. Everything else still
#                          has to pass. Use it to get a host live while the CLI
#                          or its token is still being sorted out — never as a
#                          permanent setting, because stub reports are boiler-
#                          plate and must not reach a client.
#
#  OPTIONAL — escape hatches
#    AURALIS_MIN_FREE_MB   [3072] Minimum free MB required on /opt and /var.
#    AURALIS_CHROME        Absolute path to an already-present Chrome/Chromium.
#                          Skips chromium installation; still PDF-tested.
#    AURALIS_CHROME_DEB_URL  If no non-snap chromium can be installed from the
#                          distro, fetch this vendor .deb and UNPACK it into
#                          /opt/auralis/chrome (dpkg-deb -x — never dpkg -i, so
#                          no postinst runs and no apt source / root cron is
#                          added to this shared host). Official vendor URL only,
#                          e.g. https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
#                          Empty by default: we fail loudly rather than let
#                          lib/render.py silently fall back to writing .html.
#    AURALIS_MEM_HIGH [1G] AURALIS_MEM_MAX [1500M] AURALIS_CPU_QUOTA [150%]
#    AURALIS_TASKS_MAX [256]   Resource ceilings for auralis-portal.service.
#                          Headless chromium forks per render on a shared
#                          4 vCPU / 8 GB box; unbounded, the OOM killer can take
#                          the co-tenant's ERP down for an Auralis PDF.
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
#                        VALUE NORMALISATION (identical on the Mac and here, or
#                        a different Fernet key is derived and the store bricks):
#                        a UTF-8 BOM, a leading `export `, a trailing CR and
#                        surrounding whitespace are stripped, then exactly ONE
#                        matching pair of surrounding ' or " quotes. Nothing is
#                        expanded, and a value containing `$` or a backtick is
#                        REFUSED (exit 15) because shell-vs-systemd expansion
#                        would silently derive two different secrets.
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
#        missing a required key / carrying an unexpandable-by-contract value
#    16  another install (or the update timer) holds /run/auralis/install.lock
#    20  package installation failed, or apt's simulation showed it would touch
#        packages we did not ask for (see AURALIS_ALLOW_APT_CHANGES)
#    21  no usable Chromium (missing, or snap-only — a snap cannot read the
#        temp HTML lib/render.py writes, so the PDF would silently become .html)
#    22  Chromium found but FAILED the real end-to-end PDF render test
#    30  RETRYABLE: the deploy key is not authorised on GitHub yet. The public
#        key is printed and echoed as AURALIS_DEPLOY_KEY_PUB=<key>; add it as a
#        read-only Deploy Key and re-run this script unchanged. THIS is the one
#        exit that KEEPS the payload, so the re-run needs nothing re-shipped.
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
#      AURALIS_PAYLOAD_SHREDDED=1|0
#      AURALIS_INSTALL_RESULT=ok|failed
#      AURALIS_INSTALL_STAGE=<stage that ended the run>
#      AURALIS_INSTALL_EXIT=<code>
#      AURALIS_DEPLOY_KEY_PUB=<public key>      (only on exit 30)
#
# -----------------------------------------------------------------------------
#  IDEMPOTENCE, AND WHAT A FAILED RUN LEAVES BEHIND
# -----------------------------------------------------------------------------
#  Re-running changes nothing that is already correct: user/dirs are created only
#  when missing, units are compared byte-for-byte before being rewritten (so no
#  gratuitous restarts), the repo is fast-forwarded rather than re-cloned, and
#  data files are checksum-compared — identical payload = no-op, different
#  payload = refuse unless explicitly allowed. The one deliberate exception is
#  the app itself: it is restarted at the end so the freshly pulled code runs.
#
#  A run that FAILS never leaves the host armed:
#    · the periodic timers are enabled only after verify passes, and anything
#      this run enabled/started is disabled/stopped again on failure;
#    · the portal is stopped ONLY for the seconds it takes to swap the database,
#      and is started again from the exit handler if the run dies in between —
#      after the cutover, leaving it down behind a live tunnel means 502s;
#    · to remove the installation entirely: portal/deploy/uninstall_server.sh
#      (keeps the data unless --purge-data).
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
readonly HOLD_FILE="/etc/auralis/hold-updates"   # kill switch for the updater
readonly BACKUP_DIR="/var/backups/auralis"
readonly SSH_DIR="/opt/auralis/.ssh"
readonly SSH_KEY="/opt/auralis/.ssh/id_ed25519"
readonly KNOWN_HOSTS="/opt/auralis/.ssh/known_hosts"
readonly CF_DIR="/etc/cloudflared"
readonly CF_CONF="/etc/cloudflared/auralis.yml"
readonly UNIT_DIR="/etc/systemd/system"
readonly CHROME_DIR="/opt/auralis/chrome"        # UNPACKED vendor chrome, no dpkg
readonly CFBIN_DIR="/opt/auralis/cloudflared"    # UNPACKED cloudflared, no dpkg
readonly RUN_DIR="/run/auralis"                  # root-owned 0755, tmpfs
readonly LOCK_FILE="/run/auralis/install.lock"   # shared with update.sh
readonly PROBE_DIR="/run/auralis/probe"          # root-owned INPUTS for the probe
readonly PROBE_OUT="/var/lib/auralis/.probe"     # service-user WRITABLE output
# GitHub's published ed25519 host key — pinned so the first clone cannot be
# MITM'd and so ssh never needs to ask an interactive "yes/no" question.
readonly GH_HOSTKEY='github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl'
readonly TOTAL_STAGES=13

# ------------------------------------------------------------------ options --
PAYLOAD="${AURALIS_PAYLOAD_DIR:-}"
REPO_URL="${AURALIS_REPO_URL:-git@github.com:stefangruber001/AuralisNatura.git}"
BRANCH="${AURALIS_BRANCH:-main}"
PORT="${AURALIS_PORT:-5056}"
HOSTNAME_ING="${AURALIS_HOSTNAME:-api.auralisnatura.com}"
TUNNEL_ID="${AURALIS_TUNNEL_ID:-}"
MIN_FREE_MB="${AURALIS_MIN_FREE_MB:-3072}"
CHROME="${AURALIS_CHROME:-}"
CHROME_DEB_URL="${AURALIS_CHROME_DEB_URL:-}"
MEM_HIGH="${AURALIS_MEM_HIGH:-1G}"
MEM_MAX="${AURALIS_MEM_MAX:-1500M}"
CPU_QUOTA="${AURALIS_CPU_QUOTA:-150%}"
TASKS_MAX="${AURALIS_TASKS_MAX:-256}"

_flag() { case "${1:-0}" in 1|y|Y|yes|YES|true|TRUE|on|ON) return 0 ;; *) return 1 ;; esac; }
ALLOW_DB_OVERWRITE=0; _flag "${AURALIS_ALLOW_DB_OVERWRITE:-0}"     && ALLOW_DB_OVERWRITE=1
SKIP_DATA=0;          _flag "${AURALIS_SKIP_DATA:-0}"              && SKIP_DATA=1
SKIP_PACKAGES=0;      _flag "${AURALIS_SKIP_PACKAGES:-0}"          && SKIP_PACKAGES=1
SKIP_TUNNEL=0;        _flag "${AURALIS_SKIP_TUNNEL:-0}"            && SKIP_TUNNEL=1
REQUIRE_VERIFY=0;     _flag "${AURALIS_REQUIRE_VERIFY:-0}"         && REQUIRE_VERIFY=1
REQUIRE_TOKEN=0;      _flag "${AURALIS_REQUIRE_CLAUDE_TOKEN:-0}"   && REQUIRE_TOKEN=1
ALLOW_APT_CHANGES=0;  _flag "${AURALIS_ALLOW_APT_CHANGES:-0}"      && ALLOW_APT_CHANGES=1
SKIP_HARD_PROBE=0;    _flag "${AURALIS_SKIP_HARDENED_PROBE:-0}"    && SKIP_HARD_PROBE=1
SKIP_CLAUDE_CLI=0;    _flag "${AURALIS_SKIP_CLAUDE_CLI:-0}"        && SKIP_CLAUDE_CLI=1
ALLOW_STUB=0;         _flag "${AURALIS_ALLOW_STUB:-0}"             && ALLOW_STUB=1

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
ROOT_WORK=""           # root-only scratch (0700 root:root) — set in stage 1
CHROME_SOURCE="pre-existing"
PAYLOAD_SHREDDED=0

# --- state we may have to undo ------------------------------------------------
# Nothing here is cosmetic: on a shared host a failed run must not leave a root
# timer firing, a second tunnel connector alive, or the live site stopped.
REVERT_DISABLE=()      # units this run ENABLED that were not enabled before
REVERT_STOP=()         # units this run STARTED that were not active before
REVERT_START=()        # units this run STOPPED that must be running again
PORTAL_WAS_ACTIVE=0    # auralis-portal.service was serving when we arrived
PORTAL_STOPPED_BY_US=0

stage() { STAGE="$1"; printf '\n%s== %s ==%s\n' "$C_B" "$1" "$C_0"; }
say()   { printf '   %s\n' "$*"; }
ok()    { printf '   %s✓%s %s\n' "$C_G" "$C_0" "$*"; }
warn()  { printf '   %s!%s %s\n' "$C_Y" "$C_0" "$*"; WARNINGS+=("$*"); }
die()   { local c="$1"; shift; printf '\n%sFATAL [%s] %s%s\n' "$C_R" "$STAGE" "$*" "$C_0" >&2; exit "$c"; }

trap 'rc=$?; printf "\n%sUNEXPECTED ERROR%s stage=%s line=%s cmd=%s rc=%s\n" \
      "$C_R" "$C_0" "$STAGE" "$LINENO" "$BASH_COMMAND" "$rc" >&2; exit 99' ERR

finish() {
  local rc=$? u
  set +e; trap - ERR          # never let cleanup itself trip the traps

  if [ "$rc" -ne 0 ]; then
    # 1) Never leave the live site down. We stop the portal for a few seconds to
    #    swap the database; if the run dies anywhere after that, the tunnel is
    #    still up and every client gets a 502 until someone notices.
    if [ "$PORTAL_STOPPED_BY_US" -eq 1 ] && [ "$PORTAL_WAS_ACTIVE" -eq 1 ]; then
      if ! systemctl is-active --quiet auralis-portal.service 2>/dev/null; then
        printf '\n%s· restarting auralis-portal.service (it was running before this run)%s\n' "$C_Y" "$C_0" >&2
        systemctl start auralis-portal.service >/dev/null 2>&1 \
          || printf '%s!! COULD NOT RESTART auralis-portal.service — the site is DOWN. journalctl -u auralis-portal -n 50%s\n' "$C_R" "$C_0" >&2
      fi
    fi
    # 2) Undo only what THIS run turned on. A tunnel we started is stopped (the
    #    caller re-enables the Mac on failure — two connectors would split the
    #    traffic between two databases); timers we enabled are disabled (a root
    #    job polling GitHub every 2 minutes must not survive a failed install).
    #    Anything that was already on before we arrived is left exactly as it was.
    if [ "${#REVERT_STOP[@]}" -gt 0 ]; then
      for u in "${REVERT_STOP[@]}"; do
        # A unit that is ALSO in REVERT_START was running before this run began;
        # we paused it ourselves, so "started by this run" is not true of it and
        # stopping it here only to start it again three lines down is churn that
        # reads, in the log, like the handler contradicting itself.
        case " ${REVERT_START[*]-} " in *" $u "*) continue ;; esac
        systemctl stop "$u" >/dev/null 2>&1 && printf '   · stopped %s (started by this failed run)\n' "$u" >&2
      done
    fi
    if [ "${#REVERT_DISABLE[@]}" -gt 0 ]; then
      for u in "${REVERT_DISABLE[@]}"; do
        systemctl disable --quiet "$u" >/dev/null 2>&1 && printf '   · disabled %s (enabled by this failed run)\n' "$u" >&2
      done
    fi
    if [ "${#REVERT_START[@]}" -gt 0 ]; then
      for u in "${REVERT_START[@]}"; do
        systemctl start "$u" >/dev/null 2>&1 && printf '   · restarted %s (paused by this run)\n' "$u" >&2
      done
    fi
  fi

  # Scratch always goes. The payload goes too — on EVERY terminal outcome except
  # exit 30, which is the documented "add the deploy key and re-run unchanged"
  # case and is the only reason to leave secrets on another company's host.
  rm -rf "$ROOT_WORK" "$PROBE_DIR" "$PROBE_OUT" 2>/dev/null || true
  if [ "$rc" -ne 30 ] && [ -n "$PAYLOAD" ] && [ -d "$PAYLOAD" ]; then
    find "$PAYLOAD" -type f -exec shred -u -n 1 {} + 2>/dev/null || true
    rm -rf "$PAYLOAD" 2>/dev/null || true
    if [ -e "$PAYLOAD" ]; then
      printf '%s!! payload %s could NOT be removed — it holds the data key. Delete it by hand.%s\n' \
             "$C_R" "$PAYLOAD" "$C_0" >&2
    else
      PAYLOAD_SHREDDED=1
    fi
  fi

  printf '\nAURALIS_PAYLOAD_SHREDDED=%s\n' "$PAYLOAD_SHREDDED"
  printf 'AURALIS_INSTALL_RESULT=%s\n' "$([ "$rc" -eq 0 ] && echo ok || echo failed)"
  printf 'AURALIS_INSTALL_STAGE=%s\n' "$STAGE"
  printf 'AURALIS_INSTALL_EXIT=%s\n' "$rc"
  if [ -n "$DEPLOY_PUB" ] && [ "$rc" -eq 30 ]; then
    printf 'AURALIS_DEPLOY_KEY_PUB=%s\n' "$DEPLOY_PUB"
  fi
  return 0
}
trap finish EXIT

# ------------------------------------------------------------------ helpers --
have() { command -v "$1" >/dev/null 2>&1; }

# ONE way to drop privileges in the whole kit: runuser. No sudo anywhere — sudo
# on a shared host means a sudoers rule we would have to add and later remove.
# `su` is the fallback for the rare image that ships without runuser.
RUNAS_MODE="runuser"
as_svc() {
  if [ "$RUNAS_MODE" = "runuser" ]; then
    runuser -u "$SVC_USER" -- "$@"
  else
    su -s /bin/bash "$SVC_USER" -c "$(printf '%q ' "$@")"
  fi
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

# --- unit state changes, recorded so a failed run can undo exactly its own ----
unit_installed() { systemctl cat "$1" >/dev/null 2>&1; }

enable_unit() {  # enable_unit <unit...>
  local u pre
  for u in "$@"; do
    pre="$(systemctl is-enabled "$u" 2>/dev/null || true)"
    systemctl enable --quiet "$u" || return 1
    [ "$pre" = "enabled" ] || REVERT_DISABLE+=("$u")
  done
}
start_unit() {  # start_unit <unit...>
  local u pre
  for u in "$@"; do
    pre="$(systemctl is-active "$u" 2>/dev/null || true)"
    systemctl start "$u" || return 1
    [ "$pre" = "active" ] || REVERT_STOP+=("$u")
  done
}

# =============================================================================
stage "1/$TOTAL_STAGES preflight"
# =============================================================================
[ "$(id -u)" -eq 0 ] || die 10 "must run as root (got uid $(id -u))."
ok "running as root on $(hostname -f 2>/dev/null || hostname)"

[ -d /run/systemd/system ] && have systemctl || die 11 "systemd not detected — this installer only supports systemd hosts."
ok "systemd $(systemctl --version 2>/dev/null | head -1 | awk '{print $2}' || true)"

if have runuser; then
  RUNAS_MODE="runuser"
elif have su; then
  RUNAS_MODE="su"; warn "runuser is missing — falling back to 'su -s /bin/bash $SVC_USER -c'"
else
  die 12 "neither runuser nor su is available; there is no way to drop privileges."
fi

# --- the install lock -------------------------------------------------------
# auralis-update.timer fires every 2 minutes and does `git reset --hard` + pip +
# `systemctl restart` as root. Without a shared lock it can land in the middle of
# our own fetch (index.lock) or restart the portal while the database is being
# swapped. update.sh takes the SAME lock non-blockingly and skips its tick.
mkdir -p "$RUN_DIR"; chown root:root "$RUN_DIR"; chmod 0755 "$RUN_DIR"
if have flock; then
  exec 9>"$LOCK_FILE"
  flock -w 180 9 || die 16 "another install run (or auralis-update.service) has held $LOCK_FILE for over 3 minutes. Wait for it, or: systemctl stop auralis-update.timer"
  ok "install lock held ($LOCK_FILE)"
else
  warn "flock is not installed — cannot serialise against auralis-update.service"
fi
# Belt and braces: pause the updater for the duration of this run, and restart it
# from the exit handler if the run fails (a successful run re-arms it at the end).
if unit_installed auralis-update.timer && systemctl is-active --quiet auralis-update.timer 2>/dev/null; then
  systemctl stop auralis-update.timer >/dev/null 2>&1 || true
  REVERT_START+=("auralis-update.timer")
  say "auralis-update.timer paused for this run"
fi

DISTRO_ID="unknown"; DISTRO_VER=""
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release; DISTRO_ID="${ID:-unknown}"; DISTRO_VER="${VERSION_ID:-}"
fi
say "distro: $DISTRO_ID $DISTRO_VER · kernel $(uname -r) · arch $(uname -m)"
if [ "$SKIP_PACKAGES" -eq 0 ] && ! have apt-get; then
  die 12 "no apt-get. This installer only automates Debian/Ubuntu. Install python3, python3-venv, git, curl, chromium and cloudflared by hand, then re-run with AURALIS_SKIP_PACKAGES=1."
fi

# --- root-only scratch ------------------------------------------------------
# NOT under $DATA_DIR: that directory is owned by the unprivileged service user,
# who could rename it and swap a .deb or the normalised env file between the
# moment root writes it and the moment root reads it back. Root scratch belongs
# in a root-owned parent, full stop.
root_scratch_parent() {
  local h; h="$(getent passwd 0 2>/dev/null | cut -d: -f6)"; [ -n "$h" ] || h="/root"
  if [ -d "$h" ] && [ "$(stat -c '%u' "$h" 2>/dev/null || echo 1)" = "0" ] \
     && [ -z "$(find "$h" -maxdepth 0 -perm /022 2>/dev/null)" ]; then
    printf '%s\n' "$h"
  else
    printf '%s\n' "/var/tmp"      # sticky; a 0700 root dir inside it is still safe
  fi
}
ROOT_WORK="$(mktemp -d "$(root_scratch_parent)/.auralis-install.XXXXXX")"
chown root:root "$ROOT_WORK"; chmod 0700 "$ROOT_WORK"
say "scratch: $ROOT_WORK (0700 root:root, removed on exit)"

# --- payload ---------------------------------------------------------------
[ -n "$PAYLOAD" ] || die 15 "AURALIS_PAYLOAD_DIR is not set (see the contract at the top of this file)."
if [ ! -d "$PAYLOAD" ]; then
  die 15 "payload directory $PAYLOAD does not exist.
   NOTE: this installer SHREDS the payload on every terminal outcome except
   exit 30 — it holds the data key and this host belongs to someone else too.
   The caller must re-ship the complete payload before EVERY install run."
fi
[ -f "$PAYLOAD/portal.env" ] || die 15 "payload is missing the REQUIRED file portal.env."
case "$PAYLOAD" in
  /tmp/*) warn "the payload sits under /tmp on a host shared with another company. /root/.auralis-payload is the documented location." ;;
esac
# Self-heal the permissions rather than trust the transfer: secrets sitting in a
# world-traversable directory are a GDPR problem, not a style problem.
chown -R root:root "$PAYLOAD" 2>/dev/null || true
chmod 0700 "$PAYLOAD" 2>/dev/null || true
find "$PAYLOAD" -type f -exec chmod 0600 {} + 2>/dev/null || true
ok "payload $PAYLOAD ($(find "$PAYLOAD" -maxdepth 1 -type f 2>/dev/null | wc -l || true) files, 0700 root:root)"

# --- port 5056 -------------------------------------------------------------
# History: a stale process kept the port and answered with the WRONG data while
# every fresh start silently failed to bind. On a shared host we must never kill
# a listener we do not own — so: identify, and abort if it is not ours.
port_pid=""
port_busy=0
if have ss; then
  port_pid="$(ss -H -ltnp 2>/dev/null | awk -v p="$PORT" '$4 ~ ("[:.]" p "$")' \
              | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | sed -n '1p' || true)"
  # NB: no `| grep -q .` here. grep -q exits at the first match, and under
  # `set -o pipefail` a SIGPIPE'd awk (141) would make the pipeline "fail" and
  # report a BUSY port as free — i.e. silently skip the foreign-listener guard.
  # A command substitution has no such hazard.
  [ -z "$(ss -H -ltn 2>/dev/null | awk -v p="$PORT" '$4 ~ ("[:.]" p "$")')" ] || port_busy=1
elif have lsof; then
  port_pid="$(lsof -ti "tcp:$PORT" -sTCP:LISTEN 2>/dev/null | sed -n '1p' || true)"
  [ -z "$port_pid" ] || port_busy=1
else
  # last resort: try to connect
  if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then port_busy=1; exec 3>&- 3<&-; fi
fi
if [ "$port_busy" -eq 1 ]; then
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

# --- remember how we found our own service ----------------------------------
if unit_installed auralis-portal.service && systemctl is-active --quiet auralis-portal.service 2>/dev/null; then
  PORTAL_WAS_ACTIVE=1
  say "auralis-portal.service is currently ACTIVE — this host may be serving clients right now"
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
# The floor is deliberately above the chromium tree + one backup tarball: this
# filesystem is also canei-erp's, and filling it is an outage for both of us.
for p in /opt /var/lib /var/backups; do
  a="$(avail_mb "$p" || true)"; [ -n "$a" ] || continue
  say "free on $p: ${a} MB"
  [ "$a" -ge "$MIN_FREE_MB" ] || die 14 "only ${a} MB free on $p, need ${MIN_FREE_MB} MB (AURALIS_MIN_FREE_MB)."
done
ok "disk ok"

# =============================================================================
stage "2/$TOTAL_STAGES user, group and directory tree"
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
         "$DATA_DIR/backups" "$PROBE_OUT" "$ETC_DIR" "$BACKUP_DIR"
chown "$SVC_USER:$SVC_GROUP" "$HOME_DIR" "$APP_DIR" "$SSH_DIR" "$DATA_DIR" \
      "$DATA_DIR/output_docs" "$DATA_DIR/backups" "$PROBE_OUT" "$BACKUP_DIR"
# output_docs holds the worst-case content in this whole system — rendered report
# PDFs, .eml copies of every mail, booking .ics. It is 0750 like every other data
# directory; 0755 here was one `chmod 755 /var/lib/auralis` away from publishing
# special-category health data to every account on a shared box.
chmod 0750 "$HOME_DIR" "$DATA_DIR" "$DATA_DIR/output_docs" "$DATA_DIR/backups" "$BACKUP_DIR"
chmod 0755 "$APP_DIR"
chmod 0700 "$SSH_DIR" "$PROBE_OUT"
chown root:"$SVC_GROUP" "$ETC_DIR"; chmod 0750 "$ETC_DIR"
# Root-owned inputs the service user must READ (probe HTML, keycheck.py). Root
# must never write into a directory the service user owns — a symlink planted
# there turns `cat > file` into "root truncates any file on the box".
mkdir -p "$PROBE_DIR"; chown root:root "$PROBE_DIR"; chmod 0755 "$PROBE_DIR"
# /etc/cloudflared: created 0755 when absent. Under `umask 027` a bare mkdir -p
# yields 0750 root:root, which the unprivileged cloudflared-auralis.service
# cannot traverse — it would die inside the start window at the worst possible
# moment (mid-cutover). A pre-existing directory (the other tenant's) is LEFT
# EXACTLY AS IT IS.
if [ ! -d "$CF_DIR" ]; then
  install -d -m 0755 -o root -g root "$CF_DIR"
  say "$CF_DIR created 0755 (traversable by the service user)"
fi
ok "tree ready: $HOME_DIR · $DATA_DIR · $ETC_DIR · $BACKUP_DIR"

# =============================================================================
stage "3/$TOTAL_STAGES packages"
# =============================================================================
# --no-remove: apt aborts instead of silently removing a co-tenant package to
# satisfy a conflict. needrestart's apt hook treats DEBIAN_FRONTEND=noninteractive
# as "restart services automatically" — on this host that would bounce the other
# company's app servers and database in the middle of their working day, so it is
# suspended and downgraded to list-only.
APT_OPTS=(-y --no-remove -o Dpkg::Options::=--force-confold -o Dpkg::Options::=--force-confdef)
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_SUSPEND=1
export NEEDRESTART_MODE=l
export APT_LISTCHANGES_FRONTEND=none
apt_update_done=0

apt_refresh() {
  [ "$apt_update_done" -eq 0 ] || return 0
  apt_update_done=1
  # This refreshes the SHARED package lists. Unavoidable before any install, but
  # a partial failure (a broken third-party repo of the other tenant) must be
  # reported, not swallowed.
  if ! apt-get update -qq >"$ROOT_WORK/apt-update.log" 2>&1; then
    warn "apt-get update did not fully succeed — continuing with the cached lists ($(tr '\n' ' ' <"$ROOT_WORK/apt-update.log" | cut -c1-160))"
  fi
}

apt_gate() {  # apt_gate <pkg...> — refuse a plan that touches anything else
  local sim="$ROOT_WORK/apt-sim.txt" rc=0 want=" $* " bad
  apt-get install "${APT_OPTS[@]}" -s "$@" >"$sim" 2>&1 || rc=$?
  if [ "$rc" -ne 0 ]; then
    sed -e 's/^/     apt: /' "$sim" | tail -25 >&2 || true
    die 20 "apt-get could not even SIMULATE installing: $* (see the apt output above)."
  fi
  say "apt plan for: $*"
  grep -E '^(Inst|Remv|Purg) ' "$sim" | sed -e 's/^/     · /' || say "     · (nothing to do)"
  # `Inst pkg [1.2-3] (1.2-4 …)` = an UPGRADE of an installed package.
  # `Inst pkg (1.2-4 …)`         = a brand-new package. Only the latter is ours
  # to make, plus upgrades of the packages we explicitly asked for.
  bad="$(awk -v want="$want" '
    /^(Remv|Purg) / { printf "  removes  %s\n", $2; next }
    /^Inst /        { if ($3 ~ /^\[/ && index(want, " " $2 " ") == 0) printf "  upgrades %s\n", $2 }
  ' "$sim")"
  if [ -n "$bad" ]; then
    printf '%s\n' "$bad" >&2
    if [ "$ALLOW_APT_CHANGES" -eq 1 ]; then
      warn "apt would change packages we did not ask for (listed above) — accepted because AURALIS_ALLOW_APT_CHANGES=1"
    else
      die 20 "REFUSING this apt plan: it would remove or upgrade packages that belong to the rest of this host (listed above).
   This box runs another company's production ERP. Either install what is missing
   by hand at a time you agreed with them and re-run with AURALIS_SKIP_PACKAGES=1,
   or — having read the plan above — re-run with AURALIS_ALLOW_APT_CHANGES=1."
    fi
  fi
}

apt_install() {  # install ONLY the named packages (never a local .deb path)
  [ "$#" -gt 0 ] || return 0
  apt_refresh
  apt_gate "$@"
  apt-get install "${APT_OPTS[@]}" "$@"
}

pkg_installed() { dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q "ok installed"; }

if [ "$SKIP_PACKAGES" -eq 1 ]; then
  warn "AURALIS_SKIP_PACKAGES set — no apt-get will run"
else
  missing=()
  for p in python3 python3-venv git curl ca-certificates fonts-liberation; do
    pkg_installed "$p" || missing+=("$p")
  done
  if [ "${#missing[@]}" -gt 0 ]; then
    say "installing: ${missing[*]}"
    apt_install "${missing[@]}" || die 20 "apt-get install failed for: ${missing[*]}"
  fi
  ok "base packages present ($(python3 -V 2>&1), $(git --version))"
fi

# --- chromium: a REAL deb binary, never a snap, never a dpkg-registered vendor
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
extracted_chrome() {  # a chrome we unpacked on an earlier run
  [ -d "$CHROME_DIR" ] || return 1
  find "$CHROME_DIR" -maxdepth 6 -type f -perm -u+x \
       \( -name chrome -o -name chromium -o -name chromium-browser \) 2>/dev/null | sort | sed -n '1p'
}
find_chrome() {
  local c
  for c in "$CHROME" "$(extracted_chrome || true)" \
           /usr/bin/chromium /usr/lib/chromium/chromium /usr/bin/chromium-browser \
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
is_snap_package() {  # would `apt-get install $1` actually install the snap?
  local info
  info="$(apt-cache show "$1" 2>/dev/null || true)"
  [ -n "$info" ] || return 1
  printf '%s' "$info" | grep -qiE '^Depends:.*(^|[ ,])snapd|transitional.*snap|snap.*transitional' && return 0
  printf '%s' "$info" | grep -qi 'this is a transitional package' \
    && printf '%s' "$info" | grep -qi 'snap' && return 0
  return 1
}
unpack_deb() {  # unpack_deb <url> <destdir> — NEVER dpkg -i: no postinst, no apt
  local url="$1" dest="$2" deb="$ROOT_WORK/$(basename "$dest").deb"
  # Downloaded into the ROOT-ONLY scratch dir on purpose: a .deb that lands in a
  # directory the service user owns can be swapped between download and use.
  curl -fsSL --proto '=https' --tlsv1.2 --max-time 300 -o "$deb" "$url" || return 1
  have dpkg-deb || return 1
  rm -rf "$dest"; install -d -m 0755 -o root -g root "$dest"
  dpkg-deb -x "$deb" "$dest" || return 1
  chown -R root:root "$dest"
  printf '%s\n' "$deb"
}
chrome_deb_deps() {  # the .deb's own Depends, as bare package names
  local deb="$1"
  dpkg-deb -f "$deb" Depends 2>/dev/null | tr ',' '\n' \
    | sed -e 's/|.*//' -e 's/([^)]*)//g' -e 's/[[:space:]]//g' \
    | grep -E '^[a-z0-9][a-z0-9+.-]+$' || true
}

if [ -n "$CHROME" ] && [ -x "$CHROME" ] && ! is_snap_binary "$CHROME"; then
  ok "using AURALIS_CHROME=$CHROME"
  CHROME_SOURCE="AURALIS_CHROME"
elif CHROME="$(find_chrome)"; then
  ok "chromium already installed: $CHROME"
  case "$CHROME" in "$CHROME_DIR"/*) CHROME_SOURCE="unpacked vendor .deb (earlier run)" ;; *) CHROME_SOURCE="distro package" ;; esac
elif [ "$SKIP_PACKAGES" -eq 1 ]; then
  die 21 "no usable Chromium found and AURALIS_SKIP_PACKAGES is set."
else
  for pkg in chromium chromium-browser; do
    apt-cache show "$pkg" >/dev/null 2>&1 || continue
    if is_snap_package "$pkg"; then
      say "$pkg on $DISTRO_ID $DISTRO_VER is only the transitional package for the chromium SNAP — skipping it (installing it would pull snapd onto a host that does not have it, and the snap cannot read the temp HTML render.py writes)"
      continue
    fi
    say "installing $pkg"
    apt_install "$pkg" || true
    CHROME="$(find_chrome || true)"
    if [ -n "$CHROME" ]; then CHROME_SOURCE="distro package"; break; fi
  done
  if [ -z "$CHROME" ] && [ -n "$CHROME_DEB_URL" ]; then
    # UNPACK, do not install. google-chrome-stable's postinst writes
    # /etc/apt/sources.list.d/google-chrome.list plus a signing key AND
    # /etc/cron.daily/google-chrome, which re-adds that repo as root every day —
    # permanently reconfiguring the package manager of a machine that is not only
    # ours. `dpkg-deb -x` runs no maintainer script and registers nothing.
    say "unpacking AURALIS_CHROME_DEB_URL into $CHROME_DIR (dpkg-deb -x — nothing is registered with dpkg/apt)"
    deb_path="$(unpack_deb "$CHROME_DEB_URL" "$CHROME_DIR")" \
      || die 21 "could not download/unpack $CHROME_DEB_URL"
    CHROME="$(extracted_chrome || true)"
    [ -n "$CHROME" ] || die 21 "no chrome/chromium binary inside $CHROME_DEB_URL (looked under $CHROME_DIR)."
    CHROME_SOURCE="unpacked vendor .deb"
    # An unpacked .deb brings no dependencies with it. Resolve only what is
    # genuinely missing, and let apt_gate refuse the plan if satisfying them
    # would disturb the rest of the host.
    missing_libs="$(ldd "$CHROME" 2>/dev/null | awk '/not found/ {print $1}' | sort -u | tr '\n' ' ')"
    if [ -n "$missing_libs" ]; then
      say "unpacked chrome is missing shared libraries: $missing_libs"
      deps=()
      while read -r d; do
        [ -n "$d" ] || continue
        pkg_installed "$d" || deps+=("$d")
      done < <(chrome_deb_deps "$deb_path")
      if [ "${#deps[@]}" -gt 0 ]; then
        say "installing the .deb's declared dependencies: ${deps[*]}"
        apt_install "${deps[@]}" || die 21 "could not install chrome's dependencies: ${deps[*]}"
      fi
      missing_libs="$(ldd "$CHROME" 2>/dev/null | awk '/not found/ {print $1}' | sort -u | tr '\n' ' ')"
      [ -z "$missing_libs" ] || die 21 "the unpacked chrome still cannot resolve: $missing_libs
   Install those libraries by hand (at a time agreed with the other tenant) and
   re-run with AURALIS_CHROME=$CHROME."
    fi
  fi
  [ -n "$CHROME" ] || die 21 "no non-snap Chromium available on $DISTRO_ID $DISTRO_VER.
   A snap build cannot read the temp HTML that lib/render.py writes, so the
   12-page report PDF would silently degrade to .html. Fix one of:
     · apt-get install -y chromium            (Debian, and Ubuntu with a deb source)
     · re-run with AURALIS_CHROME_DEB_URL=https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
       (it is UNPACKED into $CHROME_DIR, never installed through dpkg)
     · install Chrome/Chromium yourself and re-run with AURALIS_CHROME=/abs/path"
  ok "chromium ready: $CHROME [$CHROME_SOURCE]"
fi

# --- cloudflared: official vendor .deb, UNPACKED, NOT an apt source ----------
# Deliberately NOT adding pkg.cloudflare.com to /etc/apt/sources.list.d, and
# deliberately not `dpkg -i` either: installing the vendor package would write
# /usr/bin/cloudflared — the very binary the OTHER company's tunnel runs. We keep
# our copy under /opt/auralis and point only our own unit at it.
CFBIN=""
if [ "$SKIP_TUNNEL" -eq 1 ]; then
  warn "AURALIS_SKIP_TUNNEL set — cloudflared not installed/configured"
else
  if [ -x "$CFBIN_DIR/usr/bin/cloudflared" ]; then
    CFBIN="$CFBIN_DIR/usr/bin/cloudflared"
  elif have cloudflared; then
    CFBIN="$(command -v cloudflared)"     # the host already has one: reuse, never replace
  fi
  if [ -n "$CFBIN" ]; then
    ok "cloudflared present: $CFBIN ($("$CFBIN" --version 2>/dev/null | head -1 || true))"
  elif [ "$SKIP_PACKAGES" -eq 1 ]; then
    die 41 "cloudflared missing and AURALIS_SKIP_PACKAGES is set."
  else
    arch="$(dpkg --print-architecture)"
    case "$arch" in amd64|arm64|armhf|386) : ;; *) die 41 "unsupported architecture $arch for the cloudflared release deb." ;; esac
    url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${arch}.deb"
    say "downloading cloudflared ($arch) from Cloudflare's official release and unpacking it into $CFBIN_DIR"
    unpack_deb "$url" "$CFBIN_DIR" >/dev/null || die 41 "download/unpack failed: $url"
    CFBIN="$(find "$CFBIN_DIR" -maxdepth 4 -type f -name cloudflared -perm -u+x 2>/dev/null | sort | sed -n '1p')"
    [ -n "$CFBIN" ] || die 41 "no cloudflared binary inside the release .deb"
    ok "cloudflared unpacked: $CFBIN ($("$CFBIN" --version 2>/dev/null | head -1 || true))"
  fi
fi

# =============================================================================
stage "4/$TOTAL_STAGES chromium PDF render test"
# =============================================================================
# Deliberately BEFORE the data placement: this probe can take two minutes, and
# stage 8 stops the portal. Every second spent here used to be a second of 502s
# for live clients after the cutover.
#
# Not `--version`: the exact command line lib/render.py runs, end to end, and the
# output is checked for a real %PDF header. This is the only way to catch the
# silent .html fallback before a client receives the wrong file.
#
# The renderer is confined the same way auralis-portal.service will confine it
# (same sandbox, same MemoryMax/TasksMax), so a ceiling that is too tight fails
# HERE and not on a client's report at 23:00.
PORTAL_HARDENING=(
  "NoNewPrivileges=true"
  "PrivateTmp=true"
  "ProtectSystem=strict"
  "ProtectHome=true"
  "ProtectKernelTunables=true"
  "ProtectKernelModules=true"
  "ProtectControlGroups=true"
  "ProtectProc=invisible"
  "RestrictSUIDSGID=true"
  "RestrictRealtime=true"
  "LockPersonality=true"
  "SystemCallArchitectures=native"
  # ProtectSystem=strict makes the WHOLE hierarchy read-only, which is what makes
  # the next line mean something. With the old ProtectSystem=full, /var/lib/canei*
  # and /srv stayed writable and ReadWritePaths restricted nothing at all.
  "ReadWritePaths=$DATA_DIR $BACKUP_DIR $HOME_DIR"
  "MemoryHigh=$MEM_HIGH"
  "MemoryMax=$MEM_MAX"
  "CPUQuota=$CPU_QUOTA"
  "CPUWeight=50"
  "TasksMax=$TASKS_MAX"
  "LimitNOFILE=8192"
)
# NOT included, on purpose: RestrictNamespaces and PrivateDevices. Headless
# chromium is the fragile part of this service and both have historically broken
# it; if you add them, the probe below is what must prove they are safe.

# ── the co-tenant separation tier ────────────────────────────────────────────
# Requested explicitly: the two companies must be as separated as one kernel
# allows. These are the properties that turn "cannot damage canei" into "cannot
# SEE canei", which is the distinction that matters for confidentiality rather
# than for uptime. They are kept in a SEPARATE array because any of them could
# break headless chromium, and the render probe below decides empirically:
# strictest set first, and on failure we drop to the base set and say so. The
# result is the tightest sandbox that demonstrably still renders a report.
#
# Identify what the co-tenant owns so we can make it invisible. Targeted on
# purpose: blanket-blocking /var/lib/* would also hide dpkg and systemd state.
# The `-` prefix means "ignore if this path does not exist".
cotenant_paths() {
  local d out=""
  for d in /srv/* /var/www/*; do
    [ -d "$d" ] || continue
    case "$d" in "$DATA_DIR"|"$HOME_DIR"|"$BACKUP_DIR") continue ;; esac
    out="$out -$d"
  done
  for d in /opt/*canei* /var/lib/*canei* /srv/*canei* /home/*canei*; do
    [ -e "$d" ] || continue
    out="$out -$d"
  done
  # /srv/canei* matches both loops — dedupe so the unit file stays readable.
  printf '%s' "$(printf '%s\n' $out | awk '!seen[$0]++' | tr '\n' ' ' | sed 's/ $//')"
}
CO_PATHS="$(cotenant_paths)"
PORTAL_HARDENING_STRICT=(
  # /proc shows only OUR processes. Without this the auralis user can `ps aux`
  # and read canei's full command lines — which is where database URLs and API
  # tokens habitually leak. ProtectProc hides the process dirs; ProcSubset drops
  # the rest of /proc's global files as well.
  "ProcSubset=pid"
  # The service needs no capabilities whatsoever. An empty bounding set means a
  # compromised portal cannot regain any, even via a setuid binary.
  "CapabilityBoundingSet="
  "PrivateDevices=true"
  "ProtectHostname=true"
  "ProtectClock=true"
  "RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX"
  "SystemCallFilter=@system-service"
  "SystemCallFilter=~@privileged @resources @obsolete"
  # Anything this service creates is unreadable to every other account on the
  # box, including canei's, regardless of the directory's own mode.
  "UMask=0077"
)
# NB: an `if`, not `[ … ] && …` — under `set -e` the short-circuit form exits the
# whole script with 99 on a host that happens to have no co-tenant directories.
if [ -n "$CO_PATHS" ]; then PORTAL_HARDENING_STRICT+=("InaccessiblePaths=$CO_PATHS"); fi

# Try strict; the probe demotes us if chromium disagrees.
PORTAL_HARDENING_BASE=("${PORTAL_HARDENING[@]}")
PORTAL_HARDENING=("${PORTAL_HARDENING_BASE[@]}" "${PORTAL_HARDENING_STRICT[@]}")
SEPARATION_TIER="strict"

cat > "$PROBE_DIR/render-probe.html" <<'HTML'
<!doctype html><html><head><meta charset="utf-8"><title>Auralis render probe</title>
<style>@page{size:A4;margin:0}body{font-family:serif;padding:40mm}h1{color:#3D2719}</style>
</head><body><h1>Auralis Natura — render probe</h1><p>If this became a PDF, the
12-page report will render too.</p></body></html>
HTML
chmod 0644 "$PROBE_DIR/render-probe.html"
PROBE_PDF="$PROBE_OUT/render-probe.pdf"

HARDENED_PROBE=0
if [ "$SKIP_HARD_PROBE" -eq 0 ] && have systemd-run; then
  if systemd-run --quiet --wait --collect --pipe -p PrivateTmp=yes \
       -p User="$SVC_USER" -p Group="$SVC_GROUP" -- /bin/true >/dev/null 2>&1; then
    HARDENED_PROBE=1
  else
    warn "systemd-run cannot start transient units here — the PDF probe will NOT exercise the service sandbox"
  fi
fi

run_probe() {  # run_probe <hardened 0|1> — leaves the log in $ROOT_WORK/chrome.log
  local hardened="$1" rc=0 props=() p
  rm -f "$PROBE_PDF"
  if [ "$hardened" -eq 1 ]; then
    for p in "${PORTAL_HARDENING[@]}"; do props+=(-p "$p"); done
    systemd-run --quiet --wait --collect --pipe \
      --unit="auralis-render-probe-$$" \
      -p User="$SVC_USER" -p Group="$SVC_GROUP" \
      -p "Environment=HOME=$HOME_DIR" -p "WorkingDirectory=$HOME_DIR" \
      -p RuntimeMaxSec=150 "${props[@]}" \
      -- "$CHROME" --headless --disable-gpu --no-sandbox --no-pdf-header-footer \
         "--print-to-pdf=$PROBE_PDF" "file://$PROBE_DIR/render-probe.html" \
      >"$ROOT_WORK/chrome.log" 2>&1 || rc=$?
  else
    as_svc env HOME="$HOME_DIR" timeout 150 "$CHROME" --headless --disable-gpu \
      --no-sandbox --no-pdf-header-footer "--print-to-pdf=$PROBE_PDF" \
      "file://$PROBE_DIR/render-probe.html" >"$ROOT_WORK/chrome.log" 2>&1 || rc=$?
  fi
  # A symlink here would be the service user redirecting root's 5-byte read.
  if [ "$rc" -eq 0 ]; then
    if [ -L "$PROBE_PDF" ] || [ ! -s "$PROBE_PDF" ] \
       || [ "$(LC_ALL=C head -c 5 "$PROBE_PDF" 2>/dev/null || true)" != "%PDF-" ]; then
      rc=90
    fi
  fi
  return "$rc"
}

probe_rc=0
run_probe "$HARDENED_PROBE" || probe_rc=$?

# Demote before despairing. A failure here most likely means one of the strict
# co-tenant properties (SystemCallFilter and PrivateDevices are the usual
# suspects) disagrees with headless chromium — not that chromium is broken. Retry
# on the base set: if that renders, we ship the base set and say plainly that the
# strongest separation was not achievable, rather than either failing the install
# or silently shipping a service whose reports degrade to .html.
if [ "$probe_rc" -ne 0 ] && [ "$HARDENED_PROBE" -eq 1 ] && [ "$SEPARATION_TIER" = "strict" ]; then
  warn "the strict co-tenant sandbox stopped chromium rendering — retrying with the base sandbox"
  PORTAL_HARDENING=("${PORTAL_HARDENING_BASE[@]}")
  SEPARATION_TIER="base"
  probe_rc=0
  run_probe "$HARDENED_PROBE" || probe_rc=$?
  if [ "$probe_rc" -eq 0 ]; then
    warn "separation tier: BASE (strict was rejected by chromium)."
    warn "  You still get: a separate user, ProtectSystem=strict, ProtectProc=invisible,"
    warn "  ReadWritePaths confined to Auralis, and the memory/CPU/task ceilings."
    warn "  You do NOT get: seccomp filtering, an empty capability set, or"
    warn "  InaccessiblePaths over the co-tenant's directories."
    warn "  The failing chromium log is above; fixing it and re-running restores strict."
  fi
fi

if [ "$probe_rc" -ne 0 ] && [ "$HARDENED_PROBE" -eq 1 ]; then
  # Distinguish "chromium is broken" from "our sandbox/limits break chromium" —
  # the operator needs to know WHICH, and only one of them is our bug.
  sed -e 's/^/     chrome(sandboxed): /' "$ROOT_WORK/chrome.log" | tail -20 >&2 || true
  plain_rc=0
  run_probe 0 || plain_rc=$?
  if [ "$plain_rc" -eq 0 ]; then
    die 22 "chromium renders a PDF as $SVC_USER but FAILS inside the auralis-portal.service sandbox.
   Shipping this would mean every client report silently degrades to .html.
   The ceilings are: MemoryHigh=$MEM_HIGH MemoryMax=$MEM_MAX CPUQuota=$CPU_QUOTA TasksMax=$TASKS_MAX
   Raise them (AURALIS_MEM_MAX=2G …) and re-run, or — accepting that runtime
   rendering may fail — re-run with AURALIS_SKIP_HARDENED_PROBE=1."
  fi
  probe_rc="$plain_rc"
fi
if [ "$probe_rc" -ne 0 ]; then
  sed -e 's/^/     chrome: /' "$ROOT_WORK/chrome.log" | tail -20 >&2 || true
  [ "$probe_rc" -eq 90 ] \
    && die 22 "chromium produced no valid PDF — lib/render.py would silently write .html instead of the 12-page report." \
    || die 22 "chromium exited $probe_rc on the render probe ($CHROME)."
fi
ok "PDF render verified ($(stat -c%s "$PROBE_PDF") bytes) via $CHROME$([ "$HARDENED_PROBE" -eq 1 ] && printf ' — inside the real service sandbox + limits' || printf ' (UNSANDBOXED probe)')"

# =============================================================================
stage "5/$TOTAL_STAGES deploy key and repository"
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
ls_err="$ROOT_WORK/ls-remote.err"
if ! git_svc ls-remote --heads "$REPO_URL" >/dev/null 2>"$ls_err"; then
  if grep -qiE 'permission denied|could not read from remote|repository not found|access rights' "$ls_err"; then
    printf '\n%s%s%s\n' "$C_Y" "GitHub has not authorised this server's deploy key yet." "$C_0" >&2
    printf '\nAdd it as a READ-ONLY Deploy Key:\n' >&2
    printf '  1. https://github.com/stefangruber001/AuralisNatura/settings/keys/new\n' >&2
    printf '  2. Title: "Hetzner auralis portal"   Allow write access: NO\n' >&2
    printf '  3. Paste exactly this line:\n\n' >&2
    # `--` ends option parsing: without it printf reads the leading dashes of
    # the marker as an option cluster and aborts — which killed a live install
    # at exactly the moment it was printing the key the operator needed.
    printf -- '----- BEGIN DEPLOY KEY -----\n%s\n----- END DEPLOY KEY -----\n\n' "$DEPLOY_PUB" >&2
    printf '  4. Re-run this installer unchanged — it will continue from here.\n' >&2
    printf '     (this is the ONE exit that keeps the payload, so nothing has to be re-shipped)\n' >&2
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
stage "6/$TOTAL_STAGES virtualenv, python deps and the Claude CLI"
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

# ------------------------------------------------------------- claude CLI --
# lib/agent.py chooses the real report writer only when BOTH the config says
# claude_cli AND shutil.which("claude") resolves. A token with no binary to use
# it is still the offline "stub" writer — and the fallback is silent, so the
# first sign would be a client receiving boiler-plate. The binary is therefore
# part of the install, not something to add by hand afterwards.
#
# Installed per-user under $HOME_DIR/.local/bin, which the unit's PATH already
# names. Deliberately NOT via apt or npm: this box is canei-erp's production
# host, and neither a new apt source nor a global node toolchain belongs on it.
CLAUDE_BIN="$HOME_DIR/.local/bin/claude"
claude_version() { as_svc env HOME="$HOME_DIR" "$CLAUDE_BIN" --version 2>/dev/null | head -1 || true; }
if [ "$SKIP_CLAUDE_CLI" -eq 1 ]; then
  warn "AURALIS_SKIP_CLAUDE_CLI is set — not installing the Claude CLI. Reports will be the offline stub unless a `claude` is already on the service user's PATH."
elif [ -x "$CLAUDE_BIN" ]; then
  ok "claude CLI present: $CLAUDE_BIN $(claude_version)"
else
  say "installing the Claude Code CLI for $SVC_USER (native installer, no root-owned files outside $HOME_DIR)"
  ci_src="$ROOT_WORK/claude-install.sh"
  ci_dst="$HOME_DIR/.cache/claude-install.sh"
  ci_log="$ROOT_WORK/claude-install.log"
  ci_ok=0
  if curl -fsSL --retry 2 --max-time 90 https://claude.ai/install.sh -o "$ci_src" 2>"$ci_log" && [ -s "$ci_src" ]; then
    # ROOT_WORK is 0700 root:root, so hand the script over through a path the
    # service user can actually read; it is removed again either way.
    as_svc mkdir -p "$HOME_DIR/.cache"
    install -m 0700 -o "$SVC_USER" -g "$SVC_GROUP" "$ci_src" "$ci_dst"
    # `|| ci_rc=$?`, NOT `set +e`. With `set -E` the ERR trap is inherited into
    # shell functions and fires there even with errexit off, so `set +e` around
    # a call to as_svc() does NOT stop a non-zero exit from killing this script.
    # Only being the left side of an ||-list suppresses the trap. (See the same
    # note in verify_server.sh — and stage 13, where it really did bite.)
    ci_rc=0
    as_svc env HOME="$HOME_DIR" \
               PATH="$HOME_DIR/.local/bin:/usr/local/bin:/usr/bin:/bin" \
               bash "$ci_dst" >>"$ci_log" 2>&1 || ci_rc=$?
    rm -f "$ci_dst"
    if [ "$ci_rc" -eq 0 ] && [ -x "$CLAUDE_BIN" ]; then ci_ok=1; fi
  else
    ci_rc="curl"
  fi
  if [ "$ci_ok" -eq 1 ]; then
    ok "claude CLI installed: $CLAUDE_BIN $(claude_version)"
  else
    tail -n 12 "$ci_log" 2>/dev/null | sed -e 's/^/     /' >&2 || true
    warn "could NOT install the Claude CLI (installer exit $ci_rc) — lib/agent.py will fall back to the offline STUB report writer and verify will fail on preflight/agent."
    warn "  claude.ai/install.sh redirects to downloads.claude.ai; both must be reachable from this box."
    warn "  Fix:    runuser -u $SVC_USER -- bash -c 'curl -fsSL https://claude.ai/install.sh | bash'   then re-run this installer"
    warn "  Or:     re-run with AURALIS_ALLOW_STUB=1 to accept stub reports for now (never permanently)."
  fi
fi

# =============================================================================
stage "7/$TOTAL_STAGES environment file"
# =============================================================================
# Values are NEVER printed — only key names. Validate first so a mangled file
# fails here instead of as a cryptic systemd "Failed to parse environment file".
#
# The normalisation below MUST match, byte for byte, what migrate_to_server.sh
# writes and what keycheck.py (stage 10), preflight.py and systemd itself read.
# One divergence — a stray CR, a BOM, a pair of quotes — derives a DIFFERENT
# Fernet key from AURALIS_DATA_KEY and the whole store becomes unreadable.
# The normalised file is written into the ROOT-ONLY scratch dir: the service user
# must not be able to substitute the file that becomes /etc/auralis/portal.env.
norm="$ROOT_WORK/portal.env.norm"
awk '
  NR == 1 { sub(/^\xef\xbb\xbf/, "") }                 # UTF-8 BOM
  { sub(/\r$/, "") }                                    # CRLF from a Mac/Windows editor
  /^[[:space:]]*(#|$)/ { print; next }
  {
    line = $0
    sub(/^[[:space:]]+/, "", line)
    sub(/^export[[:space:]]+/, "", line)
    eq = index(line, "=")
    if (eq == 0) { print line; next }                   # flagged as malformed below
    key = substr(line, 1, eq - 1)
    val = substr(line, eq + 1)
    gsub(/[[:space:]]/, "", key)
    sub(/^[[:space:]]+/, "", val); sub(/[[:space:]]+$/, "", val)
    # exactly ONE matching pair of surrounding quotes, like systemd
    if (length(val) >= 2) {
      f = substr(val, 1, 1); l = substr(val, length(val), 1)
      if (f == l && (f == "\"" || f == "'\''")) val = substr(val, 2, length(val) - 2)
    }
    printf "%s=%s\n", key, val
  }
' "$PAYLOAD/portal.env" > "$norm"

bad_line="$(awk '!/^[[:space:]]*(#|$)/ && !/^[A-Za-z_][A-Za-z0-9_]*=/ {print NR; exit}' "$norm")"
[ -z "$bad_line" ] || die 15 "portal.env line $bad_line is not KEY=VALUE (comments must be on their own line)."

# Nothing is ever expanded — not here, not by systemd. But a value CONTAINING $
# or a backtick is a trap: the Mac's shell-sourced .env would have expanded it
# and this file would not, so the two ends would use different secrets and the
# migrated store would refuse to open. Name the keys, never the values.
expandable="$(awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/ { v = substr($0, index($0, "=") + 1)
                        if (v ~ /[$`]/) printf "%s ", $1 }' "$norm")"
[ -z "$expandable" ] || die 15 "these portal.env values contain \$ or a backtick: ${expandable}
   Shell-vs-systemd expansion would silently give the Mac and this server two
   DIFFERENT secrets (and with AURALIS_DATA_KEY, an unreadable store). Change the
   value(s) to characters that cannot be expanded, on the Mac first, and re-run."

# A value that only differed by surrounding whitespace is normalised (systemd
# would strip it anyway) — but say so, because it means the Mac may have been
# using the UN-stripped variant.
while read -r k; do
  [ -n "$k" ] || continue
  warn "portal.env: $k had surrounding whitespace or quotes; normalised the way systemd will read it (value never printed)"
done < <(awk -F= '
  /^[[:space:]]*(#|$)/ { next }
  { raw = $0; sub(/\r$/, "", raw); sub(/^[[:space:]]*export[[:space:]]+/, "", raw)
    eq = index(raw, "="); if (eq == 0) next
    k = substr(raw, 1, eq - 1); v = substr(raw, eq + 1)
    o = v
    sub(/^[[:space:]]+/, "", v); sub(/[[:space:]]+$/, "", v)
    if (o != v) { gsub(/[[:space:]]/, "", k); print k } }' "$PAYLOAD/portal.env" | sort -u)

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
# draft is the right production mode, but ONLY with a mailbox password to reach.
# mailer._imap_draft() returns the string "skipped — no AURALIS_SMTP_PASSWORD
# set" and nothing raises, logs or notices, so email_mode=draft with no password
# is the worst of the three states: it looks configured and silently produces no
# client mail at all. Default to `off` in that case — same behaviour, but stated
# out loud, and preflight then warns instead of failing. Add the Gmail App
# Password to portal.env and re-run to get drafts.
if grep -qE '^AURALIS_SMTP_PASSWORD=.+' "$norm"; then
  add_default AURALIS_EMAIL_MODE      draft
else
  add_default AURALIS_EMAIL_MODE      off
  if grep -qE '^AURALIS_EMAIL_MODE=(draft|send)$' "$norm"; then
    warn "portal.env asks for AURALIS_EMAIL_MODE=draft/send but carries NO AURALIS_SMTP_PASSWORD — every client mail will be silently skipped. Add the Gmail App Password to $ENV_FILE and restart auralis-portal, or set AURALIS_EMAIL_MODE=off to say so out loud."
  else
    warn "no AURALIS_SMTP_PASSWORD in portal.env — AURALIS_EMAIL_MODE=off. NO client mail (access details, reminders, reports, feedback) is produced until you add the Gmail App Password to $ENV_FILE, set AURALIS_EMAIL_MODE=draft and restart auralis-portal."
  fi
fi
add_default AURALIS_AGENT_PROVIDER    claude_cli
add_default AURALIS_PUBLIC_BASE_URL   "https://$HOSTNAME_ING"
add_default AURALIS_BOOKING_URL       "https://$HOSTNAME_ING/book"
add_default AURALIS_BACKUP_DIR        "$DATA_DIR/backups"
if [ "${#defaulted[@]}" -gt 0 ]; then say "defaulted keys: ${defaulted[*]}"; fi

{
  # AURALIS_PORT / AURALIS_CHROME are OWNED by this installer: the port must
  # match the unit + tunnel ingress, and the chromium path is whatever survived
  # the render test above.
  awk '!/^[[:space:]]*(AURALIS_PORT|AURALIS_CHROME)=/' "$norm"
  # NO timestamp in here. It used to carry one, which meant `cmp -s` never
  # matched and the file holding every secret was rewritten on every single run —
  # destroying the one audit signal that matters ("the secrets changed").
  printf '\n# --- the two lines below are set by portal/deploy/install_server.sh ---\n'
  printf 'AURALIS_PORT=%s\n' "$PORT"
  printf 'AURALIS_CHROME=%s\n' "$CHROME"
} | write_managed "$ENV_FILE" 0640 "root:$SVC_GROUP" && env_changed=1 || env_changed=0
ok "$ENV_FILE $([ "$env_changed" -eq 1 ] && echo 'written' || echo 'unchanged') 0640 root:$SVC_GROUP ($(grep -cE '^[A-Za-z_]' "$ENV_FILE" || true) keys, values not logged)"

# =============================================================================
stage "8/$TOTAL_STAGES data placement"
# =============================================================================
# The server may already be live. We stop it ONLY for the moment a store is
# actually replaced — not for a no-op re-run, and not for the tunnel-only pass —
# and the exit handler starts it again if anything below fails.
ensure_portal_stopped() {
  [ "$PORTAL_STOPPED_BY_US" -eq 0 ] || return 0
  if systemctl is-active --quiet auralis-portal.service 2>/dev/null; then
    systemctl stop auralis-portal.service
    PORTAL_STOPPED_BY_US=1
    say "auralis-portal stopped — no writer may race a database swap"
  fi
}

place_data() {  # place_data <payload-file> <target> <mode>
  local src="$1" dst="$2" mode="$3" ts
  [ -f "$src" ] || { say "$(basename "$dst"): not in payload — keeping what is on the server"; return 0; }
  if [ -s "$dst" ]; then
    if cmp -s "$src" "$dst"; then ok "$(basename "$dst"): already identical (no-op)"; return 0; fi
    if [ "$ALLOW_DB_OVERWRITE" -eq 0 ]; then
      die 33 "$dst already exists with DIFFERENT content than the payload copy.
   Refusing to clobber live data. On a running server the two files will
   essentially NEVER be byte-identical (the live -wal holds committed pages the
   main .db does not), so this is the expected answer for a plain re-run.
   Choose deliberately:
     · server data is authoritative -> re-run with AURALIS_SKIP_DATA=1
       (migrate_to_server.sh: a rehearsal re-run does this for you)
     · this payload is authoritative -> re-run with AURALIS_ALLOW_DB_OVERWRITE=1
       (migrate_to_server.sh: --import-data, or the cutover, which always does it)
       the current file (+ its WAL) is copied into $BACKUP_DIR first."
    fi
    ensure_portal_stopped
    ts="$(date -u +%Y%m%d-%H%M%S)"
    # Back the old file up WITH its -wal/-shm sidecars: a WAL holds committed
    # transactions that are not in the main .db yet, so copying the .db alone
    # would silently drop the most recent records.
    for sc in "" "-wal" "-shm"; do
      if [ -e "$dst$sc" ]; then cp -a "$dst$sc" "$BACKUP_DIR/preinstall-$ts-$(basename "$dst")$sc"; fi
    done
    warn "$(basename "$dst") overwritten; previous file (+WAL) saved as $BACKUP_DIR/preinstall-$ts-$(basename "$dst")*"
  fi
  ensure_portal_stopped
  # Only now, once we are certain we are writing: the new file must never
  # inherit the previous database's sidecars. (Doing this earlier would have
  # destroyed WAL contents even on the refuse-to-overwrite path.)
  rm -f "$dst-wal" "$dst-shm"
  install -o "$SVC_USER" -g "$SVC_GROUP" -m "$mode" "$src" "$dst"
  ok "$(basename "$dst") placed"
}

if [ "$SKIP_DATA" -eq 1 ]; then
  warn "AURALIS_SKIP_DATA set — no data files placed (the portal is not stopped)"
else
  # WAL/SHM handling lives inside place_data — it must happen only once the
  # overwrite is actually going ahead. See the comment there.
  place_data "$PAYLOAD/auralis.db"   "$DATA_DIR/auralis.db"   0640
  place_data "$PAYLOAD/clients.json" "$DATA_DIR/clients.json" 0640
  if [ -f "$PAYLOAD/output_docs.tar.gz" ]; then
    # No stop for this one on purpose: the merge only ADDS files and the app
    # never holds them open, so a multi-minute extraction must not become
    # multi-minute downtime. --no-same-permissions: as root, tar would otherwise
    # restore whatever modes the Mac's files carried instead of our 027 umask.
    tar -xzf "$PAYLOAD/output_docs.tar.gz" -C "$DATA_DIR/output_docs" \
        --no-same-owner --no-same-permissions \
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
stage "9/$TOTAL_STAGES symlinks into the worktree"
# =============================================================================
# lib/cfg.py computes ROOT = the portal dir, so the app finds its data through
# these three links without knowing anything about /var/lib/auralis. All three
# repo paths are git-ignored, so `git reset --hard` in the updater leaves them.
link_data() {  # link_data <link-path> <target>
  local link="$1" target="$2" ts sc
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
    ensure_portal_stopped
    ts="$(date -u +%Y%m%d-%H%M%S)"
    # Same reason as in place_data: a database's -wal holds committed
    # transactions the main file does not, and an orphaned -wal left next to the
    # new symlink is a file SQLite may later try to apply to the WRONG database.
    for sc in "" "-wal" "-shm"; do
      if [ -e "$link$sc" ]; then
        mv "$link$sc" "$BACKUP_DIR/worktree-$ts-$(basename "$link")$sc" \
          || die 34 "$link$sc is a real file and could not be moved aside."
      fi
    done
    warn "$link was a real file; moved (with any -wal/-shm) to $BACKUP_DIR/worktree-$ts-$(basename "$link")*"
  fi
  as_svc ln -sfn "$target" "$link" || die 34 "could not create symlink $link"
  ok "$(basename "$link") -> $target"
}
link_data "$PORTAL_DIR/auralis.db"          "$DATA_DIR/auralis.db"
link_data "$PORTAL_DIR/config/clients.json" "$DATA_DIR/clients.json"
link_data "$PORTAL_DIR/output_docs"         "$DATA_DIR/output_docs"

# =============================================================================
stage "10/$TOTAL_STAGES data-key check"
# =============================================================================
# July 2026: the console started 500-ing because a record had been encrypted
# with a throwaway .dev_data.key while the server ran with the env key. Probe it
# BEFORE anything is started or the tunnel is pointed here.
# The script lives in a ROOT-OWNED directory the service user can only read: it
# is executed AS that user, so ownership buys nothing, but a directory the
# service user owns would let it swap the file root just wrote.
cat > "$PROBE_DIR/keycheck.py" <<'PY'
import os, sys
env_file, portal_dir = sys.argv[1], sys.argv[2]
# Parse the EnvironmentFile exactly the way systemd will, and exactly the way
# install_server.sh normalised it and migrate_to_server.sh wrote it: LITERALLY.
# Sourcing it in a shell instead would expand $... and backticks inside values,
# which for a passphrase-style AURALIS_DATA_KEY yields a DIFFERENT key than the
# service gets and turns this probe into a false alarm on a good migration.
with open(env_file, encoding="utf-8") as fh:
    first = True
    for raw in fh:
        line = raw
        if first:
            line = line.lstrip("﻿")          # UTF-8 BOM
            first = False
        line = line.rstrip("\n").rstrip("\r").strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]                           # exactly one matching pair
        os.environ[k] = v
sys.path.insert(0, portal_dir)
try:
    from lib import store
    r = store.key_matches_store()
except Exception as e:                      # missing key, unreadable file, ...
    print("ERROR:%s: %s" % (e.__class__.__name__, str(e)[:200])); raise SystemExit(0)
print("MATCH" if r is True else ("MISMATCH" if r is False else "UNREADABLE"))
PY
chmod 0644 "$PROBE_DIR/keycheck.py"
# Values never pass through this shell — the child reads the env file itself.
keyres="$(as_svc "$VENV_DIR/bin/python" "$PROBE_DIR/keycheck.py" "$ENV_FILE" "$PORTAL_DIR" 2>&1 | tail -1 || true)"
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
stage "11/$TOTAL_STAGES systemd units"
# =============================================================================
# Helper scripts live in $ETC_DIR: root-owned 0750 root:auralis, so the service
# user can execute but never rewrite a script that systemd runs as root.

# ONE way to become the service user, for every script this installer generates.
if [ "$RUNAS_MODE" = "runuser" ]; then
  write_managed "$BIN_DIR/as-auralis" 0750 "root:$SVC_GROUP" <<ASRUNUSER || true
#!/usr/bin/env bash
# Managed by portal/deploy/install_server.sh — run a command as $SVC_USER.
set -Eeuo pipefail
exec runuser -u $SVC_USER -- env HOME=$HOME_DIR "\$@"
ASRUNUSER
else
  write_managed "$BIN_DIR/as-auralis" 0750 "root:$SVC_GROUP" <<ASSU || true
#!/usr/bin/env bash
# Managed by portal/deploy/install_server.sh — run a command as $SVC_USER.
# No runuser on this host, so: su, with every argument re-quoted so a filename
# with a space cannot turn into two arguments.
set -Eeuo pipefail
q=""
for a in "\$@"; do q="\$q\$(printf '%q ' "\$a")"; done
exec su -s /bin/bash $SVC_USER -c "env HOME=$HOME_DIR \$q"
ASSU
fi

write_managed "$BIN_DIR/update.sh" 0750 "root:$SVC_GROUP" <<UPDATE || true
#!/usr/bin/env bash
# Managed by portal/deploy/install_server.sh — do not edit by hand.
# Replaces the Mac launcher's 120s self-update loop: fetch, and only if origin
# moved, hard-reset + reinstall deps + restart.
# It runs as root ONLY so it can \`systemctl restart\`; every git and pip
# operation is done as $SVC_USER, so a compromised repo or a malicious sdist
# never executes with root privileges on a host we share with another company.
set -Eeuo pipefail
export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND="$GIT_SSH"

# Kill switch: \`touch $HOLD_FILE\` freezes deploys (during an incident, during
# the other tenant's change freeze, whenever). \`rm\` it to resume.
if [ -e "$HOLD_FILE" ]; then
  echo "$HOLD_FILE exists — updates are on hold, doing nothing"
  exit 0
fi

# Never run while install_server.sh is working: it does its own fetch/reset and
# swaps the database, and a \`git reset --hard\` or a restart landing in the
# middle of that is how you get a half-installed portal.
mkdir -p $RUN_DIR; chmod 0755 $RUN_DIR
exec 9>$LOCK_FILE
if ! flock -n 9; then
  echo "install lock is held (install_server.sh is running) — skipping this tick"
  exit 0
fi

# A failed fetch (network blip, key revoked) must NOT take the running app down:
# log it and wait for the next tick. Everything after this point is deliberate.
$BIN_DIR/as-auralis git -C $APP_DIR fetch --quiet origin $BRANCH \\
  || { echo "git fetch failed (network or deploy key?) — retrying next tick"; exit 0; }
local_head="\$($BIN_DIR/as-auralis git -C $APP_DIR rev-parse HEAD)"
remote_head="\$($BIN_DIR/as-auralis git -C $APP_DIR rev-parse origin/$BRANCH)"
# NB: \`[ x = y ] && exit 0\` would abort this script under \`set -e\` on the
# NOT-equal branch, i.e. exactly when there IS an update. Use a real if.
if [ "\$local_head" = "\$remote_head" ]; then exit 0; fi
echo "updating \$local_head -> \$remote_head"
$BIN_DIR/as-auralis git -C $APP_DIR reset --hard --quiet "origin/$BRANCH"
$BIN_DIR/as-auralis $VENV_DIR/bin/pip install --quiet --disable-pip-version-check --no-input -r $PORTAL_DIR/requirements.txt \\
  || echo "pip install failed — restarting with the old deps"
# re-assert the data symlinks (cheap; protects against a bad tree state)
$BIN_DIR/as-auralis ln -sfn $DATA_DIR/auralis.db   $PORTAL_DIR/auralis.db
$BIN_DIR/as-auralis ln -sfn $DATA_DIR/clients.json $PORTAL_DIR/config/clients.json
$BIN_DIR/as-auralis ln -sfn $DATA_DIR/output_docs  $PORTAL_DIR/output_docs
systemctl restart auralis-portal.service
UPDATE

write_managed "$BIN_DIR/backup.sh" 0750 "root:$SVC_GROUP" <<BACKUP || true
#!/usr/bin/env bash
# Managed by portal/deploy/install_server.sh — do not edit by hand.
# Daily tar.gz of $DATA_DIR into $BACKUP_DIR. The DB is snapshotted with SQLite's
# online backup API (WAL-safe, consistent while the server writes), exactly like
# lib/backup.py does. The rolling in-app snapshots under $DATA_DIR/backups are
# excluded — they are derived data and would double the size.
#
# THE DISK IS SHARED WITH ANOTHER COMPANY'S PRODUCTION ERP. So: never start a
# backup we cannot finish, never leave a truncated archive behind, and cap the
# total bytes as well as the file count. A skipped backup is an inconvenience;
# a full filesystem is an outage for both tenants.
set -Eeuo pipefail
KEEP=\${AURALIS_BACKUP_KEEP:-14}          # newest N tarballs
CAP_MB=\${AURALIS_BACKUP_CAP_MB:-6144}    # ... and at most this many MB in total
FLOOR_MB=\${AURALIS_BACKUP_FLOOR_MB:-2048} # never take the disk below this

ts="\$(date -u +%Y%m%d-%H%M%S)"
part="$BACKUP_DIR/.auralis-\$ts.tar.gz.part"
final="$BACKUP_DIR/auralis-\$ts.tar.gz"
stage="\$(mktemp -d $DATA_DIR/.bk.XXXXXX)"
# The .part file is removed on EVERY exit path; only a completed archive is
# renamed into place, so a half-written tarball can never be counted as a backup
# and can never survive an ENOSPC.
trap 'rm -rf "\$stage" "\$part"' EXIT

free_mb() { df -Pm "\$1" 2>/dev/null | awk 'NR==2 {print \$4}'; }
dir_mb()  { du -sm "\$1" 2>/dev/null | awk '{print \$1}'; }

free="\$(free_mb $BACKUP_DIR)"; free="\${free:-0}"
# Estimate from the last tarball if there is one, else from the data itself.
last="\$(ls -1t $BACKUP_DIR/auralis-*.tar.gz 2>/dev/null | sed -n '1p' || true)"
if [ -n "\$last" ]; then
  need=\$(( \$(du -sm "\$last" | awk '{print \$1}') * 2 + 64 ))
else
  need=\$(( \$(dir_mb $DATA_DIR) / 2 + 128 ))
fi
if [ "\$free" -lt \$(( need + FLOOR_MB )) ]; then
  echo "SKIPPING backup: only \${free} MB free on $BACKUP_DIR, need ~\${need} MB plus a \${FLOOR_MB} MB floor."
  echo "This disk is shared with another company's production system; filling it is not an option."
  echo "Free space or lower AURALIS_BACKUP_KEEP / AURALIS_BACKUP_CAP_MB, then run: systemctl start auralis-backup.service"
  exit 0
fi

if [ -f $DATA_DIR/auralis.db ]; then
  $VENV_DIR/bin/python - "\$stage/auralis.db" <<'PY'
import sqlite3, sys
src = sqlite3.connect("$DATA_DIR/auralis.db")
dst = sqlite3.connect(sys.argv[1])
src.backup(dst); dst.close(); src.close()
PY
fi
if [ -f $DATA_DIR/clients.json ]; then cp -a $DATA_DIR/clients.json "\$stage/"; fi
tar -czf "\$part" -C "\$stage" . -C $DATA_DIR ./output_docs
mv -f "\$part" "\$final"

# Rotate by COUNT first, then by TOTAL BYTES — count alone lets 14 ever-growing
# archives eat the shared filesystem. The newest is never deleted.
ls -1t $BACKUP_DIR/auralis-*.tar.gz 2>/dev/null | tail -n +\$(( KEEP + 1 )) | xargs -r rm -f || true
total=0
while read -r f; do
  [ -n "\$f" ] || continue
  sz=\$(( \$(stat -c%s "\$f") / 1048576 ))
  total=\$(( total + sz ))
  if [ "\$total" -gt "\$CAP_MB" ] && [ "\$f" != "\$final" ]; then
    rm -f "\$f"; echo "pruned \$f (total would be \${total} MB > \${CAP_MB} MB cap)"
  fi
done < <(ls -1t $BACKUP_DIR/auralis-*.tar.gz 2>/dev/null || true)
echo "backup written: \$final (\$(du -h "\$final" | cut -f1)), \${free} MB was free before"
BACKUP

unit() {  # unit <name> ; content on stdin
  if write_managed "$UNIT_DIR/$1" 0644 root:root; then CHANGED_UNITS=1; say "$1 written"; else say "$1 unchanged"; fi
}

# The hardening block is generated from ONE array (PORTAL_HARDENING, stage 4) so
# the sandbox the PDF probe proved and the sandbox the service actually gets can
# never drift apart.
{
  cat <<PORTALUNIT
# Managed by portal/deploy/install_server.sh — replaces launchd KeepAlive.
[Unit]
Description=Auralis Natura portal (Flask, 127.0.0.1:$PORT)
Documentation=file://$PORTAL_DIR/deploy/SERVER-RUNBOOK.md
After=network-online.target
Wants=network-online.target
# A crash loop must reach 'failed' and stop, instead of forking a Python
# interpreter every 10s forever and evicting the co-tenant's logs from the
# SHARED journal (journald's size limits are global, not per unit).
StartLimitIntervalSec=300
StartLimitBurst=10

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
RestartSec=10
TimeoutStopSec=20
StandardOutput=journal
StandardError=journal
SyslogIdentifier=auralis-portal
# The journal is canei-erp's too — a chatty traceback loop must not evict it.
LogRateLimitIntervalSec=30s
LogRateLimitBurst=1000
# Containment + resource ceilings — this box also runs another company's
# production ERP, and the OOM killer picks its victim by score, not by owner.
PORTALUNIT
  printf '%s\n' "${PORTAL_HARDENING[@]}"
  cat <<'PORTALTAIL'

[Install]
WantedBy=multi-user.target
PORTALTAIL
} | unit auralis-portal.service

unit auralis-update.service <<UPDATEUNIT
# Managed by portal/deploy/install_server.sh
[Unit]
Description=Auralis portal self-update from GitHub $BRANCH
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$BIN_DIR/update.sh
SyslogIdentifier=auralis-update
# A slow pip must not be SIGTERMed halfway through after the reset already landed.
TimeoutStartSec=600
# Deliberately NOT ProtectSystem=strict: this unit calls \`systemctl restart\`,
# which needs to connect to systemd's socket under a WRITABLE /run.
ProtectSystem=full
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=false
MemoryHigh=512M
MemoryMax=1G
CPUQuota=100%
CPUWeight=20
TasksMax=128
Nice=10
UPDATEUNIT

unit auralis-update.timer <<UPDATETIMER
# Managed by portal/deploy/install_server.sh — the Mac launcher polled every 120s.
[Unit]
Description=Check GitHub $BRANCH for portal updates every 2 minutes

[Timer]
# OnBootSec is a floor, not a delay, on a host that has been up for months: the
# first tick lands as soon as the timer is started. That is fine now — update.sh
# refuses to run while install_server.sh holds $LOCK_FILE, and the timers are
# only armed after the install has fully verified.
OnBootSec=3min
OnUnitActiveSec=2min
RandomizedDelaySec=30
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
TimeoutStartSec=3600
# tar + gzip on a shared 4 vCPU box at 03:20: stay out of the ERP's way.
Nice=15
IOSchedulingClass=idle
CPUQuota=60%
CPUWeight=10
MemoryHigh=256M
MemoryMax=512M
TasksMax=64
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$DATA_DIR $BACKUP_DIR
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
# Only the portal is enabled here. The two TIMERS are armed at the very end,
# after verify passes: a run that dies in the tunnel stage used to leave a root
# job polling GitHub every 2 minutes forever on a host that is not only ours.
enable_unit auralis-portal.service || die 40 "systemctl enable auralis-portal.service failed"
portal_pre="$(systemctl is-active auralis-portal.service 2>/dev/null || true)"
systemctl restart auralis-portal.service || die 40 "auralis-portal.service failed to start — journalctl -u auralis-portal -n 50"
[ "$portal_pre" = "active" ] || REVERT_STOP+=("auralis-portal.service")
PORTAL_STOPPED_BY_US=0        # it is running again; nothing left to restore
ok "auralis-portal.service installed, enabled and started"

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
stage "12/$TOTAL_STAGES cloudflared tunnel"
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

  [ -n "$CFBIN" ] || die 41 "no cloudflared binary was resolved in stage 3."
  unit cloudflared-auralis.service <<CFUNIT
# Managed by portal/deploy/install_server.sh.
# Deliberately NOT named cloudflared.service: this host already runs another
# company's tunnel and that unit must never be touched.
[Unit]
Description=Cloudflare Tunnel (Auralis) $HOSTNAME_ING -> 127.0.0.1:$PORT
After=network-online.target auralis-portal.service
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=10

[Service]
Type=simple
User=$SVC_USER
Group=$SVC_GROUP
Environment=HOME=$HOME_DIR
# --no-autoupdate is mandatory here: an auto-update would replace the binary
# underneath the OTHER company's tunnel too, if they share one.
ExecStart=$CFBIN --no-autoupdate --config $CF_CONF tunnel run
Restart=always
RestartSec=5
SyslogIdentifier=cloudflared-auralis
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
ProtectProc=invisible
RestrictSUIDSGID=true
LockPersonality=true
SystemCallArchitectures=native
ReadWritePaths=$HOME_DIR
# Co-tenant separation. Unlike the portal this is a plain Go network daemon with
# no headless chromium in it, so the strict set goes on unconditionally — there
# is nothing here that has ever needed a capability, a device node or an exotic
# syscall. If the tunnel ever fails to start right after an install, THIS block
# is the first thing to bisect (exit 41 points here).
ProcSubset=pid
CapabilityBoundingSet=
PrivateDevices=true
ProtectHostname=true
ProtectClock=true
RestrictNamespaces=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
SystemCallFilter=@system-service
SystemCallFilter=~@privileged @resources @obsolete
UMask=0077
$([ -n "$CO_PATHS" ] && printf 'InaccessiblePaths=%s' "$CO_PATHS")
MemoryHigh=150M
MemoryMax=256M
CPUWeight=20
TasksMax=64
LogRateLimitIntervalSec=30s
LogRateLimitBurst=500

[Install]
WantedBy=multi-user.target
CFUNIT

  systemctl daemon-reload
  enable_unit cloudflared-auralis.service || die 41 "could not enable cloudflared-auralis.service"
  cf_pre="$(systemctl is-active cloudflared-auralis.service 2>/dev/null || true)"
  systemctl restart cloudflared-auralis.service || die 41 "cloudflared-auralis.service failed to start — journalctl -u cloudflared-auralis -n 50"
  [ "$cf_pre" = "active" ] || REVERT_STOP+=("cloudflared-auralis.service")
  sleep 4
  systemctl is-active --quiet cloudflared-auralis.service || {
    journalctl -u cloudflared-auralis.service -n 30 --no-pager 2>/dev/null | sed -e 's/^/     /' >&2 || true
    die 41 "cloudflared-auralis.service did not stay up"
  }
  ok "cloudflared-auralis.service running (own instance, own config, own binary)"
fi

# =============================================================================
stage "13/$TOTAL_STAGES arm the timers, then verify"
# =============================================================================
# The timers are armed BEFORE verify runs, not after it.
#
# This used to be the other way round, and it could never pass: verify_server.sh
# asserts both timers are enabled, active and actually scheduled, so running it
# while they were still deliberately off produced two guaranteed FAILures and a
# non-zero exit — which then prevented the very code that would have armed them.
#
# The safety property that ordering was protecting is unchanged, because it is
# not the ordering that provides it: the EXIT handler stops and disables every
# unit THIS run turned on whenever the run ends non-zero (REVERT_STOP /
# REVERT_DISABLE, populated by start_unit/enable_unit). So a failed install
# still leaves no root timer polling GitHub on the co-tenant's production host —
# it just gets undone at the end instead of never being done.
enable_unit auralis-update.timer auralis-backup.timer || die 40 "systemctl enable failed for the timers"
start_unit  auralis-update.timer auralis-backup.timer || die 40 "timers failed to start"
ok "auralis-update.timer + auralis-backup.timer armed (both are disarmed again if verify fails)"

# --------------------------------------------------- warm the claude CLI up --
# verify's preflight does a real `claude -p` round-trip on a 60s budget and
# calls a timeout an outright FAIL. On a freshly installed CLI that would be its
# FIRST invocation ever — config directory creation, a version check, whatever
# first-run work the binary does — all charged to the measured probe. Do it here
# instead, untimed and non-fatal, so verify measures a warm CLI.
#
# The token is read by the CHILD out of the (group-readable) env file rather
# than passed in the environment of a command: argv and the environment of a
# process are readable by every account on this box, canei's included.
if [ -x "$CLAUDE_BIN" ] && grep -qE '^CLAUDE_CODE_OAUTH_TOKEN=.+' "$ENV_FILE" 2>/dev/null; then
  warm_rc=0
  as_svc env HOME="$HOME_DIR" PATH="$HOME_DIR/.local/bin:/usr/local/bin:/usr/bin:/bin" \
    bash -c '
      CLAUDE_CODE_OAUTH_TOKEN="$(sed -n "s/^CLAUDE_CODE_OAUTH_TOKEN=//p" "$1" | head -1)"
      export CLAUDE_CODE_OAUTH_TOKEN
      exec claude -p "Reply with exactly: OK" --output-format text
    ' _ "$ENV_FILE" >"$ROOT_WORK/claude-warm.log" 2>&1 || warm_rc=$?
  if [ "$warm_rc" -eq 0 ]; then
    ok "claude CLI round-tripped once (warm-up) — verify's probe will measure a warm binary"
  else
    warn "the claude CLI warm-up exited $warm_rc — verify will report the real reason in a moment:"
    tail -n 6 "$ROOT_WORK/claude-warm.log" 2>/dev/null | sed -e 's/^/     /' >&2 || true
  fi
fi

VERIFY="$PORTAL_DIR/deploy/verify_server.sh"
verify_rc=0
# --public is the post-cutover contract: the tunnel must be connected and the
# public URL must answer, and both become FAILURES instead of warnings. We are
# post-cutover exactly when our own tunnel is up on this host.
VERIFY_ARGS=()
if [ -n "${AURALIS_VERIFY_PUBLIC:-}" ]; then
  _flag "${AURALIS_VERIFY_PUBLIC}" && VERIFY_ARGS+=(--public)
elif [ "$SKIP_TUNNEL" -eq 0 ] && systemctl is-active --quiet cloudflared-auralis.service 2>/dev/null; then
  VERIFY_ARGS+=(--public)
fi
if [ "$ALLOW_STUB" -eq 1 ]; then VERIFY_ARGS+=(--allow-stub); fi
if [ -f "$VERIFY" ]; then
  say "running $VERIFY as $SVC_USER ${VERIFY_ARGS[*]:-(pre-cutover mode)}"
  # `|| verify_rc=$?` and NOT the `set +e` this used to be. verify_server.sh
  # exiting 1 is an EXPECTED outcome we want to read and report — but bash runs
  # an inherited ERR trap (set -E) from inside a shell function regardless of
  # errexit, so `set +e; as_svc …` still tripped the trap and the whole script
  # died with exit 99. That is why the first real run reported
  # AURALIS_INSTALL_EXIT=99 and never printed its own summary or the
  # "here is what to fix" block below. Only an ||-list suppresses the trap.
  verify_rc=0
  as_svc env HOME="$HOME_DIR" AURALIS_PORT="$PORT" AURALIS_HOSTNAME="$HOSTNAME_ING" \
         AURALIS_ENV_FILE="$ENV_FILE" bash "$VERIFY" ${VERIFY_ARGS[@]+"${VERIFY_ARGS[@]}"} \
    || verify_rc=$?
elif [ "$REQUIRE_VERIFY" -eq 1 ]; then
  die 40 "$VERIFY is missing and AURALIS_REQUIRE_VERIFY is set."
else
  warn "$VERIFY not present in this revision — post-install verification SKIPPED. Merge portal/deploy/verify_server.sh and re-run, or run it by hand."
fi

if [ "$verify_rc" -eq 0 ]; then
  # The updater we paused at the start of this run is armed and running again,
  # so the exit handler has nothing left to restore.
  REVERT_START=()
  if [ -e "$HOLD_FILE" ]; then
    warn "$HOLD_FILE exists — auralis-update.sh will do nothing until you remove it"
  fi
fi

# ------------------------------------------------------------------ summary --
printf '\n%s================ AURALIS INSTALL SUMMARY ================%s\n' "$C_B" "$C_0"
printf '  code      %s @ %s (%s)\n' "$APP_DIR" "$BRANCH" "$(git_svc -C "$APP_DIR" rev-parse --short HEAD || true)"
printf '  data      %s (db %s · output_docs %s files)\n' "$DATA_DIR" \
       "$( [ -f "$DATA_DIR/auralis.db" ] && stat -c%s "$DATA_DIR/auralis.db" || echo 0 )B" \
       "$(find "$DATA_DIR/output_docs" -type f 2>/dev/null | wc -l || true)"
printf '  env       %s (0640 root:%s)\n' "$ENV_FILE" "$SVC_GROUP"
printf '  chromium  %s [%s] (PDF verified%s)\n' "$CHROME" "$CHROME_SOURCE" \
       "$([ "$HARDENED_PROBE" -eq 1 ] && printf ' under the service sandbox' || true)"
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
printf '  undo      bash %s/deploy/uninstall_server.sh   (keeps the data)\n' "$PORTAL_DIR"
if [ "${#WARNINGS[@]}" -gt 0 ]; then
  printf '\n%s  %d WARNING(S):%s\n' "$C_Y" "${#WARNINGS[@]}" "$C_0"
  for w in "${WARNINGS[@]}"; do printf '   ! %s\n' "$w"; done
fi
if [ "$verify_rc" -ne 0 ]; then
  printf '\n%s  verify_server.sh FAILED (exit %s) — propagating its exit code.%s\n' "$C_R" "$verify_rc" "$C_0"
  printf '  The periodic timers this run armed are being disarmed again below.\n'
  printf '  To remove everything this kit installed on this shared host:\n'
  printf '     bash %s/deploy/uninstall_server.sh\n' "$PORTAL_DIR"
  STAGE="verify"
  exit "$verify_rc"
fi
printf '\n%s  INSTALL COMPLETE.%s\n' "$C_G" "$C_0"
STAGE="done"
exit 0
