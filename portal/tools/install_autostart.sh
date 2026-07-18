#!/bin/bash
# ONE-TIME setup (run once on the Mac): make the Auralis portal fully hands-off.
#
#   cd portal && bash tools/install_autostart.sh
#
# After this, you NEVER touch the Mac again:
#   • launchd starts the launcher at login and RELAUNCHES it if it ever exits/crashes
#   • the launcher runs the Flask server + Cloudflare tunnel (tunnel auto-restarts on drop)
#   • every `git push` to main auto-deploys within ~2 min (server restarts; the launcher
#     even reloads itself when it changes)
# For recovery after a full power-off with nobody logged in, also enable macOS auto-login
# (System Settings → Users & Groups → Automatically log in as …).
set -e

PORTAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCHER="$PORTAL_DIR/start_auralis.command"
LABEL="com.auralis.portal"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

[ -f "$LAUNCHER" ] || { echo "❌ $LAUNCHER not found — run this from the portal folder."; exit 1; }
chmod +x "$LAUNCHER"
mkdir -p "$HOME/Library/LaunchAgents" "$PORTAL_DIR/.logs"

# stop any manually-started launcher so launchd owns the single instance (avoid port clash)
pkill -f "start_auralis.command" 2>/dev/null || true
launchctl unload "$PLIST" 2>/dev/null || true

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$LAUNCHER</string></array>
  <key>WorkingDirectory</key><string>$PORTAL_DIR</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardOutPath</key><string>$PORTAL_DIR/.logs/portal.out.log</string>
  <key>StandardErrorPath</key><string>$PORTAL_DIR/.logs/portal.err.log</string>
</dict>
</plist>
EOF

launchctl load -w "$PLIST"
sleep 2
echo "✅ Auto-start installed and running (label: $LABEL)."
echo "   • Starts at login, relaunches on crash, auto-deploys every push."
echo "   • Logs:  $PORTAL_DIR/.logs/portal.out.log  (and .err.log)"
echo "   • Stop:  launchctl unload $PLIST     Start: launchctl load -w $PLIST"
echo "   • For unattended reboots, enable macOS auto-login."
