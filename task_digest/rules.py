from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .models import Priority, TaskItem
from .priority import assign_priority

_LOCK = threading.RLock()

CONDITION_LABELS: dict[str, str] = {
    "always": "Always",
    "status_is": "Status is",
    "section_is": "Section is",
    "age_at_least": "Action/status age is at least",
    "waiting_age_at_least": "Waiting age is at least",
    "overdue": "Task is overdue",
    "checks_failing": "Linked PR has failing checks",
    "changes_requested": "Linked PR has changes requested",
    "merge_conflict": "Linked PR has a merge conflict",
    "has_blocker": "Task has an incomplete dependency",
    "priority_is": "Current priority is",
}

ACTION_LABELS: dict[str, str] = {
    "set_priority": "Set priority",
    "set_state": "Classify as",
    "hide": "Hide from digest",
    "optional": "Move to optional",
    "follow_up": "Suggest follow-up",
    "add_note": "Add digest note",
}

SOURCE_LABELS: dict[str, str] = {
    "all": "Asana and GitHub",
    "asana": "Asana only",
    "github": "GitHub only",
}

_VALUE_REQUIRED_CONDITIONS = {
    "status_is",
    "section_is",
    "age_at_least",
    "waiting_age_at_least",
    "priority_is",
}
_VALUE_REQUIRED_ACTIONS = {"set_priority", "set_state", "add_note"}
_ALLOWED_PRIORITIES = {"urgent", "high", "normal", "new"}
_ALLOWED_STATES = {"action", "waiting"}
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class TaskRule:
    id: str
    name: str
    enabled: bool
    source: str
    project: str
    repository: str
    condition: str
    condition_value: str
    action: str
    action_value: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TaskRule":
        return validate_rule(value)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuleApplyResult:
    visible: list[TaskItem]
    hidden_count: int
    match_count: int
    enabled_count: int


def validate_rule(value: dict[str, Any]) -> TaskRule:
    identifier = str(value.get("id") or uuid.uuid4().hex[:12]).strip()
    name = str(value.get("name") or "Untitled rule").strip()
    if not name:
        raise ValueError("Rule name is required.")
    source = str(value.get("source") or "all").strip().casefold()
    if source not in SOURCE_LABELS:
        raise ValueError("Rule source must be all, Asana, or GitHub.")
    project = str(value.get("project") or "").strip()
    repository = str(value.get("repository") or "").strip()
    if repository and not _REPOSITORY_RE.fullmatch(repository):
        raise ValueError("Repository scope must use owner/repository.")
    condition = str(value.get("condition") or "always").strip().casefold()
    if condition not in CONDITION_LABELS:
        raise ValueError("Choose a supported rule condition.")
    condition_value = str(value.get("condition_value") or "").strip()
    if condition in _VALUE_REQUIRED_CONDITIONS and not condition_value:
        raise ValueError(f"{CONDITION_LABELS[condition]} needs a value.")
    if condition in {"age_at_least", "waiting_age_at_least"}:
        try:
            age = int(condition_value)
        except ValueError as exc:
            raise ValueError("Age conditions need a whole number of working days.") from exc
        if age < 0 or age > 365:
            raise ValueError("Age must be between 0 and 365 working days.")
        condition_value = str(age)
    if condition == "priority_is" and condition_value.casefold() not in _ALLOWED_PRIORITIES:
        raise ValueError("Priority condition must be urgent, high, normal, or new.")

    action = str(value.get("action") or "set_priority").strip().casefold()
    if action not in ACTION_LABELS:
        raise ValueError("Choose a supported rule action.")
    action_value = str(value.get("action_value") or "").strip()
    if action in _VALUE_REQUIRED_ACTIONS and not action_value:
        raise ValueError(f"{ACTION_LABELS[action]} needs a value.")
    if action == "set_priority" and action_value.casefold() not in _ALLOWED_PRIORITIES:
        raise ValueError("Priority action must be urgent, high, normal, or new.")
    if action == "set_state" and action_value.casefold() not in _ALLOWED_STATES:
        raise ValueError("Classification action must be action or waiting.")
    return TaskRule(
        id=identifier,
        name=name,
        enabled=bool(value.get("enabled", True)),
        source=source,
        project=project,
        repository=repository,
        condition=condition,
        condition_value=condition_value,
        action=action,
        action_value=action_value,
    )


class RuleStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def list(self) -> list[TaskRule]:
        return self._read()

    def save(self, value: dict[str, Any]) -> TaskRule:
        rule = validate_rule(value)
        with _LOCK:
            rules = self._read_unlocked()
            replaced = False
            output: list[TaskRule] = []
            for current in rules:
                if current.id == rule.id:
                    output.append(rule)
                    replaced = True
                else:
                    output.append(current)
            if not replaced:
                output.append(rule)
            self._write_unlocked(output)
        return rule

    def delete(self, identifier: str) -> bool:
        with _LOCK:
            rules = self._read_unlocked()
            output = [rule for rule in rules if rule.id != identifier]
            if len(output) == len(rules):
                return False
            self._write_unlocked(output)
            return True

    def toggle(self, identifier: str) -> TaskRule:
        with _LOCK:
            rules = self._read_unlocked()
            output: list[TaskRule] = []
            changed: TaskRule | None = None
            for rule in rules:
                if rule.id == identifier:
                    changed = TaskRule(**{**rule.to_dict(), "enabled": not rule.enabled})
                    output.append(changed)
                else:
                    output.append(rule)
            if changed is None:
                raise KeyError(identifier)
            self._write_unlocked(output)
            return changed

    def move(self, identifier: str, direction: str) -> None:
        with _LOCK:
            rules = self._read_unlocked()
            index = next((i for i, rule in enumerate(rules) if rule.id == identifier), None)
            if index is None:
                raise KeyError(identifier)
            target = index - 1 if direction == "up" else index + 1
            if 0 <= target < len(rules):
                rules[index], rules[target] = rules[target], rules[index]
                self._write_unlocked(rules)

    def apply(self, tasks: Iterable[TaskItem], now: datetime) -> RuleApplyResult:
        rules = [rule for rule in self.list() if rule.enabled]
        visible: list[TaskItem] = []
        hidden = 0
        matches = 0
        for task in tasks:
            is_hidden = False
            for rule in rules:
                if not rule_matches(rule, task, now):
                    continue
                matches += 1
                task.rule_matches.append(rule.name)
                if rule.action == "set_priority":
                    task.priority = rule.action_value.casefold()  # type: ignore[assignment]
                elif rule.action == "set_state":
                    task.action_state = rule.action_value.casefold()  # type: ignore[assignment]
                    if task.action_state == "action":
                        task.waiting_reason = None
                        task.stale_waiting = False
                    elif not task.waiting_reason:
                        task.waiting_reason = f"Waiting by rule: {rule.name}"
                    assign_priority(task, now)
                elif rule.action == "hide":
                    is_hidden = True
                elif rule.action == "optional":
                    task.is_optional = True
                elif rule.action == "follow_up":
                    task.stale_waiting = True
                    note = rule.action_value or "Follow-up suggested by rule"
                    if note not in task.notes:
                        task.notes.append(note)
                elif rule.action == "add_note":
                    if rule.action_value and rule.action_value not in task.notes:
                        task.notes.append(rule.action_value)
            if is_hidden:
                hidden += 1
            else:
                visible.append(task)
        return RuleApplyResult(visible, hidden, matches, len(rules))

    def _read(self) -> list[TaskRule]:
        with _LOCK:
            return self._read_unlocked()

    def _read_unlocked(self) -> list[TaskRule]:
        if not self.path.is_file():
            return []
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        raw_rules = value.get("rules", []) if isinstance(value, dict) else []
        output: list[TaskRule] = []
        for raw in raw_rules:
            if not isinstance(raw, dict):
                continue
            try:
                output.append(TaskRule.from_dict(raw))
            except ValueError:
                continue
        return output

    def _write_unlocked(self, rules: list[TaskRule]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = {"version": 1, "rules": [rule.to_dict() for rule in rules]}
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)


def _task_repositories(task: TaskItem) -> set[str]:
    repos = {f"{link.owner}/{link.repo}".casefold() for link in task.github_links}
    if task.url and "github.com/" in task.url:
        tail = task.url.split("github.com/", 1)[1].split("?", 1)[0].strip("/")
        parts = tail.split("/")
        if len(parts) >= 2:
            repos.add(f"{parts[0]}/{parts[1]}".casefold())
    return repos


def rule_matches(rule: TaskRule, task: TaskItem, now: datetime) -> bool:
    if rule.source != "all" and task.source != rule.source:
        return False
    if rule.project and str(task.project or "").casefold() != rule.project.casefold():
        return False
    if rule.repository and rule.repository.casefold() not in _task_repositories(task):
        return False

    value = rule.condition_value.casefold()
    if rule.condition == "always":
        return True
    if rule.condition == "status_is":
        return str(task.status or "").casefold() == value
    if rule.condition == "section_is":
        return str(task.section or "").casefold() == value
    if rule.condition == "age_at_least":
        return task.age_working_days >= int(rule.condition_value)
    if rule.condition == "waiting_age_at_least":
        return task.action_state == "waiting" and task.age_working_days >= int(rule.condition_value)
    if rule.condition == "overdue":
        return bool(task.due_on and task.due_on < now.date())
    if rule.condition == "checks_failing":
        linked = any(link.failed_checks or "Checks failing" in link.action_reasons for link in task.github_links if not link.is_draft)
        own_item = "checks failing" in str(task.status or "").casefold() or any("failing checks" in note.casefold() for note in task.notes)
        return linked or own_item
    if rule.condition == "changes_requested":
        linked = any(
            link.review_decision == "CHANGES_REQUESTED" or any("Changes requested" in reason for reason in link.action_reasons)
            for link in task.github_links
            if not link.is_draft
        )
        return linked or "changes requested" in str(task.status or "").casefold()
    if rule.condition == "merge_conflict":
        linked = any(
            str(link.mergeable or "").upper() == "CONFLICTING" or any("conflict" in reason.casefold() for reason in link.action_reasons)
            for link in task.github_links
            if not link.is_draft
        )
        return linked or "conflict" in str(task.status or "").casefold()
    if rule.condition == "has_blocker":
        return any(not dependency.completed for dependency in task.dependencies)
    if rule.condition == "priority_is":
        return task.priority == value
    return False


def describe_rule(rule: TaskRule) -> str:
    scope: list[str] = [SOURCE_LABELS[rule.source]]
    if rule.project:
        scope.append(f"project {rule.project}")
    if rule.repository:
        scope.append(f"repository {rule.repository}")
    condition = CONDITION_LABELS[rule.condition]
    if rule.condition_value:
        suffix = " working days" if rule.condition in {"age_at_least", "waiting_age_at_least"} else ""
        condition += f" {rule.condition_value}{suffix}"
    action = ACTION_LABELS[rule.action]
    if rule.action_value:
        action += f": {rule.action_value}"
    return f"When {condition}, {action.lower()} · {' · '.join(scope)}"
