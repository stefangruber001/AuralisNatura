#!/usr/bin/env bash
# =============================================================================
#  enable_email.sh — turn client mail on, on the server, in one command
# =============================================================================
#  Runs where the portal runs, and works out which that is:
#
#    • on Desiree's Mac (no sudo — she owns the file)
#      bash portal/deploy/enable_email.sh
#
#    • on the Linux server, as root
#      sudo bash /opt/auralis/app/portal/deploy/enable_email.sh
#
#  It asks for the Gmail App Password for team@auralisnatura.com (hidden),
#  PROVES it works before changing anything, and only then writes it into
#  /etc/auralis/portal.env, switches AURALIS_EMAIL_MODE to draft and restarts
#  the portal.
#
#  Why "proves it first": mailer._imap_draft() and _smtp_send() catch every
#  exception and return a string in a dict. A wrong password does not raise, is
#  not logged, and produces no mail — the failure mode is a client who never
#  hears back. So the credential is tested against the real Gmail servers, with
#  the real config, BEFORE it is written anywhere. Nothing is changed on a
#  failed test.
#
#  FLAGS
#    --retest        test the password already in portal.env; change nothing
#    --send-test-to EMAIL
#                    after enabling, put one real test message in Drafts (mode
#                    draft) so you can see the whole path end to end
#    --mode draft|send|off
#                    default draft — the reviewed mode: mails land in Gmail
#                    Drafts and Desiree clicks Send
#    --password-stdin
#                    read the password from stdin instead of prompting
#    -h | --help
#
#  Exit codes: 0 ok · 1 usage/precondition · 2 credential rejected · 3 write or
#  restart failed. Nothing is written unless the credential passed.
# =============================================================================
set -Eeuo pipefail

# The portal runs in one of two places and this must write the env file the
# RUNNING one reads. On the Mac that is portal/.env, owned by the founder and
# needing no root at all; on the server it is /etc/auralis/portal.env under
# systemd. Demanding sudo on a Mac just blocks the person who owns the file.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"        # …/portal
if [ -f /etc/auralis/portal.env ] && command -v systemctl >/dev/null 2>&1; then
  PLATFORM="server"
else
  PLATFORM="mac"
fi

if [ "$PLATFORM" = "server" ]; then
  ENV_FILE="${AURALIS_ENV_FILE:-/etc/auralis/portal.env}"
  APP_DIR="${AURALIS_APP_DIR:-/opt/auralis/app}"
  PORTAL_DIR="$APP_DIR/portal"
  VENV="${AURALIS_VENV:-/opt/auralis/venv}"
  PY3="$VENV/bin/python3"
  SVC_USER="${AURALIS_USER:-auralis}"
else
  ENV_FILE="${AURALIS_ENV_FILE:-$HERE/.env}"
  APP_DIR="$(cd "$HERE/.." && pwd)"
  PORTAL_DIR="$HERE"
  VENV="${AURALIS_VENV:-$HERE/.venv}"
  PY3="$([ -x "$VENV/bin/python3" ] && echo "$VENV/bin/python3" || command -v python3)"
  SVC_USER="$(id -un)"
fi
SVC_HOME="${AURALIS_SVC_HOME:-/opt/auralis}"
UNIT="$([ "$PLATFORM" = server ] && echo auralis-portal.service || echo com.auralis.portal)"

MODE="draft"; RETEST=0; PW_STDIN=0; TEST_TO=""
while [ $# -gt 0 ]; do
  case "$1" in
    --retest)         RETEST=1; shift ;;
    --send-test-to)   TEST_TO="${2:?}"; shift 2 ;;
    --mode)           MODE="${2:?}"; shift 2 ;;
    --password-stdin) PW_STDIN=1; shift ;;
    -h|--help)        sed -n '2,40p' "$0"; exit 0 ;;
    *) printf 'unknown option: %s (try --help)\n' "$1" >&2; exit 1 ;;
  esac
