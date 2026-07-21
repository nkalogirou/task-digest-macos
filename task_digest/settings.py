from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True)
class SettingSpec:
    key: str
    default: str
    kind: str = "text"
    minimum: int | None = None
    maximum: int | None = None


SETTING_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec("ASANA_WORKSPACE_GID", ""),
    SettingSpec("ASANA_PROJECT_GIDS", "", "csv"),
    SettingSpec("EXCLUDE_SECTIONS", "Drafts", "csv"),
    SettingSpec("OPTIONAL_SECTIONS", "Investigations", "csv"),
    SettingSpec("ACTION_STATUSES", "Pending,In Development,Changes Requested,To Do,Ready", "csv"),
    SettingSpec(
        "WAITING_STATUSES",
        "In Review,In Deployment,Blocked,Waiting,Waiting for Review,Waiting for Deployment",
        "csv",
    ),
    SettingSpec("STALE_WAITING_DAYS", "5", "int", 1, 60),
    SettingSpec("SMART_PLAN_MAX_ITEMS", "5", "int", 1, 10),
    SettingSpec("SMART_PLAN_STALE_WAITING_LIMIT", "1", "int", 0, 5),
    SettingSpec("INCLUDE_ASANA_DEPENDENCIES", "true", "bool"),
    SettingSpec("RECENT_COMMENT_LIMIT", "3", "int", 0, 20),
    SettingSpec("ENABLE_ASANA_WRITE_ACTIONS", "false", "bool"),
    SettingSpec("INCLUDE_GITHUB_REVIEWS", "false", "bool"),
    SettingSpec("INCLUDE_GITHUB_AUTHORED_PRS", "false", "bool"),
    SettingSpec("INCLUDE_GITHUB_ASSIGNED_ISSUES", "false", "bool"),
    SettingSpec("INCLUDE_GITHUB_MENTIONS", "false", "bool"),
    SettingSpec("INCLUDE_LINKED_PR_STATUS", "false", "bool"),
    SettingSpec("GITHUB_REPOSITORIES", "", "repos"),
    SettingSpec("GITHUB_CLI_PATH", ""),
    SettingSpec("GITHUB_REVIEW_LIMIT", "50", "int", 1, 200),
    SettingSpec("GITHUB_PR_LIMIT", "50", "int", 1, 200),
    SettingSpec("GITHUB_ISSUE_LIMIT", "50", "int", 1, 200),
    SettingSpec("GITHUB_MENTION_LIMIT", "50", "int", 1, 200),
    SettingSpec("MORNING_TIME", "10:00", "time"),
    SettingSpec("EVENING_TIME", "17:30", "time"),
    SettingSpec("SCHEDULE_WINDOW_MINUTES", "20", "int", 1, 120),
    SettingSpec("DASHBOARD_REFRESH_MINUTES", "5", "int", 1, 120),
    SettingSpec("MENU_REFRESH_MINUTES", "5", "int", 1, 120),
    SettingSpec("ACTIONABLE_NOTIFICATIONS", "true", "bool"),
    SettingSpec("NOTIFICATION_SNOOZE_MINUTES", "60", "int", 5, 1440),
    SettingSpec("OPEN_REPORT", "false", "bool"),
    SettingSpec("OPEN_DASHBOARD_ON_SCHEDULE", "false", "bool"),
    SettingSpec("BACKUP_DIR", "backups"),
    SettingSpec("BACKUP_RETENTION_COUNT", "30", "int", 1, 365),
)

SPEC_BY_KEY = {spec.key: spec for spec in SETTING_SPECS}
EDITABLE_KEYS = tuple(spec.key for spec in SETTING_SPECS)
BOOLEAN_KEYS = frozenset(spec.key for spec in SETTING_SPECS if spec.kind == "bool")

_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_ENV_KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")


