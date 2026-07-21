#!/bin/bash
set -eu
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
"$PROJECT_DIR/.venv/bin/python" - <<'PY'
from task_digest.config import Config
from task_digest.notifier import notify

config = Config.load()
notify(
    "Task Digest test",
    "Automatic notifications are working.",
    "Open the dashboard or snooze alerts",
    open_url=config.dashboard_url,
    actionable=config.actionable_notifications,
    workspace_file=config.workspace_file,
    snooze_minutes=config.notification_snooze_minutes,
)
PY
