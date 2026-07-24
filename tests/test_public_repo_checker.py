from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run_checker(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "scripts/check_public_repo.py"],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )


def _prepare_repo(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "check_public_repo.py", project / "scripts" / "check_public_repo.py")
    (project / ".gitignore").write_text(
        ".env\nlogs/*.log\noutput/*.html\nstate/dashboard_token\n",
        encoding="utf-8",
    )
    (project / "README.md").write_text("# Safe project\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "add", "README.md", ".gitignore", "scripts/check_public_repo.py"], cwd=project, check=True)
    return project


def test_checker_allows_ignored_local_runtime_files(tmp_path: Path) -> None:
    project = _prepare_repo(tmp_path)
    (project / ".env").write_text("ASANA_WORKSPACE_GID=123\n", encoding="utf-8")
    (project / "logs").mkdir()
    (project / "logs" / "app.log").write_text("private local output\n", encoding="utf-8")

    result = _run_checker(project)

    assert result.returncode == 0, result.stderr
    assert "passed" in result.stdout


def test_checker_rejects_publishable_runtime_file(tmp_path: Path) -> None:
    project = _prepare_repo(tmp_path)
    report = project / "output" / "task-digest.html"
    report.parent.mkdir()
    report.write_text("generated report\n", encoding="utf-8")
    subprocess.run(["git", "add", "-f", "output/task-digest.html"], cwd=project, check=True)

    result = _run_checker(project)

    assert result.returncode == 1
    assert "runtime file could be published: output/task-digest.html" in result.stderr
