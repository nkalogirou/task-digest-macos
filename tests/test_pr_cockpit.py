from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence

from task_digest.digest import _task_card, render_html
from task_digest.github_client import CommandResult, GitHubClient
from task_digest.models import GitHubLink, TaskItem


def _client(tmp_path: Path) -> GitHubClient:
    fake_gh = tmp_path / "gh"
    fake_gh.write_text("", encoding="utf-8")

    def runner(args: Sequence[str], env: dict[str, str]) -> CommandResult:
        command = list(args[1:])
        if command[:2] == ["pr", "view"]:
            return CommandResult(
                stdout=json.dumps(
                    {
                        "number": 142,
                        "title": "Improve permission coverage",
                        "url": "https://github.com/acme-inc/web-app/pull/142",
                        "isDraft": False,
                        "state": "OPEN",
                        "reviewDecision": "CHANGES_REQUESTED",
                        "statusCheckRollup": [],
                        "mergeStateStatus": "BLOCKED",
                        "mergeable": "MERGEABLE",
                        "createdAt": "2026-07-18T08:00:00Z",
                        "updatedAt": "2026-07-24T08:30:00Z",
                        "mergedAt": None,
                        "closedAt": None,
                        "reviewRequests": [{"login": "reviewer-a"}],
                        "latestReviews": [
                            {
                                "author": {"login": "reviewer-a"},
                                "state": "CHANGES_REQUESTED",
                                "submittedAt": "2026-07-23T13:00:00Z",
                                "body": "Please cover branch-admin permissions.",
                                "url": "https://github.com/acme-inc/web-app/pull/142#review",
                            },
                            {
                                "author": {"login": "reviewer-b"},
                                "state": "APPROVED",
                                "submittedAt": "2026-07-23T12:00:00Z",
                            },
                        ],
                        "additions": 286,
                        "deletions": 74,
                        "changedFiles": 12,
                        "commits": [
                            {
                                "committedDate": "2026-07-24T08:15:00Z",
                                "oid": "abc123",
                            }
                        ],
                        "files": [
                            {
                                "path": "tests/e2e/permissions.spec.ts",
                                "additions": 120,
                                "deletions": 10,
                            },
                            {
                                "path": "src/permissions.ts",
                                "additions": 50,
                                "deletions": 12,
                            },
                        ],
                        "baseRefName": "main",
                        "headRefName": "feature/permissions",
                        "headRefOid": "abc123",
                    }
                )
            )
        if command[:2] == ["pr", "checks"]:
            return CommandResult(
                stdout=json.dumps(
                    [
                        {
                            "bucket": "fail",
                            "completedAt": "2026-07-24T08:28:00Z",
                            "description": "End-to-end browser tests",
                            "event": "pull_request",
                            "link": "https://github.com/acme-inc/web-app/actions/runs/1",
                            "name": "e2e-chrome",
                            "startedAt": "2026-07-24T08:20:00Z",
                            "state": "FAILURE",
                            "workflow": "E2E",
                        },
                        {
                            "bucket": "pass",
                            "completedAt": "2026-07-24T08:18:00Z",
                            "link": "https://github.com/acme-inc/web-app/actions/runs/2",
                            "name": "lint",
                            "startedAt": "2026-07-24T08:17:00Z",
                            "state": "SUCCESS",
                            "workflow": "Quality",
                        },
                    ]
                )
            )
        if command[:4] == ["api", "--method", "GET", "repos/acme-inc/web-app/commits/abc123/check-runs"]:
            return CommandResult(
                stdout=json.dumps(
                    {
                        "check_runs": [
                            {
                                "name": "e2e-chrome",
                                "html_url": "https://github.com/acme-inc/web-app/actions/runs/1",
                                "output": {
                                    "title": "Browser test failure",
                                    "summary": "Timed out waiting for permissions modal.",
                                },
                            }
                        ]
                    }
                )
            )
        if command[:2] == ["api", "graphql"]:
            return CommandResult(
                stdout=json.dumps(
                    {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "reviewThreads": {
                                        "nodes": [
                                            {
                                                "id": "thread-1",
                                                "isResolved": False,
                                                "isOutdated": False,
                                                "path": "tests/e2e/permissions.spec.ts",
                                                "line": 84,
                                                "originalLine": 84,
                                                "comments": {
                                                    "nodes": [
                                                        {
                                                            "id": "comment-1",
                                                            "author": {"login": "reviewer-a"},
                                                            "body": "Check the empty state before deleting.",
                                                            "createdAt": "2026-07-23T13:01:00Z",
                                                            "url": "https://github.com/acme-inc/web-app/pull/142#discussion_r1",
                                                        }
                                                    ]
                                                },
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    }
                )
            )
        raise AssertionError(f"Unexpected command: {command}")

    return GitHubClient(cli_path=str(fake_gh), runner=runner)


def test_enriches_linked_pr_with_cockpit_details(tmp_path: Path) -> None:
    task = TaskItem(
        key="asana:1",
        title="Improve permission coverage",
        url="https://app.asana.com/0/1/1",
        source="asana",
        github_links=[
            GitHubLink(
                owner="acme-inc",
                repo="web-app",
                number=142,
                url="https://github.com/acme-inc/web-app/pull/142",
            )
        ],
    )

    loaded, errors = _client(tmp_path).enrich_linked_pull_requests(
        [task], ["acme-inc/web-app"]
    )

    assert loaded == 1
    assert errors == []
    link = task.github_links[0]
    assert link.failed_checks == ["e2e-chrome"]
    assert link.checks[0].summary == "Browser test failure — Timed out waiting for permissions modal."
    assert link.reviews[0].reviewer == "reviewer-a"
    assert link.unresolved_threads[0].path == "tests/e2e/permissions.spec.ts"
    assert link.changed_files == 12
    assert link.additions == 286
    assert link.deletions == 74
    assert link.commit_count == 1
    assert link.last_commit_at == datetime.fromisoformat("2026-07-24T08:15:00+00:00")
    assert "1 unresolved review thread" in link.action_reasons


def test_renders_pr_cockpit_without_opening_github(tmp_path: Path) -> None:
    task = TaskItem(
        key="asana:1",
        title="Improve permission coverage",
        url="https://app.asana.com/0/1/1",
        source="asana",
        github_links=[
            GitHubLink(
                owner="acme-inc",
                repo="web-app",
                number=142,
                url="https://github.com/acme-inc/web-app/pull/142",
            )
        ],
    )
    _client(tmp_path).enrich_linked_pull_requests([task], ["acme-inc/web-app"])
    output = tmp_path / "digest.html"
    render_html(
        [task],
        datetime(2026, 7, 24, 10, 0, tzinfo=timezone.utc),
        "morning",
        str(output),
    )
    rendered = output.read_text(encoding="utf-8")

    assert "Merge readiness" in rendered
    assert "1/4" in rendered
    assert "Your actions" in rendered
    assert "Waiting on" in rendered
    assert "Fix failed checks: e2e-chrome" in rendered
    assert "Address 1 unresolved review thread" in rendered
    assert "Browser test failure" in rendered
    assert "Review progress" in rendered
    assert "Check the empty state before deleting." in rendered
    assert "12 files" in rendered
    assert "+286" in rendered
    assert "tests/e2e/permissions.spec.ts" in rendered


def test_compact_plan_card_uses_lightweight_pr_summary(tmp_path: Path) -> None:
    task = TaskItem(
        key="asana:1",
        title="Improve permission coverage",
        url="https://app.asana.com/0/1/1",
        source="asana",
        focus_rank=1,
        github_links=[
            GitHubLink(
                owner="acme-inc",
                repo="web-app",
                number=142,
                url="https://github.com/acme-inc/web-app/pull/142",
            )
        ],
    )
    _client(tmp_path).enrich_linked_pull_requests([task], ["acme-inc/web-app"])
    rendered = _task_card(task, date(2026, 7, 24), compact=True)

    assert "pr-compact-copy" in rendered
    assert "Changes requested" in rendered
    assert "Merge readiness" not in rendered
    assert "Details &amp; actions" not in rendered
    assert "Open in Asana" not in rendered


def test_unread_update_is_rendered_once_in_task_metadata() -> None:
    task = TaskItem(
        key="asana:2",
        title="Update coverage",
        url="https://app.asana.com/0/1/2",
        source="asana",
        unread_updates=1,
    )
    rendered = _task_card(task, date(2026, 7, 24))

    assert rendered.count("1 new") == 1
    assert "new update(s)" not in rendered
