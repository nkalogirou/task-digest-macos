from __future__ import annotations

import argparse
import subprocess
from datetime import datetime

from .notifier import open_location
from .workspace import WorkspaceState


def main() -> int:
    parser = argparse.ArgumentParser(description="Handle an actionable Task Digest notification.")
    parser.add_argument("--alerter", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--subtitle", default="Task summary")
    parser.add_argument("--message", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--workspace-file", required=True)
    parser.add_argument("--snooze-minutes", type=int, default=60)
    args = parser.parse_args()

    result = subprocess.run(
        [
            args.alerter,
            "--title",
            args.title,
            "--subtitle",
            args.subtitle,
            "--message",
            args.message,
            "--actions",
            f"Open Dashboard,Snooze {args.snooze_minutes} min",
            "--closeLabel",
            "Dismiss",
            "--sound",
            "default",
            "--group",
            "task-digest",
            "--timeout",
            "3600",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    answer = result.stdout.strip()
    if answer == "Open Dashboard" or answer == "@CONTENTCLICKED":
        open_location(args.url)
    elif answer.startswith("Snooze"):
        WorkspaceState(args.workspace_file).pause_notifications(
            datetime.now().astimezone(),
            args.snooze_minutes,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
