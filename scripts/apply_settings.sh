#!/bin/bash
set -eu
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$PROJECT_DIR/logs/settings-apply.log"
APP_PLIST="$HOME/Library/LaunchAgents/app.taskdigest.macos.plist"
mkdir -p "$PROJECT_DIR/logs"
sleep 1
{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Applying dashboard settings"
  "$PROJECT_DIR/scripts/install_launch_agent.sh"
  if [ -f "$APP_PLIST" ]; then
    launchctl kickstart -k "gui/$(id -u)/app.taskdigest.macos" || true
  else
    launchctl kickstart -k "gui/$(id -u)/app.taskdigest.menubar" || true
    launchctl kickstart -k "gui/$(id -u)/app.taskdigest.dashboard" || true
  fi
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Settings applied"
} >> "$LOG_FILE" 2>&1
