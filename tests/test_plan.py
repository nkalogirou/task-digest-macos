from datetime import date, timedelta

from task_digest.models import GitHubLink, RelatedTask, TaskItem
from task_digest.plan import build_smart_plan


def _task(key: str, title: str, **kwargs) -> TaskItem:
    return TaskItem(key=key, title=title, url=None, source=kwargs.pop("source", "asana"), **kwargs)


def test_smart_plan_prioritizes_due_blockers_and_reviews() -> None:
    today = date(2026, 7, 21)
    ordinary = _task("asana:1", "Ordinary", priority="normal", age_working_days=2)
    due = _task("asana:2", "Due today", priority="new", due_on=today)
    review = _task(
        "github-review:org/repo#1",
        "Review PR",
        source="github",
        github_kind="review_request",
        priority="new",
    )
    linked = _task("asana:3", "Broken PR", priority="new")
    linked.github_links = [GitHubLink("org", "repo", 2, "https://github.com/org/repo/pull/2", action_reasons=["Checks failing"])]

    plan = build_smart_plan([ordinary, due, review, linked], today, max_items=3)

    assert len(plan.candidates) == 3
    assert plan.candidates[0].task.key in {"asana:2", "asana:3"}
    assert {candidate.task.key for candidate in plan.candidates} == {"asana:2", "asana:3", "github-review:org/repo#1"}
    assert any("Due today" in candidate.reasons for candidate in plan.candidates)
    assert any("Linked PR needs action" in candidate.reasons for candidate in plan.candidates)


def test_smart_plan_limits_stale_waiting_and_skips_optional() -> None:
    today = date(2026, 7, 21)
    waiting_a = _task("asana:w1", "Waiting A", action_state="waiting", stale_waiting=True, age_working_days=7)
    waiting_b = _task("asana:w2", "Waiting B", action_state="waiting", stale_waiting=True, age_working_days=8)
    optional = _task("asana:o", "Optional", is_optional=True, priority="urgent")
    action = _task("asana:a", "Action", priority="high")

    plan = build_smart_plan([waiting_a, waiting_b, optional, action], today, max_items=5, stale_waiting_limit=1)

    keys = plan.keys
    assert "asana:a" in keys
    assert "asana:o" not in keys
    assert len([key for key in keys if key.startswith("asana:w")]) == 1


def test_smart_plan_keeps_existing_focus_first_even_if_blocked() -> None:
    today = date(2026, 7, 21)
    focused = _task("asana:f", "Focused", priority="new", focus_rank=0)
    focused.dependencies = [RelatedTask("d", "Dependency", completed=False)]
    urgent = _task("asana:u", "Urgent", priority="urgent", due_on=today - timedelta(days=1))

    plan = build_smart_plan([urgent, focused], today, max_items=2)

    assert plan.keys[0] == "asana:f"
    assert "Already in your focus" in plan.candidates[0].reasons
