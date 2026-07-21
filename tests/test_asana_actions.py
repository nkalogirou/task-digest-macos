from datetime import date, datetime, timezone
from pathlib import Path

import httpx

from task_digest.asana_client import AsanaClient
from task_digest.digest import render_html
from task_digest.models import (
    AsanaSectionOption,
    AsanaStatusOption,
    StatusSource,
    TaskItem,
)
from task_digest.settings import BOOLEAN_KEYS, read_settings


def _client_with_transport(handler):
    client = AsanaClient("token")
    client.client.close()
    client.client = httpx.Client(
        base_url=client.BASE_URL,
        headers={"Authorization": "Bearer token"},
        transport=httpx.MockTransport(handler),
    )
    return client


def test_asana_write_methods_send_expected_payloads() -> None:
    requests: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path, __import__("json").loads(request.content or b"{}")))
        return httpx.Response(200, json={"data": {"ok": True}})

    client = _client_with_transport(handler)
    try:
        client.complete_task("123")
        client.set_due_on("123", date(2026, 7, 24))
        client.set_assignee("123", None)
        client.add_comment("123", "Please review")
        client.move_task_to_section("123", "sec-1", "project")
        client.move_task_to_section("123", "mine-1", "my_tasks")
        client.set_enum_status("123", "field-1", "option-2")
    finally:
        client.close()

    assert requests[0] == ("PUT", "/api/1.0/tasks/123", {"data": {"completed": True}})
    assert requests[1][2] == {"data": {"due_on": "2026-07-24"}}
    assert requests[2][2] == {"data": {"assignee": None}}
    assert requests[3] == ("POST", "/api/1.0/tasks/123/stories", {"data": {"text": "Please review"}})
    assert requests[4] == ("POST", "/api/1.0/sections/sec-1/addTask", {"data": {"task": "123"}})
    assert requests[5][2] == {"data": {"assignee_section": "mine-1"}}
    assert requests[6][2] == {"data": {"custom_fields": {"field-1": "option-2"}}}


def test_empty_comment_is_rejected_before_request() -> None:
    client = _client_with_transport(lambda request: httpx.Response(500))
    try:
        try:
            client.add_comment("123", "   ")
        except ValueError as exc:
            assert "cannot be empty" in str(exc)
        else:
            raise AssertionError("Expected ValueError")
    finally:
        client.close()


def test_asana_write_controls_render_for_asana_task(tmp_path: Path) -> None:
    task = TaskItem(
        key="asana:123",
        title="Create tests",
        url="https://app.asana.com/0/1/123",
        source="asana",
        due_on=date(2026, 7, 24),
        status="In Development",
        status_source=StatusSource(kind="custom_field", gid="field-1", name="Status", value="In Development"),
        asana_sections=[
            AsanaSectionOption(gid="mine-1", name="Today", scope="my_tasks"),
            AsanaSectionOption(gid="sec-1", name="In Review", scope="project", project_name="Web Platform"),
        ],
        asana_status_options=[
            AsanaStatusOption(gid="opt-1", name="In Development"),
            AsanaStatusOption(gid="opt-2", name="In Review"),
        ],
    )
    output = tmp_path / "digest.html"
    render_html(
        [task],
        datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc),
        "dashboard",
        str(output),
        action_token="token",
        dashboard_url="http://127.0.0.1:8765",
        asana_write_enabled=True,
    )
    text = output.read_text()
    assert "Update in Asana" in text
    assert "Mark complete" in text
    assert "Unassign me" in text
    assert "Post comment" in text
    assert "My Tasks" in text
    assert "Web Platform" in text
    assert 'name="option_gid"' in text
    assert 'class="asana-write-form' in text


def test_asana_write_controls_can_be_disabled(tmp_path: Path) -> None:
    output = tmp_path / "digest.html"
    task = TaskItem(key="asana:123", title="Task", url=None, source="asana")
    render_html(
        [task],
        datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc),
        "dashboard",
        str(output),
        action_token="token",
        dashboard_url="http://127.0.0.1:8765",
        asana_write_enabled=False,
    )
    assert "Update in Asana" not in output.read_text()


def test_asana_write_setting_is_editable(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("ASANA_WORKSPACE_GID=workspace\nENABLE_ASANA_WRITE_ACTIONS=false\n")
    assert "ENABLE_ASANA_WRITE_ACTIONS" in BOOLEAN_KEYS
    assert read_settings(env)["ENABLE_ASANA_WRITE_ACTIONS"] == "false"