done
case "$MODE" in draft|send|off) ;; *) printf -- '--mode must be draft, send or off\n' >&2; exit 1 ;; esac

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_G=$'\033[32m'; C_Y=$'\033[33m'; C_R=$'\033[31m'; C_B=$'\033[1m'; C_D=$'\033[2m'; C_0=$'\033[0m'
else C_G=''; C_Y=''; C_R=''; C_B=''; C_D=''; C_0=''; fi
ok()   { printf '   %s✓%s %s\n' "$C_G" "$C_0" "$1"; }
warn() { printf '   %s!%s %s\n' "$C_Y" "$C_0" "$1" >&2; }
say()  { printf '   %s·%s %s\n' "$C_D" "$C_0" "$1"; }
step() { printf '\n%s── %s%s\n' "$C_B" "$1" "$C_0"; }
die()  { local c="$1"; shift; printf '\n%s✗ %s%s\n' "$C_R" "$*" "$C_0" >&2; exit "$c"; }
trap 'rc=$?; [ $rc -eq 0 ] || printf "\n%s✗ enable_email.sh stopped at line %s (exit %s)%s\n" "$C_R" "$LINENO" "$rc" "$C_0" >&2' ERR

printf '%s\n╔════════════════════════════════════════════════════════════╗\n' "$C_B"
printf   '║   Auralis Natura — enable client email                     ║\n'
printf   '╚════════════════════════════════════════════════════════════╝%s\n' "$C_0"

# ── preconditions ────────────────────────────────────────────────────────────
step "Checks"
if [ "$PLATFORM" = "server" ]; then
  [ "$(id -u)" -eq 0 ] || die 1 "on the server this must run as root (got uid $(id -u)) — try: sudo bash $0"
fi
say "detected: $PLATFORM · env file $ENV_FILE"
[ -f "$ENV_FILE" ]   || die 1 "$ENV_FILE does not exist — has install_server.sh run on this host?"
[ -x "$PY3" ] || die 1 "no python3 found ($PY3) — cannot prove the credential without it"
[ -f "$PORTAL_DIR/lib/mailer.py" ] || die 1 "$PORTAL_DIR/lib/mailer.py is missing — wrong APP_DIR?"
ok "$([ "$PLATFORM" = server ] && echo "root, " )$ENV_FILE writable, python and portal code in place"

# The address and hosts are config, not something to ask about. Print them so a
# surprise (wrong mailbox, wrong host) is caught before a password is typed.
SMTP_USER="$("$PY3" - "$PORTAL_DIR" <<'PY' 2>/dev/null || true
import json, sys, pathlib
p = pathlib.Path(sys.argv[1]) / "config" / "config.json"
c = json.loads(p.read_text())
print(c.get("smtp_user", ""))
PY
)"
[ -n "$SMTP_USER" ] || die 1 "could not read smtp_user from $PORTAL_DIR/config/config.json"
say "mailbox   $SMTP_USER"
say "smtp      smtp.gmail.com:587 (STARTTLS)   ·   imap  imap.gmail.com:993 (SSL)"

# ── the password ─────────────────────────────────────────────────────────────
step "App password"
PW=""
if [ "$RETEST" -eq 1 ]; then
  PW="$(sed -n 's/^AURALIS_SMTP_PASSWORD=//p' "$ENV_FILE" | head -1)"
  [ -n "$PW" ] || die 1 "--retest, but $ENV_FILE has no AURALIS_SMTP_PASSWORD to test"
  ok "re-testing the password already in $ENV_FILE (never printed)"
elif [ "$PW_STDIN" -eq 1 ]; then
  IFS= read -r PW || true
else
  cat <<'HOWTO'
   Where to get it (2 minutes, on any device):
     1. myaccount.google.com  →  sign in as the mailbox above
     2. Security  →  2-Step Verification must be ON (app passwords need it)
     3. Search the page for "App passwords"  →  create one, name it "Auralis"
     4. Google shows 16 letters in four groups — copy them
   The spaces Google shows are display only; paste it either way, they are
   stripped here. Input is hidden.
HOWTO
  printf '\n   %sApp password:%s ' "$C_B" "$C_0"
  IFS= read -r -s PW || true
  printf '\n'
fi

