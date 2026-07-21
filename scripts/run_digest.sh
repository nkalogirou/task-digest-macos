#!/bin/bash
set -eu
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
mkdir -p logs output state
"$PROJECT_DIR/.venv/bin/python" -m task_digest >> "$PROJECT_DIR/logs/launchd.log" 2>&1
