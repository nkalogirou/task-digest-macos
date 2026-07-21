#!/bin/bash
set -eu
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
if [ ! -x "$PROJECT_DIR/.venv/bin/python" ]; then
  echo "Create the virtual environment first."
  exit 1
fi
"$PROJECT_DIR/.venv/bin/python" -m task_digest.keychain store-asana
python3 - <<'PY'
from pathlib import Path
path = Path('.env')
if not path.exists():
    raise SystemExit
lines = path.read_text(encoding='utf-8').splitlines()
output = []
for line in lines:
    if line.startswith('ASANA_TOKEN='):
        output.append('# ASANA_TOKEN moved to macOS Keychain')
    else:
        output.append(line)
if not any(line.startswith('ASANA_TOKEN_KEYCHAIN_SERVICE=') for line in output):
    output.append('ASANA_TOKEN_KEYCHAIN_SERVICE=app.taskdigest.asana')
if not any(line.startswith('ASANA_TOKEN_KEYCHAIN_ACCOUNT=') for line in output):
    output.append('ASANA_TOKEN_KEYCHAIN_ACCOUNT=asana')
path.write_text('\n'.join(output) + '\n', encoding='utf-8')
PY
echo "The token was removed from .env and stored in your login Keychain."
