#!/bin/bash
set -euo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
  echo "Release bundles can only be built on macOS." >&2
  exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-$PROJECT_DIR/.venv/bin/python}"
VERSION="$(tr -d '[:space:]' < "$PROJECT_DIR/VERSION")"
APP_NAME="Task Digest.app"
APP="$PROJECT_DIR/dist/$APP_NAME"
RELEASE_DIR="$PROJECT_DIR/release"
STAGING="$PROJECT_DIR/build/release-staging"
IDENTITY="${APPLE_SIGNING_IDENTITY:--}"
ENTITLEMENTS="$PROJECT_DIR/packaging/entitlements.plist"
NOTARIZE="${NOTARIZE:-0}"

if [ ! -x "$PYTHON" ]; then
  echo "Python environment not found at $PYTHON" >&2
  exit 1
fi

"$PYTHON" -m pip install -r "$PROJECT_DIR/requirements.txt" -r "$PROJECT_DIR/requirements-macos.txt"
rm -rf "$PROJECT_DIR/build" "$PROJECT_DIR/dist" "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

PYPROJECT="$PROJECT_DIR/pyproject.toml"
STASH="$PROJECT_DIR/.pyproject.toml.py2app-build"
restore_pyproject() {
  if [ -f "$STASH" ]; then mv "$STASH" "$PYPROJECT"; fi
}
trap restore_pyproject EXIT INT TERM
if [ -f "$PYPROJECT" ]; then mv "$PYPROJECT" "$STASH"; fi
(
  cd "$PROJECT_DIR"
  "$PYTHON" setup_app.py py2app
)
restore_pyproject
trap - EXIT INT TERM

if [ ! -d "$APP" ]; then
  echo "Build did not create $APP" >&2
  exit 1
fi

sign_macho() {
  local path="$1"
  if /usr/bin/file "$path" | /usr/bin/grep -q 'Mach-O'; then
    if [ "$IDENTITY" = "-" ]; then
      /usr/bin/codesign --force --sign - "$path"
    else
      /usr/bin/codesign --force --options runtime --timestamp --sign "$IDENTITY" "$path"
    fi
  fi
}

while IFS= read -r -d '' file; do sign_macho "$file"; done < <(
  /usr/bin/find "$APP/Contents" -type f \( -name '*.so' -o -name '*.dylib' -o -perm -111 \) -print0
)

if [ "$IDENTITY" = "-" ]; then
  /usr/bin/codesign --force --deep --sign - "$APP"
else
  /usr/bin/codesign --force --deep --options runtime --timestamp \
    --entitlements "$ENTITLEMENTS" --sign "$IDENTITY" "$APP"
fi
/usr/bin/codesign --verify --deep --strict --verbose=2 "$APP"

if [ "$NOTARIZE" = "1" ]; then
  : "${APPLE_ID:?APPLE_ID is required for notarization}"
  : "${APPLE_APP_SPECIFIC_PASSWORD:?APPLE_APP_SPECIFIC_PASSWORD is required for notarization}"
  : "${APPLE_TEAM_ID:?APPLE_TEAM_ID is required for notarization}"
  if [ "$IDENTITY" = "-" ]; then
    echo "Notarization requires a Developer ID Application identity." >&2
    exit 1
  fi
  NOTARY_ZIP="$PROJECT_DIR/build/Task-Digest-notary.zip"
  /usr/bin/ditto -c -k --keepParent "$APP" "$NOTARY_ZIP"
  /usr/bin/xcrun notarytool submit "$NOTARY_ZIP" \
    --apple-id "$APPLE_ID" \
    --password "$APPLE_APP_SPECIFIC_PASSWORD" \
    --team-id "$APPLE_TEAM_ID" \
    --wait
  /usr/bin/xcrun stapler staple "$APP"
  /usr/bin/xcrun stapler validate "$APP"
fi

rm -rf "$STAGING"
mkdir -p "$STAGING"
/usr/bin/ditto "$APP" "$STAGING/$APP_NAME"
/bin/ln -s /Applications "$STAGING/Applications"
DMG="$RELEASE_DIR/Task-Digest-$VERSION.dmg"
/usr/bin/hdiutil create -volname "Task Digest" -srcfolder "$STAGING" -ov -format UDZO "$DMG"

ZIP="$RELEASE_DIR/Task-Digest-$VERSION-macOS.zip"
/usr/bin/ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"

if [ "$NOTARIZE" = "1" ]; then
  /usr/bin/xcrun notarytool submit "$DMG" \
    --apple-id "$APPLE_ID" \
    --password "$APPLE_APP_SPECIFIC_PASSWORD" \
    --team-id "$APPLE_TEAM_ID" \
    --wait
  /usr/bin/xcrun stapler staple "$DMG"
  /usr/bin/xcrun stapler validate "$DMG"
  /usr/sbin/spctl --assess --type execute --verbose=2 "$APP"
fi

(
  cd "$RELEASE_DIR"
  /usr/bin/shasum -a 256 "$(basename "$DMG")" "$(basename "$ZIP")" > SHA256SUMS.txt
)

echo "Release artifacts created in $RELEASE_DIR"
ls -lh "$RELEASE_DIR"
