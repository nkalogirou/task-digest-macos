from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .changes import DigestChanges
from .models import TaskItem

_LOCK = threading.RLock()


class ActivityJournal:
    def __init__(self, path: str) -> None:
        self.path = Path(path).expanduser()

    def _read(self) -> dict[str, Any]:
        with _LOCK:
            if not self.path.exists():
                return {"runs": [], "events": []}
            try:
                value = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {"runs": [], "events": []}
            return value if isinstance(value, dict) else {"runs": [], "events": []}

    def _write(self, value: dict[str, Any]) -> None:
        with _LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            tmp.replace(self.path)

    def record(self, period: str, now: datetime, tasks: list[TaskItem], changes: DigestChanges) -> None:
        data = self._read()
        runs = data.setdefault("runs", [])
        events = data.setdefault("events", [])
        run_id = f"{now.date().isoformat()}:{period}"
        run = {
            "id": run_id,
            "at": now.isoformat(),
            "period": period,
            "counts": {
                "action": sum(1 for task in tasks if task.action_state == "action" and not task.is_optional),
                "waiting": sum(1 for task in tasks if task.action_state == "waiting" and not task.is_optional),
                "focus": sum(1 for task in tasks if task.is_focused),
                "reviews": sum(1 for task in tasks if task.github_kind == "review_request"),
                "unread": sum(task.unread_updates for task in tasks),
            },
        }
        runs[:] = [entry for entry in runs if entry.get("id") != run_id]
        runs.append(run)

        def add_event(kind: str, key: str, title: str, **metadata: object) -> None:
            event_id = f"{now.date().isoformat()}:{kind}:{key}"
            if any(entry.get("id") == event_id for entry in events):
                return
            event = {
                "id": event_id,
                "date": now.date().isoformat(),
                "at": now.isoformat(),
                "kind": kind,
                "key": key,
                "title": title,
            }
            event.update({name: value for name, value in metadata.items() if value is not None})
            events.append(event)

        for task in changes.new:
            add_event("new", task.key, task.title, url=task.url, source=task.source)
        for change in changes.status_changed:
            add_event(
                "status_changed",
                change.task.key,
                change.task.title,
                url=change.task.url,
                source=change.task.source,
                old_status=change.old.get("status"),
                new_status=change.task.status,
            )
            old_links = change.old.get("github_action") or []
            new_links = {link.key: link for link in change.task.github_links}
            for old_link in old_links:
                key = str(old_link.get("key") or "")
                current = new_links.get(key)
                if current and str(current.state or "").upper() == "MERGED" and str(old_link.get("state") or "").upper() != "MERGED":
                    add_event("pr_merged", key, current.title or key, url=current.url, source="github")
        for removed in changes.removed:
            if removed.github_kind == "review_request":
                add_event("review_completed", removed.key, removed.title, url=removed.url, source=removed.source)
            elif removed.source == "asana":
                add_event("completed", removed.key, removed.title, url=removed.url, source=removed.source)
            else:
                add_event("cleared", removed.key, removed.title, url=removed.url, source=removed.source)

        cutoff = (now.date() - timedelta(days=60)).isoformat()
        data["runs"] = [entry for entry in runs if str(entry.get("at") or "")[:10] >= cutoff]
        data["events"] = [entry for entry in events if str(entry.get("date") or "") >= cutoff]
        self._write(data)

    def events_between(self, start: date, end: date) -> list[dict[str, Any]]:
        data = self._read()
        results: list[dict[str, Any]] = []
        for entry in data.get("events", []):
            if not isinstance(entry, dict):
                continue
            try:
                event_date = date.fromisoformat(str(entry.get("date") or ""))
            except ValueError:
                continue
            if start <= event_date <= end:
                results.append(dict(entry))
        return sorted(results, key=lambda item: str(item.get("at") or ""))

    def summaries(self, today: date) -> dict[str, Any]:
        data = self._read()
        events = [entry for entry in data.get("events", []) if isinstance(entry, dict)]
        runs = [entry for entry in data.get("runs", []) if isinstance(entry, dict)]
        monday = today - timedelta(days=today.weekday())

        def count_range(start: date, end: date) -> dict[str, int]:
            counts = {
                "new": 0,
                "completed": 0,
                "status_changed": 0,
                "reviews_completed": 0,
                "prs_merged": 0,
                "cleared": 0,
            }
            for event in events:
                try:
                    event_date = date.fromisoformat(str(event.get("date")))
                except ValueError:
                    continue
                if not (start <= event_date <= end):
                    continue
                kind = str(event.get("kind") or "")
                mapping = {
                    "new": "new",
                    "completed": "completed",
                    "status_changed": "status_changed",
                    "review_completed": "reviews_completed",
                    "pr_merged": "prs_merged",
                    "cleared": "cleared",
                }
                key = mapping.get(kind)
                if key:
                    counts[key] += 1
            return counts

        latest_run = None
        if runs:
            latest_run = max(runs, key=lambda entry: str(entry.get("at") or ""))
        return {
            "daily": count_range(today, today),
            "weekly": count_range(monday, today),
            "latest_counts": (latest_run or {}).get("counts", {}),
            "week_start": monday.isoformat(),
        }
