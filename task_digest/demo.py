from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from .config import Config
from .digest import render_html
from .models import (
    GitHubCheckDetail,
    GitHubLink,
    GitHubReviewDetail,
    GitHubReviewThread,
    RelatedTask,
    SourceStatus,
    StatusSource,
    TaskComment,
    TaskEvent,
    TaskItem,
)


def _working_day_offset(day: date, offset: int) -> date:
    """Move by working days, where negative values move backwards."""
    direction = 1 if offset >= 0 else -1
    remaining = abs(offset)
    current = day
    while remaining:
        current += timedelta(days=direction)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _at(day: date, hour: int = 10, minute: int = 0, tzinfo=None) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=tzinfo).replace(hour=hour, minute=minute)


def demo_config(host: str = "127.0.0.1", port: int = 8777) -> Config:
    """Return an isolated configuration that never requires external credentials."""
    return Config(
        asana_token="",
        asana_workspace_gid="demo-workspace",
        asana_token_keychain_service="app.taskdigest.demo.asana",
        asana_token_keychain_account="demo",
        asana_project_gids=set(),
        excluded_sections={"drafts"},
        optional_sections={"investigations"},
        action_statuses={"pending", "in development", "changes requested", "to do", "ready"},
        waiting_statuses={"in review", "in deployment", "blocked", "waiting"},
        stale_waiting_days=5,
        smart_plan_max_items=5,
        smart_plan_stale_waiting_limit=1,
        include_asana_dependencies=True,
        recent_comment_limit=3,
        enable_asana_write_actions=False,
        include_github_reviews=True,
        include_github_authored_prs=True,
        include_github_assigned_issues=True,
        include_github_mentions=True,
        include_linked_pr_status=True,
        github_repositories=["example-org/web-app", "example-org/test-suite"],
        github_cli_path=None,
        github_review_limit=50,
        github_pr_limit=50,
        github_issue_limit=50,
        github_mention_limit=50,
        morning_time=datetime.strptime("10:00", "%H:%M").time(),
        evening_time=datetime.strptime("17:30", "%H:%M").time(),
        schedule_window_minutes=20,
        state_file="state/demo_digest_state.json",
        preferences_file="state/demo_task_preferences.json",
        workspace_file="state/demo_workspace.json",
        journal_file="state/demo_activity_log.json",
        rules_file="state/demo_task_rules.json",
        report_file="output/demo-dashboard.html",
        history_dir="history/demo",
        backup_dir="backups/demo",
        backup_retention_count=5,
        dashboard_token_file="state/demo_dashboard_token",
        dashboard_host=host,
        dashboard_port=port,
        dashboard_refresh_minutes=60,
        menu_refresh_minutes=60,
        actionable_notifications=False,
        notification_snooze_minutes=60,
        open_report=False,
        open_dashboard_on_schedule=False,
    )


