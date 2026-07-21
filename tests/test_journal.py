from datetime import date, datetime, timezone

from task_digest.changes import compare_snapshots, snapshot_tasks
from task_digest.journal import ActivityJournal
from task_digest.models import TaskItem


def _task(key: str, *, source: str = "asana", github_kind: str | None = None) -> TaskItem:
    return TaskItem(
        key=key,
        title=key,
        url=None,
        source=source,  # type: ignore[arg-type]
        github_kind=github_kind,  # type: ignore[arg-type]
    )


def test_journal_records_daily_and_weekly_activity(tmp_path) -> None:
    journal = ActivityJournal(str(tmp_path / "activity.json"))
    now = datetime(2026, 7, 20, 17, 30, tzinfo=timezone.utc)
    current = [_task("asana:new")]
    previous = snapshot_tasks([
        _task("asana:done"),
        _task("github-review:repo#1", source="github", github_kind="review_request"),
    ])
    changes = compare_snapshots(previous, current)
    journal.record("evening", now, current, changes)

    summary = journal.summaries(date(2026, 7, 20))
    assert summary["daily"]["new"] == 1
    assert summary["daily"]["completed"] == 1
    assert summary["daily"]["reviews_completed"] == 1
    assert summary["weekly"] == summary["daily"]
