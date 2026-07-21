#!/bin/bash
set -eu

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# Make the repository package importable for helper scripts that are executed
# by file path during setup. This avoids depending on the caller's working
# directory or an editable package installation.
export PYTHONPATH="$PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "Task Digest currently supports macOS only." >&2
  exit 1
fi

find_python() {
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if (3, 11) <= sys.version_info < (3, 13) else 1)
PY
      then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

PYTHON="$(find_python || true)"
if [ -z "$PYTHON" ]; then
  echo "Python 3.11 or 3.12 is required." >&2
  echo "With Homebrew: brew install python@3.12" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Creating virtual environment with $PYTHON..."
  "$PYTHON" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example."
fi

echo
echo "Asana authentication"
if ! python -m task_digest.keychain check-asana >/dev/null 2>&1; then
  echo "Paste an Asana personal access token when prompted. It is stored in macOS Keychain."
  python -m task_digest.keychain store-asana
else
  echo "Asana token already exists in macOS Keychain."
fi

echo
python scripts/list_asana_workspaces.py
printf '\nEnter the Asana workspace GID to use: '
read -r ASANA_WORKSPACE_GID
if [ -z "$ASANA_WORKSPACE_GID" ]; then
  echo "A workspace GID is required." >&2
  exit 1
fi

printf '\nEnable GitHub integration? [Y/n]: '
read -r ENABLE_GITHUB
ENABLE_GITHUB="${ENABLE_GITHUB:-Y}"
GITHUB_REPOSITORIES=""
if [[ "$ENABLE_GITHUB" =~ ^[Yy]$ ]]; then
  if ! command -v gh >/dev/null 2>&1; then
    echo "GitHub CLI is required. Install it with: brew install gh" >&2
    exit 1
  fi
  if ! gh auth status --hostname github.com >/dev/null 2>&1; then
    echo "Starting GitHub browser authentication..."
    gh auth login --web --git-protocol https --skip-ssh-key
  fi
  printf 'Comma-separated GitHub repositories (owner/repository): '
  read -r GITHUB_REPOSITORIES
  if [ -z "$GITHUB_REPOSITORIES" ]; then
    echo "At least one repository is required when GitHub integration is enabled." >&2
    exit 1
  fi
fi

python - "$ASANA_WORKSPACE_GID" "$GITHUB_REPOSITORIES" "$ENABLE_GITHUB" <<'PY'
from pathlib import Path
import re
import sys

path = Path('.env')
workspace, repositories, enabled = sys.argv[1:4]
use_github = enabled.lower().startswith('y')
updates = {
    'ASANA_WORKSPACE_GID': workspace,
    'GITHUB_REPOSITORIES': repositories,
    'INCLUDE_GITHUB_REVIEWS': str(use_github).lower(),
    'INCLUDE_GITHUB_AUTHORED_PRS': str(use_github).lower(),
    'INCLUDE_GITHUB_ASSIGNED_ISSUES': str(use_github).lower(),
    'INCLUDE_GITHUB_MENTIONS': str(use_github).lower(),
    'INCLUDE_LINKED_PR_STATUS': str(use_github).lower(),
}
lines = path.read_text(encoding='utf-8').splitlines()
seen = set()
out = []
for line in lines:
    match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=', line)
    if match and match.group(1) in updates:
        key = match.group(1)
        out.append(f'{key}={updates[key]}')
        seen.add(key)
    else:
        out.append(line)
for key, value in updates.items():
    if key not in seen:
        out.append(f'{key}={value}')
path.write_text('\n'.join(out).rstrip() + '\n', encoding='utf-8')
PY

echo
echo "Running test suite..."
python -m pytest -q

echo
echo "Building and installing Task Digest..."
scripts/install_all.sh

echo
echo "Setup complete. Open http://127.0.0.1:8765 or use the Task Digest menu-bar item."
