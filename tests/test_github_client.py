from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Sequence

from task_digest.github_client import CommandResult, GitHubClient


def _runner(args: Sequence[str], env: dict[str, str]) -> CommandResult:
    command = list(args[1:])
    if command == ["api", "user", "--jq", ".login"]:
        return CommandResult(stdout="octocat\n")
    if command[:2] == ["pr", "list"]:
        return CommandResult(
            stdout=json.dumps(
                [
                    {
                        "number": 1551,
                        "title": "Refactor authentication tests",
                        "url": "https://github.com/acme-inc/web-app/pull/1551",
                        "author": {"login": "billyblanas"},
                        "isDraft": False,
                        "createdAt": "2026-07-17T08:00:00Z",
                        "updatedAt": "2026-07-20T08:00:00Z",
                    },
                    {
                        "number": 1552,
                        "title": "Draft PR",
                        "url": "https://github.com/acme-inc/web-app/pull/1552",
                        "author": {"login": "someone"},
                        "isDraft": True,
                        "createdAt": "2026-07-17T08:00:00Z",
                        "updatedAt": "2026-07-20T08:00:00Z",
                    },
                ]
            )
        )
    if command[:3] == ["api", "--paginate", "--slurp"]:
        return CommandResult(
            stdout=json.dumps(
                [
                    [
                        {
                            "event": "review_requested",
                            "created_at": "2026-07-20T07:30:00Z",
                            "requested_reviewer": {"login": "octocat"},
                        }
                    ]
                ]
            )
        )
    raise AssertionError(f"Unexpected command: {command}")


def test_lists_review_requests_and_uses_request_time(tmp_path: Path) -> None:
    fake_gh = tmp_path / "gh"
    fake_gh.write_text("", encoding="utf-8")
    client = GitHubClient(cli_path=str(fake_gh), runner=_runner)
    reviews = client.list_review_requests(["acme-inc/web-app"])

    assert len(reviews) == 1
    review = reviews[0]
    assert review.source == "github"
    assert review.key == "github-review:acme-inc/web-app#1551"
    assert review.assigned_at == datetime.fromisoformat("2026-07-20T07:30:00+00:00")
    assert review.project == "acme-inc/web-app"
    assert "Opened by @billyblanas" in review.notes


def test_empty_review_list_is_valid(tmp_path: Path) -> None:
    fake_gh = tmp_path / "gh"
    fake_gh.write_text("", encoding="utf-8")

    def empty_runner(args: Sequence[str], env: dict[str, str]) -> CommandResult:
        command = list(args[1:])
        if command == ["api", "user", "--jq", ".login"]:
            return CommandResult(stdout="octocat\n")
        if command[:2] == ["pr", "list"]:
            return CommandResult(stdout="[]")
        raise AssertionError(f"Unexpected command: {command}")

    client = GitHubClient(cli_path=str(fake_gh), runner=empty_runner)
    assert client.list_review_requests(["acme-inc/web-app"]) == []


