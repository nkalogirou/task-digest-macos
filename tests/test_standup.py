from __future__ import annotations

import json
from datetime import date

from task_digest.journal import ActivityJournal
from task_digest.models import TaskItem
from task_digest.standup import build_standup, previous_workday, render_standup_page, save_standup


def _task(
    key: str,
    title: str,
    *,
    action_state: str = "action",
    priority: str = "normal",
    focus_rank: int | None = None,
    waiting_reason: str | None = None,
    stale_waiting: bool = False,
) -> TaskItem:
    return TaskItem(
        key=key,
        title=title,
        url=f"https://example.test/{key}",
        source="asana",
        status="In Development" if action_state == "action" else "In Review",
        project="Web Platform",
        action_state=action_state,  # type: ignore[arg-type]
        priority=priority,  # type: ignore[arg-type]
        focus_rank=focus_rank,
        waiting_reason=waiting_reason,
        stale_waiting=stale_waiting,
        age_working_days=6 if stale_waiting else 1,
    )


def test_previous_workday_skips_weekend() -> None:
    assert previous_workday(date(2026, 7, 20)) == date(2026, 7, 17)
    assert previous_workday(date(2026, 7, 21)) == date(2026, 7, 20)


def test_build_standup_uses_focus_and_previous_workday_events(tmp_path) -> None:
    path = tmp_path / "journal.json"
    path.write_text(
        json.dumps(
            {
                "runs": [],
                "events": [
                    {
                        "id": "1",
                        "date": "2026-07-20",
                        "at": "2026-07-20T16:00:00+03:00",
                        "kind": "completed",
                        "key": "asana:done",
                        "title": "Finished task",
                        "url": "https://example.test/done",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    tasks = [
        _task("asana:normal", "Normal task", priority="urgent"),
        _task("asana:focus", "Focused task", priority="new", focus_rank=0),
        _task(
            "asana:waiting",
            "Waiting task",
            action_state="waiting",
            waiting_reason="Waiting for review",
            stale_waiting=True,
        ),
    ]
    report = build_standup(tasks, ActivityJournal(str(path)), date(2026, 7, 21))
    assert [entry.title for entry in report.yesterday] == ["Finished task"]
    assert report.today[0].title == "Focused task"
    assert report.waiting[0].title == "Waiting task"
    assert "follow-up suggested" in report.waiting[0].detail


def test_render_standup_page_contains_copy_and_save_controls(tmp_path) -> None:
    journal = ActivityJournal(str(tmp_path / "journal.json"))
    report = build_standup([_task("asana:one", "One task")], journal, date(2026, 7, 21))
    page = render_standup_page(report, "token", "http://127.0.0.1:8765")
    assert "Copy to clipboard" in page
    assert "Save to history" in page
    assert 'href="http://127.0.0.1:8765/standup"' in page
    assert "One task" in page


def test_save_standup_creates_markdown_history(tmp_path) -> None:
    report = build_standup(
        [_task("asana:one", "One task")],
        ActivityJournal(str(tmp_path / "journal.json")),
        date(2026, 7, 21),
    )
    path = save_standup(report, str(tmp_path / "history"))
    assert path.name == "standup-2026-07-21.md"
    assert "# Stand-up" in path.read_text(encoding="utf-8")
    assert "One task" in path.read_text(encoding="utf-8")
