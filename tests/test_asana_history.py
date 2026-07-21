from datetime import datetime, timezone

from task_digest.asana_client import AsanaClient
from task_digest.models import StatusSource


def test_first_assignment_to_current_user() -> None:
    stories = [
        {
            "created_at": "2026-07-01T09:00:00.000Z",
            "assignee": {"gid": "me"},
        },
        {
            "created_at": "2026-07-05T09:00:00.000Z",
            "assignee": {"gid": "other"},
        },
        {
            "created_at": "2026-07-10T09:00:00.000Z",
            "assignee": {"gid": "me"},
        },
    ]
    assert AsanaClient._first_assignment_to_user(stories, "me") == datetime(
        2026, 7, 1, 9, 0, tzinfo=timezone.utc
    )


def test_latest_custom_status_change_matching_current_value() -> None:
    source = StatusSource(kind="custom_field", gid="status-field", name="Status")
    stories = [
        {
            "created_at": "2026-07-03T09:00:00.000Z",
            "custom_field": {"gid": "status-field", "name": "Status"},
            "new_enum_value": {"name": "In Deployment"},
        },
        {
            "created_at": "2026-07-12T09:00:00.000Z",
            "custom_field": {"gid": "status-field", "name": "Status"},
            "new_enum_value": {"name": "In Review"},
        },
    ]
    assert AsanaClient._latest_status_change(stories, "In Review", source) == datetime(
        2026, 7, 12, 9, 0, tzinfo=timezone.utc
    )


def test_empty_status_field_does_not_fall_back_to_section() -> None:
    task = {
        "custom_fields": [
            {
                "gid": "status-field",
                "name": "Status",
                "display_value": None,
                "enum_value": None,
            }
        ],
        "assignee_status": "inbox",
    }
    status, source = AsanaClient._derive_status(
        task,
        {"gid": "section-1", "name": "In Development"},
    )
    assert status is None
    assert source is not None
    assert source.kind == "custom_field"


def test_drafts_membership_is_excluded() -> None:
    membership, visibility = AsanaClient._select_membership(
        [
            {
                "project": {"gid": "project-1", "name": "Web Platform"},
                "section": {"gid": "section-drafts", "name": "Drafts"},
            }
        ],
        project_gids=None,
        excluded_sections={"drafts"},
        optional_sections={"investigations"},
    )
    assert membership["section"]["name"] == "Drafts"
    assert visibility == "excluded"


def test_investigations_membership_is_optional() -> None:
    membership, visibility = AsanaClient._select_membership(
        [
            {
                "project": {"gid": "project-1", "name": "Web Platform"},
                "section": {"gid": "section-investigations", "name": "Investigations"},
            }
        ],
        project_gids=None,
        excluded_sections={"drafts"},
        optional_sections={"investigations"},
    )
    assert membership["section"]["name"] == "Investigations"
    assert visibility == "optional"


def test_list_assigned_tasks_uses_full_task_membership(monkeypatch) -> None:
    client = AsanaClient("test-token")
    try:
        monkeypatch.setattr(client, "get_me", lambda: {"gid": "me"})
        monkeypatch.setattr(
            client,
            "_get_paginated",
            lambda path, params: [{"gid": "task-1", "name": "Summary without memberships"}]
            if path == "/tasks"
            else [],
        )
        monkeypatch.setattr(
            client,
            "_get_task_details",
            lambda task_gid, opt_fields: {
                "gid": task_gid,
                "name": "Translation regression coverage",
                "completed": False,
                "created_at": "2026-07-01T09:00:00.000Z",
                "permalink_url": "https://app.asana.com/0/1/task-1",
                "memberships": [
                    {
                        "project": {"gid": "project-1", "name": "Web Platform"},
                        "section": {"gid": "section-1", "name": "Investigations"},
                    }
                ],
                "custom_fields": [],
            },
        )
        monkeypatch.setattr(
            client,
            "_get_task_timeline",
            lambda **kwargs: (datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc), None, []),
        )
        monkeypatch.setattr(client, "_get_github_links", lambda task_gid, task=None: [])

        items = client.list_assigned_tasks(
            workspace_gid="workspace-1",
            optional_sections={"investigations"},
            excluded_sections={"drafts"},
        )

        assert len(items) == 1
        assert items[0].section == "Investigations"
        assert items[0].is_optional is True
    finally:
        client.close()


def test_hydrate_missing_section_uses_project_section_lookup(monkeypatch) -> None:
    client = AsanaClient("test-token")
    try:
        monkeypatch.setattr(
            client,
            "_find_task_section_in_project",
            lambda task_gid, project_gid: {
                "gid": "section-drafts",
                "name": "Drafts",
            },
        )
        memberships = client._hydrate_missing_sections(
            "task-1",
            [
                {
                    "project": {"gid": "project-1", "name": "Web Platform"},
                    "section": None,
                }
            ],
        )
        assert memberships[0]["section"]["name"] == "Drafts"
    finally:
        client.close()


def test_project_section_lookup_builds_and_reuses_cache(monkeypatch) -> None:
    client = AsanaClient("test-token")
    calls: list[str] = []

    def fake_get_paginated(path, params):
        calls.append(path)
        if path == "/projects/project-1/sections":
            return [
                {"gid": "section-investigations", "name": "Investigations"},
                {"gid": "section-drafts", "name": "Drafts"},
            ]
        if path == "/sections/section-investigations/tasks":
            return [{"gid": "task-investigation"}]
        if path == "/sections/section-drafts/tasks":
            return [{"gid": "task-draft"}]
        raise AssertionError(f"Unexpected path: {path}")

    try:
        monkeypatch.setattr(client, "_get_paginated", fake_get_paginated)
        first = client._find_task_section_in_project("task-investigation", "project-1")
        second = client._find_task_section_in_project("task-draft", "project-1")

        assert first == {"gid": "section-investigations", "name": "Investigations"}
        assert second == {"gid": "section-drafts", "name": "Drafts"}
        assert calls.count("/projects/project-1/sections") == 1
    finally:
        client.close()


