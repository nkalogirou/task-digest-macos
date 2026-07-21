from datetime import date, datetime, timezone

from task_digest.models import TaskItem
from task_digest.preferences import TaskPreferences, add_working_days


def _task(status: str = "In Development") -> TaskItem:
    return TaskItem(
        key="asana:1",
        title="Example task",
        url="https://app.asana.com/0/1/1",
        source="asana",
        status=status,
        section="Today",
    )


def test_add_working_days_skips_weekend() -> None:
    assert add_working_days(date(2026, 7, 17), 1) == date(2026, 7, 20)
    assert add_working_days(date(2026, 7, 17), 3) == date(2026, 7, 22)


def test_snooze_for_working_days_hides_until_wake_date(tmp_path) -> None:
    prefs = TaskPreferences(str(tmp_path / "prefs.json"))
    item = _task()
    now = datetime(2026, 7, 17, 9, 0, tzinfo=timezone.utc)
    wake_on = prefs.snooze_for_working_days(item, 1, now.date(), now)
    assert wake_on == date(2026, 7, 20)

    hidden = prefs.filter([item], date(2026, 7, 17))
    assert hidden.visible == []
    assert hidden.snoozed_count == 1

    visible = prefs.filter([item], date(2026, 7, 20))
    assert visible.visible == [item]
    assert prefs.entries == {}


def test_snooze_until_change_reappears_when_status_changes(tmp_path) -> None:
    prefs = TaskPreferences(str(tmp_path / "prefs.json"))
    item = _task("In Development")
    now = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    prefs.snooze_until_change(item, now)

    assert prefs.filter([item], now.date()).visible == []

    changed = _task("In Review")
    result = prefs.filter([changed], now.date())
    assert result.visible == [changed]
    assert result.expired_or_changed_count == 1


def test_ignore_remains_hidden_and_restore_works(tmp_path) -> None:
    prefs = TaskPreferences(str(tmp_path / "prefs.json"))
    item = _task()
    now = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    prefs.ignore(item, now)

    result = prefs.filter([item], now.date())
    assert result.visible == []
    assert result.ignored_count == 1
    assert prefs.restore(item.key) is True
    assert prefs.filter([item], now.date()).visible == [item]


def test_snooze_until_change_wakes_when_linked_pr_blocker_changes(tmp_path) -> None:
    from task_digest.models import GitHubLink

    prefs = TaskPreferences(str(tmp_path / "prefs.json"))
    item = _task()
    item.github_links = [
        GitHubLink(
            owner="acme-inc",
            repo="web-app",
            number=1549,
            url="https://github.com/acme-inc/web-app/pull/1549",
        )
    ]
    now = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    prefs.snooze_until_change(item, now)
    assert prefs.filter([item], now.date()).visible == []

    changed = _task()
    changed.github_links = [
        GitHubLink(
            owner="acme-inc",
            repo="web-app",
            number=1549,
            url="https://github.com/acme-inc/web-app/pull/1549",
            action_reasons=["Checks failing"],
        )
    ]
    result = prefs.filter([changed], now.date())
    assert result.visible == [changed]
