from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import TaskItem
from .priority import PRIORITY_RANK


@dataclass
class TaskChange:
    task: TaskItem
    old: dict[str, Any]


@dataclass
class RemovedTask:
    key: str
    title: str
    url: str | None
    status: str | None
    action_state: str
    is_optional: bool
    source: str = "asana"
    github_kind: str | None = None


@dataclass
class DigestChanges:
    baseline_available: bool
    new: list[TaskItem] = field(default_factory=list)
    status_changed: list[TaskChange] = field(default_factory=list)
    priority_increased: list[TaskChange] = field(default_factory=list)
    due_changed: list[TaskChange] = field(default_factory=list)
    removed: list[RemovedTask] = field(default_factory=list)
    still_action: list[TaskItem] = field(default_factory=list)

    @property
    def change_count(self) -> int:
        return (
            len(self.new)
            + len(self.status_changed)
            + len(self.priority_increased)
            + len(self.due_changed)
            + len(self.removed)
        )


def _github_snapshot(item: TaskItem) -> list[dict[str, Any]]:
    return [
        {
            "key": link.key,
            "state": link.state,
            "draft": link.is_draft,
            "reasons": list(link.action_reasons),
            "pending_reviewers": list(link.pending_reviewers),
            "checks_pending": link.checks_pending,
            "approvals": link.approvals,
            "review_decision": link.review_decision,
            "merge_state_status": link.merge_state_status,
            "unresolved_threads": len(link.unresolved_threads),
            "checks": [
                {"name": check.name, "bucket": check.bucket, "state": check.state}
                for check in link.checks
            ],
        }
        for link in item.github_links
    ]


def snapshot_tasks(tasks: list[TaskItem]) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for item in tasks:
        snapshot[item.key] = {
            "title": item.title,
            "url": item.url,
            "source": item.source,
            "github_kind": item.github_kind,
            "status": item.status,
            "priority": item.priority,
            "due_on": item.due_on.isoformat() if item.due_on else None,
            "action_state": item.action_state,
            "waiting_reason": item.waiting_reason,
            "is_optional": item.is_optional,
            "section": item.section,
            "project": item.project,
            "github_action": _github_snapshot(item),
        }
    return snapshot


def compare_snapshots(
    previous: dict[str, dict[str, Any]],
    tasks: list[TaskItem],
    suppressed_keys: set[str] | None = None,
) -> DigestChanges:
    current_by_key = {item.key: item for item in tasks}
    suppressed_keys = suppressed_keys or set()
    changes = DigestChanges(
        baseline_available=bool(previous),
        still_action=[
            item
            for item in tasks
            if item.source == "asana" and not item.is_optional and item.action_state == "action"
        ],
    )

    if not previous:
        changes.new = list(tasks)
        return changes

    for key, item in current_by_key.items():
        old = previous.get(key)
        if old is None:
            changes.new.append(item)
            continue

        if (
            old.get("status") != item.status
            or old.get("action_state") != item.action_state
            or old.get("waiting_reason") != item.waiting_reason
            or old.get("github_action") != _github_snapshot(item)
        ):
            changes.status_changed.append(TaskChange(task=item, old=old))

        old_priority = str(old.get("priority") or "new")
        if (
            old_priority in PRIORITY_RANK
            and PRIORITY_RANK[item.priority] < PRIORITY_RANK[old_priority]
        ):
            changes.priority_increased.append(TaskChange(task=item, old=old))

        new_due = item.due_on.isoformat() if item.due_on else None
        if old.get("due_on") != new_due:
            changes.due_changed.append(TaskChange(task=item, old=old))

    for key, old in previous.items():
        if key in current_by_key or key in suppressed_keys:
            continue
        changes.removed.append(
            RemovedTask(
                key=key,
                title=str(old.get("title") or "Untitled task"),
                url=old.get("url"),
                status=old.get("status"),
                action_state=str(old.get("action_state") or "action"),
                is_optional=bool(old.get("is_optional")),
                source=str(old.get("source") or "asana"),
                github_kind=(str(old.get("github_kind")) if old.get("github_kind") else None),
            )
        )

    return changes
