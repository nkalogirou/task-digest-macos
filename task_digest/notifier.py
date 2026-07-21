from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _apple_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def notify(
    title: str,
    body: str,
    subtitle: str = "Task summary",
    open_url: str | None = None,
    actionable: bool = False,
    workspace_file: str | None = None,
    snooze_minutes: int = 60,
) -> None:
    """Show a macOS notification.

    When Alerter is installed, a detached helper provides Open Dashboard and
    Snooze notifications actions without blocking the scheduled digest. The
    simpler terminal-notifier and osascript fallbacks remain available.
    """
    alerter = shutil.which("alerter")
    if actionable and alerter and open_url and workspace_file:
        command = [
            sys.executable,
            "-m",
            "task_digest.notification_worker",
            "--alerter",
            alerter,
            "--title",
            title,
            "--subtitle",
            subtitle,
            "--message",
            body,
            "--url",
            open_url,
            "--workspace-file",
            workspace_file,
            "--snooze-minutes",
            str(max(1, snooze_minutes)),
        ]
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=dict(os.environ),
        )
        return

    terminal_notifier = shutil.which("terminal-notifier")
    if terminal_notifier:
        args = [
            terminal_notifier,
            "-title",
            title,
            "-subtitle",
            subtitle,
            "-message",
            body,
            "-sound",
            "default",
            "-group",
            "task-digest",
        ]
        if open_url:
            args.extend(["-open", open_url])
        subprocess.run(args, check=True)
        return

    script = (
        f'display notification "{_apple_escape(body)}" '
        f'with title "{_apple_escape(title)}" '
        f'subtitle "{_apple_escape(subtitle)}" sound name "default"'
    )
    subprocess.run(["osascript", "-e", script], check=True)


def open_report(path: Path) -> None:
    subprocess.run(["open", str(path)], check=True)


def open_location(url: str) -> None:
    subprocess.run(["open", url], check=True)
