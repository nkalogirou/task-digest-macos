from __future__ import annotations

from datetime import date, datetime, timedelta

from .models import ActionState, Priority, TaskItem

PRIORITY_RANK = {"urgent": 0, "high": 1, "normal": 2, "new": 3}


def working_days_between(start: date, end: date) -> int:
    """Count Monday-Friday boundaries after start up to and including end."""
    if end <= start:
        return 0
    count = 0
    cursor = start + timedelta(days=1)
    while cursor <= end:
        if cursor.weekday() < 5:
            count += 1
        cursor += timedelta(days=1)
    return count


def working_days_until(today: date, due_on: date) -> int:
    """Return the number of Monday-Friday boundaries from today to a future due date."""
    if due_on <= today:
        return 0
    return working_days_between(today, due_on)


def _age_priority(age_working_days: int, action_state: ActionState) -> Priority:
    if action_state == "waiting":
        if age_working_days >= 6:
            return "high"
        if age_working_days >= 1:
            return "normal"
        return "new"

    if age_working_days >= 6:
        return "urgent"
    if age_working_days >= 3:
        return "high"
    if age_working_days >= 1:
        return "normal"
    return "new"


def _due_priority(due_on: date | None, today: date) -> Priority | None:
    if not due_on:
        return None
    if due_on <= today:
        return "urgent"

    days = working_days_until(today, due_on)
    if days <= 1:
        return "high"
    if days <= 3:
        return "normal"
    return None


def priority_for(
    age_working_days: int,
    due_on: date | None,
    today: date,
    action_state: ActionState = "action",
) -> Priority:
    age_priority = _age_priority(age_working_days, action_state)
    due_priority = _due_priority(due_on, today)
    if due_priority and PRIORITY_RANK[due_priority] < PRIORITY_RANK[age_priority]:
        return due_priority
    return age_priority


def classify_action_state(
    item: TaskItem,
    action_statuses: set[str],
    waiting_statuses: set[str],
) -> TaskItem:
    status = str(item.status or "").strip().casefold()
    if status and status in waiting_statuses:
        item.action_state = "waiting"
    elif status and status in action_statuses:
        item.action_state = "action"
    else:
        # Unknown statuses stay actionable so the digest never silently hides work.
        item.action_state = "action"
    return item


def assign_priority(item: TaskItem, now: datetime) -> TaskItem:
    if item.status and item.status_changed_at:
        start = item.status_changed_at.date()
        item.age_basis = "status"
    else:
        assignment_start = item.assigned_at or item.created_at or now
        start = assignment_start.date()
        item.age_basis = "assigned"

    item.age_working_days = working_days_between(start, now.date())
    item.priority = priority_for(
        item.age_working_days,
        item.due_on,
        now.date(),
        action_state=item.action_state,
    )
    return item
