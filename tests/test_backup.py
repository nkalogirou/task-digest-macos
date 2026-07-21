from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from task_digest.backup import BackupManager


def prepare_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "state").mkdir(parents=True)
    (project / "history").mkdir()
    (project / ".env").write_text("ASANA_WORKSPACE_GID=123\nASANA_TOKEN=secret\nMORNING_TIME=10:00\n", encoding="utf-8")
    (project / "VERSION").write_text("21\n", encoding="utf-8")
    (project / "state" / "workspace.json").write_text('{"focus": ["a"]}', encoding="utf-8")
    (project / "state" / "dashboard_token").write_text("do-not-back-up", encoding="utf-8")
    (project / "history" / "2026-07-21-morning.html").write_text("report", encoding="utf-8")
    return project


def test_create_excludes_tokens_and_includes_local_state(tmp_path: Path) -> None:
    project = prepare_project(tmp_path)
    manager = BackupManager(project, "backups", retention_count=5)
    info = manager.create("manual", datetime(2026, 7, 21, 10, 0, 0).astimezone())
    with zipfile.ZipFile(info.path) as archive:
        assert "manifest.json" in archive.namelist()
        assert "state/workspace.json" in archive.namelist()
        assert "state/dashboard_token" not in archive.namelist()
        env = archive.read(".env").decode()
        assert "ASANA_TOKEN" not in env
        assert "ASANA_WORKSPACE_GID=123" in env


def test_restore_creates_safety_backup_and_restores_files(tmp_path: Path) -> None:
    project = prepare_project(tmp_path)
    manager = BackupManager(project, "backups", retention_count=10)
    backup = manager.create("manual", datetime(2026, 7, 21, 10, 0, 0).astimezone())
    (project / "state" / "workspace.json").write_text('{"focus": []}', encoding="utf-8")
    (project / ".env").write_text("ASANA_WORKSPACE_GID=999\n", encoding="utf-8")
    safety = manager.restore(backup.name, datetime(2026, 7, 21, 11, 0, 0).astimezone())
    assert safety.path.exists()
    assert "before-restore" in safety.name
    assert json.loads((project / "state" / "workspace.json").read_text()) == {"focus": ["a"]}
    assert "ASANA_WORKSPACE_GID=123" in (project / ".env").read_text()


def test_daily_backup_runs_once_per_day(tmp_path: Path) -> None:
    project = prepare_project(tmp_path)
    manager = BackupManager(project, "backups", retention_count=5)
    assert manager.ensure_daily(datetime(2026, 7, 21).date()) is not None
    assert manager.ensure_daily(datetime(2026, 7, 21).date()) is None


def test_rejects_unsafe_archive(tmp_path: Path) -> None:
    project = prepare_project(tmp_path)
    manager = BackupManager(project, "backups", retention_count=5)
    manager.backup_dir.mkdir(parents=True)
    path = manager.backup_dir / "task-digest-backup-20260721-100000-manual.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", "{}")
        archive.writestr("../evil", "bad")
    with pytest.raises(ValueError):
        manager.restore(path.name)


def test_retention_keeps_newest_backups(tmp_path: Path) -> None:
    project = prepare_project(tmp_path)
    manager = BackupManager(project, "backups", retention_count=2)
    manager.create("one", datetime(2026, 7, 21, 9, 0, 0).astimezone())
    manager.create("two", datetime(2026, 7, 21, 10, 0, 0).astimezone())
    manager.create("three", datetime(2026, 7, 21, 11, 0, 0).astimezone())
    backups = manager.list()
    assert len(backups) == 2
    assert backups[0].reason == "three"
