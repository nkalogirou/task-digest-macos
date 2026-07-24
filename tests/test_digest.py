from datetime import date, datetime, timezone

from task_digest.changes import compare_snapshots, snapshot_tasks
from task_digest.digest import (
    _age_description,
    _due_description,
    notification_summary,
    render_html,
    split_tasks,
)
from task_digest.models import TaskItem


def _task(
    key: str,
    title: str,
    *,
    status: str | None = None,
    action_state: str = "action",
    priority: str = "new",
    due_on: date | None = None,
    optional: bool = False,
) -> TaskItem:
    return TaskItem(
        key=key,
        title=title,
        url=f"https://app.asana.com/0/1/{key}",
        source="asana",
        status=status,
        action_state=action_state,  # type: ignore[arg-type]
        priority=priority,  # type: ignore[arg-type]
        due_on=due_on,
        is_optional=optional,
    )


def test_split_tasks_separates_action_waiting_and_optional() -> None:
    action, waiting, optional = split_tasks(
        [
            _task("1", "Action"),
            _task("2", "Review", action_state="waiting"),
            _task("3", "Investigation", optional=True),
        ]
    )
    assert [item.key for item in action] == ["1"]
    assert [item.key for item in waiting] == ["2"]
    assert [item.key for item in optional] == ["3"]


def test_age_description_for_assignment() -> None:
    item = _task("1", "A")
    item.age_basis = "assigned"
    item.age_working_days = 3
    assert _age_description(item) == "Assigned to task 3 working days ago"


def test_age_description_for_status() -> None:
    item = _task("1", "A", status="In Review")
    item.status_changed_at = datetime(2026, 7, 17, tzinfo=timezone.utc)
    item.age_basis = "status"
    item.age_working_days = 1
    assert _age_description(item) == "In Review for 1 working day"


def test_due_description() -> None:
    today = date(2026, 7, 20)
    assert _due_description(_task("1", "A", due_on=today), today) == "Due today"
    assert "Overdue" in (_due_description(_task("2", "B", due_on=date(2026, 7, 17)), today) or "")
    assert _due_description(_task("3", "C", due_on=date(2026, 7, 21)), today) == "Due tomorrow"


def test_notification_summary_uses_workflow_groups() -> None:
    tasks = [
        _task("1", "Action", priority="urgent"),
        _task("2", "Waiting", action_state="waiting", priority="high"),
        _task("3", "Investigation", optional=True),
    ]
    title, body = notification_summary(tasks)
    assert title == "Task Digest: 1 need action · 0 PR blocker(s) · 0 review(s)"
    assert "Waiting 1" in body
    assert "Investigations 1" in body


def test_html_renders_needs_action_waiting_and_collapsed_investigations(tmp_path) -> None:
    tasks = [
        _task("1", "Build", status="In Development", priority="high"),
        _task("2", "Review", status="In Review", action_state="waiting"),
        _task("3", "Research", optional=True),
    ]
    output = tmp_path / "digest.html"
    render_html(tasks, datetime(2026, 7, 20, 15, 0, tzinfo=timezone.utc), "morning", str(output))
    html = output.read_text(encoding="utf-8")
    assert "Needs action" in html
    assert "Waiting on others" in html
    assert '<details class="optional-section">' in html
    assert "Research" in html
    assert "GitHub reviews required" in html
    assert "No reviews currently requested from you." in html


def test_evening_report_shows_changes_and_still_action(tmp_path) -> None:
    previous_task = _task("1", "Build", status="Pending", priority="normal")
    previous = snapshot_tasks([previous_task])
    current = _task("1", "Build", status="In Development", priority="high")
    current.age_basis = "status"
    changes = compare_snapshots(previous, [current])

    output = tmp_path / "digest.html"
    render_html(
        [current],
        datetime(2026, 7, 20, 17, 30, tzinfo=timezone.utc),
        "evening",
        str(output),
        changes=changes,
    )
    html = output.read_text(encoding="utf-8")
    assert "Evening changes" in html
    assert "Status changed" in html
    assert "Pending → In Development" in html
    assert "Still needs action" in html


