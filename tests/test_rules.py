from __future__ import annotations

from datetime import datetime, timedelta, timezone

from task_digest.models import GitHubLink, RelatedTask, TaskItem
from task_digest.rules import RuleStore, describe_rule


def _task(**changes: object) -> TaskItem:
    values: dict[str, object] = {
        "key": "asana:1",
        "title": "Fix tests",
        "url": "https://app.asana.com/0/1/1",
        "source": "asana",
        "project": "Web Platform",
        "status": "In Review",
        "action_state": "waiting",
        "age_working_days": 7,
        "priority": "high",
    }
    values.update(changes)
    return TaskItem(**values)  # type: ignore[arg-type]


def test_rule_store_saves_toggles_and_reorders(tmp_path) -> None:
    store = RuleStore(tmp_path / "rules.json")
    first = store.save(
        {
            "name": "Stale review",
            "source": "asana",
            "condition": "waiting_age_at_least",
            "condition_value": "5",
            "action": "follow_up",
            "action_value": "Send a follow-up",
        }
    )
    second = store.save(
        {
            "name": "Urgent checks",
            "source": "all",
            "condition": "checks_failing",
            "action": "set_priority",
            "action_value": "urgent",
        }
    )

    assert [rule.name for rule in store.list()] == ["Stale review", "Urgent checks"]
    store.move(second.id, "up")
    assert [rule.name for rule in store.list()] == ["Urgent checks", "Stale review"]
    assert store.toggle(first.id).enabled is False
    assert store.delete(second.id) is True
    assert [rule.name for rule in store.list()] == ["Stale review"]


def test_rules_apply_scopes_and_actions(tmp_path) -> None:
    store = RuleStore(tmp_path / "rules.json")
    store.save(
        {
            "name": "Escalate failing Web PRs",
            "source": "asana",
            "project": "Web Platform",
            "repository": "acme-inc/web-app",
            "condition": "checks_failing",
            "action": "set_priority",
            "action_value": "urgent",
        }
    )
    store.save(
        {
            "name": "Hide completed blockers",
            "source": "asana",
            "condition": "section_is",
            "condition_value": "Archive",
            "action": "hide",
        }
    )
    task = _task(
        github_links=[
            GitHubLink(
                "acme-inc",
                "web-app",
                100,
                "https://github.com/acme-inc/web-app/pull/100",
                failed_checks=["e2e"],
                action_reasons=["Checks failing"],
            )
        ]
    )
    hidden = _task(key="asana:2", title="Old", section="Archive")

    result = store.apply([task, hidden], datetime.now(timezone.utc))

    assert result.visible == [task]
    assert result.hidden_count == 1
    assert task.priority == "urgent"
    assert task.rule_matches == ["Escalate failing Web PRs"]
    assert result.match_count == 2


def test_rule_can_suggest_follow_up_for_stale_waiting(tmp_path) -> None:
    store = RuleStore(tmp_path / "rules.json")
    rule = store.save(
        {
            "name": "Follow up after five days",
            "source": "asana",
            "condition": "waiting_age_at_least",
            "condition_value": "5",
            "action": "follow_up",
            "action_value": "Follow up with reviewer",
        }
    )
    task = _task(dependencies=[RelatedTask("2", "Fixture update", completed=True)])
    result = store.apply([task], datetime.now(timezone.utc) + timedelta(days=1))

    assert result.visible == [task]
    assert task.stale_waiting is True
    assert "Follow up with reviewer" in task.notes
    assert "waiting age is at least 5 working days" in describe_rule(rule).casefold()