def test_lists_authored_prs_with_changes_checks_and_conflicts(tmp_path: Path) -> None:
    fake_gh = tmp_path / "gh"
    fake_gh.write_text("", encoding="utf-8")

    def authored_runner(args: Sequence[str], env: dict[str, str]) -> CommandResult:
        command = list(args[1:])
        if command == ["api", "user", "--jq", ".login"]:
            return CommandResult(stdout="octocat\n")
        if command[:2] == ["pr", "list"] and "--author" in command:
            return CommandResult(
                stdout=json.dumps(
                    [
                        {
                            "number": 1600,
                            "title": "Fix checkout tests",
                            "url": "https://github.com/acme-inc/web-app/pull/1600",
                            "isDraft": False,
                            "createdAt": "2026-07-15T08:00:00Z",
                            "updatedAt": "2026-07-20T08:00:00Z",
                            "reviewDecision": "CHANGES_REQUESTED",
                            "latestReviews": [
                                {
                                    "state": "CHANGES_REQUESTED",
                                    "submittedAt": "2026-07-17T09:30:00Z",
                                }
                            ],
                            "statusCheckRollup": [
                                {
                                    "name": "e2e",
                                    "conclusion": "FAILURE",
                                    "completedAt": "2026-07-18T11:00:00Z",
                                }
                            ],
                            "mergeStateStatus": "DIRTY",
                            "mergeable": "CONFLICTING",
                        },
                        {
                            "number": 1601,
                            "title": "Healthy PR",
                            "url": "https://github.com/acme-inc/web-app/pull/1601",
                            "isDraft": False,
                            "createdAt": "2026-07-19T08:00:00Z",
                            "updatedAt": "2026-07-20T08:00:00Z",
                            "reviewDecision": "APPROVED",
                            "latestReviews": [],
                            "statusCheckRollup": [
                                {"name": "e2e", "conclusion": "SUCCESS"}
                            ],
                            "mergeStateStatus": "CLEAN",
                            "mergeable": "MERGEABLE",
                        },
                    ]
                )
            )
        raise AssertionError(f"Unexpected command: {command}")

    client = GitHubClient(cli_path=str(fake_gh), runner=authored_runner)
    pulls = client.list_authored_prs_needing_action(["acme-inc/web-app"])

    assert len(pulls) == 1
    pull = pulls[0]
    assert pull.github_kind == "authored_pr"
    assert pull.key == "github-authored:acme-inc/web-app#1600"
    assert pull.status == "Changes requested · Checks failing · Merge conflict"
    assert pull.assigned_at == datetime.fromisoformat("2026-07-17T09:30:00+00:00")
    assert "Failing checks: e2e" in pull.notes
    assert "Resolve merge conflicts with the base branch" in pull.notes


def test_authored_pr_without_action_is_omitted(tmp_path: Path) -> None:
    fake_gh = tmp_path / "gh"
    fake_gh.write_text("", encoding="utf-8")

    def clean_runner(args: Sequence[str], env: dict[str, str]) -> CommandResult:
        command = list(args[1:])
        if command == ["api", "user", "--jq", ".login"]:
            return CommandResult(stdout="octocat\n")
        if command[:2] == ["pr", "list"]:
            return CommandResult(
                stdout=json.dumps(
                    [
                        {
                            "number": 1601,
                            "title": "Healthy PR",
                            "isDraft": False,
                            "reviewDecision": "APPROVED",
                            "statusCheckRollup": [],
                            "mergeStateStatus": "CLEAN",
                            "mergeable": "MERGEABLE",
                        }
                    ]
                )
            )
        raise AssertionError(f"Unexpected command: {command}")

    client = GitHubClient(cli_path=str(fake_gh), runner=clean_runner)
    assert client.list_authored_prs_needing_action(["acme-inc/web-app"]) == []


def test_authored_draft_pr_is_omitted_even_when_blocked(tmp_path: Path) -> None:
    fake_gh = tmp_path / "gh"
    fake_gh.write_text("", encoding="utf-8")

    def draft_runner(args: Sequence[str], env: dict[str, str]) -> CommandResult:
        command = list(args[1:])
        if command == ["api", "user", "--jq", ".login"]:
            return CommandResult(stdout="octocat\n")
        if command[:2] == ["pr", "list"]:
            return CommandResult(
                stdout=json.dumps(
                    [
                        {
                            "number": 1602,
                            "title": "Draft with failing checks",
                            "url": "https://github.com/acme-inc/web-app/pull/1602",
                            "isDraft": True,
                            "createdAt": "2026-07-20T08:00:00Z",
                            "updatedAt": "2026-07-20T09:00:00Z",
                            "reviewDecision": "CHANGES_REQUESTED",
                            "latestReviews": [
                                {
                                    "state": "CHANGES_REQUESTED",
                                    "submittedAt": "2026-07-20T08:30:00Z",
                                }
                            ],
                            "statusCheckRollup": [
                                {"name": "e2e", "conclusion": "FAILURE"}
                            ],
                            "mergeStateStatus": "DIRTY",
                            "mergeable": "CONFLICTING",
                        }
                    ]
                )
            )
        raise AssertionError(f"Unexpected command: {command}")

    client = GitHubClient(cli_path=str(fake_gh), runner=draft_runner)
    assert client.list_authored_prs_needing_action(["acme-inc/web-app"]) == []