def test_html_renders_github_review_request(tmp_path) -> None:
    review = TaskItem(
        key="github:acme-inc/web-app#1551",
        title="Refactor authentication tests",
        url="https://github.com/acme-inc/web-app/pull/1551",
        source="github",
        assigned_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
        project="acme-inc/web-app",
        notes=["Opened by @billyblanas"],
        priority="normal",
        age_working_days=1,
    )
    output = tmp_path / "digest.html"
    render_html([review], datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc), "morning", str(output))
    html = output.read_text(encoding="utf-8")
    assert "GitHub reviews required" in html
    assert "Refactor authentication tests" in html
    assert "Review requested 1 working day ago" in html
    assert "Opened by @billyblanas" in html


def test_html_renders_authored_pr_needing_action(tmp_path) -> None:
    pull = TaskItem(
        key="github-authored:acme-inc/web-app#1600",
        title="PR #1600 — Fix checkout tests",
        url="https://github.com/acme-inc/web-app/pull/1600",
        source="github",
        github_kind="authored_pr",
        assigned_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
        status="Changes requested · Checks failing",
        project="acme-inc/web-app",
        notes=["Failing checks: e2e"],
        priority="normal",
        age_working_days=1,
    )
    output = tmp_path / "digest.html"
    render_html([pull], datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc), "morning", str(output))
    html = output.read_text(encoding="utf-8")
    assert "Your PRs needing action" in html
    assert "PR #1600 — Fix checkout tests" in html
    assert "Needs action for 1 working day" in html
    assert "Changes requested · Checks failing" in html
    assert "Failing checks: e2e" in html


def test_html_renders_assigned_issues_and_mentions(tmp_path) -> None:
    assigned = TaskItem(
        key="github-issue:acme-inc/web-app#42",
        title="Issue #42 — Investigate flaky test",
        url="https://github.com/acme-inc/web-app/issues/42",
        source="github",
        github_kind="assigned_issue",
        project="acme-inc/web-app",
        priority="normal",
        age_working_days=2,
    )
    mention = TaskItem(
        key="github-mention:acme-inc/web-app#43",
        title="Issue #43 — Please investigate",
        url="https://github.com/acme-inc/web-app/issues/43",
        source="github",
        github_kind="mention",
        project="acme-inc/web-app",
        priority="new",
        age_working_days=0,
    )
    output = tmp_path / "digest.html"
    render_html([assigned, mention], datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc), "morning", str(output))
    html = output.read_text(encoding="utf-8")
    assert "GitHub issues assigned to you" in html
    assert "Issue #42" in html
    assert "GitHub mentions" in html
    assert "Issue #43" in html


def test_html_renders_dynamic_buttons_and_linked_pr_alert(tmp_path) -> None:
    from task_digest.models import GitHubLink

    task = _task("asana:1", "Build", status="In Development")
    task.github_links = [
        GitHubLink(
            owner="acme-inc",
            repo="web-app",
            number=1549,
            url="https://github.com/acme-inc/web-app/pull/1549",
            action_reasons=["Checks failing"],
            failed_checks=["e2e"],
        ),
        GitHubLink(
            owner="acme-inc",
            repo="web-app",
            number=1550,
            url="https://github.com/acme-inc/web-app/pull/1550",
            is_draft=True,
        ),
    ]
    output = tmp_path / "digest.html"
    render_html(
        [task],
        datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc),
        "morning",
        str(output),
        action_token="secret",
        dashboard_url="http://127.0.0.1:8765",
    )
    rendered = output.read_text(encoding="utf-8")
    assert "GitHub action required" in rendered
    assert "Checks failing" in rendered
    assert "Tomorrow" in rendered
    assert "3 workdays" in rendered
    assert "Until change" in rendered
    assert "pull/1549" in rendered
    assert "pull/1550" not in rendered


def test_html_marks_stale_waiting_for_follow_up(tmp_path) -> None:
    task = _task("asana:2", "Waiting task", status="In Review", action_state="waiting")
    task.stale_waiting = True
    output = tmp_path / "digest.html"
    render_html(
        [task],
        datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc),
        "morning",
        str(output),
    )
    assert "Follow-up suggested" in output.read_text(encoding="utf-8")


