#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

PYTHON="$PROJECT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="$(command -v python3 || true)"
fi
if [ -z "$PYTHON" ]; then
  echo "Python 3 is required." >&2
  exit 1
fi

HOST="${TASK_DIGEST_DEMO_HOST:-127.0.0.1}"
PORT="${TASK_DIGEST_DEMO_PORT:-8777}"
URL="http://$HOST:$PORT"

if [ "${1:-}" = "--static" ]; then
  exec "$PYTHON" -m task_digest --demo --open-report
fi

if command -v open >/dev/null 2>&1; then
  (sleep 1; open "$URL") >/dev/null 2>&1 &
fi
exec "$PYTHON" -m task_digest.dashboard --demo --host "$HOST" --port "$PORT"
