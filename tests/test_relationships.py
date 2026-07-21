from task_digest.models import RelatedTask, TaskItem
from task_digest.relationships import has_relationships, recommended_next, relationship_tree_html


def test_relationship_tree_highlights_first_incomplete_dependency() -> None:
    done = RelatedTask("1", "Prepare fixtures", completed=True)
    blocker = RelatedTask("2", "Fix API response", url="https://app.asana.com/2", completed=False)
    task = TaskItem(
        key="asana:main",
        title="Create regression coverage",
        url="https://app.asana.com/main",
        source="asana",
        dependencies=[done, blocker],
        dependents=[RelatedTask("3", "Release regression suite")],
    )

    assert recommended_next(task) is blocker
    assert has_relationships(task) is True
    rendered = relationship_tree_html(task, expanded=True)
    assert "Task relationship map" in rendered
    assert "Fix API response" in rendered
    assert "Start here" in rendered
    assert "Release regression suite" in rendered
    assert " open" in rendered


def test_current_task_is_recommended_when_no_open_blocker() -> None:
    task = TaskItem(
        key="asana:main",
        title="Ship tests",
        url=None,
        source="asana",
        dependencies=[RelatedTask("1", "Fixtures", completed=True)],
    )

    assert recommended_next(task) is None
    rendered = relationship_tree_html(task)
    assert "Work on this task" in rendered
    assert 'class="relation-node current recommended"' in rendered