def test_lists_assigned_issues_with_assignment_time(tmp_path: Path) -> None:
    fake_gh = tmp_path / "gh"
    fake_gh.write_text("", encoding="utf-8")

    def issue_runner(args: Sequence[str], env: dict[str, str]) -> CommandResult:
        command = list(args[1:])
        if command == ["api", "user", "--jq", ".login"]:
            return CommandResult(stdout="octocat\n")
        if command[:2] == ["issue", "list"]:
            return CommandResult(
                stdout=json.dumps(
                    [
                        {
                            "number": 42,
                            "title": "Investigate flaky test",
                            "url": "https://github.com/acme-inc/web-app/issues/42",
                            "author": {"login": "billyblanas"},
                            "labels": [{"name": "bug"}],
                            "createdAt": "2026-07-10T08:00:00Z",
                            "updatedAt": "2026-07-20T08:00:00Z",
                        }
                    ]
                )
            )
        if command[:3] == ["api", "--paginate", "--slurp"]:
            return CommandResult(
                stdout=json.dumps(
                    [[{"event": "assigned", "created_at": "2026-07-17T09:00:00Z", "assignee": {"login": "octocat"}}]]
                )
            )
        raise AssertionError(f"Unexpected command: {command}")

    client = GitHubClient(cli_path=str(fake_gh), runner=issue_runner)
    issues = client.list_assigned_issues(["acme-inc/web-app"])

    assert len(issues) == 1
    issue = issues[0]
    assert issue.github_kind == "assigned_issue"
    assert issue.key == "github-issue:acme-inc/web-app#42"
    assert issue.assigned_at == datetime.fromisoformat("2026-07-17T09:00:00+00:00")
    assert "Labels: bug" in issue.notes


def test_lists_mentions_and_omits_draft_prs(tmp_path: Path) -> None:
    fake_gh = tmp_path / "gh"
    fake_gh.write_text("", encoding="utf-8")

    def mention_runner(args: Sequence[str], env: dict[str, str]) -> CommandResult:
        command = list(args[1:])
        if command == ["api", "user", "--jq", ".login"]:
            return CommandResult(stdout="octocat\n")
        if command[:2] == ["search", "issues"]:
            return CommandResult(
                stdout=json.dumps(
                    [
                        {
                            "number": 43,
                            "title": "Issue mention",
                            "url": "https://github.com/acme-inc/web-app/issues/43",
                            "repository": {"nameWithOwner": "acme-inc/web-app"},
                            "author": {"login": "someone"},
                            "createdAt": "2026-07-18T08:00:00Z",
                            "updatedAt": "2026-07-20T08:00:00Z",
                        }
                    ]
                )
            )
        if command[:2] == ["search", "prs"]:
            return CommandResult(
                stdout=json.dumps(
                    [
                        {
                            "number": 1700,
                            "title": "Draft mention",
                            "url": "https://github.com/acme-inc/web-app/pull/1700",
                            "author": {"login": "someone"},
                            "isDraft": True,
                            "createdAt": "2026-07-18T08:00:00Z",
                            "updatedAt": "2026-07-20T08:00:00Z",
                        }
                    ]
                )
            )
        if command == ["api", "repos/acme-inc/web-app/issues/43"]:
            return CommandResult(
                stdout=json.dumps({"body": "Please ask @octocat", "created_at": "2026-07-19T10:00:00Z"})
            )
        if command[:3] == ["api", "--paginate", "--slurp"]:
            return CommandResult(stdout="[[]]")
        raise AssertionError(f"Unexpected command: {command}")

    client = GitHubClient(cli_path=str(fake_gh), runner=mention_runner)
    mentions = client.list_mentions(["acme-inc/web-app"])

    assert len(mentions) == 1
    mention = mentions[0]
    assert mention.github_kind == "mention"
    assert mention.key == "github-mention:acme-inc/web-app#43"
    assert mention.assigned_at == datetime.fromisoformat("2026-07-19T10:00:00+00:00")


