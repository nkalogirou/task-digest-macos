from datetime import datetime, timezone

from task_digest.digest import render_html, render_text
from task_digest.models import GitHubLink, SourceStatus, TaskItem


def test_report_shows_source_health_and_linked_pr(tmp_path) -> None:
    item = TaskItem(
        key="asana:1",
        title="Create workspace",
        url="https://app.asana.com/0/1/1",
        source="asana",
        github_links=[
            GitHubLink(
                owner="acme-inc",
                repo="web-app",
                number=1549,
                url="https://github.com/acme-inc/web-app/pull/1549",
                title="#1549 Create and delete a workspace",
            )
        ],
    )
    statuses = [
        SourceStatus(name="Asana", ok=True, detail="Loaded 1 task"),
        SourceStatus(name="GitHub", ok=False, detail="Authentication expired"),
    ]
    now = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)
    text = render_text(
        [item],
        now,
        "morning",
        source_statuses=statuses,
        hidden_summary=(1, 2),
    )
    assert "Linked GitHub PR #1549" in text
    assert "Source health" in text
    assert "1 snoozed · 2 ignored" in text

    path = render_html(
        [item],
        now,
        "morning",
        str(tmp_path / "report.html"),
        source_statuses=statuses,
        hidden_summary=(1, 2),
    )
    html = path.read_text(encoding="utf-8")
    assert "PR #1549 · acme-inc/web-app" in html
    assert "Authentication expired" in html
    assert "1 snoozed · 2 ignored" in html
