from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .models import Priority, TaskEvent, TaskItem

_LOCK = threading.RLock()
_ALLOWED_PRIORITIES = {"urgent", "high", "normal", "new"}


def _iso(value: datetime) -> str:
    return value.isoformat()


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class WorkspaceState:
    """Local user-controlled metadata that never modifies Asana or GitHub."""

    def __init__(self, path: str) -> None:
        self.path = Path(path).expanduser()

    def _read(self) -> dict[str, Any]:
        with _LOCK:
            if not self.path.exists():
                return {"items": {}, "focus_order": [], "smart_plan_date": None, "notifications_paused_until": None}
            try:
                value = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {"items": {}, "focus_order": [], "smart_plan_date": None, "notifications_paused_until": None}
            if not isinstance(value, dict):
                return {"items": {}, "focus_order": [], "smart_plan_date": None, "notifications_paused_until": None}
            value.setdefault("items", {})
            value.setdefault("focus_order", [])
            value.setdefault("smart_plan_date", None)
            value.setdefault("notifications_paused_until", None)
            return value

    def _write(self, value: dict[str, Any]) -> None:
        with _LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            temporary.replace(self.path)

    def _item(self, data: dict[str, Any], key: str) -> dict[str, Any]:
        items = data.setdefault("items", {})
        item = items.setdefault(key, {})
        return item

    def apply(self, tasks: list[TaskItem], now: datetime) -> None:
        data = self._read()
        items = data.get("items", {}) if isinstance(data.get("items"), dict) else {}
        focus_order = [str(key) for key in data.get("focus_order", []) if key]
        smart_plan_date = str(data.get("smart_plan_date") or "")
        if smart_plan_date and smart_plan_date != now.date().isoformat():
            focus_order = []
        focus_rank = {key: index for index, key in enumerate(focus_order)}
        for task in tasks:
            raw = items.get(task.key, {}) if isinstance(items.get(task.key), dict) else {}
            task.local_note = str(raw.get("note") or "")
            override = str(raw.get("priority_override") or "").lower()
            if override in _ALLOWED_PRIORITIES:
                task.manual_priority = override  # type: ignore[assignment]
                task.priority = override  # type: ignore[assignment]
            task.focus_rank = focus_rank.get(task.key)
            seen_at = _parse_datetime(raw.get("updates_seen_at"))
            unread = 0
            for comment in task.recent_comments:
                comment.unread = seen_at is None or comment.created_at > seen_at
                if comment.unread:
                    unread += 1
            task.unread_updates = unread
            local_events = raw.get("events", []) if isinstance(raw.get("events"), list) else []
            for entry in local_events:
                if not isinstance(entry, dict):
                    continue
                title = str(entry.get("title") or "Local action").strip()
                if not title:
                    continue
                task.timeline_events.append(
                    TaskEvent(
                        id=str(entry.get("id") or f"local:{task.key}:{entry.get('at') or title}"),
                        source="local",
                        kind="local",
                        title=title,
                        created_at=_parse_datetime(entry.get("at")),
                        detail=str(entry.get("detail") or "").strip() or None,
                    )
                )

    def record_event(
        self,
        key: str,
        title: str,
        detail: str | None = None,
        when: datetime | None = None,
    ) -> None:
        if not key or not title.strip():
            return
        moment = when or datetime.now().astimezone()
        data = self._read()
        item = self._item(data, key)
        events = item.setdefault("events", [])
        if not isinstance(events, list):
            events = []
            item["events"] = events
        event = {
            "id": f"local:{moment.isoformat()}:{len(events)}",
            "at": moment.isoformat(),
            "title": title.strip(),
        }
        if detail and detail.strip():
            event["detail"] = detail.strip()
        events.append(event)
        item["events"] = events[-60:]
        self._write(data)

    def set_note(self, key: str, note: str) -> None:
        cleaned = note.strip()
        data = self._read()
        self._item(data, key)["note"] = cleaned
        self._write(data)
        self.record_event(key, "Private note updated" if cleaned else "Private note cleared")

    def set_priority(self, key: str, value: str | None) -> None:
        normalized = str(value or "").lower()
        if normalized and normalized not in _ALLOWED_PRIORITIES:
            raise ValueError(f"Unsupported priority: {value}")
        data = self._read()
        item = self._item(data, key)
        if normalized:
            item["priority_override"] = normalized
        else:
            item.pop("priority_override", None)
        self._write(data)
        label = normalized.title() if normalized else "Automatic"
        self.record_event(key, "Priority override changed", label)

    def toggle_focus(self, key: str, today: date | datetime | None = None) -> bool:
        data = self._read()
        order = [str(value) for value in data.get("focus_order", []) if value]
        day = today.date() if isinstance(today, datetime) else (today or date.today())
        smart_plan_date = str(data.get("smart_plan_date") or "")
        if smart_plan_date and smart_plan_date != day.isoformat():
            order = []
        if key in order:
            order.remove(key)
            focused = False
        else:
            order.append(key)
            focused = True
        data["focus_order"] = order
        data["smart_plan_date"] = None
        self._write(data)
        self.record_event(key, "Added to today’s plan" if focused else "Removed from today’s plan")
        return focused

    def set_focus_order(self, keys: list[str]) -> None:
        clean: list[str] = []
        for key in keys:
            if key and key not in clean:
                clean.append(key)
        data = self._read()
        existing = [str(value) for value in data.get("focus_order", []) if value]
        for key in existing:
            if key not in clean:
                clean.append(key)
        data["focus_order"] = clean
        self._write(data)

    def accept_smart_plan(self, keys: list[str], today: datetime | date) -> None:
        clean: list[str] = []
        for key in keys:
            if key and key not in clean:
                clean.append(key)
        day = today.date() if isinstance(today, datetime) else today
        data = self._read()
        data["focus_order"] = clean
        data["smart_plan_date"] = day.isoformat()
        self._write(data)
        for key in clean:
            self.record_event(key, "Added to smart plan", f"Plan for {day.isoformat()}")

    def clear_focus(self) -> None:
        data = self._read()
        data["focus_order"] = []
        data["smart_plan_date"] = None
        self._write(data)

    def smart_plan_date(self) -> str | None:
        value = self._read().get("smart_plan_date")
        return str(value) if value else None

    def mark_updates_read(self, key: str, when: datetime) -> None:
        data = self._read()
        self._item(data, key)["updates_seen_at"] = _iso(when)
        self._write(data)
        self.record_event(key, "Marked task updates read", when=when)

    def pause_notifications(self, now: datetime, minutes: int = 60) -> datetime:
        until = now + timedelta(minutes=max(1, minutes))
        data = self._read()
        data["notifications_paused_until"] = _iso(until)
        self._write(data)
        return until

    def resume_notifications(self) -> None:
        data = self._read()
        data["notifications_paused_until"] = None
        self._write(data)

    def notifications_paused_until(self) -> datetime | None:
        return _parse_datetime(self._read().get("notifications_paused_until"))

    def notifications_are_paused(self, now: datetime) -> bool:
        until = self.notifications_paused_until()
        if until is None:
            return False
        if until.tzinfo is None and now.tzinfo is not None:
            until = until.replace(tzinfo=now.tzinfo)
        return until > now

    def focus_order(self) -> list[str]:
        return [str(value) for value in self._read().get("focus_order", []) if value]
