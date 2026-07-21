from __future__ import annotations

from datetime import datetime, timezone
from http import HTTPStatus
from types import SimpleNamespace

from task_digest.dashboard import DashboardHandler


def _payload() -> dict[str, object]:
    return {
        "services": [
            {
                "key": "app",
                "name": "Task Digest app",
                "ok": True,
                "pid": 123,
                "detail": "Running",
            }
        ],
        "source_statuses": [
            {"name": "Asana", "ok": True, "detail": "Loaded 3 assigned task(s)"}
        ],
        "github_auth": {"ok": True, "detail": "Authenticated"},
        "asana_auth": {"ok": True, "detail": "Token available through macOS Keychain"},
        "next_run": datetime(2026, 7, 21, 17, 30, tzinfo=timezone.utc).isoformat(),
        "next_period": "Evening",
        "hidden": {"snoozed": 0, "ignored": 0},
        "last_refresh": datetime(2026, 7, 21, 11, 6, tzinfo=timezone.utc).isoformat(),
    }


def test_system_page_renders_without_settings_helpers(monkeypatch, tmp_path) -> None:
    handler = object.__new__(DashboardHandler)
    handler.server = SimpleNamespace(
        action_token="token",
        diagnostics_payload=lambda: _payload(),
    )
    monkeypatch.chdir(tmp_path)

    rendered = handler._system_page()

    assert "System status" in rendered
    assert "Task Digest app" in rendered
    assert "Asana authentication" in rendered
    assert "Restart all services" in rendered


def test_system_route_returns_error_page_instead_of_empty_response() -> None:
    handler = object.__new__(DashboardHandler)
    handler.path = "/system"
    handler._system_page = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    handler._error_page = lambda exc: f"error: {exc}"
    sent: list[tuple[str, HTTPStatus]] = []
    handler._send_html = lambda body, status=HTTPStatus.OK: sent.append((body, status))

    handler.do_GET()

    assert sent == [("error: boom", HTTPStatus.INTERNAL_SERVER_ERROR)]
