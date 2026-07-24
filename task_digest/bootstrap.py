from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values

from . import __version__
from .asana_client import AsanaClient
from .keychain import KeychainItem, read_secret, store_secret

APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "Task Digest"
PROJECT_PATH_FILE = APP_SUPPORT_DIR / "project_path"
LOGIN_AGENT = Path.home() / "Library" / "LaunchAgents" / "app.taskdigest.macos.plist"
RUNTIME_DIRS = ("state", "logs", "output", "history", "backups")


def is_bundled() -> bool:
    return bool(getattr(sys, "frozen", False)) or ".app/Contents/MacOS/" in str(Path(sys.executable))


def _default_env_text() -> str:
    from importlib.resources import files

    try:
        return files("task_digest").joinpath("defaults.env").read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError):
        resource = Path(sys.executable).resolve().parent.parent / "Resources" / "defaults.env"
        if resource.is_file():
            return resource.read_text(encoding="utf-8")
        raise


def is_source_project(path: Path) -> bool:
    return (path / ".env").is_file() and (path / "task_digest").is_dir()


def ensure_runtime_layout(root: Path = APP_SUPPORT_DIR) -> Path:
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    for name in RUNTIME_DIRS:
        (root / name).mkdir(parents=True, exist_ok=True)
    env_path = root / ".env"
    if not env_path.exists():
        env_path.write_text(_default_env_text(), encoding="utf-8")
        try:
            env_path.chmod(0o600)
        except OSError:
            pass
    (root / "VERSION").write_text(__version__ + "\n", encoding="utf-8")
    return root


def resolve_runtime_dir(
    env: Mapping[str, str] | None = None,
    path_file: Path = PROJECT_PATH_FILE,
    cwd: Path | None = None,
    fallback_dir: Path = APP_SUPPORT_DIR,
) -> tuple[Path, bool]:
    values = env if env is not None else os.environ
    candidates: list[Path] = []
    configured = values.get("TASK_DIGEST_PROJECT_DIR", "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())
    if path_file.is_file():
        try:
            stored = path_file.read_text(encoding="utf-8").strip()
        except OSError:
            stored = ""
        if stored:
            candidates.append(Path(stored).expanduser())
    candidates.append(cwd or Path.cwd())
    for candidate in candidates:
        resolved = candidate.resolve()
        if is_source_project(resolved):
            return resolved, True
    return ensure_runtime_layout(fallback_dir), False


def _replace_env_value(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    prefix = key + "="
    changed = False
    result: list[str] = []
    for line in lines:
        if line.startswith(prefix):
            result.append(prefix + value)
            changed = True
        else:
            result.append(line)
    if not changed:
        result.append(prefix + value)
    path.write_text("\n".join(result) + "\n", encoding="utf-8")


def onboarding_required(runtime_dir: Path) -> bool:
    values = dotenv_values(runtime_dir / ".env")
    workspace = str(values.get("ASANA_WORKSPACE_GID") or "").strip()
    service = str(values.get("ASANA_TOKEN_KEYCHAIN_SERVICE") or "app.taskdigest.asana")
    account = str(values.get("ASANA_TOKEN_KEYCHAIN_ACCOUNT") or "asana")
    return not workspace or not read_secret(KeychainItem(service, account))


def _run_applescript(script: str) -> str:
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "Setup was cancelled").strip())
    return result.stdout.strip()


def _apple_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def run_first_launch_setup(runtime_dir: Path) -> None:
    env_path = runtime_dir / ".env"
    values = dotenv_values(env_path)
    service = str(values.get("ASANA_TOKEN_KEYCHAIN_SERVICE") or "app.taskdigest.asana")
    account = str(values.get("ASANA_TOKEN_KEYCHAIN_ACCOUNT") or "asana")
    item = KeychainItem(service, account)
    token = read_secret(item)
    if not token:
        token = _run_applescript(
            'text returned of (display dialog "Paste an Asana personal access token. '
            'It will be stored in your macOS Keychain." default answer "" with hidden answer '
            'buttons {"Cancel", "Continue"} default button "Continue" with title "Task Digest setup")'
        ).strip()
        if not token:
            raise RuntimeError("An Asana token is required to finish setup.")
        store_secret(item, token)

    workspace_gid = str(values.get("ASANA_WORKSPACE_GID") or "").strip()
    if workspace_gid:
        return

    client = AsanaClient(token)
    try:
        workspaces = client.list_workspaces()
    finally:
        client.close()
    if not workspaces:
        raise RuntimeError("No Asana workspaces were returned for this account.")
    choices = [
        (str(row.get("gid") or ""), str(row.get("name") or "Unnamed workspace"))
        for row in workspaces
        if row.get("gid")
    ]
    if len(choices) == 1:
        selected_gid = choices[0][0]
    else:
        listing = "\\n".join(f"{index + 1}. {name}" for index, (_, name) in enumerate(choices))
        response = _run_applescript(
            'text returned of (display dialog "Choose the Asana workspace number:\\n\\n'
            + _apple_string(listing)
            + '" default answer "1" buttons {"Cancel", "Continue"} default button "Continue" '
            'with title "Task Digest setup")'
        )
        try:
            position = int(response.strip()) - 1
            selected_gid = choices[position][0]
        except (ValueError, IndexError) as exc:
            raise RuntimeError("The selected workspace number was not valid.") from exc
    _replace_env_value(env_path, "ASANA_WORKSPACE_GID", selected_gid)


def ensure_login_agent(runtime_dir: Path, executable: Path | None = None) -> Path | None:
    if sys.platform != "darwin" or not is_bundled():
        return None
    executable = (executable or Path(sys.executable)).resolve()
    LOGIN_AGENT.parent.mkdir(parents=True, exist_ok=True)
    logs = runtime_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>app.taskdigest.macos</string>
  <key>ProgramArguments</key><array><string>{executable}</string></array>
  <key>WorkingDirectory</key><string>{runtime_dir}</string>
  <key>EnvironmentVariables</key><dict><key>TASK_DIGEST_DATA_DIR</key><string>{runtime_dir}</string></dict>
  <key>LimitLoadToSessionType</key><string>Aqua</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ProcessType</key><string>Interactive</string>
  <key>ThrottleInterval</key><integer>15</integer>
  <key>StandardOutPath</key><string>{logs / "app.stdout.log"}</string>
  <key>StandardErrorPath</key><string>{logs / "app.stderr.log"}</string>
</dict>
</plist>
'''
    LOGIN_AGENT.write_text(plist, encoding="utf-8")
    return LOGIN_AGENT
