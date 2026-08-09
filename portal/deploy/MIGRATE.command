#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  MIGRATE.command — DOUBLE-CLICK THIS ON THE MAC
# ─────────────────────────────────────────────────────────────────────────────
#  Moves the Auralis portal from this Mac to the Hetzner server, so the Mac can
#  be closed for good. Everything that can be automated is; you are asked only
#  where a human genuinely has to decide.
#
#  Finder → the repo → portal → deploy → double-click MIGRATE.command
#
#  Any arguments are passed straight to migrate_to_server.sh, and
#  AURALIS_TARGET picks a different server, e.g.
#      AURALIS_TARGET=root@1.2.3.4 bash MIGRATE.command --allow-stub
#  (If macOS refuses the first time: right-click → Open → Open.)
#
#  It does, in order:
#    1. checks THIS clone actually holds the portal data (.env + auralis.db) —
#       a fresh clone does not, because both are gitignored, and migrating from
#       the wrong clone would ship an empty database over the real one
#    2. brings the clone up to date with the deploy kit, explaining clearly if
#       local commits mean that cannot be done automatically
#    3. runs the full local preflight — nothing remote is touched
#    4. shows you the result and asks whether to go on to the cutover
#    5. hands over to migrate_to_server.sh, which owns the real work
#
#  Written for the Mac's bash 3.2: no associative arrays, no readarray, no ${x,,}.
# ─────────────────────────────────────────────────────────────────────────────
set -Eeuo pipefail

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
PORTAL_DIR="$(cd "$SELF_DIR/.." && pwd)"
REPO_DIR="$(cd "$PORTAL_DIR/.." && pwd)"
BRANCH="${AURALIS_BRANCH:-claude/webpage-launch-styling-rrtfdl}"

if [ -t 1 ]; then B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; D=$'\033[2m'; N=$'\033[0m'
else B=''; G=''; Y=''; R=''; D=''; N=''; fi
say()  { printf '%s\n' "$1"; }
ok()   { printf '   %s✓%s %s\n' "$G" "$N" "$1"; }
info() { printf '   %s·%s %s\n' "$D" "$N" "$1"; }
warn() { printf '   %s!%s %s\n' "$Y" "$N" "$1" >&2; }
step() { printf '\n%s── %s%s\n' "$B" "$1" "$N"; }
# Double-clicked from Finder, the window closes the instant we exit — so every
# exit path pauses, or the operator never sees why it stopped.
hold() { printf '\n%sPress Return to close this window.%s ' "$D" "$N"; read -r _ || true; }
die()  { printf '\n%s✗ %s%s\n' "$R" "$1" "$N" >&2; hold; exit 1; }
trap 'rc=$?; [ $rc -eq 0 ] || { printf "\n%s✗ stopped at line %s (exit %s)%s\n" "$R" "$LINENO" "$rc" "$N" >&2; hold; }' ERR

clear 2>/dev/null || true
printf '%s\n╔════════════════════════════════════════════════════════════╗\n' "$B"
printf   '║   Auralis Natura — migrate the portal to the server        ║\n'
printf   '╚════════════════════════════════════════════════════════════╝%s\n' "$N"
info "repo   $REPO_DIR"

# ── 1. is the data actually here? ────────────────────────────────────────────
step "Checking this is the clone with the portal data"
MISSING=""
[ -f "$PORTAL_DIR/.env" ]        || MISSING="$MISSING portal/.env"
[ -f "$PORTAL_DIR/auralis.db" ]  || MISSING="$MISSING portal/auralis.db"
if [ -n "$MISSING" ]; then
  say ""
  printf '%s   This clone is missing:%s%s\n' "$R" "$MISSING" "$N"
  say ""
  say "   Both files are gitignored on purpose, so a FRESH clone never has them."
  say "   The migration must run from the working copy the portal actually ran in"
  say "   — the one whose Terminal you used to start start_auralis.command."
  say ""
  say "   Find it:"
  say "       ls -la ~/*/portal/.env ~/*/*/portal/.env 2>/dev/null"
  say ""
  say "   Then double-click MIGRATE.command inside THAT copy's portal/deploy/."
  say "   If that copy does not have this file yet, in Terminal:"
  say "       cd <that-copy> && git fetch origin && git merge origin/$BRANCH"
  die "wrong clone — nothing was changed"
