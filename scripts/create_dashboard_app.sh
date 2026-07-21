#!/bin/bash
set -eu
APP_DIR="$HOME/Applications"
APP_PATH="$APP_DIR/Task Digest.app"
mkdir -p "$APP_DIR"
rm -rf "$APP_PATH"
osacompile -o "$APP_PATH" \
  -e 'on run' \
  -e 'open location "http://127.0.0.1:8765"' \
  -e 'end run'
echo "Created $APP_PATH"
echo "Open it from Spotlight or drag it to the Dock."
