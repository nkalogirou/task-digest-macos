from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from task_digest.dashboard import DashboardServer
from task_digest.demo import demo_config, demo_source_statuses, demo_tasks, render_demo_report
from task_digest.main import main


def test_demo_config_is_isolated_and_credential_free() -> None:
    config = demo_config(port=9901)
    assert config.asana_token == ""
    assert config.asana_workspace_gid == "demo-workspace"
    assert config.dashboard_port == 9901
    assert config.workspace_file.startswith("state/demo_")
    assert config.report_file == "output/demo-dashboard.html"
    assert config.enable_asana_write_actions is False


def test_demo_tasks_cover_action_waiting_github_and_optional_states() -> None:
    now = datetime(2026, 7, 24, 11, 30, tzinfo=timezone.utc)
    tasks = demo_tasks(now)
    assert len(tasks) >= 7
    assert any(task.source == "asana" and task.action_state == "action" for task in tasks)
    assert any(task.action_state == "waiting" and task.stale_waiting for task in tasks)
    assert any(task.github_kind == "review_request" for task in tasks)
    assert any(task.github_kind == "authored_pr" for task in tasks)
    assert any(task.is_optional for task in tasks)
    assert any(link.action_required for task in tasks for link in task.github_links)
    serialized = "\n".join([task.title + " " + (task.url or "") for task in tasks]).lower()
    assert ("epi" + "gnosis") not in serialized
    assert ("nkalo" + "girou") not in serialized


def test_demo_report_contains_badge_and_sanitized_sources(tmp_path: Path) -> None:
    report = render_demo_report(
        tmp_path / "demo.html",
        now=datetime(2026, 7, 24, 11, 30, tzinfo=timezone.utc),
    )
    page = report.read_text(encoding="utf-8")
    assert "Demo data" in page
    assert "Improve permission coverage" in page
    assert "example-org/web-app" in page
    assert "no external services contacted" in page


def test_demo_dashboard_server_uses_demo_collection(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = demo_config(port=0)
    server = DashboardServer(("127.0.0.1", 0), config, demo=True)
    try:
        tasks, statuses, warning, hidden = server.collect_visible(force=True)
        assert tasks
        assert warning is None
        assert hidden == (0, 0)
        assert statuses == demo_source_statuses()
        rendered = server.render_dashboard(force=True)
        assert "Demo data" in rendered
    finally:
        server.server_close()


def test_main_demo_does_not_require_environment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["task-digest", "--demo"])
    assert main() == 0
    assert (tmp_path / "output" / "demo-dashboard.html").exists()
