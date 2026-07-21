#!/bin/bash
set -eu
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
PLIST="$HOME/Library/LaunchAgents/app.taskdigest.scheduler.plist"
LABEL="app.taskdigest.scheduler"
mkdir -p "$HOME/Library/LaunchAgents" "$PROJECT_DIR/logs" "$PROJECT_DIR/history"
TIMES="$($PYTHON - "$PROJECT_DIR/.env" <<'PY'
from pathlib import Path
import sys
from dotenv import dotenv_values
values = dotenv_values(Path(sys.argv[1]))
def parts(key, default):
    value = str(values.get(key) or default)
    hour, minute = value.split(':', 1)
    return int(hour), int(minute)
mh, mm = parts('MORNING_TIME', '10:00')
eh, em = parts('EVENING_TIME', '17:30')
print(mh, mm, eh, em)
PY
)"
set -- $TIMES
MORNING_HOUR="$1"
MORNING_MINUTE="$2"
EVENING_HOUR="$3"
EVENING_MINUTE="$4"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PROJECT_DIR/scripts/run_digest.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$PROJECT_DIR</string>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>$MORNING_HOUR</integer><key>Minute</key><integer>$MORNING_MINUTE</integer></dict>
    <dict><key>Hour</key><integer>$EVENING_HOUR</integer><key>Minute</key><integer>$EVENING_MINUTE</integer></dict>
  </array>
  <key>StandardOutPath</key>
  <string>$PROJECT_DIR/logs/launchd.stdout.log</string>
  <key>StandardErrorPath</key>
  <string>$PROJECT_DIR/logs/launchd.stderr.log</string>
</dict>
</plist>
EOF
plutil -lint "$PLIST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if launchctl bootstrap "gui/$(id -u)" "$PLIST"; then
  launchctl enable "gui/$(id -u)/$LABEL" || true
else
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
fi
echo "Installed: $PLIST"
printf 'Runs at %02d:%02d and %02d:%02d using your Mac current timezone and shows a notification.\n' \
  "$MORNING_HOUR" "$MORNING_MINUTE" "$EVENING_HOUR" "$EVENING_MINUTE"
echo "The Python script ignores Saturday and Sunday."
