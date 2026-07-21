#!/bin/bash
set -eu
PLIST="$HOME/Library/LaunchAgents/app.taskdigest.scheduler.plist"
LABEL="app.taskdigest.scheduler"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "Removed local task digest schedule."