# Google renders the password as "abcd efgh ijkl mnop" and everybody pastes it
# with the spaces. SMTP AUTH then fails with a completely unrelated-looking
# error. Tokens here are alphanumeric, so stripping every whitespace character
# is always safe and always right.
RAW_LEN=${#PW}
PW="$(printf '%s' "$PW" | tr -d '[:space:]')"
[ -n "$PW" ] || die 1 "no password given — nothing was changed"
if [ "${#PW}" -ne "$RAW_LEN" ]; then
  say "stripped $(( RAW_LEN - ${#PW} )) space(s) — that is how Google displays it"
fi
if [ "${#PW}" -ne 16 ]; then
  warn "a Gmail app password is 16 characters; this one is ${#PW}. Testing it anyway."
  warn "  (If this is your normal Google password it will be rejected — Google requires an app password.)"
fi
ok "password read (${#PW} chars, never printed or logged)"

# ── prove it, before changing anything ───────────────────────────────────────
step "Testing against Gmail (nothing has been changed yet)"
# Run as the SERVICE user with the service's config, so a pass here means the
# service will pass too. The password goes in via the environment of this one
# child — never argv, which every account on this shared host can read.
TEST_RC=0
# On the server: as the SERVICE user with its config, so a pass here means the
# service will pass too. On the Mac the founder IS that user, so no switch is
# needed — and none is possible without the root password. Either way the
# password goes in through the environment of one child, never argv.
if [ "$PLATFORM" = "server" ]; then
  PROVE=(runuser -u "$SVC_USER" -- env HOME="$SVC_HOME" AURALIS_TEST_PW="$PW" "$PY3")
else
  PROVE=(env AURALIS_TEST_PW="$PW" "$PY3")
fi
AURALIS_TEST_PW="$PW" "${PROVE[@]}" - "$PORTAL_DIR" <<'PY' || TEST_RC=$?
import json, os, pathlib, smtplib, imaplib, ssl, sys

portal = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(portal))
from lib import mailer                      # the SAME resolver the mailer uses

cfg = json.loads((portal / "config" / "config.json").read_text())
user = cfg.get("smtp_user", "")
pw   = os.environ["AURALIS_TEST_PW"]
sh, sp = cfg.get("smtp_host", "smtp.gmail.com"), int(cfg.get("smtp_port", 587))
ih, ip = cfg.get("imap_host", "imap.gmail.com"), int(cfg.get("imap_port", 993))

def fail(msg, hint=""):
    print("FAIL " + msg)
    if hint:
        print("HINT " + hint)
    sys.exit(2)


def tls_hint():
    """A certificate failure is NOT a network problem, and saying 'check the port'
    sends you to look at a firewall that is working perfectly. On macOS this is
    almost always a Python with no CA bundle: python.org builds ship the roots in
    a script you have to run once. It matters beyond this check — the portal
    sends mail with this same interpreter, so until it is fixed no client mail
    can leave the machine at all."""
    import glob
    bits = ["The TLS handshake succeeded and the CERTIFICATE could not be verified — "
            "the port is open, the trust store is empty."]
    installer = sorted(glob.glob("/Applications/Python 3.*/Install Certificates.command"))
    if installer:
        bits.append('Run this once, then try again:  "%s"' % installer[-1])
    else:
        bits.append("Fix it for THIS interpreter (%s):" % sys.executable)
        bits.append("  %s -m pip install --upgrade certifi" % sys.executable)
        bits.append("If that does not help, install python via Homebrew "
                    "(brew install python) — its certificates are wired up.")
    bits.append("The portal sends mail with the same python3, so this must be fixed "
                "here, not worked around.")
    return "  ".join(bits)

# ---- SMTP (used by email_mode=send, and the cheapest proof of the credential)
try:
    s = smtplib.SMTP(sh, sp, timeout=25)
    s.starttls(context=ssl.create_default_context())
    s.login(user, pw)
    s.quit()
    print("OK   smtp   %s authenticated on %s:%d (STARTTLS)" % (user, sh, sp))
except smtplib.SMTPAuthenticationError as e:
    fail("smtp   %s was REJECTED by %s:%d — %s" % (user, sh, sp, e.smtp_error.decode("utf-8", "replace")[:160]),
         "Almost always: this is not an app password, 2-Step Verification is off, "
         "or a Workspace admin has blocked app passwords for this account.")
except ssl.SSLCertVerificationError as e:
    fail("smtp   TLS certificate could not be verified for %s:%d — %s" % (sh, sp, e),
         tls_hint())
except Exception as e:
    fail("smtp   could not reach %s:%d — %s: %s" % (sh, sp, type(e).__name__, e),
         "Check outbound port 587 from this host.")

