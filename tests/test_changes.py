from datetime import date

from task_digest.changes import compare_snapshots, snapshot_tasks
from task_digest.models import TaskItem


def task(
    key: str,
    *,
    status: str = "Pending",
    priority: str = "normal",
    due_on: date | None = None,
) -> TaskItem:
    return TaskItem(
        key=key,
        title=f"Task {key}",
        url=None,
        source="asana",
        status=status,
        priority=priority,  # type: ignore[arg-type]
        due_on=due_on,
    )


def test_compare_snapshots_detects_new_status_due_priority_and_removed() -> None:
    previous = snapshot_tasks(
        [
            task("1", status="Pending", priority="normal"),
            task("2"),
            task("3", due_on=date(2026, 7, 25)),
        ]
    )
    current = [
        task("1", status="In Development", priority="high"),
        task("3", due_on=date(2026, 7, 22)),
        task("4"),
    ]
    changes = compare_snapshots(previous, current)
    assert changes.baseline_available
    assert [item.key for item in changes.new] == ["4"]
    assert [change.task.key for change in changes.status_changed] == ["1"]
    assert [change.task.key for change in changes.priority_increased] == ["1"]
    assert [change.task.key for change in changes.due_changed] == ["3"]
    assert [item.key for item in changes.removed] == ["2"]


def test_no_previous_snapshot_is_not_a_real_evening_baseline() -> None:
    changes = compare_snapshots({}, [task("1")])
    assert not changes.baseline_available
    assert [item.key for item in changes.new] == ["1"]


def test_suppressed_task_is_not_reported_as_removed() -> None:
    previous = {
        "asana:1": {
            "title": "Snoozed task",
            "url": None,
            "status": "Pending",
            "action_state": "action",
            "is_optional": False,
            "source": "asana",
        }
    }
    changes = compare_snapshots(previous, [], suppressed_keys={"asana:1"})
    assert changes.removed == []
