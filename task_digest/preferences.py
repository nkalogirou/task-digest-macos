from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from .models import TaskItem


@dataclass(frozen=True)
class PreferenceResult:
    visible: list[TaskItem]
    suppressed_keys: set[str]
    snoozed_count: int
    ignored_count: int
    expired_or_changed_count: int


def add_working_days(start: date, days: int) -> date:
    """Return the date reached after advancing Monday-Friday working days."""
    if days < 0:
        raise ValueError("days must be zero or greater")
    cursor = start
    remaining = days
    while remaining:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            remaining -= 1
    return cursor


def task_fingerprint(item: TaskItem) -> str:
    due = item.due_on.isoformat() if item.due_on else ""
    links = ",".join(
        sorted(
            f"{link.key}:{link.state or ''}:{link.is_draft}:{'|'.join(link.action_reasons)}"
            for link in item.github_links
        )
    )
    return "|".join(
        [
            item.status or "",
            item.section or "",
            item.action_state,
            due,
            links,
        ]
    )


class TaskPreferences:
    """Local snooze and ignore rules stored separately from digest send state."""

    def __init__(self, path: str) -> None:
        self.path = Path(path).expanduser()
        self.entries: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(raw, dict):
            self.entries = {
                str(key): value
                for key, value in raw.items()
                if isinstance(value, dict)
            }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.entries, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def ignore(self, item: TaskItem, now: datetime) -> None:
        self.entries[item.key] = {
            "mode": "ignore",
            "title": item.title,
            "created_at": now.isoformat(),
        }
        self.save()

    def snooze_for_working_days(
        self,
        item: TaskItem,
        days: int,
        today: date,
        now: datetime,
    ) -> date:
        if days < 1:
            raise ValueError("working days must be at least 1")
        wake_on = add_working_days(today, days)
        self.entries[item.key] = {
            "mode": "until_date",
            "title": item.title,
            "wake_on": wake_on.isoformat(),
            "created_at": now.isoformat(),
        }
        self.save()
        return wake_on

    def snooze_until_change(self, item: TaskItem, now: datetime) -> None:
        self.entries[item.key] = {
            "mode": "until_change",
            "title": item.title,
            "fingerprint": task_fingerprint(item),
            "created_at": now.isoformat(),
        }
        self.save()

    def restore(self, key: str) -> bool:
        removed = self.entries.pop(key, None) is not None
        if removed:
            self.save()
        return removed

    def list_entries(self) -> list[tuple[str, dict[str, Any]]]:
        return sorted(self.entries.items(), key=lambda pair: pair[1].get("title", pair[0]).casefold())

    def filter(self, tasks: Iterable[TaskItem], today: date) -> PreferenceResult:
        task_list = list(tasks)
        visible: list[TaskItem] = []
        suppressed: set[str] = set()
        snoozed = 0
        ignored = 0
        cleared = 0
        changed = False

        for item in task_list:
            rule = self.entries.get(item.key)
            if not rule:
                visible.append(item)
                continue

            mode = str(rule.get("mode") or "")
            if mode == "ignore":
                ignored += 1
                suppressed.add(item.key)
                continue

            if mode == "until_date":
                raw_wake = str(rule.get("wake_on") or "")
                try:
                    wake_on = date.fromisoformat(raw_wake)
                except ValueError:
                    wake_on = today
                if today < wake_on:
                    snoozed += 1
                    suppressed.add(item.key)
                    continue
                self.entries.pop(item.key, None)
                cleared += 1
                changed = True
                visible.append(item)
                continue

            if mode == "until_change":
                if str(rule.get("fingerprint") or "") == task_fingerprint(item):
                    snoozed += 1
                    suppressed.add(item.key)
                    continue
                self.entries.pop(item.key, None)
                cleared += 1
                changed = True
                visible.append(item)
                continue

            # Unknown preference modes are ignored and removed rather than hiding work.
            self.entries.pop(item.key, None)
            cleared += 1
            changed = True
            visible.append(item)

        # Remove temporary snoozes for tasks that no longer exist. Permanent ignores
        # are retained so a recurring item with the same key remains ignored.
        task_keys = {item.key for item in task_list}
        for key, rule in list(self.entries.items()):
            if key in task_keys or rule.get("mode") == "ignore":
                continue
            self.entries.pop(key, None)
            cleared += 1
            changed = True

        if changed:
            self.save()

        return PreferenceResult(
            visible=visible,
            suppressed_keys=suppressed,
            snoozed_count=snoozed,
            ignored_count=ignored,
            expired_or_changed_count=cleared,
        )
