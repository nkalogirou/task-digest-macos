from datetime import datetime, timezone
from pathlib import Path

from task_digest.runtime import get_or_create_action_token, save_history


def test_action_token_is_stable_and_saved_privately(tmp_path: Path) -> None:
    path = tmp_path / "state" / "token"
    first = get_or_create_action_token(str(path))
    second = get_or_create_action_token(str(path))
    assert first == second
    assert len(first) >= 32
    assert path.exists()


def test_save_history_uses_date_and_period(tmp_path: Path) -> None:
    report = tmp_path / "report.html"
    report.write_text("<p>report</p>", encoding="utf-8")
    destination = save_history(
        report,
        str(tmp_path / "history"),
        datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc),
        "morning",
    )
    assert destination.name == "2026-07-20-morning.html"
    assert destination.read_text(encoding="utf-8") == "<p>report</p>"
