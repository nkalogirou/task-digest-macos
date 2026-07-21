from __future__ import annotations

from pathlib import Path

import pytest

from task_digest.settings import EDITABLE_KEYS, normalize_submitted_settings, read_settings, save_settings


def _valid_values() -> dict[str, str]:
    values = {key: "" for key in EDITABLE_KEYS}
    values.update(
        {
            "ASANA_WORKSPACE_GID": "1234567890",
            "ASANA_PROJECT_GIDS": "",
            "EXCLUDE_SECTIONS": "Drafts, Backlog, drafts",
            "OPTIONAL_SECTIONS": "Investigations",
            "ACTION_STATUSES": "Pending, In Development",
            "WAITING_STATUSES": "In Review, In Deployment",
            "STALE_WAITING_DAYS": "5",
            "INCLUDE_ASANA_DEPENDENCIES": "true",
            "RECENT_COMMENT_LIMIT": "3",
            "INCLUDE_GITHUB_REVIEWS": "true",
            "INCLUDE_GITHUB_AUTHORED_PRS": "true",
            "INCLUDE_GITHUB_ASSIGNED_ISSUES": "true",
            "INCLUDE_GITHUB_MENTIONS": "true",
            "INCLUDE_LINKED_PR_STATUS": "true",
            "GITHUB_REPOSITORIES": "acme-inc/web-app, acme-inc/test-fixtures",
            "GITHUB_CLI_PATH": "",
            "GITHUB_REVIEW_LIMIT": "50",
            "GITHUB_PR_LIMIT": "50",
            "GITHUB_ISSUE_LIMIT": "50",
            "GITHUB_MENTION_LIMIT": "50",
            "MORNING_TIME": "10:00",
            "EVENING_TIME": "17:30",
            "SCHEDULE_WINDOW_MINUTES": "20",
            "DASHBOARD_REFRESH_MINUTES": "5",
            "MENU_REFRESH_MINUTES": "5",
            "ACTIONABLE_NOTIFICATIONS": "true",
            "NOTIFICATION_SNOOZE_MINUTES": "60",
            "OPEN_REPORT": "false",
            "OPEN_DASHBOARD_ON_SCHEDULE": "false",
        }
    )
    return values


def test_normalize_settings_validates_and_deduplicates_csv() -> None:
    result = normalize_submitted_settings(_valid_values())
    assert result["EXCLUDE_SECTIONS"] == "Drafts,Backlog"
    assert result["GITHUB_REPOSITORIES"] == (
        "acme-inc/web-app,acme-inc/test-fixtures"
    )
    assert result["ACTIONABLE_NOTIFICATIONS"] == "true"


def test_normalize_settings_rejects_bad_time_and_repository() -> None:
    values = _valid_values()
    values["MORNING_TIME"] = "25:00"
    values["GITHUB_REPOSITORIES"] = "not-a-repository"
    with pytest.raises(ValueError) as error:
        normalize_submitted_settings(values)
    message = str(error.value)
    assert "MORNING_TIME" in message
    assert "owner/repository" in message


def test_save_settings_preserves_secret_and_unknown_values(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# Keep this comment\nASANA_TOKEN=secret-value\nCUSTOM_SETTING=keep-me\nMORNING_TIME=09:00\n",
        encoding="utf-8",
    )
    save_settings(_valid_values(), env)
    text = env.read_text(encoding="utf-8")
    assert "ASANA_TOKEN=secret-value" in text
    assert "CUSTOM_SETTING=keep-me" in text
    assert "MORNING_TIME=10:00" in text
    assert text.count("MORNING_TIME=") == 1
    assert "# Managed by the Task Digest Settings page" in text


def test_read_settings_uses_defaults_for_missing_keys(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("ASANA_WORKSPACE_GID=42\n", encoding="utf-8")
    values = read_settings(env)
    assert values["ASANA_WORKSPACE_GID"] == "42"
    assert values["MORNING_TIME"] == "10:00"
    assert values["EXCLUDE_SECTIONS"] == "Drafts"


def test_github_repositories_can_be_blank_when_all_github_sources_are_disabled() -> None:
    values = _valid_values()
    values["GITHUB_REPOSITORIES"] = ""
    for key in (
        "INCLUDE_GITHUB_REVIEWS",
        "INCLUDE_GITHUB_AUTHORED_PRS",
        "INCLUDE_GITHUB_ASSIGNED_ISSUES",
        "INCLUDE_GITHUB_MENTIONS",
        "INCLUDE_LINKED_PR_STATUS",
    ):
        values[key] = "false"
    result = normalize_submitted_settings(values)
    assert result["GITHUB_REPOSITORIES"] == ""


def test_public_default_disables_asana_write_actions(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("ASANA_WORKSPACE_GID=42\n", encoding="utf-8")
    values = read_settings(env)
    assert values["ENABLE_ASANA_WRITE_ACTIONS"] == "false"


def test_public_defaults_disable_github_sources(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("ASANA_WORKSPACE_GID=42\n", encoding="utf-8")
    values = read_settings(env)
    assert values["GITHUB_REPOSITORIES"] == ""
    assert values["INCLUDE_GITHUB_REVIEWS"] == "false"
    assert values["INCLUDE_GITHUB_AUTHORED_PRS"] == "false"
    assert values["INCLUDE_GITHUB_ASSIGNED_ISSUES"] == "false"
    assert values["INCLUDE_GITHUB_MENTIONS"] == "false"
    assert values["INCLUDE_LINKED_PR_STATUS"] == "false"
