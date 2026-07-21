#!/bin/bash
set -eu

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "Task Digest currently supports macOS only." >&2
  exit 1
fi

if [ ! -x "$PROJECT_DIR/.venv/bin/python" ]; then
  echo "Virtual environment not found. Run scripts/setup_local.sh first." >&2
  exit 1
fi

"$PROJECT_DIR/.venv/bin/python" -m pip install -r "$PROJECT_DIR/requirements.txt"
"$PROJECT_DIR/scripts/install_launch_agent.sh"
"$PROJECT_DIR/scripts/install_native_app.sh"

echo "Task Digest is installed: native app, scheduled notifications, dashboard, and menu bar."
echo "Optional notification buttons: brew install vjeantet/tap/alerter"
