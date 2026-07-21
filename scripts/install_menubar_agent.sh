#!/bin/bash
set -eu
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/app.taskdigest.menubar.plist"
LABEL="app.taskdigest.menubar"
mkdir -p "$HOME/Library/LaunchAgents" "$PROJECT_DIR/logs"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>$PROJECT_DIR/.venv/bin/python</string><string>-m</string><string>task_digest.menubar</string>
  </array>
  <key>WorkingDirectory</key><string>$PROJECT_DIR</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>15</integer>
  <key>StandardOutPath</key><string>$PROJECT_DIR/logs/menubar.stdout.log</string>
  <key>StandardErrorPath</key><string>$PROJECT_DIR/logs/menubar.stderr.log</string>
</dict></plist>
EOF
plutil -lint "$PLIST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/$LABEL" || true
echo "Menu bar app installed. Look for the ✓ icon beside the clock."
