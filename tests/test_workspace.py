from datetime import datetime, timezone

from task_digest.models import TaskComment, TaskItem
from task_digest.workspace import WorkspaceState


def _task(key: str) -> TaskItem:
    return TaskItem(key=key, title=key, url=None, source="asana")


def test_workspace_applies_note_priority_focus_and_unread(tmp_path) -> None:
    path = tmp_path / "workspace.json"
    workspace = WorkspaceState(str(path))
    now = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)
    task = _task("asana:1")
    task.recent_comments = [
        TaskComment("c1", "Alex", "Old", datetime(2026, 7, 19, 8, 0, tzinfo=timezone.utc)),
        TaskComment("c2", "Sam", "New", datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)),
    ]

    workspace.set_note(task.key, "Check admin permissions")
    workspace.set_priority(task.key, "urgent")
    workspace.toggle_focus(task.key)
    workspace.mark_updates_read(task.key, datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc))
    workspace.apply([task], now)

    assert task.local_note == "Check admin permissions"
    assert task.priority == "urgent"
    assert task.manual_priority == "urgent"
    assert task.is_focused
    assert task.unread_updates == 1
    assert [comment.unread for comment in task.recent_comments] == [False, True]


def test_workspace_focus_order_and_notification_pause(tmp_path) -> None:
    workspace = WorkspaceState(str(tmp_path / "workspace.json"))
    first, second = _task("asana:1"), _task("asana:2")
    workspace.toggle_focus(first.key)
    workspace.toggle_focus(second.key)
    workspace.set_focus_order([second.key, first.key])
    workspace.apply([first, second], datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc))

    assert second.focus_rank == 0
    assert first.focus_rank == 1

    now = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)
    workspace.pause_notifications(now, 60)
    assert workspace.notifications_are_paused(now)
    workspace.resume_notifications()
    assert not workspace.notifications_are_paused(now)


def test_smart_plan_expires_next_day_but_manual_focus_persists(tmp_path) -> None:
    workspace = WorkspaceState(str(tmp_path / "workspace.json"))
    task = _task("asana:1")
    plan_day = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)
    workspace.accept_smart_plan([task.key], plan_day)
    workspace.apply([task], plan_day)
    assert task.is_focused

    next_day_task = _task("asana:1")
    workspace.apply([next_day_task], datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc))
    assert not next_day_task.is_focused

    workspace.toggle_focus(task.key, datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc))
    manual_task = _task("asana:1")
    workspace.apply([manual_task], datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc))
    assert manual_task.is_focused


def test_clear_focus_removes_plan(tmp_path) -> None:
    workspace = WorkspaceState(str(tmp_path / "workspace.json"))
    now = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)
    workspace.accept_smart_plan(["asana:1", "asana:2"], now)
    workspace.clear_focus()
    assert workspace.focus_order() == []
    assert workspace.smart_plan_date() is None


def test_workspace_local_actions_appear_in_task_timeline(tmp_path) -> None:
    workspace = WorkspaceState(str(tmp_path / "workspace.json"))
    when = datetime(2026, 7, 21, 9, 30, tzinfo=timezone.utc)
    workspace.record_event("asana:1", "Priority override changed", "High", when)
    task = TaskItem(key="asana:1", title="Test task", url=None, source="asana")

    workspace.apply([task], when)

    assert len(task.timeline_events) == 1
    assert task.timeline_events[0].source == "local"
    assert task.timeline_events[0].title == "Priority override changed"
    assert task.timeline_events[0].detail == "High"
