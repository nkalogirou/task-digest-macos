from __future__ import annotations

from pathlib import Path

import pytest

from task_digest.app import dashboard_is_available, resolve_project_dir


def _project(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / ".env").write_text("ASANA_WORKSPACE_GID=1\n", encoding="utf-8")
    (path / "task_digest").mkdir()
    return path


def test_resolve_project_dir_prefers_environment(tmp_path: Path) -> None:
    project = _project(tmp_path / "project")
    marker = tmp_path / "project_path"
    marker.write_text(str(tmp_path / "other"), encoding="utf-8")
    assert resolve_project_dir(
        env={"TASK_DIGEST_PROJECT_DIR": str(project)},
        path_file=marker,
        cwd=tmp_path,
    ) == project.resolve()


def test_resolve_project_dir_uses_application_support_marker(tmp_path: Path) -> None:
    project = _project(tmp_path / "project")
    marker = tmp_path / "project_path"
    marker.write_text(str(project), encoding="utf-8")
    assert resolve_project_dir(env={}, path_file=marker, cwd=tmp_path) == project.resolve()


def test_resolve_project_dir_rejects_invalid_locations(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="could not locate"):
        resolve_project_dir(env={}, path_file=tmp_path / "missing", cwd=tmp_path)


def test_dashboard_probe_returns_false_for_closed_port() -> None:
    assert dashboard_is_available("127.0.0.1", 1, timeout=0.01) is False
