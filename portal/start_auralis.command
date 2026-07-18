#!/bin/bash
# Auralis portal launcher (macOS). Double-click to run.
#
# Starts BOTH the Flask server AND the Cloudflare tunnel and keeps each alive:
#   • the tunnel is supervised — if it drops (Error 1033) it auto-restarts in 5s
#   • the server auto-restarts and self-updates from GitHub main every ~120s
#   • the Mac is kept awake (caffeinate)
# One window, one thing to start. Ctrl-C stops everything cleanly.
cd "$(dirname "$0")" || exit 1
SELF="$PWD/$(basename "$0")"; SELF_HASH="$(shasum "$SELF" 2>/dev/null | awk '{print $1}')"

# --- load .env safely: ignore comments/blank lines, export KEY=VALUE only ---
if [ -f .env ]; then
  while IFS= read -r line; do
    case "$line" in ''|\#*) continue;; esac
    key="${line%%=*}"; val="${line#*=}"
    export "${key// /}"="$val"
  done < .env
fi
export PYTHONUNBUFFERED=1

# keep the Mac awake for as long as this launcher runs
caffeinate -dimsu & CAF=$!

# --- Cloudflare tunnel command ---
# Prefer TUNNEL_CMD from .env; else the auralis tunnel config file; else a named tunnel.
# Must route api.auralisnatura.com -> http://127.0.0.1:${AURALIS_PORT:-5056}.
# NOTE: use the *auralis* tunnel/config, NOT Paramur's (that mix-up caused past 1033s).
TUNNEL_CFG="${AURALIS_TUNNEL_CONFIG:-$HOME/.cloudflared/auralis.yml}"
if [ -z "$TUNNEL_CMD" ]; then
  if [ -f "$TUNNEL_CFG" ]; then
    TUNNEL_CMD="cloudflared tunnel --config $TUNNEL_CFG run"
  elif [ -n "$AURALIS_TUNNEL" ]; then
    TUNNEL_CMD="cloudflared tunnel run $AURALIS_TUNNEL"
  fi
fi

# --- tunnel supervisor (auto-restart) ---
TUN=""
if command -v cloudflared >/dev/null 2>&1 && [ -n "$TUNNEL_CMD" ]; then
  ( while true; do
      echo "🌐 starting Cloudflare tunnel: $TUNNEL_CMD"
      eval "$TUNNEL_CMD"
      echo "⚠ tunnel exited (code $?) — restarting in 5s"
      sleep 5
    done ) &
  TUN=$!
  echo "🌐 tunnel supervisor up (pid $TUN)"
else
  echo "⚠ Cloudflare tunnel NOT started — the site shows Error 1033 until it runs:"
  command -v cloudflared >/dev/null 2>&1 || echo "   • cloudflared not installed →  brew install cloudflared"
  [ -f "$TUNNEL_CFG" ] || echo "   • missing $TUNNEL_CFG → copy deploy/auralis-tunnel.example.yml there and fill the tunnel id + credentials, or set TUNNEL_CMD in .env"
fi

# --- clean shutdown: stop the tunnel (and its cloudflared child), server, caffeinate ---
cleanup() {
  [ -n "$TUN" ] && { pkill -P "$TUN" 2>/dev/null; kill "$TUN" 2>/dev/null; }  # targeted: only our cloudflared
  kill "$SRV" 2>/dev/null
  kill "$CAF" 2>/dev/null
}
trap cleanup EXIT INT TERM

# --- Flask server (self-update + auto-restart) ---
while true; do
  git fetch origin main --quiet 2>/dev/null
  if [ -n "$(git rev-parse origin/main 2>/dev/null)" ] && [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
    echo "↻ updating"; git reset --hard origin/main --quiet    # clients.json + auralis.db* are git-ignored → preserved
    if ! python3 -m pip install -q -r requirements.txt; then echo "⚠ pip install failed — check dependencies"; fi
    # if the launcher itself changed, reload it so launcher updates activate with no manual restart
    NEW_HASH="$(shasum "$SELF" 2>/dev/null | awk '{print $1}')"
    if [ -n "$NEW_HASH" ] && [ "$NEW_HASH" != "$SELF_HASH" ]; then
      echo "↻ launcher changed — reloading itself"; cleanup; exec "$SELF"
    fi
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
