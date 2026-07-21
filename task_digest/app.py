from __future__ import annotations

import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from .config import Config
from .dashboard import DashboardServer

APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "Task Digest"
PROJECT_PATH_FILE = APP_SUPPORT_DIR / "project_path"


def resolve_project_dir(
    env: Optional[dict[str, str]] = None,
    path_file: Optional[Path] = None,
    cwd: Optional[Path] = None,
) -> Path:
    values = env if env is not None else os.environ
    configured = values.get("TASK_DIGEST_PROJECT_DIR", "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())

    marker = path_file or PROJECT_PATH_FILE
    if marker.is_file():
        try:
            stored = marker.read_text(encoding="utf-8").strip()
        except OSError:
            stored = ""
        if stored:
            candidates.append(Path(stored).expanduser())

    candidates.append(cwd or Path.cwd())

    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / ".env").is_file() and (resolved / "task_digest").is_dir():
            return resolved
    raise RuntimeError(
        "Task Digest could not locate its project folder. Re-run scripts/install_native_app.sh from the project folder."
    )


def dashboard_is_available(host: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_dashboard(config: Config) -> DashboardServer | None:
    if dashboard_is_available(config.dashboard_host, config.dashboard_port):
        return None

    server = DashboardServer((config.dashboard_host, config.dashboard_port), config)
    thread = threading.Thread(
        target=server.serve_forever,
        name="task-digest-dashboard",
        daemon=True,
    )
    thread.start()

    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        if dashboard_is_available(config.dashboard_host, config.dashboard_port):
            return server
        time.sleep(0.1)
    server.shutdown()
    server.server_close()
    raise RuntimeError("The Task Digest dashboard did not start within 8 seconds.")


def _show_startup_error(message: str) -> None:
    escaped = message.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display alert "Task Digest could not start" message "{escaped}" as critical'
    try:
        subprocess.run(["/usr/bin/osascript", "-e", script], check=False, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        pass


def main() -> int:
    server: DashboardServer | None = None
    try:
        project_dir = resolve_project_dir()
        os.chdir(project_dir)
        config = Config.load()
        server = start_dashboard(config)
        from .menubar import main as run_menubar

        return run_menubar()
    except Exception as exc:
        _show_startup_error(str(exc))
        raise
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
