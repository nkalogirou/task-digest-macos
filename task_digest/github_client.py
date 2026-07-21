from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence

from .models import GitHubLink, TaskEvent, TaskItem


class GitHubClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str = ""
    returncode: int = 0


CommandRunner = Callable[[Sequence[str], dict[str, str]], CommandResult]


def _default_runner(args: Sequence[str], env: dict[str, str]) -> CommandResult:
    completed = subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    return CommandResult(
        stdout=completed.stdout,
        stderr=completed.stderr,
        returncode=completed.returncode,
    )


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _flatten_pages(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    flattened: list[dict[str, object]] = []
    for entry in value:
        if isinstance(entry, list):
            flattened.extend(item for item in entry if isinstance(item, dict))
        elif isinstance(entry, dict):
            flattened.append(entry)
    return flattened


def _rows(output: str, repository: str) -> list[dict[str, object]]:
    try:
        parsed = json.loads(output or "[]")
    except json.JSONDecodeError as exc:
        raise GitHubClientError(f"Could not parse GitHub CLI output for {repository}: {exc}") from exc
    if not isinstance(parsed, list):
        return []
    return [row for row in parsed if isinstance(row, dict)]


def _repository_parts(repository: str) -> tuple[str, str]:
    if "/" not in repository:
        raise GitHubClientError(
            f"Invalid repository '{repository}'. Expected the format owner/repository."
        )
    return tuple(repository.split("/", 1))  # type: ignore[return-value]


def _sortable_time(item: TaskItem) -> float:
    value = item.assigned_at or item.created_at
    return value.timestamp() if value else float("inf")


def _latest_changes_requested_at(reviews: object) -> datetime | None:
    if not isinstance(reviews, list):
        return None
    timestamps: list[datetime] = []
    for review in reviews:
        if not isinstance(review, dict):
            continue
        if str(review.get("state") or "").upper() != "CHANGES_REQUESTED":
            continue
        submitted = _parse_datetime(review.get("submittedAt") or review.get("submitted_at"))
        if submitted:
            timestamps.append(submitted)
    return max(timestamps) if timestamps else None


_FAILED_CHECK_VALUES = {
    "FAIL",
    "FAILURE",
    "ERROR",
    "TIMED_OUT",
    "ACTION_REQUIRED",
    "STARTUP_FAILURE",
    "STALE",
}


def _failed_checks(rollup: object) -> list[tuple[str, datetime | None]]:
    if not isinstance(rollup, list):
        return []
    failed: list[tuple[str, datetime | None]] = []
    for check in rollup:
        if not isinstance(check, dict):
            continue
        bucket = str(check.get("bucket") or "").upper()
        conclusion = str(check.get("conclusion") or "").upper()
        state = str(check.get("state") or "").upper()
        if bucket not in _FAILED_CHECK_VALUES and conclusion not in _FAILED_CHECK_VALUES and state not in _FAILED_CHECK_VALUES:
            continue
        name = str(check.get("name") or check.get("context") or "Unnamed check")
        timestamp = _parse_datetime(
            check.get("completedAt")
            or check.get("completed_at")
            or check.get("startedAt")
            or check.get("started_at")
        )
        failed.append((name, timestamp))
    return failed


def _checks_pending(rollup: object) -> bool:
    if not isinstance(rollup, list):
        return False
    pending_values = {"PENDING", "QUEUED", "IN_PROGRESS", "EXPECTED", "WAITING"}
    for check in rollup:
        if not isinstance(check, dict):
            continue
        values = {
            str(check.get("bucket") or "").upper(),
            str(check.get("state") or "").upper(),
            str(check.get("status") or "").upper(),
        }
        if values.intersection(pending_values):
            return True
    return False


def _reviewer_names(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("login") or entry.get("slug") or entry.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _approval_count(value: object) -> int:
    if not isinstance(value, list):
        return 0
    authors: set[str] = set()
    for entry in value:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("state") or "").upper() != "APPROVED":
            continue
        author = entry.get("author") or {}
        name = str(author.get("login") or author.get("name") or "") if isinstance(author, dict) else ""
        authors.add(name or str(entry.get("id") or len(authors)))
    return len(authors)


class GitHubClient:
    def __init__(
        self,
        cli_path: str | None = None,
        runner: CommandRunner | None = None,
    ) -> None:
        self.cli_path = self._resolve_cli(cli_path)
        self._runner = runner or _default_runner
        self._login: str | None = None

    @staticmethod
    def _resolve_cli(configured: str | None) -> str:
        candidates: Iterable[str | None] = (
            configured,
            shutil.which("gh"),
            "/opt/homebrew/bin/gh",
            "/usr/local/bin/gh",
        )
        for candidate in candidates:
            if candidate and Path(candidate).expanduser().is_file():
                return str(Path(candidate).expanduser())
        raise GitHubClientError(
            "GitHub CLI was not found. Install it with 'brew install gh', then run 'gh auth login --web'."
        )

    def _run(self, *args: str) -> str:
        env = dict(os.environ)
        env["GH_PAGER"] = "cat"
        result = self._runner([self.cli_path, *args], env)
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "Unknown GitHub CLI error").strip()
            raise GitHubClientError(message)
        return result.stdout.strip()

    def current_login(self) -> str:
        if self._login:
            return self._login
        output = self._run("api", "user", "--jq", ".login")
        if not output:
            raise GitHubClientError(
                "GitHub CLI is not authenticated. Run 'gh auth login --web' and try again."
            )
        self._login = output.strip()
        return self._login

    def list_review_requests(
        self,
        repositories: list[str],
        limit: int = 50,
    ) -> list[TaskItem]:
        if not repositories:
            return []
        login = self.current_login()
        items: list[TaskItem] = []
        for repository in repositories:
            items.extend(self._list_repository_reviews(repository, login, limit))
        return sorted(items, key=lambda item: (_sortable_time(item), item.title.lower()))

    def _list_repository_reviews(
        self,
        repository: str,
        login: str,
        limit: int,
    ) -> list[TaskItem]:
        owner, repo = _repository_parts(repository)
        output = self._run(
            "pr",
            "list",
            "--repo",
            repository,
            "--state",
            "open",
            "--search",
            "review-requested:@me",
            "--limit",
            str(limit),
            "--json",
            "number,title,url,author,isDraft,createdAt,updatedAt",
        )

        reviews: list[TaskItem] = []
        for row in _rows(output, repository):
            if bool(row.get("isDraft")):
                continue
            number = int(row.get("number") or 0)
            if number <= 0:
                continue
            requested_at, estimated = self._review_requested_at(owner, repo, number, login)
            created_at = _parse_datetime(row.get("createdAt"))
            if requested_at is None:
                requested_at = _parse_datetime(row.get("updatedAt")) or created_at
                estimated = True

            author_value = row.get("author")
            author = ""
            if isinstance(author_value, dict):
                author = str(author_value.get("login") or author_value.get("name") or "")

            notes: list[str] = []
            if author:
                notes.append(f"Opened by @{author}")
            if estimated:
                notes.append("Review-request age is estimated")

            reviews.append(
                TaskItem(
                    key=f"github-review:{owner}/{repo}#{number}",
                    title=str(row.get("title") or f"Pull request #{number}"),
                    url=str(row.get("url") or f"https://github.com/{owner}/{repo}/pull/{number}"),
                    source="github",
                    github_kind="review_request",
                    created_at=created_at,
                    assigned_at=requested_at,
                    project=f"{owner}/{repo}",
                    notes=notes,
                    action_state="action",
                )
            )
        return reviews

    def list_authored_prs_needing_action(
        self,
        repositories: list[str],
        limit: int = 50,
    ) -> list[TaskItem]:
        if not repositories:
            return []
        # Validate authentication once before issuing repository queries.
        self.current_login()
        items: list[TaskItem] = []
        for repository in repositories:
            items.extend(self._list_repository_authored_prs(repository, limit))
        return sorted(items, key=lambda item: (_sortable_time(item), item.title.lower()))

    def _list_repository_authored_prs(
        self,
        repository: str,
        limit: int,
    ) -> list[TaskItem]:
        owner, repo = _repository_parts(repository)
        output = self._run(
            "pr",
            "list",
            "--repo",
            repository,
            "--state",
            "open",
            "--author",
            "@me",
            "--limit",
            str(limit),
            "--json",
            "number,title,url,isDraft,createdAt,updatedAt,reviewDecision,statusCheckRollup,mergeStateStatus,mergeable,latestReviews",
        )

        results: list[TaskItem] = []
        for row in _rows(output, repository):
            # Draft pull requests are intentionally excluded from the digest.
            if bool(row.get("isDraft")):
                continue

            number = int(row.get("number") or 0)
            if number <= 0:
                continue

            reasons: list[str] = []
            notes: list[str] = []
            action_times: list[datetime] = []
            estimated = False

            review_decision = str(row.get("reviewDecision") or "").upper()
            if review_decision == "CHANGES_REQUESTED":
                reasons.append("Changes requested")
                review_time = _latest_changes_requested_at(row.get("latestReviews"))
                if review_time:
                    action_times.append(review_time)
                else:
                    estimated = True

            failures = _failed_checks(row.get("statusCheckRollup"))
            if failures:
                reasons.append("Checks failing")
                failure_names = [name for name, _ in failures]
                visible = ", ".join(failure_names[:3])
                if len(failure_names) > 3:
                    visible += f" +{len(failure_names) - 3} more"
                notes.append(f"Failing checks: {visible}")
                known_failure_times = [when for _, when in failures if when]
                if known_failure_times:
                    action_times.append(min(known_failure_times))
                else:
                    estimated = True

            mergeable = str(row.get("mergeable") or "").upper()
            merge_state = str(row.get("mergeStateStatus") or "").upper()
            if mergeable == "CONFLICTING" or merge_state == "DIRTY":
                reasons.append("Merge conflict")
                notes.append("Resolve merge conflicts with the base branch")
                # GitHub does not expose the exact moment a conflict started in this list response.
                estimated = True

            if not reasons:
                continue

            created_at = _parse_datetime(row.get("createdAt"))
            updated_at = _parse_datetime(row.get("updatedAt"))
            if not action_times:
                fallback = updated_at or created_at
                if fallback:
                    action_times.append(fallback)
                estimated = True

            if estimated:
                notes.append("Action age is estimated")

            status = " · ".join(reasons)
            results.append(
                TaskItem(
                    key=f"github-authored:{owner}/{repo}#{number}",
                    title=f"PR #{number} — {str(row.get('title') or 'Untitled pull request')}",
                    url=str(row.get("url") or f"https://github.com/{owner}/{repo}/pull/{number}"),
                    source="github",
                    github_kind="authored_pr",
                    created_at=created_at,
                    assigned_at=min(action_times) if action_times else created_at,
                    status=status,
                    project=f"{owner}/{repo}",
                    notes=notes,
                    action_state="action",
                )
            )
        return results


    def enrich_linked_pull_requests(
        self,
        tasks: list[TaskItem],
        repositories: list[str],
    ) -> tuple[int, list[str]]:
        """Add live action-only status to PRs attached to Asana tasks.

        Healthy PRs remain simple links. Draft PR links are hidden. PRs with
        requested changes, failed checks, merge conflicts, or a merged/closed
        state are annotated so the Asana task can be acted on directly.
        """
        allowed = {repository.casefold() for repository in repositories}
        cache: dict[str, GitHubLink] = {}
        errors: list[str] = []
        loaded = 0

        for task in tasks:
            if task.source != "asana":
                continue
            for link in task.github_links:
                if link.kind != "pull":
                    continue
                repository = f"{link.owner}/{link.repo}"
                if allowed and repository.casefold() not in allowed:
                    continue

                cached = cache.get(link.key)
                if cached:
                    self._copy_link_status(cached, link)
                else:
                    try:
                        self._load_linked_pull_status(link)
                    except GitHubClientError as exc:
                        errors.append(f"{link.key}: {exc}")
                        continue
                    cache[link.key] = link
                    loaded += 1

                if link.is_draft:
                    continue
                task.timeline_events.append(self._linked_pr_event(link))
                if link.action_reasons:
                    task.action_state = "action"
                    task.notes.append(
                        "GitHub action required: " + " · ".join(link.action_reasons)
                    )
                    if link.failed_checks:
                        visible = ", ".join(link.failed_checks[:3])
                        if len(link.failed_checks) > 3:
                            visible += f" +{len(link.failed_checks) - 3} more"
                        task.notes.append(f"Failing checks: {visible}")

        return loaded, errors

    @staticmethod
    def _copy_link_status(source: GitHubLink, target: GitHubLink) -> None:
        target.title = source.title
        target.is_draft = source.is_draft
        target.state = source.state
        target.action_reasons = list(source.action_reasons)
        target.failed_checks = list(source.failed_checks)
        target.pending_reviewers = list(source.pending_reviewers)
        target.approvals = source.approvals
        target.checks_pending = source.checks_pending
        target.review_decision = source.review_decision
        target.mergeable = source.mergeable
        target.created_at = source.created_at
        target.updated_at = source.updated_at
        target.merged_at = source.merged_at
        target.closed_at = source.closed_at

    def _load_linked_pull_status(self, link: GitHubLink) -> None:
        repository = f"{link.owner}/{link.repo}"
        output = self._run(
            "pr",
            "view",
            str(link.number),
            "--repo",
            repository,
            "--json",
            "number,title,url,isDraft,state,reviewDecision,statusCheckRollup,mergeStateStatus,mergeable,createdAt,updatedAt,mergedAt,closedAt,reviewRequests,latestReviews",
        )
        try:
            row = json.loads(output or "{}")
        except json.JSONDecodeError as exc:
            raise GitHubClientError(
                f"Could not parse GitHub CLI output for {link.key}: {exc}"
            ) from exc
        if not isinstance(row, dict):
            raise GitHubClientError(f"Unexpected GitHub CLI response for {link.key}")

        link.title = str(row.get("title") or link.title or "").strip() or None
        link.url = str(row.get("url") or link.url)
        link.is_draft = bool(row.get("isDraft"))
        link.state = str(row.get("state") or "").upper() or None
        link.review_decision = str(row.get("reviewDecision") or "").upper() or None
        link.pending_reviewers = _reviewer_names(row.get("reviewRequests"))
        link.approvals = _approval_count(row.get("latestReviews"))
        link.checks_pending = _checks_pending(row.get("statusCheckRollup"))
        link.mergeable = str(row.get("mergeable") or "").upper() or None
        link.created_at = _parse_datetime(row.get("createdAt"))
        link.updated_at = _parse_datetime(row.get("updatedAt"))
        link.merged_at = _parse_datetime(row.get("mergedAt"))
        link.closed_at = _parse_datetime(row.get("closedAt"))
        if link.is_draft:
            return

        reasons: list[str] = []
        if link.review_decision == "CHANGES_REQUESTED":
            reasons.append("Changes requested")

        failures = _failed_checks(row.get("statusCheckRollup"))
        if failures:
            reasons.append("Checks failing")
            link.failed_checks = [name for name, _ in failures]

        mergeable = str(row.get("mergeable") or "").upper()
        merge_state = str(row.get("mergeStateStatus") or "").upper()
        if mergeable == "CONFLICTING" or merge_state == "DIRTY":
            reasons.append("Merge conflict")

        if row.get("mergedAt") or link.state == "MERGED":
            reasons.append("PR merged — update Asana")
        elif row.get("closedAt") or link.state == "CLOSED":
            reasons.append("PR closed — update Asana")

        link.action_reasons = reasons


    @staticmethod
    def _linked_pr_event(link: GitHubLink) -> TaskEvent:
        detail_parts: list[str] = []
        if link.action_reasons:
            detail_parts.extend(link.action_reasons)
        else:
            if link.pending_reviewers:
                detail_parts.append("Waiting for " + ", ".join("@" + name for name in link.pending_reviewers))
            if link.checks_pending:
                detail_parts.append("CI running")
            if link.approvals:
                detail_parts.append(f"{link.approvals} approval(s)")
            if link.state:
                detail_parts.append(link.state.title())
        timestamp = link.merged_at or link.closed_at or link.updated_at or link.created_at
        return TaskEvent(
            id=f"github:{link.key}:{timestamp.isoformat() if timestamp else 'current'}",
            source="github",
            kind="github",
            title=f"PR #{link.number} — {link.title or link.key}",
            created_at=timestamp,
            detail=" · ".join(detail_parts) or "Linked pull request",
            url=link.url,
            current=True,
        )


    def list_assigned_issues(
        self,
        repositories: list[str],
        limit: int = 50,
    ) -> list[TaskItem]:
        if not repositories:
            return []
        login = self.current_login()
        items: list[TaskItem] = []
        for repository in repositories:
            items.extend(self._list_repository_assigned_issues(repository, login, limit))
        return sorted(items, key=lambda item: (_sortable_time(item), item.title.lower()))

    def _list_repository_assigned_issues(
        self,
        repository: str,
        login: str,
        limit: int,
    ) -> list[TaskItem]:
        owner, repo = _repository_parts(repository)
        output = self._run(
            "issue",
            "list",
            "--repo",
            repository,
            "--state",
            "open",
            "--assignee",
            "@me",
            "--limit",
            str(limit),
            "--json",
            "number,title,url,author,labels,createdAt,updatedAt",
        )

        results: list[TaskItem] = []
        for row in _rows(output, repository):
            number = int(row.get("number") or 0)
            if number <= 0:
                continue
            assigned_at, estimated = self._assigned_at(owner, repo, number, login)
            created_at = _parse_datetime(row.get("createdAt"))
            if assigned_at is None:
                assigned_at = _parse_datetime(row.get("updatedAt")) or created_at
                estimated = True

            notes: list[str] = []
            author_value = row.get("author")
            if isinstance(author_value, dict):
                author = str(author_value.get("login") or author_value.get("name") or "")
                if author:
                    notes.append(f"Opened by @{author}")

            label_names: list[str] = []
            labels = row.get("labels")
            if isinstance(labels, list):
                for label in labels:
                    if isinstance(label, dict) and label.get("name"):
                        label_names.append(str(label["name"]))
            if label_names:
                visible = ", ".join(label_names[:4])
                if len(label_names) > 4:
                    visible += f" +{len(label_names) - 4} more"
                notes.append(f"Labels: {visible}")
            if estimated:
                notes.append("Assignment age is estimated")

            results.append(
                TaskItem(
                    key=f"github-issue:{owner}/{repo}#{number}",
                    title=f"Issue #{number} — {str(row.get('title') or 'Untitled issue')}",
                    url=str(row.get("url") or f"https://github.com/{owner}/{repo}/issues/{number}"),
                    source="github",
                    github_kind="assigned_issue",
                    created_at=created_at,
                    assigned_at=assigned_at,
                    status="Assigned to you",
                    project=f"{owner}/{repo}",
                    notes=notes,
                    action_state="action",
                )
            )
        return results

    def list_mentions(
        self,
        repositories: list[str],
        limit: int = 50,
    ) -> list[TaskItem]:
        if not repositories:
            return []
        login = self.current_login()
        items: list[TaskItem] = []
        for repository in repositories:
            items.extend(self._list_repository_mentions(repository, login, limit))
        deduped: dict[str, TaskItem] = {}
        for item in items:
            existing = deduped.get(item.key)
            if existing is None or _sortable_time(item) > _sortable_time(existing):
                deduped[item.key] = item
        return sorted(deduped.values(), key=lambda item: (_sortable_time(item), item.title.lower()))

    def _list_repository_mentions(
        self,
        repository: str,
        login: str,
        limit: int,
    ) -> list[TaskItem]:
        owner, repo = _repository_parts(repository)
        common_fields = "number,title,url,repository,author,createdAt,updatedAt"
        issue_output = self._run(
            "search",
            "issues",
            "--repo",
            repository,
            "--state",
            "open",
            "--mentions",
            login,
            "--limit",
            str(limit),
            "--json",
            common_fields,
        )
        pr_output = self._run(
            "search",
            "prs",
            "--repo",
            repository,
            "--state",
            "open",
            "--mentions",
            login,
            "--limit",
            str(limit),
            "--json",
            common_fields + ",isDraft",
        )

        results: list[TaskItem] = []
        for kind, output in (("issue", issue_output), ("pull", pr_output)):
            for row in _rows(output, repository):
                if kind == "pull" and bool(row.get("isDraft")):
                    continue
                number = int(row.get("number") or 0)
                if number <= 0:
                    continue
                mentioned_at = self._latest_mention_at(
                    owner,
                    repo,
                    number,
                    login,
                    is_pull_request=(kind == "pull"),
                )
                created_at = _parse_datetime(row.get("createdAt"))
                estimated = mentioned_at is None
                if mentioned_at is None:
                    mentioned_at = _parse_datetime(row.get("updatedAt")) or created_at

                author = ""
                author_value = row.get("author")
                if isinstance(author_value, dict):
                    author = str(author_value.get("login") or author_value.get("name") or "")

                notes = [f"Mentioned in {'PR' if kind == 'pull' else 'issue'} #{number}"]
                if author:
                    notes.append(f"Opened by @{author}")
                if estimated:
                    notes.append("Mention age is estimated")

                results.append(
                    TaskItem(
                        key=f"github-mention:{owner}/{repo}#{number}",
                        title=f"{'PR' if kind == 'pull' else 'Issue'} #{number} — {str(row.get('title') or 'Untitled item')}",
                        url=str(
                            row.get("url")
                            or f"https://github.com/{owner}/{repo}/{'pull' if kind == 'pull' else 'issues'}/{number}"
                        ),
                        source="github",
                        github_kind="mention",
                        created_at=created_at,
                        assigned_at=mentioned_at,
                        status="Mentioned you",
                        project=f"{owner}/{repo}",
                        notes=notes,
                        action_state="action",
                    )
                )
        return results

    def _assigned_at(
        self,
        owner: str,
        repo: str,
        number: int,
        login: str,
    ) -> tuple[datetime | None, bool]:
        output = self._run(
            "api",
            "--paginate",
            "--slurp",
            "-H",
            "Accept: application/vnd.github+json",
            f"repos/{owner}/{repo}/issues/{number}/timeline?per_page=100",
        )
        try:
            events = _flatten_pages(json.loads(output or "[]"))
        except json.JSONDecodeError:
            return None, True
        timestamps: list[datetime] = []
        for event in events:
            if event.get("event") != "assigned":
                continue
            assignee = event.get("assignee")
            if not isinstance(assignee, dict):
                continue
            if str(assignee.get("login") or "").casefold() != login.casefold():
                continue
            created_at = _parse_datetime(event.get("created_at"))
            if created_at:
                timestamps.append(created_at)
        return (max(timestamps), False) if timestamps else (None, True)

    @staticmethod
    def _contains_mention(body: object, login: str) -> bool:
        if not body:
            return False
        pattern = rf"(?<![A-Za-z0-9-])@{re.escape(login)}(?![A-Za-z0-9-])"
        return re.search(pattern, str(body), flags=re.IGNORECASE) is not None

    def _latest_mention_at(
        self,
        owner: str,
        repo: str,
        number: int,
        login: str,
        is_pull_request: bool,
    ) -> datetime | None:
        candidates: list[datetime] = []

        issue_output = self._run("api", f"repos/{owner}/{repo}/issues/{number}")
        try:
            issue = json.loads(issue_output or "{}")
        except json.JSONDecodeError:
            issue = {}
        if isinstance(issue, dict) and self._contains_mention(issue.get("body"), login):
            created = _parse_datetime(issue.get("created_at"))
            if created:
                candidates.append(created)

        endpoint_specs = [
            (f"repos/{owner}/{repo}/issues/{number}/comments?per_page=100", "created_at"),
        ]
        if is_pull_request:
            endpoint_specs.extend(
                [
                    (f"repos/{owner}/{repo}/pulls/{number}/comments?per_page=100", "created_at"),
                    (f"repos/{owner}/{repo}/pulls/{number}/reviews?per_page=100", "submitted_at"),
                ]
            )

        for endpoint, timestamp_field in endpoint_specs:
            output = self._run("api", "--paginate", "--slurp", endpoint)
            try:
                entries = _flatten_pages(json.loads(output or "[]"))
            except json.JSONDecodeError:
                continue
            for entry in entries:
                if not self._contains_mention(entry.get("body"), login):
                    continue
                timestamp = _parse_datetime(entry.get(timestamp_field) or entry.get("created_at"))
                if timestamp:
                    candidates.append(timestamp)

        return max(candidates) if candidates else None

    def _review_requested_at(
        self,
        owner: str,
        repo: str,
        number: int,
        login: str,
    ) -> tuple[datetime | None, bool]:
        output = self._run(
            "api",
            "--paginate",
            "--slurp",
            "-H",
            "Accept: application/vnd.github+json",
            f"repos/{owner}/{repo}/issues/{number}/timeline?per_page=100",
        )
        try:
            events = _flatten_pages(json.loads(output or "[]"))
        except json.JSONDecodeError:
            return None, True

        direct: list[datetime] = []
        team: list[datetime] = []
        for event in events:
            if event.get("event") != "review_requested":
                continue
            created_at = _parse_datetime(event.get("created_at"))
            if created_at is None:
                continue
            reviewer = event.get("requested_reviewer")
            if isinstance(reviewer, dict) and str(reviewer.get("login") or "").casefold() == login.casefold():
                direct.append(created_at)
                continue
            requested_team = event.get("requested_team")
            if isinstance(requested_team, dict):
                team.append(created_at)

        if direct:
            return max(direct), False
        if team:
            return max(team), False
        return None, True
