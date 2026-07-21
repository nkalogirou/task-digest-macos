#!/bin/bash
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
  echo "The native Task Digest app can only be built on macOS." >&2
  exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
APP_NAME="Task Digest.app"
APP_DEST="$HOME/Applications/$APP_NAME"
APP_EXEC="$APP_DEST/Contents/MacOS/Task Digest"
APP_SUPPORT="$HOME/Library/Application Support/Task Digest"
PLIST="$HOME/Library/LaunchAgents/app.taskdigest.macos.plist"
LABEL="app.taskdigest.macos"

mkdir -p "$HOME/Applications" "$HOME/Library/LaunchAgents" "$APP_SUPPORT" "$PROJECT_DIR/logs"
printf '%s\n' "$PROJECT_DIR" > "$APP_SUPPORT/project_path"

"$PYTHON" -m pip install -r "$PROJECT_DIR/requirements-macos.txt"
rm -rf "$PROJECT_DIR/build" "$PROJECT_DIR/dist"

# py2app 0.28.9+ rejects any install_requires metadata. Setuptools reads
# [project].dependencies from pyproject.toml as install_requires even though
# runtime dependencies are already installed in the virtual environment.
# Temporarily hide pyproject.toml for the dedicated app-bundle build and always
# restore it, including when the build fails or is interrupted.
PYPROJECT="$PROJECT_DIR/pyproject.toml"
PYPROJECT_STASH="$PROJECT_DIR/.pyproject.toml.py2app-build"
restore_pyproject() {
  if [ -f "$PYPROJECT_STASH" ]; then
    mv "$PYPROJECT_STASH" "$PYPROJECT"
  fi
}
trap restore_pyproject EXIT INT TERM
if [ -f "$PYPROJECT" ]; then
  mv "$PYPROJECT" "$PYPROJECT_STASH"
fi
(
  cd "$PROJECT_DIR"
  "$PYTHON" setup_app.py py2app
)
restore_pyproject
trap - EXIT INT TERM

if [ ! -d "$PROJECT_DIR/dist/$APP_NAME" ]; then
  echo "The app build completed without creating dist/$APP_NAME." >&2
  exit 1
fi

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
pkill -f "Task Digest.app/Contents/MacOS/Task Digest" 2>/dev/null || true

rm -rf "$APP_DEST"
/usr/bin/ditto "$PROJECT_DIR/dist/$APP_NAME" "$APP_DEST"
/usr/bin/codesign --force --deep --sign - "$APP_DEST" >/dev/null 2>&1 || true

# Remove the old split dashboard/menu-bar agents. The native app now owns both.
for OLD_LABEL in \
  app.taskdigest.dashboard \
  app.taskdigest.menubar
do
  launchctl bootout "gui/$(id -u)/$OLD_LABEL" 2>/dev/null || true
done
rm -f \
  "$HOME/Library/LaunchAgents/app.taskdigest.dashboard.plist" \
  "$HOME/Library/LaunchAgents/app.taskdigest.menubar.plist"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$APP_EXEC</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>TASK_DIGEST_PROJECT_DIR</key>
    <string>$PROJECT_DIR</string>
  </dict>
  <key>WorkingDirectory</key>
  <string>$PROJECT_DIR</string>
  <key>LimitLoadToSessionType</key>
  <string>Aqua</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>
  <key>ProcessType</key>
  <string>Interactive</string>
  <key>ThrottleInterval</key>
  <integer>15</integer>
  <key>StandardOutPath</key>
  <string>$PROJECT_DIR/logs/app.stdout.log</string>
  <key>StandardErrorPath</key>
  <string>$PROJECT_DIR/logs/app.stderr.log</string>
</dict>
</plist>
EOF

plutil -lint "$PLIST"
if launchctl bootstrap "gui/$(id -u)" "$PLIST"; then
  launchctl enable "gui/$(id -u)/$LABEL" || true
  launchctl kickstart -k "gui/$(id -u)/$LABEL" || true
else
  echo "The login agent could not be registered. Starting the app directly instead." >&2
  open "$APP_DEST"
fi

sleep 2
open "http://127.0.0.1:8765"
echo "Native Task Digest installed at: $APP_DEST"
echo "It now owns both the dashboard and menu-bar icon and starts at login."
