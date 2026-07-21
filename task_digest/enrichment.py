from __future__ import annotations

from datetime import datetime

from .models import TaskItem
from .priority import assign_priority, classify_action_state
from .workspace import WorkspaceState


def _github_waiting_reason(task: TaskItem) -> str | None:
    for link in task.github_links:
        if link.is_draft or link.kind != "pull" or link.action_required:
            continue
        if link.checks_pending:
            return "Waiting for CI checks"
        if link.pending_reviewers:
            names = ", ".join(f"@{name}" for name in link.pending_reviewers[:4])
            if len(link.pending_reviewers) > 4:
                names += f" +{len(link.pending_reviewers) - 4} more"
            return f"Waiting for review from {names}"
        if link.review_decision == "APPROVED" or link.approvals:
            return "Approved — waiting to merge"
    return None


def enrich_asana_task(
    task: TaskItem,
    now: datetime,
    action_statuses: set[str],
    waiting_statuses: set[str],
    stale_waiting_days: int,
) -> None:
    classify_action_state(task, action_statuses=action_statuses, waiting_statuses=waiting_statuses)

    incomplete_dependencies = [dependency for dependency in task.dependencies if not dependency.completed]
    if incomplete_dependencies:
        task.action_state = "waiting"
        names = ", ".join(dependency.title for dependency in incomplete_dependencies[:3])
        if len(incomplete_dependencies) > 3:
            names += f" +{len(incomplete_dependencies) - 3} more"
        task.waiting_reason = f"Blocked by {names}"
    elif task.action_state == "waiting":
        github_reason = _github_waiting_reason(task)
        normalized = str(task.status or "").casefold()
        if github_reason:
            task.waiting_reason = github_reason
        elif "deployment" in normalized:
            task.waiting_reason = "Waiting for deployment"
        elif "review" in normalized:
            task.waiting_reason = "Waiting for review"
        elif "blocked" in normalized:
            task.waiting_reason = "Blocked — dependency or clarification needed"
        else:
            task.waiting_reason = f"Waiting in {task.status}" if task.status else "Waiting on others"

    # A linked GitHub blocker always turns the task back into actionable work.
    if any(link.action_required and not link.is_draft for link in task.github_links):
        task.action_state = "action"
        task.waiting_reason = None

    assign_priority(task, now)
    task.stale_waiting = (
        not task.is_optional
        and task.action_state == "waiting"
        and task.age_working_days >= stale_waiting_days
    )
    if task.stale_waiting:
        task.notes.append(
            f"Follow-up suggested: waiting {task.age_working_days} working days"
        )


def apply_local_workspace(tasks: list[TaskItem], workspace: WorkspaceState, now: datetime) -> None:
    workspace.apply(tasks, now)
