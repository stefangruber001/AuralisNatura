#!/bin/bash
# Auralis portal launcher (macOS). Double-click to run. Self-updates from GitHub
# main every ~120s (a `git push` reaches this Mac in ~2 min) and keeps it awake.
cd "$(dirname "$0")" || exit 1

# load .env safely: ignore comments/blank lines, export KEY=VALUE only
if [ -f .env ]; then
  while IFS= read -r line; do
    case "$line" in ''|\#*) continue;; esac
    key="${line%%=*}"; val="${line#*=}"
    export "${key// /}"="$val"
  done < .env
fi
export PYTHONUNBUFFERED=1
caffeinate -dimsu & CAF=$!; trap 'kill $CAF 2>/dev/null' EXIT

while true; do
  git fetch origin main --quiet 2>/dev/null
  if [ -n "$(git rev-parse origin/main 2>/dev/null)" ] && [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
    echo "↻ updating"; git reset --hard origin/main --quiet    # clients.json + auralis.db* are git-ignored → preserved
    if ! python3 -m pip install -q -r requirements.txt; then echo "⚠ pip install failed — check dependencies"; fi
  fi
  echo "▶ Auralis portal — http://127.0.0.1:${AURALIS_PORT:-5056}  (Ctrl-C to stop)"
  python3 run.py & SRV=$!
  while kill -0 $SRV 2>/dev/null; do
    sleep 120
    git fetch origin main --quiet 2>/dev/null
    REMOTE=$(git rev-parse origin/main 2>/dev/null)
    if [ -n "$REMOTE" ] && [ "$(git rev-parse HEAD)" != "$REMOTE" ]; then
      echo "↻ new version — restarting"; kill $SRV 2>/dev/null; wait $SRV 2>/dev/null; break
    fi
  done
  wait $SRV 2>/dev/null
  sleep 3   # backoff so a crash-on-startup can't hot-loop
done
