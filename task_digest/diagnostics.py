from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from .config import Config


@dataclass(frozen=True)
class ServiceDefinition:
    key: str
    name: str
    label: str
    plist_name: str
    stdout_log: str
    stderr_log: str
    persistent: bool


@dataclass(frozen=True)
class ServiceStatus:
    key: str
    name: str
    label: str
    loaded: bool
    state: str
    pid: int | None
    last_exit_code: int | None
    plist_exists: bool
    detail: str

    @property
    def ok(self) -> bool:
        if not self.loaded or not self.plist_exists:
            return False
        if self.key == "scheduler":
            return self.last_exit_code in {None, 0}
        return self.state == "running"


NATIVE_APP_SERVICE = ServiceDefinition(
    key="app",
    name="Task Digest app",
    label="app.taskdigest.macos",
    plist_name="app.taskdigest.macos.plist",
    stdout_log="app.stdout.log",
    stderr_log="app.stderr.log",
    persistent=True,
)

LEGACY_SERVICES: tuple[ServiceDefinition, ...] = (
    ServiceDefinition(
        key="dashboard",
        name="Dashboard",
        label="app.taskdigest.dashboard",
        plist_name="app.taskdigest.dashboard.plist",
        stdout_log="dashboard.stdout.log",
        stderr_log="dashboard.stderr.log",
        persistent=True,
    ),
    ServiceDefinition(
        key="menubar",
        name="Menu bar",
        label="app.taskdigest.menubar",
        plist_name="app.taskdigest.menubar.plist",
        stdout_log="menubar.stdout.log",
        stderr_log="menubar.stderr.log",
        persistent=True,
    ),
)

SCHEDULER_SERVICE = ServiceDefinition(
    key="scheduler",
    name="Scheduled digest",
    label="app.taskdigest.scheduler",
    plist_name="app.taskdigest.scheduler.plist",
    stdout_log="launchd.stdout.log",
    stderr_log="launchd.stderr.log",
    persistent=False,
)

SERVICES: tuple[ServiceDefinition, ...] = (
    NATIVE_APP_SERVICE,
    *LEGACY_SERVICES,
    SCHEDULER_SERVICE,
)


def active_services(home: Path | None = None) -> tuple[ServiceDefinition, ...]:
    home = home or Path.home()
    native_plist = home / "Library" / "LaunchAgents" / NATIVE_APP_SERVICE.plist_name
    if native_plist.exists():
        return (NATIVE_APP_SERVICE, SCHEDULER_SERVICE)
    return (*LEGACY_SERVICES, SCHEDULER_SERVICE)



def service_definition(key: str) -> ServiceDefinition:
    for service in SERVICES:
        if service.key == key:
            return service
    raise ValueError(f"Unknown Task Digest service: {key}")


def _parse_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    return int(match.group(1)) if match else None


def inspect_service(service: ServiceDefinition, home: Path | None = None) -> ServiceStatus:
    home = home or Path.home()
    plist = home / "Library" / "LaunchAgents" / service.plist_name
    target = f"gui/{os.getuid()}/{service.label}"
    launchctl = shutil.which("launchctl")
    if sys.platform != "darwin" or not launchctl:
        return ServiceStatus(
            key=service.key,
            name=service.name,
            label=service.label,
            loaded=False,
            state="unavailable",
            pid=None,
            last_exit_code=None,
            plist_exists=plist.exists(),
            detail="launchctl is available only on macOS",
        )
    result = subprocess.run(
        [launchctl, "print", target],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=8,
    )
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    if result.returncode != 0:
        return ServiceStatus(
            key=service.key,
            name=service.name,
            label=service.label,
            loaded=False,
            state="not loaded",
            pid=None,
            last_exit_code=None,
            plist_exists=plist.exists(),
            detail=(output.strip() or "Launch Agent is not loaded")[:240],
        )
    state_match = re.search(r"^\s*state\s*=\s*([^\n]+)", output, flags=re.MULTILINE)
    state = state_match.group(1).strip() if state_match else "loaded"
    pid = _parse_int(r"^\s*pid\s*=\s*(\d+)", output)
    last_exit = _parse_int(r"^\s*last exit code\s*=\s*(-?\d+)", output)
    if service.key == "scheduler" and state != "running":
        detail = "Loaded and waiting for the next scheduled time"
    elif state == "running":
        detail = f"Running with PID {pid}" if pid else "Running"
    else:
        detail = f"Loaded; state is {state}"
    if last_exit not in {None, 0}:
        detail += f"; last exit code {last_exit}"
    return ServiceStatus(
        key=service.key,
        name=service.name,
        label=service.label,
        loaded=True,
        state=state,
        pid=pid,
        last_exit_code=last_exit,
        plist_exists=plist.exists(),
        detail=detail,
    )


