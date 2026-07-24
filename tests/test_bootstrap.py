from __future__ import annotations

from pathlib import Path

from task_digest import bootstrap


def test_runtime_layout_creates_private_configuration_and_directories(tmp_path: Path) -> None:
    root = bootstrap.ensure_runtime_layout(tmp_path / "support")
    assert (root / ".env").is_file()
    assert "ASANA_WORKSPACE_GID=" in (root / ".env").read_text(encoding="utf-8")
    assert (root / "VERSION").read_text(encoding="utf-8").strip()
    for name in bootstrap.RUNTIME_DIRS:
        assert (root / name).is_dir()


def test_resolve_runtime_dir_prefers_source_checkout(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".env").write_text("ASANA_WORKSPACE_GID=1\n", encoding="utf-8")
    (source / "task_digest").mkdir()
    runtime, source_mode = bootstrap.resolve_runtime_dir(
        env={"TASK_DIGEST_PROJECT_DIR": str(source)},
        path_file=tmp_path / "missing",
        cwd=tmp_path,
        fallback_dir=tmp_path / "support",
    )
    assert runtime == source.resolve()
    assert source_mode is True


def test_resolve_runtime_dir_creates_application_support_fallback(tmp_path: Path) -> None:
    fallback = tmp_path / "support"
    runtime, source_mode = bootstrap.resolve_runtime_dir(
        env={},
        path_file=tmp_path / "missing",
        cwd=tmp_path / "not-a-project",
        fallback_dir=fallback,
    )
    assert runtime == fallback.resolve()
    assert source_mode is False
    assert (runtime / ".env").is_file()


def test_onboarding_required_checks_workspace_and_keychain(tmp_path: Path, monkeypatch) -> None:
    root = bootstrap.ensure_runtime_layout(tmp_path)
    monkeypatch.setattr(bootstrap, "read_secret", lambda _item: None)
    assert bootstrap.onboarding_required(root) is True
    (root / ".env").write_text(
        "ASANA_WORKSPACE_GID=123\nASANA_TOKEN_KEYCHAIN_SERVICE=test\nASANA_TOKEN_KEYCHAIN_ACCOUNT=asana\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bootstrap, "read_secret", lambda _item: "token")
    assert bootstrap.onboarding_required(root) is False
