from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from datetime import time
from typing import List, Optional, Set

from dotenv import load_dotenv

from .keychain import resolve_asana_token


def _parse_time(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(hour=int(hour), minute=int(minute))


def _csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalized_set(value: str) -> Set[str]:
    return {item.casefold() for item in _csv(value)}


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    asana_token: str
    asana_workspace_gid: str
    asana_token_keychain_service: str
    asana_token_keychain_account: str
    asana_project_gids: Set[str]
    excluded_sections: Set[str]
    optional_sections: Set[str]
    action_statuses: Set[str]
    waiting_statuses: Set[str]
    stale_waiting_days: int
    smart_plan_max_items: int
    smart_plan_stale_waiting_limit: int
    include_asana_dependencies: bool
    recent_comment_limit: int
    enable_asana_write_actions: bool
    include_github_reviews: bool
    include_github_authored_prs: bool
    include_github_assigned_issues: bool
    include_github_mentions: bool
    include_linked_pr_status: bool
    github_repositories: List[str]
    github_cli_path: Optional[str]
    github_review_limit: int
    github_pr_limit: int
    github_issue_limit: int
    github_mention_limit: int
    morning_time: time
    evening_time: time
    schedule_window_minutes: int
    state_file: str
    preferences_file: str
    workspace_file: str
    journal_file: str
    rules_file: str
    report_file: str
    history_dir: str
    backup_dir: str
    backup_retention_count: int
    dashboard_token_file: str
    dashboard_host: str
    dashboard_port: int
    dashboard_refresh_minutes: int
    menu_refresh_minutes: int
    actionable_notifications: bool
    notification_snooze_minutes: int
    open_report: bool
    open_dashboard_on_schedule: bool

    @property
    def dashboard_url(self) -> str:
        return f"http://{self.dashboard_host}:{self.dashboard_port}"

    @classmethod
    def load(cls) -> "Config":
        load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)
        workspace_gid = os.getenv("ASANA_WORKSPACE_GID", "").strip()
        if not workspace_gid:
            raise RuntimeError("Missing required environment variable: ASANA_WORKSPACE_GID")
        keychain_service = os.getenv(
            "ASANA_TOKEN_KEYCHAIN_SERVICE",
            "app.taskdigest.asana",
        )
        keychain_account = os.getenv("ASANA_TOKEN_KEYCHAIN_ACCOUNT", "asana")
        asana_token = resolve_asana_token(keychain_service, keychain_account)
        return cls(
            asana_token=asana_token,
            asana_workspace_gid=workspace_gid,
            asana_token_keychain_service=keychain_service,
            asana_token_keychain_account=keychain_account,
            asana_project_gids=set(_csv(os.getenv("ASANA_PROJECT_GIDS", ""))),
            excluded_sections=_normalized_set(os.getenv("EXCLUDE_SECTIONS", "Drafts")),
            optional_sections=_normalized_set(os.getenv("OPTIONAL_SECTIONS", "Investigations")),
            action_statuses=_normalized_set(
                os.getenv(
                    "ACTION_STATUSES",
                    "Pending,In Development,Changes Requested,To Do,Ready",
                )
            ),
            waiting_statuses=_normalized_set(
                os.getenv(
                    "WAITING_STATUSES",
                    "In Review,In Deployment,Blocked,Waiting,Waiting for Review,Waiting for Deployment",
                )
            ),
            stale_waiting_days=int(os.getenv("STALE_WAITING_DAYS", "5")),
            smart_plan_max_items=max(1, min(10, int(os.getenv("SMART_PLAN_MAX_ITEMS", "5")))),
            smart_plan_stale_waiting_limit=max(0, min(5, int(os.getenv("SMART_PLAN_STALE_WAITING_LIMIT", "1")))),
            include_asana_dependencies=_bool(os.getenv("INCLUDE_ASANA_DEPENDENCIES", "true")),
            recent_comment_limit=max(0, int(os.getenv("RECENT_COMMENT_LIMIT", "3"))),
            enable_asana_write_actions=_bool(os.getenv("ENABLE_ASANA_WRITE_ACTIONS", "false")),
            include_github_reviews=_bool(os.getenv("INCLUDE_GITHUB_REVIEWS", "false")),
            include_github_authored_prs=_bool(os.getenv("INCLUDE_GITHUB_AUTHORED_PRS", "false")),
            include_github_assigned_issues=_bool(os.getenv("INCLUDE_GITHUB_ASSIGNED_ISSUES", "false")),
            include_github_mentions=_bool(os.getenv("INCLUDE_GITHUB_MENTIONS", "false")),
            include_linked_pr_status=_bool(os.getenv("INCLUDE_LINKED_PR_STATUS", "false")),
            github_repositories=_csv(
                os.getenv(
                    "GITHUB_REPOSITORIES",
                    "",
                )
            ),
            github_cli_path=os.getenv("GITHUB_CLI_PATH") or None,
            github_review_limit=int(os.getenv("GITHUB_REVIEW_LIMIT", "50")),
            github_pr_limit=int(os.getenv("GITHUB_PR_LIMIT", "50")),
            github_issue_limit=int(os.getenv("GITHUB_ISSUE_LIMIT", "50")),
            github_mention_limit=int(os.getenv("GITHUB_MENTION_LIMIT", "50")),
            morning_time=_parse_time(os.getenv("MORNING_TIME", "10:00")),
            evening_time=_parse_time(os.getenv("EVENING_TIME", "17:30")),
            schedule_window_minutes=int(os.getenv("SCHEDULE_WINDOW_MINUTES", "20")),
            state_file=os.getenv("STATE_FILE", "state/digest_state.json"),
            preferences_file=os.getenv("PREFERENCES_FILE", "state/task_preferences.json"),
            workspace_file=os.getenv("WORKSPACE_FILE", "state/workspace.json"),
            journal_file=os.getenv("JOURNAL_FILE", "state/activity_log.json"),
            rules_file=os.getenv("RULES_FILE", "state/task_rules.json"),
            report_file=os.getenv("REPORT_FILE", "output/task-digest.html"),
            history_dir=os.getenv("HISTORY_DIR", "history"),
            backup_dir=os.getenv("BACKUP_DIR", "backups"),
            backup_retention_count=max(1, int(os.getenv("BACKUP_RETENTION_COUNT", "30"))),
            dashboard_token_file=os.getenv("DASHBOARD_TOKEN_FILE", "state/dashboard_token"),
            dashboard_host=os.getenv("DASHBOARD_HOST", "127.0.0.1"),
            dashboard_port=int(os.getenv("DASHBOARD_PORT", "8765")),
            dashboard_refresh_minutes=max(1, int(os.getenv("DASHBOARD_REFRESH_MINUTES", "5"))),
            menu_refresh_minutes=max(1, int(os.getenv("MENU_REFRESH_MINUTES", "5"))),
            actionable_notifications=_bool(os.getenv("ACTIONABLE_NOTIFICATIONS", "true")),
            notification_snooze_minutes=max(1, int(os.getenv("NOTIFICATION_SNOOZE_MINUTES", "60"))),
            open_report=_bool(os.getenv("OPEN_REPORT", "false")),
            open_dashboard_on_schedule=_bool(os.getenv("OPEN_DASHBOARD_ON_SCHEDULE", "false")),
        )