def inspect_services(home: Path | None = None) -> list[ServiceStatus]:
    return [inspect_service(service, home=home) for service in active_services(home)]


def restart_service(key: str, home: Path | None = None, delayed: bool = False) -> None:
    service = service_definition(key)
    home = home or Path.home()
    plist = home / "Library" / "LaunchAgents" / service.plist_name
    if sys.platform != "darwin":
        raise RuntimeError("Service controls are available only on macOS.")
    launchctl = shutil.which("launchctl")
    if not launchctl:
        raise RuntimeError("The launchctl command was not found.")
    if not plist.is_file():
        raise RuntimeError(f"Launch Agent file is missing: {plist}")
    target = f"gui/{os.getuid()}/{service.label}"

    if service.persistent:
        command = [launchctl, "kickstart", "-k", target]
        probe = subprocess.run(
            [launchctl, "print", target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if probe.returncode != 0:
            command = [launchctl, "bootstrap", f"gui/{os.getuid()}", str(plist)]
    else:
        # A calendar-only agent normally has no running process. Reloading the
        # plist verifies that the schedule is registered without forcing a digest.
        subprocess.run(
            [launchctl, "bootout", target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        command = [launchctl, "bootstrap", f"gui/{os.getuid()}", str(plist)]

    if delayed:
        shell = "sleep 0.8; exec " + " ".join(_shell_quote(part) for part in command)
        subprocess.Popen(
            ["/bin/sh", "-c", shell],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "Could not restart service").strip())


def restart_all_services(home: Path | None = None) -> None:
    home = home or Path.home()
    restart_service("scheduler", home=home)
    native_plist = home / "Library" / "LaunchAgents" / NATIVE_APP_SERVICE.plist_name
    if native_plist.exists():
        # Restart the app after the HTTP response has had time to finish.
        restart_service("app", home=home, delayed=True)
        return
    # Legacy installation: restart the current dashboard last.
    restart_service("menubar", home=home)
    restart_service("dashboard", home=home, delayed=True)


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def next_scheduled_run(config: Config, now: datetime) -> tuple[datetime, str]:
    candidates: list[tuple[datetime, str]] = []
    for offset in range(0, 10):
        day = (now + timedelta(days=offset)).date()
        if day.weekday() >= 5:
            continue
        for label, clock in (("Morning", config.morning_time), ("Evening", config.evening_time)):
            candidate = datetime.combine(day, clock, tzinfo=now.tzinfo)
            if candidate > now:
                candidates.append((candidate, label))
    if not candidates:
        raise RuntimeError("Could not calculate the next scheduled digest.")
    return min(candidates, key=lambda item: item[0])


def github_auth_status(cli_path: str | None = None) -> tuple[bool, str]:
    executable = None
    for candidate in (cli_path, shutil.which("gh"), "/opt/homebrew/bin/gh", "/usr/local/bin/gh"):
        if candidate and Path(candidate).expanduser().is_file():
            executable = str(Path(candidate).expanduser())
            break
    if not executable:
        return False, "GitHub CLI is not installed"
    try:
        result = subprocess.run(
            [executable, "auth", "status", "--active", "--hostname", "github.com"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=12,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    one_line = " ".join(line.strip() for line in output.splitlines() if line.strip())
    return result.returncode == 0, (one_line[:300] or "No authentication details returned")


def tail_log(path: Path, line_count: int = 30) -> str:
    if not path.is_file():
        return "Log file does not exist yet."
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return f"Could not read log: {exc}"
    if not lines:
        return "Log is empty."
    return "\n".join(lines[-max(1, line_count):])


def log_files(project_dir: Path) -> Iterable[tuple[str, str, Path]]:
    logs_dir = project_dir / "logs"
    for service in active_services():
        yield service.key + "-stderr", f"{service.name} errors", logs_dir / service.stderr_log
        yield service.key + "-stdout", f"{service.name} output", logs_dir / service.stdout_log