def test_html_renders_focus_notes_dependencies_comments_and_theme(tmp_path) -> None:
    from task_digest.models import RelatedTask, TaskComment

    task = _task("asana:focus", "Focused task", status="In Review", action_state="waiting")
    task.focus_rank = 0
    task.waiting_reason = "Waiting for review from @alex"
    task.local_note = "Retest branch-admin permissions"
    task.manual_priority = "high"
    task.dependencies = [RelatedTask("2", "Prepare fixture", completed=False)]
    task.dependents = [RelatedTask("3", "Release suite", completed=False)]
    task.recent_comments = [
        TaskComment(
            "c1",
            "Alex",
            "Please cover the empty-state case.",
            datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc),
            unread=True,
        )
    ]
    task.unread_updates = 1
    output = tmp_path / "digest.html"
    render_html(
        [task],
        datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc),
        "dashboard",
        str(output),
        action_token="secret",
        dashboard_url="http://127.0.0.1:8765",
        summaries={
            "daily": {"new": 1, "completed": 2, "status_changed": 1, "reviews_completed": 0, "prs_merged": 0, "cleared": 0},
            "weekly": {"new": 3, "completed": 5, "status_changed": 4, "reviews_completed": 2, "prs_merged": 1, "cleared": 0},
            "latest_counts": {"action": 1, "waiting": 1, "focus": 1, "unread": 1},
        },
    )
    rendered = output.read_text(encoding="utf-8")
    assert "Today's plan" in rendered
    assert "Retest branch-admin permissions" in rendered
    assert "Prepare fixture" in rendered
    assert "Release suite" in rendered
    assert "Please cover the empty-state case." in rendered
    assert "Mark 1 update(s) read" in rendered
    assert "Priority override" in rendered
    assert "prefers-color-scheme:dark" in rendered
    assert "Drag to reorder" in rendered
    assert "Daily & weekly summaries" in rendered
    assert "This week" in rendered


def test_html_renders_smart_today_plan_controls(tmp_path) -> None:
    due = _task("asana:due", "Due today", due_on=date(2026, 7, 20), priority="urgent")
    review = TaskItem(
        key="github-review:org/repo#9",
        title="Review requested",
        url="https://github.com/org/repo/pull/9",
        source="github",
        github_kind="review_request",
        priority="high",
    )
    output = tmp_path / "digest.html"
    render_html(
        [due, review],
        datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc),
        "dashboard",
        str(output),
        action_token="secret",
        dashboard_url="http://127.0.0.1:8765",
        smart_plan_max_items=4,
    )
    rendered = output.read_text(encoding="utf-8")
    assert "Today's plan" in rendered
    assert "Use suggested plan" in rendered
    assert "Due today" in rendered
    assert "Review requested from you" in rendered
    assert 'value="accept_smart_plan"' in rendered


def test_html_renders_collapsed_activity_timeline(tmp_path) -> None:
    from task_digest.models import TaskEvent

    task = _task("asana:timeline", "Timeline task", status="In Review")
    task.timeline_events = [
        TaskEvent(
            id="comment-1",
            source="asana",
            kind="comment",
            title="Comment added",
            created_at=datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc),
            detail="Please retest this.",
            actor="Alex",
        ),
        TaskEvent(
            id="local-1",
            source="local",
            kind="local",
            title="Added to today’s plan",
            created_at=datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc),
        ),
    ]
    output = tmp_path / "digest.html"

    render_html(
        [task],
        datetime(2026, 7, 20, 11, 0, tzinfo=timezone.utc),
        "morning",
        str(output),
    )

    rendered = output.read_text(encoding="utf-8")
    assert "Activity timeline" in rendered
    assert "Please retest this." in rendered
    assert "Added to today’s plan" in rendered
    assert 'class="timeline"' in rendered