fi
ok "portal/.env and portal/auralis.db are here"
[ -f "$PORTAL_DIR/config/clients.json" ] && ok "config/clients.json is here" \
  || warn "no config/clients.json — portal logins will be empty on the server"

# ── 2. bring the kit up to date ──────────────────────────────────────────────
step "Updating this clone"
[ -d "$REPO_DIR/.git" ] || die "not a git repo: $REPO_DIR"
git -C "$REPO_DIR" fetch origin "$BRANCH" --quiet 2>/dev/null \
  || warn "could not reach GitHub — continuing with what is on disk"

CUR="$(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
info "on branch $CUR"
AHEAD=0; BEHIND=0
if git -C "$REPO_DIR" rev-parse --verify --quiet "origin/$BRANCH" >/dev/null; then
  AHEAD="$(git -C "$REPO_DIR" rev-list --count "origin/$BRANCH..HEAD" 2>/dev/null || echo 0)"
  BEHIND="$(git -C "$REPO_DIR" rev-list --count "HEAD..origin/$BRANCH" 2>/dev/null || echo 0)"
fi

if [ "$BEHIND" -eq 0 ]; then
  ok "already has the deploy kit"
elif [ "$AHEAD" -eq 0 ]; then
  # Clean fast-forward: the common case, and safe — no local work exists.
  if git -C "$REPO_DIR" merge --ff-only "origin/$BRANCH" --quiet 2>/dev/null; then
    ok "updated ($BEHIND new commits)"
  else
    warn "fast-forward failed — most likely uncommitted local edits"
    warn "  git -C '$REPO_DIR' status"
    die "could not update this clone safely"
  fi
else
  # Diverged. Their commits are real work; never rebase or reset them silently.
  say ""
  warn "this clone has $AHEAD local commit(s) that are NOT on GitHub,"
  warn "and GitHub has $BEHIND commit(s) this clone does not have."
  say ""
  say "   Your $AHEAD commits are safe and nothing here will touch them, but they"
  say "   have to be merged before the deploy kit is complete in this copy."
  say ""
  say "   See what is local-only:"
  say "       git -C '$REPO_DIR' log --oneline origin/$BRANCH..HEAD"
  say "   Then merge (keeps both sides):"
  say "       git -C '$REPO_DIR' merge origin/$BRANCH"
  say ""
  die "clone diverged — merge first, then double-click this again"
fi

MIG="$PORTAL_DIR/deploy/migrate_to_server.sh"
[ -f "$MIG" ] || die "migrate_to_server.sh is missing after the update — is the merge complete?"
ok "deploy kit present"

# ── 3. preflight — nothing remote ────────────────────────────────────────────
step "Preflight (local only — the server is not touched)"
say ""
PF_RC=0
bash "$MIG" --preflight-only "$@" || PF_RC=$?
if [ "$PF_RC" -ne 0 ]; then
  say ""
  die "preflight failed (exit $PF_RC). Nothing was migrated. Send the output above to Claude."
fi

# ── 4. the decision ──────────────────────────────────────────────────────────
say ""
printf '%s── Ready to migrate%s\n' "$B" "$N"
say ""
say "   Preflight passed. The next step:"
say "     · installs and verifies everything on the server while THIS Mac keeps"
say "       serving — nothing user-visible moves yet"
say "     · then asks you to type a confirmation before the live site switches"
say ""
say "   You can stop at any point. Rollback is one command and stays available."
say ""
printf '   %sStart the migration now? [y/N]%s ' "$B" "$N"
read -r ANS || true
case "${ANS:-}" in
  y|Y|yes|YES) ;;
  *) say ""; ok "Nothing changed. Double-click this again whenever you are ready."; hold; exit 0 ;;
esac

# ── 5. hand over ─────────────────────────────────────────────────────────────
say ""
bash "$MIG" --cutover "$@"
RC=$?
say ""
[ "$RC" -eq 0 ] && ok "migration finished — see the summary above" \
                || warn "migration exited with $RC — read the output above"
hold
exit "$RC"