# ---- IMAP + the drafts folder (this is the path email_mode=draft actually uses)
M = None
try:
    M = imaplib.IMAP4_SSL(ih, ip, timeout=25)
    M.login(user, pw)
    print("OK   imap   %s authenticated on %s:%d (SSL)" % (user, ih, ip))
    box = mailer.drafts_mailbox(M)
    typ, _ = M.select(box, readonly=True)
    if typ != "OK":
        fail("drafts %s is not selectable (%s)" % (box.strip('"'), typ),
             "email_mode=draft APPENDs there; without it every report mail is lost.")
    print("OK   drafts %s is selectable — email_mode=draft will work" % box.strip('"'))
except imaplib.IMAP4.error as e:
    fail("imap   login refused by %s:%d — %s" % (ih, ip, e),
         "Enable IMAP in Gmail: Settings -> Forwarding and POP/IMAP -> Enable IMAP.")
except Exception as e:
    fail("imap   could not reach %s:%d — %s: %s" % (ih, ip, type(e).__name__, e))
finally:
    try:
        if M is not None:
            M.logout()
    except Exception:
        pass
print("PASS")
PY

if [ "$TEST_RC" -ne 0 ]; then
  printf '\n'
  die 2 "the credential did NOT pass — $ENV_FILE is untouched and the portal was not restarted.
   Fix what the HINT above says and run this again."
fi
ok "credential proven against the real Gmail servers"

if [ "$RETEST" -eq 1 ]; then
  printf '\n%s  The password already in %s works. Nothing was changed.%s\n' "$C_G" "$ENV_FILE" "$C_0"
  exit 0
fi

# ── write it ─────────────────────────────────────────────────────────────────
step "Writing $ENV_FILE"
# Atomic, in the same directory, preserving 0640 root:auralis. A half-written
# env file is a service that will not start.
BACKUP="$ENV_FILE.bak-$(date +%Y%m%d-%H%M%S)"
if [ -f "$ENV_FILE" ]; then cp -p "$ENV_FILE" "$BACKUP"; else : > "$ENV_FILE"; : > "$BACKUP"; fi
chmod 0600 "$BACKUP"
say "previous file kept at $BACKUP (0600 root-only)"

TMP="$(mktemp "$(dirname "$ENV_FILE")/.portal.env.XXXXXX")"
if [ "$PLATFORM" = "server" ]; then chmod 0640 "$TMP"; chown "root:$SVC_USER" "$TMP"
else chmod 0600 "$TMP"; fi
{
  # Drop the two keys we own, keep everything else exactly as it was.
  [ -f "$ENV_FILE" ] && { grep -vE '^[[:space:]]*(AURALIS_SMTP_PASSWORD|AURALIS_EMAIL_MODE)=' "$ENV_FILE" || true; }
  printf 'AURALIS_SMTP_PASSWORD=%s\n' "$PW"
  printf 'AURALIS_EMAIL_MODE=%s\n'    "$MODE"
} > "$TMP"
# No quotes, no CRLF: systemd's EnvironmentFile keeps quotes literally, and a
# quoted password is a different password.
mv -f "$TMP" "$ENV_FILE"
ok "$ENV_FILE updated — AURALIS_EMAIL_MODE=$MODE, password stored"

# ── restart and confirm ──────────────────────────────────────────────────────
step "Restarting the portal"
if [ "$PLATFORM" = "server" ]; then
  systemctl restart "$UNIT" || die 3 "systemctl restart $UNIT failed — journalctl -u $UNIT -n 50"
  sleep 3
  systemctl is-active --quiet "$UNIT" || {
    journalctl -u "$UNIT" -n 30 --no-pager 2>/dev/null | sed -e 's/^/     /' >&2 || true
    printf '\n%s  Restoring %s from %s%s\n' "$C_Y" "$ENV_FILE" "$BACKUP" "$C_0" >&2
    cp -p "$BACKUP" "$ENV_FILE" && chmod 0640 "$ENV_FILE" && chown "root:$SVC_USER" "$ENV_FILE"
    systemctl restart "$UNIT" >/dev/null 2>&1 || true
    die 3 "$UNIT did not stay up with the new env file — rolled back."
  }
else
  launchctl kickstart -k "gui/$(id -u)/$UNIT" 2>/dev/null \
    || { launchctl unload "$HOME/Library/LaunchAgents/$UNIT.plist" 2>/dev/null || true
         launchctl load -w "$HOME/Library/LaunchAgents/$UNIT.plist" 2>/dev/null \
         || warn "no launchd job found — restart start_auralis.command by hand"; }
  sleep 5
