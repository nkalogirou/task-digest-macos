from datetime import datetime, timezone

from task_digest.enrichment import enrich_asana_task
from task_digest.models import GitHubLink, RelatedTask, TaskItem


def _task(status: str = "In Review") -> TaskItem:
    return TaskItem(
        key="asana:1",
        title="Task",
        url=None,
        source="asana",
        status=status,
        status_changed_at=datetime(2026, 7, 15, tzinfo=timezone.utc),
        age_basis="status",
    )


def test_incomplete_dependency_explains_waiting_reason() -> None:
    task = _task("In Development")
    task.dependencies = [RelatedTask("2", "Prepare fixtures", completed=False)]
    enrich_asana_task(
        task,
        datetime(2026, 7, 20, tzinfo=timezone.utc),
        action_statuses={"in development"},
        waiting_statuses={"in review"},
        stale_waiting_days=5,
    )
    assert task.action_state == "waiting"
    assert task.waiting_reason == "Blocked by Prepare fixtures"


def test_pending_github_reviewers_explain_waiting_reason() -> None:
    task = _task()
    task.github_links = [
        GitHubLink(
            owner="acme-inc",
            repo="web-app",
            number=99,
            url="https://github.com/acme-inc/web-app/pull/99",
            pending_reviewers=["alex", "sam"],
        )
    ]
    enrich_asana_task(
        task,
        datetime(2026, 7, 20, tzinfo=timezone.utc),
        action_statuses={"in development"},
        waiting_statuses={"in review"},
        stale_waiting_days=2,
    )
    assert task.action_state == "waiting"
    assert task.waiting_reason == "Waiting for review from @alex, @sam"
    assert task.stale_waiting
