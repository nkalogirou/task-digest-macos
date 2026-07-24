from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def test_workspace_helper_imports_when_run_by_path(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    script = project_root / "scripts" / "list_asana_workspaces.py"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import runpy; "
                f"runpy.run_path({str(script)!r}, run_name='task_digest_workspace_helper_test')"
            ),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_native_app_build_isolates_pyproject_metadata() -> None:
    project_root = Path(__file__).resolve().parents[1]
    script = (project_root / "scripts" / "install_native_app.sh").read_text(encoding="utf-8")
    setup_app = (project_root / "setup_app.py").read_text(encoding="utf-8")

    assert ".pyproject.toml.py2app-build" in script
    assert "trap restore_pyproject EXIT INT TERM" in script
    assert "setup_requires" not in setup_app


def test_release_build_uses_hardened_runtime_and_notarytool() -> None:
    project_root = Path(__file__).resolve().parents[1]
    script = (project_root / "scripts" / "build_release.sh").read_text(encoding="utf-8")
    workflow = (project_root / ".github" / "workflows" / "release-macos.yml").read_text(encoding="utf-8")

    assert "--options runtime" in script
    assert "notarytool submit" in script
    assert "stapler staple" in script
    assert "SHA256SUMS.txt" in script
    assert "APPLE_CERTIFICATE_P12_BASE64" in workflow
    assert "gh release create" in workflow