def demo_tasks(now: datetime | None = None) -> list[TaskItem]:
    """Build realistic, sanitized tasks for screenshots and product demos."""
    now = now or datetime.now().astimezone()
    today = now.date()
    tz = now.tzinfo

    blocker = RelatedTask(
        gid="demo-fixtures",
        title="Refresh checkout fixtures",
        url="https://app.asana.com/0/demo/demo-fixtures",
        completed=False,
    )
    downstream = RelatedTask(
        gid="demo-regression",
        title="Run release regression suite",
        url="https://app.asana.com/0/demo/demo-regression",
        completed=False,
    )

    linked_pr = GitHubLink(
        owner="example-org",
        repo="web-app",
        number=142,
        url="https://github.com/example-org/web-app/pull/142",
        title="Improve permission coverage",
        state="OPEN",
        review_decision="CHANGES_REQUESTED",
        action_reasons=["Changes requested", "Checks failing"],
        failed_checks=["e2e-chrome", "accessibility"],
        pending_reviewers=["reviewer-a"],
        approvals=1,
        mergeable="MERGEABLE",
        merge_state_status="BLOCKED",
        changed_files=12,
        additions=286,
        deletions=74,
        commit_count=4,
        top_files=[
            "tests/e2e/permissions.spec.ts",
            "src/permissions/access-control.ts",
            "tests/fixtures/roles.json",
        ],
        base_ref_name="main",
        head_ref_name="feature/permission-coverage",
        head_ref_oid="demo-head-oid",
        checks=[
            GitHubCheckDetail(
                name="e2e-chrome",
                state="FAILURE",
                bucket="fail",
                url="https://github.com/example-org/web-app/actions/runs/142",
                workflow="End-to-end tests",
                started_at=_at(today, 8, 40, tzinfo=tz),
                completed_at=_at(today, 8, 48, tzinfo=tz),
                summary="Timed out waiting for the permissions modal.",
            ),
            GitHubCheckDetail(
                name="lint",
                state="SUCCESS",
                bucket="pass",
                url="https://github.com/example-org/web-app/actions/runs/141",
                started_at=_at(today, 8, 36, tzinfo=tz),
                completed_at=_at(today, 8, 37, tzinfo=tz),
            ),
            GitHubCheckDetail(
                name="accessibility",
                state="IN_PROGRESS",
                bucket="pending",
                url="https://github.com/example-org/web-app/actions/runs/143",
                started_at=_at(today, 9, 18, tzinfo=tz),
            ),
        ],
        reviews=[
            GitHubReviewDetail(
                reviewer="reviewer-a",
                state="CHANGES_REQUESTED",
                submitted_at=_at(_working_day_offset(today, -1), 15, 20, tzinfo=tz),
                body="Please cover the branch-admin path before this is merged.",
                url="https://github.com/example-org/web-app/pull/142#pullrequestreview-1",
                requested=True,
            ),
            GitHubReviewDetail(
                reviewer="reviewer-b",
                state="APPROVED",
                submitted_at=_at(_working_day_offset(today, -1), 13, 5, tzinfo=tz),
                url="https://github.com/example-org/web-app/pull/142#pullrequestreview-2",
            ),
        ],
        unresolved_threads=[
            GitHubReviewThread(
                id="demo-thread-1",
                author="reviewer-a",
                body="This assertion should verify the empty state before attempting the delete action.",
                path="tests/e2e/permissions.spec.ts",
                line=84,
                created_at=_at(_working_day_offset(today, -1), 15, 18, tzinfo=tz),
                url="https://github.com/example-org/web-app/pull/142#discussion_r1",
            ),
            GitHubReviewThread(
                id="demo-thread-2",
                author="reviewer-a",
                body="Could this fixture include a branch-admin role so the new path is covered?",
                path="tests/fixtures/roles.json",
                line=21,
                created_at=_at(_working_day_offset(today, -1), 15, 19, tzinfo=tz),
                url="https://github.com/example-org/web-app/pull/142#discussion_r2",
            ),
        ],
        last_commit_at=_at(today, 8, 35, tzinfo=tz),
        last_review_at=_at(_working_day_offset(today, -1), 15, 20, tzinfo=tz),
        created_at=_at(_working_day_offset(today, -6), 9, tzinfo=tz),
        updated_at=_at(today, 9, 25, tzinfo=tz),
    )

    tasks = [
        TaskItem(
            key="asana:demo-permissions",
            title="Improve permission coverage",
            url="https://app.asana.com/0/demo/demo-permissions",
            source="asana",
            created_at=_at(_working_day_offset(today, -8), 9, tzinfo=tz),
            assigned_at=_at(_working_day_offset(today, -5), 11, tzinfo=tz),
            status_changed_at=_at(_working_day_offset(today, -4), 10, tzinfo=tz),
            due_on=_working_day_offset(today, 1),
            status="In Development",
            status_source=StatusSource(kind="section", name="In Development", value="In Development"),
            project="Release Sprint",
            section="In Development",
            github_links=[linked_pr],
            priority="urgent",
            age_basis="status",
            age_working_days=4,
            notes=["GitHub action required: changes requested and checks failing"],
            action_state="action",
            dependencies=[blocker],
            dependents=[downstream],
            recent_comments=[
                TaskComment(
                    gid="demo-comment-1",
                    author="Alex Morgan",
                    text="The permission matrix is ready for another pass.",
                    created_at=_at(today, 9, 12, tzinfo=tz),
                    unread=True,
                )
            ],
            unread_updates=1,
            focus_rank=1,
            timeline_events=[
                TaskEvent(
                    id="demo-event-pr",
                    source="github",
                    kind="github",
                    title="Changes requested on PR #142",
                    created_at=_at(today, 9, 25, tzinfo=tz),
                    detail="Two checks are failing.",
                    actor="reviewer-a",
                    url=linked_pr.url,
                ),
                TaskEvent(
                    id="demo-event-status",
                    source="asana",
                    kind="status",
                    title="Moved to In Development",
                    created_at=_at(_working_day_offset(today, -4), 10, tzinfo=tz),
                ),
            ],
        ),
        TaskItem(
            key="github-review:example-org/web-app#156",
            title="Review access-control changes",
            url="https://github.com/example-org/web-app/pull/156",
            source="github",
            created_at=_at(_working_day_offset(today, -3), 12, tzinfo=tz),
            assigned_at=_at(_working_day_offset(today, -2), 15, tzinfo=tz),
            project="example-org/web-app",
            github_kind="review_request",
            priority="high",
            age_basis="assigned",
            age_working_days=2,
            action_state="action",
            focus_rank=2,
            notes=["Review requested from you"],
        ),
        TaskItem(
            key="asana:demo-onboarding",
            title="Continue onboarding tests",
            url="https://app.asana.com/0/demo/demo-onboarding",
            source="asana",
            created_at=_at(_working_day_offset(today, -3), 8, tzinfo=tz),
            assigned_at=_at(_working_day_offset(today, -1), 9, tzinfo=tz),
            status_changed_at=_at(_working_day_offset(today, -1), 9, tzinfo=tz),
            due_on=_working_day_offset(today, 3),
            status="Pending",
            project="Onboarding Quality",
            section="Pending",
            priority="normal",
            age_basis="status",
            age_working_days=1,
            action_state="action",
            focus_rank=3,
            recent_comments=[
                TaskComment(
                    gid="demo-comment-2",
                    author="Jamie Lee",
                    text="The new sample account is available in staging.",
                    created_at=_at(today, 8, 45, tzinfo=tz),
                    unread=True,
                )
            ],
            unread_updates=1,
        ),
        TaskItem(
            key="asana:demo-fixture-refactor",
            title="Refactor test fixtures",
            url="https://app.asana.com/0/demo/demo-fixture-refactor",
            source="asana",
            created_at=_at(_working_day_offset(today, -10), 9, tzinfo=tz),
            assigned_at=_at(_working_day_offset(today, -9), 9, tzinfo=tz),
            status_changed_at=_at(_working_day_offset(today, -7), 13, tzinfo=tz),
            status="In Review",
            project="Test Platform",
            section="In Review",
            github_links=[
                GitHubLink(
                    owner="example-org",
                    repo="test-suite",
                    number=151,
                    url="https://github.com/example-org/test-suite/pull/151",
                    title="Refactor shared fixtures",
                    state="OPEN",
                    pending_reviewers=["reviewer-b", "reviewer-c"],
                    approvals=0,
                    checks_pending=False,
                    mergeable="MERGEABLE",
                    created_at=_at(_working_day_offset(today, -8), 11, tzinfo=tz),
                    updated_at=_at(_working_day_offset(today, -1), 16, tzinfo=tz),
                )
            ],
            priority="high",
            age_basis="status",
            age_working_days=7,
            action_state="waiting",
            stale_waiting=True,
            waiting_reason="Waiting for review from @reviewer-b and @reviewer-c",
            notes=["Follow-up suggested"],
            unread_updates=1,
        ),
        TaskItem(
            key="github-authored:example-org/test-suite#160",
            title="Fix flaky checkout spec",
            url="https://github.com/example-org/test-suite/pull/160",
            source="github",
            created_at=_at(_working_day_offset(today, -4), 10, tzinfo=tz),
            status_changed_at=_at(_working_day_offset(today, -1), 14, tzinfo=tz),
            project="example-org/test-suite",
            github_kind="authored_pr",
            priority="high",
            age_basis="status",
            age_working_days=1,
            action_state="action",
            notes=["Checks failing: e2e-safari", "Changes requested"],
        ),
        TaskItem(
            key="github-issue:example-org/web-app#88",
            title="Investigate intermittent login timeout",
            url="https://github.com/example-org/web-app/issues/88",
            source="github",
            created_at=_at(_working_day_offset(today, -5), 10, tzinfo=tz),
            assigned_at=_at(_working_day_offset(today, -2), 10, tzinfo=tz),
            project="example-org/web-app",
            github_kind="assigned_issue",
            priority="normal",
            age_basis="assigned",
            age_working_days=2,
            action_state="action",
        ),
        TaskItem(
            key="asana:demo-investigation",
            title="Evaluate test-data cleanup options",
            url="https://app.asana.com/0/demo/demo-investigation",
            source="asana",
            created_at=_at(_working_day_offset(today, -2), 11, tzinfo=tz),
            assigned_at=_at(_working_day_offset(today, -1), 11, tzinfo=tz),
            status="Investigation",
            project="Quality Improvements",
            section="Investigations",
            priority="new",
            age_basis="assigned",
            age_working_days=1,
            is_optional=True,
            action_state="action",
        ),
    ]
    return tasks


