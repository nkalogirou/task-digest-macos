from __future__ import annotations

from types import SimpleNamespace

from task_digest.dashboard import DashboardHandler
from task_digest.models import RelatedTask, TaskItem
from task_digest.rules import RuleStore


def _config(tmp_path):
    return SimpleNamespace(
        rules_file=str(tmp_path / "rules.json"),
        excluded_sections={"drafts"},
        optional_sections={"investigations"},
        action_statuses={"pending", "in development"},
        waiting_statuses={"in review"},
    )


def test_rule_editor_renders_base_and_custom_rules(tmp_path) -> None:
    config = _config(tmp_path)
    rule = RuleStore(config.rules_file).save(
        {
            "name": "Escalate checks",
            "source": "all",
            "condition": "checks_failing",
            "action": "set_priority",
            "action_value": "urgent",
        }
    )
    handler = object.__new__(DashboardHandler)
    handler.server = SimpleNamespace(config=config, action_token="token")

    rendered = handler._rules_page(edit_id=rule.id)

    assert "Rule editor" in rendered
    assert "Base workflow rules" in rendered
    assert "Escalate checks" in rendered
    assert "Save changes" in rendered
    assert "GitHub repository scope" in rendered


def test_relationship_page_renders_connected_tasks(tmp_path) -> None:
    task = TaskItem(
        key="asana:1",
        title="Main task",
        url="https://app.asana.com/1",
        source="asana",
        project="Sprint",
        dependencies=[RelatedTask("2", "Blocking task", completed=False)],
    )
    handler = object.__new__(DashboardHandler)
    handler.server = SimpleNamespace(collect_visible=lambda force=False: ([task], [], None, (0, 0)))

    rendered = handler._relationships_page()

    assert "Task relationships" in rendered
    assert "Blocking task" in rendered
    assert "Start here" in rendered
    assert "1 incomplete upstream task" in rendered
