from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Iterable

import httpx

from .models import (
    AsanaSectionOption,
    AsanaStatusOption,
    GitHubLink,
    RelatedTask,
    StatusSource,
    TaskComment,
    TaskEvent,
    TaskItem,
)

GITHUB_RE = re.compile(
    r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/(?:pull|issues)/(?P<number>\d+)",
    re.IGNORECASE,
)
STATUS_FIELD_NAMES = {"status", "task status", "state"}


class AsanaClient:
    BASE_URL = "https://app.asana.com/api/1.0"

    def __init__(self, token: str, timeout: float = 30.0) -> None:
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=timeout,
        )
        self._project_section_task_cache: dict[str, dict[str, dict[str, Any]]] = {}
        self._project_sections_cache: dict[str, list[AsanaSectionOption]] = {}
        self._my_task_sections_cache: dict[str, list[AsanaSectionOption]] = {}

    def close(self) -> None:
        self.client.close()

    def _get_paginated(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        next_params = dict(params)
        while True:
            response = self.client.get(path, params=next_params)
            response.raise_for_status()
            payload = response.json()
            results.extend(payload.get("data", []))
            next_page = payload.get("next_page")
            if not next_page or not next_page.get("offset"):
                break
            next_params["offset"] = next_page["offset"]
        return results

    def list_workspaces(self) -> list[dict[str, Any]]:
        return self._get_paginated("/workspaces", {"limit": 100})

    def update_task(self, task_gid: str, fields: dict[str, Any]) -> dict[str, Any]:
        response = self.client.put(f"/tasks/{task_gid}", json={"data": fields})
        response.raise_for_status()
        return response.json().get("data", {})

    def complete_task(self, task_gid: str) -> dict[str, Any]:
        return self.update_task(task_gid, {"completed": True})

    def set_due_on(self, task_gid: str, due_on: date | None) -> dict[str, Any]:
        return self.update_task(task_gid, {"due_on": due_on.isoformat() if due_on else None})

    def set_assignee(self, task_gid: str, assignee_gid: str | None) -> dict[str, Any]:
        return self.update_task(task_gid, {"assignee": assignee_gid})

    def add_comment(self, task_gid: str, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("The Asana comment cannot be empty.")
        response = self.client.post(
            f"/tasks/{task_gid}/stories",
            json={"data": {"text": cleaned}},
        )
        response.raise_for_status()
        return response.json().get("data", {})

    def move_task_to_section(self, task_gid: str, section_gid: str, scope: str) -> dict[str, Any]:
        if scope == "my_tasks":
            return self.update_task(task_gid, {"assignee_section": section_gid})
        if scope != "project":
            raise ValueError(f"Unsupported Asana section scope: {scope}")
        response = self.client.post(
            f"/sections/{section_gid}/addTask",
            json={"data": {"task": task_gid}},
        )
        response.raise_for_status()
        return response.json().get("data", {})

    def set_enum_status(self, task_gid: str, field_gid: str, option_gid: str) -> dict[str, Any]:
        if not field_gid or not option_gid:
            raise ValueError("A status field and option are required.")
        return self.update_task(task_gid, {"custom_fields": {field_gid: option_gid}})

    def get_me(self) -> dict[str, Any]:
        response = self.client.get("/users/me", params={"opt_fields": "gid,name"})
        response.raise_for_status()
        return response.json().get("data", {})

    def _get_task_details(self, task_gid: str, opt_fields: str) -> dict[str, Any]:
        """Fetch the full task record.

        Asana's collection endpoint can occasionally return incomplete membership
        details. The single-task endpoint is used as the source of truth for the
        current project section so Drafts/Investigations are classified reliably.
        """
        response = self.client.get(
            f"/tasks/{task_gid}",
            params={"opt_fields": opt_fields},
        )
        response.raise_for_status()
        return response.json().get("data", {})

    def list_assigned_tasks(
        self,
        workspace_gid: str,
        project_gids: set[str] | None = None,
        excluded_sections: set[str] | None = None,
        optional_sections: set[str] | None = None,
        include_dependencies: bool = True,
        recent_comment_limit: int = 3,
        include_write_options: bool = False,
    ) -> list[TaskItem]:
        me_gid = str(self.get_me().get("gid") or "")
        opt_fields = ",".join(
            [
                "gid",
                "name",
                "completed",
                "created_at",
                "modified_at",
                "due_on",
                "due_at",
                "permalink_url",
                "notes",
                "html_notes",
                "external",
                "external.data",
                "assignee_status",
                "assignee_section",
                "assignee_section.gid",
                "assignee_section.name",
                "memberships",
                "memberships.project",
                "memberships.project.gid",
                "memberships.project.name",
                "memberships.section",
                "memberships.section.gid",
                "memberships.section.name",
                "custom_fields.gid",
                "custom_fields.name",
                "custom_fields.display_value",
                "custom_fields.enum_value.gid",
                "custom_fields.enum_value.name",
                "custom_fields.enum_options.gid",
                "custom_fields.enum_options.name",
                "custom_fields.enum_options.enabled",
            ]
        )
        raw_tasks = self._get_paginated(
            "/tasks",
            {
                "assignee": "me",
                "workspace": workspace_gid,
                "completed_since": "now",
                "limit": 100,
                "opt_fields": opt_fields,
            },
        )

        excluded_sections = excluded_sections or set()
        optional_sections = optional_sections or set()
        my_task_sections = self._get_my_task_sections(workspace_gid) if include_write_options else []

        items: list[TaskItem] = []
        for task_summary in raw_tasks:
            task_gid = str(task_summary.get("gid") or "")
            task = self._get_task_details(task_gid, opt_fields) if task_gid else task_summary
            if task.get("completed"):
                continue
            memberships = self._hydrate_missing_sections(
                task_gid=task_gid,
                memberships=task.get("memberships") or [],
            )
            if project_gids:
                task_project_gids = {
                    str(m.get("project", {}).get("gid"))
                    for m in memberships
                    if m.get("project", {}).get("gid")
                }
                if not task_project_gids.intersection(project_gids):
                    continue

            membership, project_visibility = self._select_membership(
                memberships,
                project_gids=project_gids,
                excluded_sections=excluded_sections,
                optional_sections=optional_sections,
            )
            assignee_section = task.get("assignee_section") or {}
            my_tasks_visibility = self._section_visibility(
                assignee_section.get("name"),
                excluded_sections=excluded_sections,
                optional_sections=optional_sections,
            )
            # Sections shown in the user's My Tasks view are exposed by Asana as
            # assignee_section, not as a project membership. My Tasks visibility
            # takes precedence because it is the list the user is organizing here.
            visibility = (
                my_tasks_visibility
                if my_tasks_visibility != "actionable"
                else project_visibility
            )
            if visibility == "excluded":
                continue

            project_data = membership.get("project") or {}
            project = project_data.get("name")
            project_gid = str(project_data.get("gid") or "")
            section_data = membership.get("section") or {}
            section = str(assignee_section.get("name") or "").strip() or section_data.get("name")
            status, status_source = self._derive_status(task, section_data)
            created_at = self._parse_datetime(task.get("created_at"))
            timeline = self._get_task_timeline(
                task_gid=str(task["gid"]),
                me_gid=me_gid,
                status=status,
                status_source=status_source,
                created_at=created_at,
            )
            # Keep compatibility with older test doubles and local extensions
            # that returned the original three-value timeline tuple.
            if len(timeline) == 3:
                assigned_at, status_changed_at, history_notes = timeline
                recent_comments = []
                timeline_events = []
            elif len(timeline) == 4:
                assigned_at, status_changed_at, history_notes, recent_comments = timeline
                timeline_events = []
            else:
                assigned_at, status_changed_at, history_notes, recent_comments, timeline_events = timeline
            item = TaskItem(
                key=f"asana:{task['gid']}",
                title=task.get("name") or "Untitled task",
                url=task.get("permalink_url"),
                source="asana",
                created_at=created_at,
                assigned_at=assigned_at,
                status_changed_at=status_changed_at,
                due_on=self._parse_date(task.get("due_on"), task.get("due_at")),
                status=status,
                status_source=status_source,
                project=project,
                section=section,
                github_links=self._get_github_links(str(task["gid"]), task),
                notes=history_notes,
                is_optional=visibility == "optional",
                dependencies=(self._get_related_tasks(str(task["gid"]), "dependencies") if include_dependencies else []),
                dependents=(self._get_related_tasks(str(task["gid"]), "dependents") if include_dependencies else []),
                recent_comments=recent_comments[: max(0, recent_comment_limit)],
                asana_sections=self._merge_section_options(
                    my_task_sections,
                    self._get_project_sections(project_gid, str(project or "")) if include_write_options and project_gid else [],
                ),
                asana_status_options=self._status_options(task, status_source) if include_write_options else [],
                timeline_events=timeline_events,
            )
            item.timeline_events.extend(self._relationship_events(item))
            items.append(item)
        return items

    def _get_my_task_sections(self, workspace_gid: str) -> list[AsanaSectionOption]:
        if workspace_gid in self._my_task_sections_cache:
            return self._my_task_sections_cache[workspace_gid]
        try:
            response = self.client.get(
                "/users/me/user_task_list",
                params={"workspace": workspace_gid, "opt_fields": "gid,name"},
            )
            response.raise_for_status()
            user_task_list = response.json().get("data", {})
            list_gid = str(user_task_list.get("gid") or "")
            rows = self._get_paginated(
                f"/projects/{list_gid}/sections",
                {"limit": 100, "opt_fields": "gid,name"},
            ) if list_gid else []
        except httpx.HTTPError:
            rows = []
        options = [
            AsanaSectionOption(
                gid=str(row.get("gid") or ""),
                name=str(row.get("name") or "Untitled section"),
                scope="my_tasks",
            )
            for row in rows
            if row.get("gid")
        ]
        self._my_task_sections_cache[workspace_gid] = options
        return options

    def _get_project_sections(self, project_gid: str, project_name: str) -> list[AsanaSectionOption]:
        if project_gid in self._project_sections_cache:
            return self._project_sections_cache[project_gid]
        try:
            rows = self._get_paginated(
                f"/projects/{project_gid}/sections",
                {"limit": 100, "opt_fields": "gid,name"},
            )
        except httpx.HTTPError:
            rows = []
        options = [
            AsanaSectionOption(
                gid=str(row.get("gid") or ""),
                name=str(row.get("name") or "Untitled section"),
                scope="project",
                project_name=project_name or None,
            )
            for row in rows
            if row.get("gid")
        ]
        self._project_sections_cache[project_gid] = options
        return options

    @staticmethod
    def _merge_section_options(*groups: list[AsanaSectionOption]) -> list[AsanaSectionOption]:
        merged: list[AsanaSectionOption] = []
        seen: set[tuple[str, str]] = set()
        for group in groups:
            for option in group:
                identity = (option.scope, option.gid)
                if identity in seen:
                    continue
                seen.add(identity)
                merged.append(option)
        return merged

    @staticmethod
    def _status_options(task: dict[str, Any], source: StatusSource | None) -> list[AsanaStatusOption]:
        if not source or source.kind != "custom_field" or not source.gid:
            return []
        for field in task.get("custom_fields") or []:
            if str(field.get("gid") or "") != source.gid:
                continue
            return [
                AsanaStatusOption(gid=str(option.get("gid") or ""), name=str(option.get("name") or ""))
                for option in field.get("enum_options") or []
                if option.get("gid") and option.get("name") and option.get("enabled", True)
            ]
        return []

    def _hydrate_missing_sections(
        self,
        task_gid: str,
        memberships: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Fill missing section data using the project section task lists.

        Asana can return a project membership without its section even when the
        task is visibly inside a section in the UI. Asking for the parent fields
        fixes most cases; this fallback maps the task through the project's
        section endpoints for the remaining cases.
        """
        hydrated: list[dict[str, Any]] = []
        for raw_membership in memberships:
            membership = dict(raw_membership)
            project = dict(membership.get("project") or {})
            section = membership.get("section") or {}
            project_gid = str(project.get("gid") or "")
            if task_gid and project_gid and not section.get("name"):
                resolved = self._find_task_section_in_project(task_gid, project_gid)
                if resolved:
                    membership["section"] = resolved
            hydrated.append(membership)
        return hydrated

    def _find_task_section_in_project(
        self,
        task_gid: str,
        project_gid: str,
    ) -> dict[str, Any] | None:
        if project_gid not in self._project_section_task_cache:
            task_sections: dict[str, dict[str, Any]] = {}
            try:
                sections = self._get_paginated(
                    f"/projects/{project_gid}/sections",
                    {"limit": 100, "opt_fields": "gid,name"},
                )
                for section in sections:
                    section_gid = str(section.get("gid") or "")
                    if not section_gid:
                        continue
                    tasks = self._get_paginated(
                        f"/sections/{section_gid}/tasks",
                        {"limit": 100, "opt_fields": "gid"},
                    )
                    section_record = {
                        "gid": section_gid,
                        "name": str(section.get("name") or ""),
                    }
                    for task in tasks:
                        listed_task_gid = str(task.get("gid") or "")
                        if listed_task_gid:
                            task_sections[listed_task_gid] = section_record
            except httpx.HTTPStatusError:
                # Keep the digest working even when the token cannot read project
                # sections. The task remains actionable rather than being hidden
                # based on a guess.
                task_sections = {}
            self._project_section_task_cache[project_gid] = task_sections
        return self._project_section_task_cache[project_gid].get(task_gid)


    @classmethod
    def _section_visibility(
        cls,
        section_name: Any,
        excluded_sections: set[str],
        optional_sections: set[str],
    ) -> str:
        normalized = cls._normalize(section_name)
        if normalized in excluded_sections:
            return "excluded"
        if normalized in optional_sections:
            return "optional"
        return "actionable"

    @classmethod
    def _select_membership(
        cls,
        memberships: list[dict[str, Any]],
        project_gids: set[str] | None,
        excluded_sections: set[str],
        optional_sections: set[str],
    ) -> tuple[dict[str, Any], str]:
        candidates = [m for m in memberships if m.get("project")]
        if project_gids:
            candidates = [
                m
                for m in candidates
                if str((m.get("project") or {}).get("gid") or "") in project_gids
            ]

        excluded = next(
            (
                m
                for m in candidates
                if cls._normalize((m.get("section") or {}).get("name")) in excluded_sections
            ),
            None,
        )
        if excluded:
            return excluded, "excluded"

        optional = next(
            (
                m
                for m in candidates
                if cls._normalize((m.get("section") or {}).get("name")) in optional_sections
            ),
            None,
        )
        if optional:
            return optional, "optional"

        return (candidates[0] if candidates else {}), "actionable"

    def _get_task_timeline(
        self,
        task_gid: str,
        me_gid: str,
        status: str | None,
        status_source: StatusSource | None,
        created_at: datetime | None,
    ) -> tuple[datetime | None, datetime | None, list[str], list[TaskComment], list[TaskEvent]]:
        notes: list[str] = []
        opt_fields = ",".join(
            [
                "gid",
                "created_at",
                "resource_subtype",
                "assignee.gid",
                "assignee.name",
                "old_section.gid",
                "old_section.name",
                "new_section.gid",
                "new_section.name",
                "custom_field.gid",
                "custom_field.name",
                "old_enum_value.gid",
                "old_enum_value.name",
                "new_enum_value.gid",
                "new_enum_value.name",
                "old_text_value",
                "new_text_value",
                "old_multi_enum_values.gid",
                "old_multi_enum_values.name",
                "new_multi_enum_values.gid",
                "new_multi_enum_values.name",
                "created_by.gid",
                "created_by.name",
                "text",
                "html_text",
            ]
        )
        try:
            stories = self._get_paginated(
                f"/tasks/{task_gid}/stories",
                {"limit": 100, "opt_fields": opt_fields},
            )
        except httpx.HTTPStatusError as exc:
            notes.append(f"Could not read Asana history ({exc.response.status_code})")
            return created_at, None, notes, [], []

        assigned_at = self._first_assignment_to_user(stories, me_gid) or created_at
        status_changed_at = self._latest_status_change(stories, status, status_source)
        recent_comments = self._recent_comments(stories)
        timeline_events = self._story_events(stories, me_gid)
        return assigned_at, status_changed_at, notes, recent_comments, timeline_events


    @classmethod
    def _story_events(cls, stories: list[dict[str, Any]], me_gid: str) -> list[TaskEvent]:
        events: list[TaskEvent] = []
        for story in stories:
            created_at = cls._parse_datetime(story.get("created_at"))
            if created_at is None:
                continue
            subtype = str(story.get("resource_subtype") or "").strip()
            creator = story.get("created_by") or {}
            actor = str(creator.get("name") or "").strip() or None
            event_id = str(story.get("gid") or f"asana:{subtype}:{created_at.isoformat()}")

            if subtype == "comment_added":
                text = str(story.get("text") or "").strip()
                if text:
                    events.append(TaskEvent(event_id, "asana", "comment", "Comment added", created_at, text, actor))
                continue

            assignee = story.get("assignee") or {}
            assignee_gid = str(assignee.get("gid") or "")
            if assignee_gid:
                name = str(assignee.get("name") or ("you" if assignee_gid == me_gid else assignee_gid))
                title = "Assigned to you" if assignee_gid == me_gid else f"Assigned to {name}"
                events.append(TaskEvent(event_id, "asana", "assignment", title, created_at, actor=actor))
                continue

            new_section = story.get("new_section") or {}
            if new_section.get("name"):
                old_section = story.get("old_section") or {}
                before = str(old_section.get("name") or "No section")
                after = str(new_section.get("name") or "")
                events.append(TaskEvent(event_id, "asana", "status", "Section changed", created_at, f"{before} → {after}", actor))
                continue

            field = story.get("custom_field") or {}
            if field.get("name"):
                before = cls._story_old_custom_value(story) or "No value"
                after = cls._story_new_custom_value(story) or "No value"
                events.append(TaskEvent(event_id, "asana", "status", f"{field.get('name')} changed", created_at, f"{before} → {after}", actor))
                continue

            text = str(story.get("text") or "").strip()
            labels = {
                "marked_complete": "Marked complete",
                "marked_incomplete": "Reopened",
                "due_date_changed": "Due date changed",
                "name_changed": "Task name changed",
                "dependency_added": "Dependency added",
                "dependency_removed": "Dependency removed",
                "added_to_project": "Added to project",
                "removed_from_project": "Removed from project",
            }
            title = labels.get(subtype)
            if title or text:
                events.append(TaskEvent(event_id, "asana", "due_date" if "due" in subtype else "system", title or subtype.replace("_", " ").title(), created_at, text or None, actor))

        return sorted(events, key=lambda event: event.created_at or datetime.min.replace(tzinfo=None), reverse=True)

    @staticmethod
    def _story_old_custom_value(story: dict[str, Any]) -> str | None:
        enum_value = story.get("old_enum_value") or {}
        if enum_value.get("name") is not None:
            return str(enum_value["name"])
        if story.get("old_text_value") is not None:
            return str(story["old_text_value"])
        multi_values = story.get("old_multi_enum_values") or []
        if multi_values:
            return ", ".join(str(value.get("name") or "") for value in multi_values)
        return None

    @staticmethod
    def _relationship_events(item: TaskItem) -> list[TaskEvent]:
        events: list[TaskEvent] = []
        for dependency in item.dependencies:
            state = "Completed" if dependency.completed else "Currently blocking"
            events.append(TaskEvent(f"dependency:{dependency.gid}", "asana", "dependency", dependency.title, detail=state, url=dependency.url, current=True))
        for dependent in item.dependents:
            events.append(TaskEvent(f"dependent:{dependent.gid}", "asana", "dependency", dependent.title, detail="Currently depends on this task", url=dependent.url, current=True))
        return events


    @classmethod
    def _recent_comments(cls, stories: list[dict[str, Any]]) -> list[TaskComment]:
        comments: list[TaskComment] = []
        for story in stories:
            if str(story.get("resource_subtype") or "") != "comment_added":
                continue
            created_at = cls._parse_datetime(story.get("created_at"))
            if created_at is None:
                continue
            text = str(story.get("text") or "").strip()
            if not text:
                continue
            creator = story.get("created_by") or {}
            comments.append(
                TaskComment(
                    gid=str(story.get("gid") or ""),
                    author=str(creator.get("name") or "Unknown"),
                    text=text,
                    created_at=created_at,
                )
            )
        return sorted(comments, key=lambda comment: comment.created_at, reverse=True)

    def _get_related_tasks(self, task_gid: str, relation: str) -> list[RelatedTask]:
        if relation not in {"dependencies", "dependents"}:
            raise ValueError(f"Unsupported Asana relation: {relation}")
        try:
            rows = self._get_paginated(
                f"/tasks/{task_gid}/{relation}",
                {
                    "limit": 100,
                    "opt_fields": "gid,name,completed,permalink_url",
                },
            )
        except httpx.HTTPStatusError:
            return []
        return [
            RelatedTask(
                gid=str(row.get("gid") or ""),
                title=str(row.get("name") or "Untitled task"),
                url=str(row.get("permalink_url") or "") or None,
                completed=bool(row.get("completed")),
            )
            for row in rows
            if row.get("gid")
        ]

    @classmethod
    def _first_assignment_to_user(
        cls,
        stories: list[dict[str, Any]],
        user_gid: str,
    ) -> datetime | None:
        candidates: list[datetime] = []
        for story in stories:
            assignee_gid = str((story.get("assignee") or {}).get("gid") or "")
            if not assignee_gid or assignee_gid != user_gid:
                continue
            created_at = cls._parse_datetime(story.get("created_at"))
            if created_at:
                candidates.append(created_at)
        return min(candidates) if candidates else None

    @classmethod
    def _latest_status_change(
        cls,
        stories: list[dict[str, Any]],
        status: str | None,
        source: StatusSource | None,
    ) -> datetime | None:
        if not status or not source:
            return None

        candidates: list[datetime] = []
        expected = cls._normalize(status)
        for story in stories:
            matched = False
            if source.kind == "custom_field":
                field = story.get("custom_field") or {}
                same_field = bool(source.gid and str(field.get("gid") or "") == source.gid)
                if not same_field and source.name:
                    same_field = cls._normalize(field.get("name")) == cls._normalize(source.name)
                if same_field:
                    new_value = cls._story_new_custom_value(story)
                    matched = cls._normalize(new_value) == expected
            elif source.kind == "section":
                new_section = story.get("new_section") or {}
                same_section = bool(source.gid and str(new_section.get("gid") or "") == source.gid)
                if not same_section and source.name:
                    same_section = cls._normalize(new_section.get("name")) == cls._normalize(source.name)
                matched = same_section

            if matched:
                created_at = cls._parse_datetime(story.get("created_at"))
                if created_at:
                    candidates.append(created_at)
        return max(candidates) if candidates else None

    @staticmethod
    def _story_new_custom_value(story: dict[str, Any]) -> str | None:
        enum_value = story.get("new_enum_value") or {}
        if enum_value.get("name") is not None:
            return str(enum_value["name"])
        if story.get("new_text_value") is not None:
            return str(story["new_text_value"])
        multi_values = story.get("new_multi_enum_values") or []
        if multi_values:
            return ", ".join(str(value.get("name") or "") for value in multi_values)
        return None

    @staticmethod
    def _iter_strings(value: Any) -> Iterable[str]:
        if isinstance(value, str):
            yield value
            return
        if isinstance(value, dict):
            for nested in value.values():
                yield from AsanaClient._iter_strings(nested)
            return
        if isinstance(value, (list, tuple, set)):
            for nested in value:
                yield from AsanaClient._iter_strings(nested)

    def _get_github_links(
        self,
        task_gid: str,
        task: dict[str, Any] | None = None,
    ) -> list[GitHubLink]:
        params = {
            "limit": 100,
            "opt_fields": (
                "name,view_url,permanent_url,download_url,host,"
                "resource_subtype,parent"
            ),
        }
        try:
            attachments = self._get_paginated(
                f"/tasks/{task_gid}/attachments",
                params,
            )
        except httpx.HTTPStatusError:
            # Compatibility fallback for older Asana API behavior.
            attachments = self._get_paginated(
                "/attachments",
                {**params, "parent": task_gid},
            )

        links: dict[str, GitHubLink] = {}
        sources: list[tuple[str, str | None]] = []
        for attachment in attachments:
            attachment_name = str(attachment.get("name") or "").strip() or None
            for candidate in self._iter_strings(attachment):
                sources.append((candidate, attachment_name))

        # GitHub app attachments normally expose view_url, but links can also be
        # present in task notes or external app metadata. Parsing both makes the
        # digest resilient while the Asana GitHub card is still synchronizing.
        if task:
            for field in ("notes", "html_notes", "external"):
                for candidate in self._iter_strings(task.get(field)):
                    sources.append((candidate, None))

        for candidate, attachment_name in sources:
            for match in GITHUB_RE.finditer(candidate):
                kind = "issue" if "/issues/" in match.group(0).lower() else "pull"
                canonical_url = (
                    f"https://github.com/{match.group('owner')}/{match.group('repo')}/"
                    f"{'issues' if kind == 'issue' else 'pull'}/{match.group('number')}"
                )
                link = GitHubLink(
                    owner=match.group("owner"),
                    repo=match.group("repo"),
                    number=int(match.group("number")),
                    url=canonical_url,
                    kind=kind,
                    title=attachment_name,
                )
                existing = links.get(link.key)
                if existing is None or (not existing.title and link.title):
                    links[link.key] = link
        return sorted(links.values(), key=lambda link: (link.owner.casefold(), link.repo.casefold(), link.number))

    @staticmethod
    def _derive_status(
        task: dict[str, Any],
        section: dict[str, Any],
    ) -> tuple[str | None, StatusSource | None]:
        for field in task.get("custom_fields") or []:
            name = str(field.get("name") or "").strip()
            if name.lower() not in STATUS_FIELD_NAMES:
                continue
            value = field.get("display_value") or (field.get("enum_value") or {}).get("name")
            status = str(value).strip() if value else None
            return status, StatusSource(
                kind="custom_field",
                gid=str(field.get("gid") or "") or None,
                name=name,
                value=status,
            )

        section_name = str(section.get("name") or "").strip() or None
        if section_name:
            return section_name, StatusSource(
                kind="section",
                gid=str(section.get("gid") or "") or None,
                name=section_name,
                value=section_name,
            )

        assignee_status = str(task.get("assignee_status") or "").strip() or None
        if assignee_status:
            return assignee_status, StatusSource(
                kind="assignee_status",
                name="assignee_status",
                value=assignee_status,
            )
        return None, None

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @staticmethod
    def _parse_date(due_on: str | None, due_at: str | None) -> date | None:
        if due_on:
            return date.fromisoformat(due_on)
        if due_at:
            return datetime.fromisoformat(due_at.replace("Z", "+00:00")).date()
        return None

    @staticmethod
    def _normalize(value: Any) -> str:
        return str(value or "").strip().casefold()
