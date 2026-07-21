from __future__ import annotations

from html import escape

from .models import RelatedTask, TaskItem


def recommended_next(item: TaskItem) -> RelatedTask | None:
    """Return the first incomplete upstream dependency, if one exists."""
    return next((task for task in item.dependencies if not task.completed), None)


def has_relationships(item: TaskItem) -> bool:
    return bool(item.dependencies or item.dependents)


def _node(task: RelatedTask, role: str, recommended: bool = False) -> str:
    classes = ["relation-node", role]
    if task.completed:
        classes.append("done")
    if recommended:
        classes.append("recommended")
    title = escape(task.title)
    if task.url:
        title = f'<a href="{escape(task.url, quote=True)}">{title}</a>'
    status = "Complete" if task.completed else ("Start here" if recommended else "Open")
    return (
        f'<div class="{" ".join(classes)}">'
        f'<span class="relation-role">{escape(status)}</span><strong>{title}</strong></div>'
    )


def relationship_tree_html(item: TaskItem, *, expanded: bool = False) -> str:
    if not has_relationships(item):
        return ""
    next_task = recommended_next(item)
    upstream = "".join(
        _node(dependency, "upstream", recommended=next_task is dependency)
        for dependency in item.dependencies
    ) or '<div class="relation-empty">No upstream blockers</div>'
    current_classes = "relation-node current"
    if next_task is None:
        current_classes += " recommended"
    current_label = "Start here" if next_task is None else "Current task"
    current_title = escape(item.title)
    if item.url:
        current_title = f'<a href="{escape(item.url, quote=True)}">{current_title}</a>'
    current = (
        f'<div class="{current_classes}"><span class="relation-role">{current_label}</span>'
        f'<strong>{current_title}</strong></div>'
    )
    downstream = "".join(_node(dependent, "downstream") for dependent in item.dependents)
    downstream_html = (
        '<div class="relation-lane downstream-lane"><span class="lane-label">Then unblocks</span>'
        f'<div class="relation-nodes">{downstream}</div></div>'
        if downstream
        else ""
    )
    open_attr = " open" if expanded else ""
    summary = "Task relationship map"
    recommendation = (
        f'<div class="relationship-callout"><strong>Recommended first:</strong> '
        f'{escape(next_task.title) if next_task else "Work on this task"}</div>'
    )
    return (
        f'<details class="relationship-view"{open_attr}><summary>{summary}</summary>'
        f'{recommendation}<div class="relationship-tree">'
        '<div class="relation-lane upstream-lane"><span class="lane-label">Blocked by</span>'
        f'<div class="relation-nodes">{upstream}</div></div>'
        '<div class="relation-arrow" aria-hidden="true">↓</div>'
        f'<div class="relation-lane current-lane"><span class="lane-label">Current</span><div class="relation-nodes">{current}</div></div>'
        + ('<div class="relation-arrow" aria-hidden="true">↓</div>' if downstream else "")
        + downstream_html
        + "</div></details>"
    )