fi
ok "portal restarted"

# preflight --net now exercises the real logins the way the running service
# resolves them (its env file, its venv, its user). preflight has no --only, so
# ask for JSON and show the three lines that belong to this change; its exit
# code covers every check, which is not what we are asserting here.
step "Verifying the way the app sees it"
# preflight must see the PATH the SERVICE sees. runuser resets PATH to the login
# default, which has no /opt/auralis/.local/bin — so the `claude` CLI the
# installer put there reads as missing and preflight/agent fails for no reason.
SVC_PATH="$(systemctl show auralis-portal.service --property=Environment --value 2>/dev/null \
            | tr ' ' '\n' | sed -n 's/^PATH=//p' | head -1)"
[ -n "$SVC_PATH" ] || SVC_PATH="$SVC_HOME/.local/bin:$SVC_HOME/bin:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"

# Through a FILE, not an inlined shell expansion. This used to embed the JSON
# with \${PF_OUT@Q}, which is bash ANSI-C quoting (\$'...') — valid bash, and an
# instant SyntaxError once Python parses it, which dumped the whole payload.
PF_JSON="$(mktemp)"
runuser -u "$SVC_USER" -- env HOME="$SVC_HOME" PATH="$SVC_PATH" \
  "$PY3" "$PORTAL_DIR/tools/preflight.py" \
  --env-file "$ENV_FILE" --json --net --no-pdf --no-agent >"$PF_JSON" 2>&1 || true
"$PY3" - "$PF_JSON" <<'PFPY' || warn "could not parse preflight output — run it by hand"
import json, sys, pathlib
raw = pathlib.Path(sys.argv[1]).read_text(errors="replace")
i = raw.find("{")
if i < 0:
    print("   ! preflight produced no JSON:", " ".join(raw.split())[-200:]); sys.exit(1)
d = json.loads(raw[i:])
mark = {"ok": " ok ", "warn": "WARN", "fail": "FAIL"}
for c in d.get("checks", []):
    if c.get("name") in ("email", "smtp_login", "imap_login"):
        print("   %s %-11s %s" % (mark.get(str(c.get("severity")), "FAIL"),
                                  c["name"], " ".join(str(c.get("detail", "")).split())))
PFPY
rm -f "$PF_JSON"

# ── optional: one real message, end to end ───────────────────────────────────
if [ -n "$TEST_TO" ]; then
  step "Test message to $TEST_TO"
  if [ "$PLATFORM" = "server" ]; then RUNAS=(runuser -u "$SVC_USER" -- env HOME="$SVC_HOME" "$PY3")
  else RUNAS=("$PY3"); fi
  "${RUNAS[@]}" - \
    "$PORTAL_DIR" "$TEST_TO" "$ENV_FILE" <<'PY' || warn "the test message did not go through — see above"
import os, pathlib, sys
portal, to, envf = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
sys.path.insert(0, str(portal))
for line in pathlib.Path(envf).read_text().splitlines():
    if line.startswith(("AURALIS_", "CLAUDE_")) and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)
from lib import mailer
from email.message import EmailMessage
m = EmailMessage()
m["Subject"] = "Auralis Natura — email path test"
m["From"] = os.environ.get("AURALIS_FROM_EMAIL", "team@auralisnatura.com")
m["To"] = to
m.set_content("If you are reading this in Gmail Drafts, the server can produce client mail.\n"
              "Sent by portal/deploy/enable_email.sh. Safe to delete.\n")
print("   result:", mailer.deliver(m, "_email-test"))
PY
  say "in draft mode this lands in Gmail Drafts, NOT in $TEST_TO's inbox — open Gmail to see it"
fi

printf '\n%s  EMAIL IS ON (mode=%s).%s\n' "$C_G" "$MODE" "$C_0"
cat <<EOF

  What happens now: the console produces access-details, appointment-reminder,
  report and feedback mails as GMAIL DRAFTS for $SMTP_USER. Nothing is sent
  automatically — you open Gmail, read it, click Send.

  Turn it off again:  sed -i 's/^AURALIS_EMAIL_MODE=.*/AURALIS_EMAIL_MODE=off/' $ENV_FILE && systemctl restart $UNIT
  Re-test the stored password:  bash $0 --retest
EOF