def test_my_tasks_drafts_section_is_excluded(monkeypatch) -> None:
    client = AsanaClient("test-token")
    try:
        monkeypatch.setattr(client, "get_me", lambda: {"gid": "me"})
        monkeypatch.setattr(
            client,
            "_get_paginated",
            lambda path, params: [{"gid": "task-1", "name": "Draft summary"}]
            if path == "/tasks"
            else [],
        )
        monkeypatch.setattr(
            client,
            "_get_task_details",
            lambda task_gid, opt_fields: {
                "gid": task_gid,
                "name": "Draft task",
                "completed": False,
                "created_at": "2026-07-01T09:00:00.000Z",
                "permalink_url": "https://app.asana.com/0/1/task-1",
                "assignee_section": {"gid": "my-drafts", "name": "Drafts"},
                "memberships": [
                    {
                        "project": {"gid": "project-1", "name": "Web Platform"},
                        "section": {"gid": "project-section", "name": "Pending"},
                    }
                ],
                "custom_fields": [],
            },
        )
        monkeypatch.setattr(client, "_get_task_timeline", lambda **kwargs: (None, None, []))
        monkeypatch.setattr(client, "_get_github_links", lambda task_gid, task=None: [])

        items = client.list_assigned_tasks(
            workspace_gid="workspace-1",
            excluded_sections={"drafts"},
            optional_sections={"investigations"},
        )
        assert items == []
    finally:
        client.close()


def test_my_tasks_investigations_section_is_optional(monkeypatch) -> None:
    client = AsanaClient("test-token")
    try:
        monkeypatch.setattr(client, "get_me", lambda: {"gid": "me"})
        monkeypatch.setattr(
            client,
            "_get_paginated",
            lambda path, params: [{"gid": "task-1", "name": "Investigation summary"}]
            if path == "/tasks"
            else [],
        )
        monkeypatch.setattr(
            client,
            "_get_task_details",
            lambda task_gid, opt_fields: {
                "gid": task_gid,
                "name": "Investigation task",
                "completed": False,
                "created_at": "2026-07-01T09:00:00.000Z",
                "permalink_url": "https://app.asana.com/0/1/task-1",
                "assignee_section": {"gid": "my-investigations", "name": "Investigations"},
                "memberships": [
                    {
                        "project": {"gid": "project-1", "name": "Web Platform"},
                        "section": {"gid": "project-section", "name": "In Review"},
                    }
                ],
                "custom_fields": [],
            },
        )
        monkeypatch.setattr(client, "_get_task_timeline", lambda **kwargs: (None, None, []))
        monkeypatch.setattr(client, "_get_github_links", lambda task_gid, task=None: [])

        items = client.list_assigned_tasks(
            workspace_gid="workspace-1",
            excluded_sections={"drafts"},
            optional_sections={"investigations"},
        )
        assert len(items) == 1
        assert items[0].is_optional is True
        assert items[0].section == "Investigations"
    finally:
        client.close()


def test_github_app_attachment_is_linked_to_asana_task(monkeypatch) -> None:
    client = AsanaClient("test-token")
    try:
        monkeypatch.setattr(
            client,
            "_get_paginated",
            lambda path, params: [
                {
                    "name": "#1381 Fix access-control coverage",
                    "view_url": "https://github.com/acme-inc/web-app/pull/1381",
                    "host": "github",
                }
            ]
            if path == "/tasks/task-1/attachments"
            else [],
        )
        links = client._get_github_links("task-1", {})
        assert len(links) == 1
        assert links[0].kind == "pull"
        assert links[0].url == "https://github.com/acme-inc/web-app/pull/1381"
        assert links[0].title == "#1381 Fix access-control coverage"
    finally:
        client.close()


def test_github_link_can_be_found_in_task_notes(monkeypatch) -> None:
    client = AsanaClient("test-token")
    try:
        monkeypatch.setattr(client, "_get_paginated", lambda path, params: [])
        links = client._get_github_links(
            "task-1",
            {"notes": "Implementation: https://github.com/acme-inc/web-app/pull/1549"},
        )
        assert [link.key for link in links] == ["acme-inc/web-app#1549"]
    finally:
        client.close()


def test_story_events_builds_combined_activity_timeline() -> None:
    stories = [
        {
            "gid": "assign-1",
            "created_at": "2026-07-01T09:00:00.000Z",
            "resource_subtype": "assigned",
            "assignee": {"gid": "me", "name": "Alex"},
            "created_by": {"name": "Maria"},
        },
        {
            "gid": "status-1",
            "created_at": "2026-07-02T10:00:00.000Z",
            "resource_subtype": "enum_custom_field_changed",
            "custom_field": {"gid": "status", "name": "Status"},
            "old_enum_value": {"name": "Pending"},
            "new_enum_value": {"name": "In Development"},
            "created_by": {"name": "Alex"},
        },
        {
            "gid": "comment-1",
            "created_at": "2026-07-03T11:00:00.000Z",
            "resource_subtype": "comment_added",
            "text": "Ready for another look.",
            "created_by": {"name": "Alex"},
        },
    ]

    events = AsanaClient._story_events(stories, "me")

    assert [event.kind for event in events] == ["comment", "status", "assignment"]
    assert events[0].detail == "Ready for another look."
    assert events[1].detail == "Pending → In Development"
    assert events[2].title == "Assigned to you"
