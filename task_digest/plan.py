from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .models import TaskItem
from .priority import PRIORITY_RANK, working_days_until


@dataclass(frozen=True)
class PlanCandidate:
    task: TaskItem
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SmartPlan:
    candidates: tuple[PlanCandidate, ...]
    max_items: int

    @property
    def keys(self) -> list[str]:
        return [candidate.task.key for candidate in self.candidates]


def _append_reason(reasons: list[str], reason: str) -> None:
    if reason and reason not in reasons:
        reasons.append(reason)


def _score_task(task: TaskItem, today: date) -> PlanCandidate | None:
    if task.is_optional:
        return None

    score = 0
    reasons: list[str] = []

    if task.is_focused:
        score += 1_000
        _append_reason(reasons, "Already in your focus")

    if task.action_state == "waiting":
        if not task.stale_waiting:
            return PlanCandidate(task, score, tuple(reasons)) if task.is_focused else None
        score += 150
        _append_reason(reasons, f"Follow up after {task.age_working_days} working days")
    else:
        score += 90

    if task.due_on:
        if task.due_on < today:
            score += 430
            _append_reason(reasons, "Overdue")
        elif task.due_on == today:
            score += 400
            _append_reason(reasons, "Due today")
        else:
            days = working_days_until(today, task.due_on)
            if days <= 1:
                score += 300
                _append_reason(reasons, "Due next working day")
            elif days <= 3:
                score += 180
                _append_reason(reasons, f"Due in {days} working days")

    manual_scores = {"urgent": 360, "high": 240, "normal": 100, "new": 30}
    automatic_scores = {"urgent": 260, "high": 160, "normal": 70, "new": 20}
    if task.manual_priority:
        score += manual_scores[task.manual_priority]
        _append_reason(reasons, f"Manual {task.manual_priority} priority")
    else:
        score += automatic_scores[task.priority]
        if task.priority in {"urgent", "high"}:
            _append_reason(reasons, f"{task.priority.title()} priority")

    github_scores = {
        "authored_pr": (330, "Your PR needs action"),
        "review_request": (290, "Review requested from you"),
        "assigned_issue": (170, "GitHub issue assigned to you"),
        "mention": (140, "You were mentioned on GitHub"),
    }
    if task.github_kind in github_scores:
        points, reason = github_scores[task.github_kind]
        score += points
        _append_reason(reasons, reason)

    if any(link.action_required for link in task.github_links):
        score += 300
        _append_reason(reasons, "Linked PR needs action")

    if task.unread_updates:
        score += min(80, task.unread_updates * 18)
        _append_reason(reasons, f"{task.unread_updates} unread update(s)")

    if task.age_working_days:
        score += min(100, task.age_working_days * 9)
        if task.age_working_days >= 5 and task.action_state == "action":
            _append_reason(reasons, f"Actionable for {task.age_working_days} working days")

    incomplete_dependencies = [item for item in task.dependencies if not item.completed]
    if incomplete_dependencies:
        score -= min(160, len(incomplete_dependencies) * 80)
        _append_reason(reasons, f"Blocked by {len(incomplete_dependencies)} dependency")

    return PlanCandidate(task=task, score=score, reasons=tuple(reasons[:4]))


def build_smart_plan(
    tasks: list[TaskItem],
    today: date,
    max_items: int = 5,
    stale_waiting_limit: int = 1,
) -> SmartPlan:
    """Recommend a compact daily plan without changing any external source."""
    maximum = max(1, min(10, int(max_items)))
    waiting_limit = max(0, min(maximum, int(stale_waiting_limit)))
    candidates = [candidate for task in tasks if (candidate := _score_task(task, today)) is not None]
    candidates.sort(
        key=lambda candidate: (
            0 if candidate.task.is_focused else 1,
            -candidate.score,
            candidate.task.due_on or date.max,
            PRIORITY_RANK[candidate.task.priority],
            candidate.task.title.casefold(),
        )
    )

    selected: list[PlanCandidate] = []
    waiting_count = 0
    for candidate in candidates:
        if candidate.task.action_state == "waiting":
            if not candidate.task.is_focused and waiting_count >= waiting_limit:
                continue
            waiting_count += 1
        selected.append(candidate)
        if len(selected) >= maximum:
            break
    return SmartPlan(candidates=tuple(selected), max_items=maximum)
