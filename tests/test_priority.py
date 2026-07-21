from datetime import date, datetime, timezone

from task_digest.models import TaskItem
from task_digest.priority import (
    assign_priority,
    classify_action_state,
    priority_for,
    working_days_between,
    working_days_until,
)


def test_weekend_is_ignored() -> None:
    assert working_days_between(date(2026, 7, 17), date(2026, 7, 20)) == 1
    assert working_days_until(date(2026, 7, 17), date(2026, 7, 20)) == 1


def test_priority_thresholds_for_action_tasks() -> None:
    today = date(2026, 7, 20)
    assert priority_for(0, None, today) == "new"
    assert priority_for(1, None, today) == "normal"
    assert priority_for(3, None, today) == "high"
    assert priority_for(6, None, today) == "urgent"


def test_due_dates_override_age() -> None:
    today = date(2026, 7, 20)
    assert priority_for(0, date(2026, 7, 19), today) == "urgent"
    assert priority_for(0, today, today) == "urgent"
    assert priority_for(0, date(2026, 7, 21), today) == "high"
    assert priority_for(0, date(2026, 7, 22), today) == "normal"


def test_waiting_tasks_do_not_become_urgent_from_age_alone() -> None:
    today = date(2026, 7, 20)
    assert priority_for(20, None, today, action_state="waiting") == "high"
    assert priority_for(20, today, today, action_state="waiting") == "urgent"


def test_priority_uses_current_status_age_when_available() -> None:
    item = TaskItem(
        key="1",
        title="A",
        url=None,
        source="asana",
        assigned_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        status="In Review",
        status_changed_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
    )
    classify_action_state(item, {"in development"}, {"in review"})
    assign_priority(item, datetime(2026, 7, 20, tzinfo=timezone.utc))
    assert item.action_state == "waiting"
    assert item.age_basis == "status"
    assert item.age_working_days == 1
    assert item.priority == "normal"


def test_unknown_status_remains_actionable() -> None:
    item = TaskItem(key="1", title="A", url=None, source="asana", status="Custom")
    classify_action_state(item, {"pending"}, {"in review"})
    assert item.action_state == "action"
