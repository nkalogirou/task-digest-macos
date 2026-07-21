from __future__ import annotations

from datetime import datetime, time, timezone
from pathlib import Path
from types import SimpleNamespace

from task_digest.diagnostics import (
    ServiceDefinition,
    inspect_service,
    next_scheduled_run,
    tail_log,
)


def _config(morning: time = time(10, 0), evening: time = time(17, 30)) -> SimpleNamespace:
    return SimpleNamespace(morning_time=morning, evening_time=evening)


def test_next_scheduled_run_skips_weekend() -> None:
    now = datetime(2026, 7, 24, 18, 0, tzinfo=timezone.utc)  # Friday evening
    value, label = next_scheduled_run(_config(), now)
    assert value == datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)
    assert label == "Morning"


def test_next_scheduled_run_uses_same_day_when_available() -> None:
    now = datetime(2026, 7, 20, 11, 0, tzinfo=timezone.utc)
    value, label = next_scheduled_run(_config(), now)
    assert value == datetime(2026, 7, 20, 17, 30, tzinfo=timezone.utc)
    assert label == "Evening"


def test_tail_log_returns_recent_lines(tmp_path: Path) -> None:
    path = tmp_path / "app.log"
    path.write_text("one\ntwo\nthree\n", encoding="utf-8")
    assert tail_log(path, 2) == "two\nthree"


def test_inspect_service_reports_unavailable_off_macos(tmp_path: Path, monkeypatch) -> None:
    service = ServiceDefinition("x", "Example", "example", "example.plist", "out", "err", True)
    monkeypatch.setattr("task_digest.diagnostics.sys.platform", "linux")
    status = inspect_service(service, home=tmp_path)
    assert status.state == "unavailable"
    assert not status.ok


def test_active_services_prefers_native_app_when_installed(tmp_path: Path) -> None:
    from task_digest.diagnostics import active_services

    launch_agents = tmp_path / "Library" / "LaunchAgents"
    launch_agents.mkdir(parents=True)
    (launch_agents / "app.taskdigest.macos.plist").write_text("plist", encoding="utf-8")
    assert [service.key for service in active_services(tmp_path)] == ["app", "scheduler"]


def test_active_services_uses_legacy_services_without_native_app(tmp_path: Path) -> None:
    from task_digest.diagnostics import active_services

    assert [service.key for service in active_services(tmp_path)] == ["dashboard", "menubar", "scheduler"]


def test_github_auth_status_decodes_utf8_output_explicitly(tmp_path: Path, monkeypatch) -> None:
    from subprocess import CompletedProcess

    from task_digest.diagnostics import github_auth_status

    executable = tmp_path / "gh"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(args, **kwargs):
        captured.update(kwargs)
        return CompletedProcess(args=args, returncode=0, stdout="✓ Logged in to github.com", stderr="")

    monkeypatch.setattr("task_digest.diagnostics.subprocess.run", fake_run)

    ok, detail = github_auth_status(str(executable))

    assert ok
    assert "✓ Logged in" in detail
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