def test_dashboard_uses_wide_two_column_workspace(tmp_path) -> None:
    tasks = [
        _task("1", "Action task", status="In Development"),
        _task("2", "Waiting task", status="In Review", action_state="waiting"),
    ]
    output = tmp_path / "digest.html"
    render_html(
        tasks,
        datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc),
        "dashboard",
        str(output),
        source_statuses=[],
    )
    rendered = output.read_text(encoding="utf-8")
    assert 'class="dashboard-workspace"' in rendered
    assert 'class="dashboard-primary"' in rendered
    assert 'class="dashboard-secondary"' in rendered
    assert "Work queue" in rendered
    assert "Attention & context" in rendered
    assert "width: min(1480px, 100%)" in rendered


def test_task_card_has_scannable_badges_and_collapsed_details(tmp_path) -> None:
    task = _task("asana:card", "Improve task cards", status="In Review", action_state="waiting", priority="high", due_on=date(2026, 7, 21))
    task.age_basis = "status"
    task.age_working_days = 3
    task.project = "Product Sprint"
    task.unread_updates = 2
    output = tmp_path / "digest.html"
    render_html(
        [task],
        datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc),
        "dashboard",
        str(output),
        action_token="secret",
        dashboard_url="http://127.0.0.1:8765",
    )
    rendered = output.read_text(encoding="utf-8")
    assert 'class="priority-pill tone-high">High</span>' in rendered
    assert 'class="task-meta"' in rendered
    assert ">In Review</span>" in rendered
    assert ">3 working days</span>" in rendered
    assert ">Due tomorrow</span>" in rendered
    assert ">Product Sprint</span>" in rendered
    assert ">2 new</span>" in rendered
    assert "Details &amp; actions" in rendered
    assert "Open in Asana" in rendered


def test_linked_github_row_has_live_status_badges(tmp_path) -> None:
    from task_digest.models import GitHubLink

    task = _task("asana:github-row", "Linked PR card", status="In Development")
    task.github_links = [
        GitHubLink(
            owner="example-org",
            repo="web-tests",
            number=142,
            url="https://github.com/example-org/web-tests/pull/142",
            title="Improve permission coverage",
            pending_reviewers=["reviewer"],
            checks_pending=True,
        )
    ]
    output = tmp_path / "digest.html"
    render_html([task], datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc), "dashboard", str(output))
    rendered = output.read_text(encoding="utf-8")
    assert 'class="github-item"' in rendered
    assert "PR #142 · example-org/web-tests" in rendered
    assert "1 review pending" in rendered
    assert "CI running" in rendered
    assert "Open linked PR" in rendered


def test_dashboard_promotes_today_plan_before_controls_and_metrics(tmp_path) -> None:
    task = _task("asana:focus-first", "Plan-first task", status="In Development")
    task.focus_rank = 0
    output = tmp_path / "digest.html"
    render_html(
        [task],
        datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc),
        "dashboard",
        str(output),
        action_token="secret",
        dashboard_url="http://127.0.0.1:8765",
    )
    rendered = output.read_text(encoding="utf-8")
    plan_position = rendered.index("Today's plan")
    controls_position = rendered.index('class="dashboard-controls"')
    metrics_position = rendered.index('class="dashboard-metrics"')
    assert plan_position < controls_position < metrics_position


def test_dashboard_uses_four_primary_metrics_and_collapsed_secondary_metrics(tmp_path) -> None:
    tasks = [
        _task("1", "Action", status="In Development"),
        _task("2", "Waiting", status="In Review", action_state="waiting"),
        _task("3", "Investigation", optional=True),
    ]
    output = tmp_path / "digest.html"
    render_html(tasks, datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc), "dashboard", str(output))
    rendered = output.read_text(encoding="utf-8")
    primary_start = rendered.index('class="summary-grid primary-metrics"')
    secondary_start = rendered.index('class="more-metrics"')
    primary_html = rendered[primary_start:secondary_start]
    assert primary_html.count('class="summary-card ') == 4
    assert "Need action" in primary_html
    assert "Reviews" in primary_html
    assert "Waiting" in primary_html
    assert "New updates" in primary_html
    assert "More metrics" in rendered
    assert "Due / overdue" in rendered
    assert "PR blockers" in rendered
    assert "Investigations" in rendered
    assert "Plan items" in rendered
