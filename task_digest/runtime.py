from __future__ import annotations

import secrets
import shutil
from datetime import datetime
from pathlib import Path


def get_or_create_action_token(path: str) -> str:
    token_path = Path(path).expanduser()
    if token_path.exists():
        token = token_path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    token_path.write_text(token + "\n", encoding="utf-8")
    try:
        token_path.chmod(0o600)
    except OSError:
        pass
    return token


def save_history(report: Path, history_dir: str, now: datetime, period: str) -> Path:
    directory = Path(history_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{now:%Y-%m-%d}-{period}.html"
    shutil.copyfile(report, destination)
    return destination