def read_settings(path: str | Path = ".env") -> dict[str, str]:
    env_path = Path(path)
    raw = dotenv_values(env_path) if env_path.is_file() else {}
    values: dict[str, str] = {}
    for spec in SETTING_SPECS:
        value = raw.get(spec.key)
        if value is None:
            value = os.getenv(spec.key)
        values[spec.key] = str(value) if value is not None else spec.default
    return values


def normalize_submitted_settings(values: Mapping[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    errors: list[str] = []
    for spec in SETTING_SPECS:
        raw = values.get(spec.key, spec.default)
        value = str(raw).strip()
        try:
            normalized[spec.key] = _normalize_value(spec, value)
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        raise ValueError("\n".join(errors))
    if not normalized["ASANA_WORKSPACE_GID"]:
        raise ValueError("Asana workspace GID is required.")
    github_enabled = any(
        normalized[key] == "true"
        for key in (
            "INCLUDE_GITHUB_REVIEWS",
            "INCLUDE_GITHUB_AUTHORED_PRS",
            "INCLUDE_GITHUB_ASSIGNED_ISSUES",
            "INCLUDE_GITHUB_MENTIONS",
            "INCLUDE_LINKED_PR_STATUS",
        )
    )
    if github_enabled and not normalized["GITHUB_REPOSITORIES"]:
        raise ValueError("Add at least one GitHub repository, or disable all GitHub sources.")
    if normalized["MORNING_TIME"] == normalized["EVENING_TIME"]:
        raise ValueError("Morning and evening notification times must be different.")
    return normalized


def save_settings(values: Mapping[str, str], path: str | Path = ".env") -> dict[str, str]:
    env_path = Path(path)
    normalized = normalize_submitted_settings(values)
    _write_env_updates(env_path, normalized)
    return normalized


def _normalize_value(spec: SettingSpec, value: str) -> str:
    if not value and spec.kind in {"int", "time"}:
        value = spec.default
    if spec.kind == "bool":
        return "true" if value.casefold() in {"1", "true", "yes", "on"} else "false"
    if spec.kind == "time":
        if not _TIME_RE.fullmatch(value):
            raise ValueError(f"{spec.key} must use 24-hour HH:MM format.")
        return value
    if spec.kind == "int":
        try:
            number = int(value)
        except ValueError as exc:
            raise ValueError(f"{spec.key} must be a whole number.") from exc
        if spec.minimum is not None and number < spec.minimum:
            raise ValueError(f"{spec.key} must be at least {spec.minimum}.")
        if spec.maximum is not None and number > spec.maximum:
            raise ValueError(f"{spec.key} must be at most {spec.maximum}.")
        return str(number)
    if spec.kind in {"csv", "repos"}:
        items: list[str] = []
        seen: set[str] = set()
        for item in value.split(","):
            cleaned = item.strip()
            if not cleaned:
                continue
            identity = cleaned.casefold()
            if identity in seen:
                continue
            if spec.kind == "repos" and not _REPOSITORY_RE.fullmatch(cleaned):
                raise ValueError(f"Invalid GitHub repository '{cleaned}'. Use owner/repository.")
            seen.add(identity)
            items.append(cleaned)
        return ",".join(items)
    if spec.key == "GITHUB_CLI_PATH" and value:
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValueError("GITHUB_CLI_PATH must be an absolute path, or left blank for automatic detection.")
    return value


def _write_env_updates(path: Path, updates: Mapping[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    original = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = original.splitlines()
    emitted: set[str] = set()
    output: list[str] = []
    for line in lines:
        match = _ENV_KEY_RE.match(line)
        if not match:
            output.append(line)
            continue
        key = match.group(1)
        if key not in updates:
            output.append(line)
            continue
        if key in emitted:
            continue
        output.append(f"{key}={updates[key]}")
        emitted.add(key)
    missing = [key for key in EDITABLE_KEYS if key not in emitted]
    if missing:
        if output and output[-1].strip():
            output.append("")
        output.append("# Managed by the Task Digest Settings page")
        output.extend(f"{key}={updates[key]}" for key in missing)
    text = "\n".join(output).rstrip() + "\n"
    fd, temporary_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