def demo_source_statuses() -> list[SourceStatus]:
    return [
        SourceStatus(name="Demo mode", ok=True, detail="Sanitized sample data; no external services contacted"),
        SourceStatus(name="Asana", ok=True, detail="Loaded 4 demonstration task(s)"),
        SourceStatus(name="GitHub", ok=True, detail="Loaded 3 demonstration item(s) from 2 repositories"),
        SourceStatus(name="Local filters", ok=True, detail="0 snoozed · 0 ignored"),
    ]


def demo_summaries() -> dict[str, object]:
    return {
        "daily": {
            "completed": 2,
            "new": 1,
            "status_changed": 3,
            "reviews_completed": 1,
            "prs_merged": 1,
            "cleared": 2,
        },
        "weekly": {
            "completed": 9,
            "new": 6,
            "status_changed": 14,
            "reviews_completed": 7,
            "prs_merged": 4,
            "cleared": 8,
        },
        "latest_counts": {"action": 5, "waiting": 1, "focus": 3, "unread": 3},
    }


def render_demo_report(
    output_path: str | Path = "output/demo-dashboard.html",
    now: datetime | None = None,
    dashboard_url: str | None = None,
    action_token: str | None = None,
) -> Path:
    now = now or datetime.now().astimezone()
    return render_html(
        demo_tasks(now),
        now,
        "demo",
        str(output_path),
        source_statuses=demo_source_statuses(),
        hidden_summary=(0, 0),
        action_token=action_token,
        dashboard_url=dashboard_url,
        refresh_minutes=60,
        summaries=demo_summaries(),
        asana_write_enabled=False,
        smart_plan_max_items=5,
        smart_plan_stale_waiting_limit=1,
        demo_mode=True,
    )
