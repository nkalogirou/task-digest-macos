#!/bin/bash
set -eu
for LABEL in \
  app.taskdigest.macos \
  app.taskdigest.dashboard \
  app.taskdigest.scheduler \
  app.taskdigest.menubar
do
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
done
rm -f \
  "$HOME/Library/LaunchAgents/app.taskdigest.macos.plist" \
  "$HOME/Library/LaunchAgents/app.taskdigest.dashboard.plist" \
  "$HOME/Library/LaunchAgents/app.taskdigest.scheduler.plist" \
  "$HOME/Library/LaunchAgents/app.taskdigest.menubar.plist"
rm -rf "$HOME/Applications/Task Digest.app"
rm -f "$HOME/Library/Application Support/Task Digest/project_path"
echo "Task Digest app and background agents were removed. Local data remains in the project folder."
