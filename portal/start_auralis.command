#!/bin/bash
# Auralis portal launcher (macOS). Double-click to run. Self-updates from GitHub
# every 120s: a `git push` to main reaches this Mac within ~2 minutes.
cd "$(dirname "$0")" || exit 1
[ -f .env ] && set -a && . ./.env && set +a
export PYTHONUNBUFFERED=1
caffeinate -dimsu &                      # keep the Mac awake while serving
CAF=$!; trap 'kill $CAF 2>/dev/null' EXIT
while true; do
  git fetch origin main --quiet 2>/dev/null
  LOCAL=$(git rev-parse HEAD 2>/dev/null); REMOTE=$(git rev-parse origin/main 2>/dev/null)
  if [ -n "$REMOTE" ] && [ "$LOCAL" != "$REMOTE" ]; then
    echo "↻ updating to $REMOTE"; git reset --hard origin/main --quiet
    python3 -m pip install -q -r requirements.txt 2>/dev/null
  fi
  echo "▶ Auralis portal on http://127.0.0.1:${AURALIS_PORT:-5056}  (Ctrl-C to stop)"
  python3 run.py &
  SRV=$!
  # poll for updates; restart the server when a new commit lands
  while kill -0 $SRV 2>/dev/null; do
    sleep 120
    git fetch origin main --quiet 2>/dev/null
    [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main 2>/dev/null)" ] && { echo "↻ new version"; kill $SRV; break; }
  done
  wait $SRV 2>/dev/null
done