def test_enriches_asana_linked_pr_with_action_only_status(tmp_path: Path) -> None:
    from task_digest.models import GitHubLink, TaskItem

    fake_gh = tmp_path / "gh"
    fake_gh.write_text("", encoding="utf-8")

    def linked_runner(args: Sequence[str], env: dict[str, str]) -> CommandResult:
        command = list(args[1:])
        if command[:2] == ["pr", "view"]:
            return CommandResult(
                stdout=json.dumps(
                    {
                        "number": 1549,
                        "title": "Create and delete a workspace",
                        "url": "https://github.com/acme-inc/web-app/pull/1549",
                        "isDraft": False,
                        "state": "OPEN",
                        "reviewDecision": "CHANGES_REQUESTED",
                        "statusCheckRollup": [
                            {"name": "e2e", "conclusion": "FAILURE"}
                        ],
                        "mergeStateStatus": "DIRTY",
                        "mergeable": "CONFLICTING",
                        "mergedAt": None,
                        "closedAt": None,
                    }
                )
            )
        raise AssertionError(f"Unexpected command: {command}")

    task = TaskItem(
        key="asana:1",
        title="Asana task",
        url="https://app.asana.com/0/1/1",
        source="asana",
        action_state="waiting",
        github_links=[
            GitHubLink(
                owner="acme-inc",
                repo="web-app",
                number=1549,
                url="https://github.com/acme-inc/web-app/pull/1549",
            )
        ],
    )
    client = GitHubClient(cli_path=str(fake_gh), runner=linked_runner)
    loaded, errors = client.enrich_linked_pull_requests(
        [task], ["acme-inc/web-app"]
    )

    assert loaded == 1
    assert errors == []
    assert task.action_state == "action"
    assert task.github_links[0].action_reasons == [
        "Changes requested",
        "Checks failing",
        "Merge conflict",
    ]
    assert "GitHub action required" in " ".join(task.notes)
    assert "Failing checks: e2e" in task.notes


def test_enriches_linked_draft_but_does_not_mark_task_action(tmp_path: Path) -> None:
    from task_digest.models import GitHubLink, TaskItem

    fake_gh = tmp_path / "gh"
    fake_gh.write_text("", encoding="utf-8")

    def draft_runner(args: Sequence[str], env: dict[str, str]) -> CommandResult:
        command = list(args[1:])
        if command[:2] == ["pr", "view"]:
            return CommandResult(
                stdout=json.dumps(
                    {
                        "number": 1550,
                        "title": "Draft work",
                        "url": "https://github.com/acme-inc/web-app/pull/1550",
                        "isDraft": True,
                        "state": "OPEN",
                        "reviewDecision": "CHANGES_REQUESTED",
                        "statusCheckRollup": [],
                        "mergeStateStatus": "DIRTY",
                        "mergeable": "CONFLICTING",
                    }
                )
            )
        raise AssertionError(f"Unexpected command: {command}")

    task = TaskItem(
        key="asana:2",
        title="Draft-linked task",
        url=None,
        source="asana",
        action_state="waiting",
        github_links=[
            GitHubLink(
                owner="acme-inc",
                repo="web-app",
                number=1550,
                url="https://github.com/acme-inc/web-app/pull/1550",
            )
        ],
    )
    client = GitHubClient(cli_path=str(fake_gh), runner=draft_runner)
    client.enrich_linked_pull_requests([task], ["acme-inc/web-app"])

    assert task.github_links[0].is_draft is True
    assert task.github_links[0].action_reasons == []
    assert task.action_state == "waiting"
