from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Optional

from .asana_client import AsanaClient
from .backup import BackupManager
from .changes import compare_snapshots, snapshot_tasks
from .config import Config
from .digest import notification_summary, render_html, render_text
from .enrichment import apply_local_workspace, enrich_asana_task
from .journal import ActivityJournal
from .github_client import GitHubClient, GitHubClientError
from .models import SourceStatus, TaskItem
from .notifier import notify, open_location, open_report
from .preferences import TaskPreferences
from .priority import assign_priority
from .runtime import get_or_create_action_token, save_history
from .rules import RuleStore
from .state import DigestState
from .workspace import WorkspaceState


@dataclass
class TaskCollection:
    tasks: list[TaskItem]
    source_statuses: list[SourceStatus]
    github_warning: str | None


def _minutes_from(a: time, b: time) -> int:
    return abs((a.hour * 60 + a.minute) - (b.hour * 60 + b.minute))


def _period_for(now: datetime, config: Config, force: Optional[str]) -> Optional[str]:
    if force:
        return force
    if now.weekday() >= 5:
        return None
    current = now.time().replace(second=0, microsecond=0)
    if _minutes_from(current, config.morning_time) <= config.schedule_window_minutes:
        return "morning"
    if _minutes_from(current, config.evening_time) <= config.schedule_window_minutes:
        return "evening"
    return None


def _short_error(exc: Exception) -> str:
    text = str(exc).strip().replace("\n", " ")
    return text[:220] or exc.__class__.__name__


def collect_tasks(config: Config, now: datetime) -> TaskCollection:
    tasks: list[TaskItem] = []
    source_statuses: list[SourceStatus] = []
    asana_tasks: list[TaskItem] = []

    asana = AsanaClient(config.asana_token)
    try:
        asana_tasks = asana.list_assigned_tasks(
            config.asana_workspace_gid,
            config.asana_project_gids or None,
            excluded_sections=config.excluded_sections,
            optional_sections=config.optional_sections,
            include_dependencies=config.include_asana_dependencies,
            recent_comment_limit=config.recent_comment_limit,
            include_write_options=config.enable_asana_write_actions,
        )
        tasks.extend(asana_tasks)
        source_statuses.append(
            SourceStatus(
                name="Asana",
                ok=True,
                detail=f"Loaded {len(asana_tasks)} assigned task(s)",
            )
        )
    except Exception as exc:  # Keep GitHub sections usable when Asana is temporarily unavailable.
        source_statuses.append(
            SourceStatus(name="Asana", ok=False, detail=_short_error(exc))
        )
    finally:
        asana.close()

    github_enabled = any(
        (
            config.include_github_reviews,
            config.include_github_authored_prs,
            config.include_github_assigned_issues,
            config.include_github_mentions,
            config.include_linked_pr_status and bool(asana_tasks),
        )
    )
    github_errors: list[str] = []
    github_loaded = 0
    github: GitHubClient | None = None

    if github_enabled:
        try:
            github = GitHubClient(cli_path=config.github_cli_path)
        except GitHubClientError as exc:
            github_errors.append(str(exc))

        if github and config.include_linked_pr_status and asana_tasks:
            loaded, errors = github.enrich_linked_pull_requests(
                asana_tasks,
                config.github_repositories,
            )
            github_loaded += loaded
            github_errors.extend(f"Linked PR status: {error}" for error in errors)

    # GitHub status and Asana dependencies affect whether work is actionable,
    # so classification happens only after both sources have been enriched.
    for item in asana_tasks:
        enrich_asana_task(
            item,
            now=now,
            action_statuses=config.action_statuses,
            waiting_statuses=config.waiting_statuses,
            stale_waiting_days=config.stale_waiting_days,
        )

    if github_enabled:
        if github and config.include_github_reviews:
            try:
                reviews = github.list_review_requests(
                    config.github_repositories,
                    limit=config.github_review_limit,
                )
                for review in reviews:
                    assign_priority(review, now)
                tasks.extend(reviews)
                github_loaded += len(reviews)
            except GitHubClientError as exc:
                github_errors.append(f"Review requests: {exc}")

        if github and config.include_github_authored_prs:
            try:
                authored_prs = github.list_authored_prs_needing_action(
                    config.github_repositories,
                    limit=config.github_pr_limit,
                )
                linked_prs = {
                    link.key: task.title
                    for task in tasks
                    if task.source == "asana"
                    for link in task.github_links
                    if link.kind == "pull" and not link.is_draft
                }
                added = 0
                for pull_request in authored_prs:
                    assign_priority(pull_request, now)
                    key = pull_request.key.removeprefix("github-authored:")
                    # The blocker is already displayed inside the Asana task card.
                    if key in linked_prs:
                        continue
                    tasks.append(pull_request)
                    added += 1
                github_loaded += added
            except GitHubClientError as exc:
                github_errors.append(f"Your pull requests: {exc}")

        if github and config.include_github_assigned_issues:
            try:
                assigned_issues = github.list_assigned_issues(
                    config.github_repositories,
                    limit=config.github_issue_limit,
                )
                linked_urls = {
                    link.url
                    for task in tasks
                    if task.source == "asana"
                    for link in task.github_links
                    if not link.is_draft
                }
                added = 0
                for issue in assigned_issues:
                    if issue.url in linked_urls:
                        continue
                    assign_priority(issue, now)
                    tasks.append(issue)
                    added += 1
                github_loaded += added
            except GitHubClientError as exc:
                github_errors.append(f"Assigned issues: {exc}")

        if github and config.include_github_mentions:
            try:
                mentions = github.list_mentions(
                    config.github_repositories,
                    limit=config.github_mention_limit,
                )
                occupied_urls = {item.url for item in tasks if item.url}
                occupied_urls.update(
                    link.url
                    for task in tasks
                    if task.source == "asana"
                    for link in task.github_links
                    if not link.is_draft
                )
                added = 0
                for mention in mentions:
                    if mention.url in occupied_urls:
                        continue
                    assign_priority(mention, now)
                    tasks.append(mention)
                    added += 1
                    if mention.url:
                        occupied_urls.add(mention.url)
                github_loaded += added
            except GitHubClientError as exc:
                github_errors.append(f"Mentions: {exc}")

        if github_errors:
            source_statuses.append(
                SourceStatus(
                    name="GitHub",
                    ok=False,
                    detail=" | ".join(dict.fromkeys(github_errors)),
                )
            )
        else:
            source_statuses.append(
                SourceStatus(
                    name="GitHub",
                    ok=True,
                    detail=(
                        f"Loaded {github_loaded} live/relevant item(s) from "
                        f"{len(config.github_repositories)} repositorie(s)"
                    ),
                )
            )
    else:
        source_statuses.append(
            SourceStatus(name="GitHub", ok=True, detail="GitHub sources disabled")
        )

    try:
        rule_result = RuleStore(config.rules_file).apply(tasks, now)
        tasks = rule_result.visible
        source_statuses.append(
            SourceStatus(
                name="Rules",
                ok=True,
                detail=(
                    f"{rule_result.enabled_count} enabled · "
                    f"{rule_result.match_count} match(es) · "
                    f"{rule_result.hidden_count} hidden"
                ),
            )
        )
    except Exception as exc:
        source_statuses.append(SourceStatus(name="Rules", ok=False, detail=_short_error(exc)))

    workspace = WorkspaceState(config.workspace_file)
    apply_local_workspace(tasks, workspace, now)

    github_warning = " | ".join(dict.fromkeys(github_errors)) if github_errors else None
    return TaskCollection(
        tasks=tasks,
        source_statuses=source_statuses,
        github_warning=github_warning,
    )


def _resolve_item(tasks: list[TaskItem], identifier: str) -> TaskItem:
    exact_key = [item for item in tasks if item.key == identifier]
    if exact_key:
        return exact_key[0]
    exact_url = [item for item in tasks if item.url == identifier]
    if exact_url:
        return exact_url[0]
    title_matches = [
        item for item in tasks if item.title.casefold() == identifier.casefold()
    ]
    if len(title_matches) == 1:
        return title_matches[0]
    if len(title_matches) > 1:
        raise RuntimeError("More than one task has that title. Use the task key from --list-items.")
    raise RuntimeError(f"No current task matches: {identifier}")


def _print_items(tasks: list[TaskItem]) -> None:
    if not tasks:
        print("No current tasks found.")
        return
    for item in sorted(tasks, key=lambda value: (value.source, value.title.casefold())):
        status = f" · {item.status}" if item.status else ""
        print(f"{item.key}\n  {item.title}{status}")
        if item.url:
            print(f"  {item.url}")


def _manage_preferences(args: argparse.Namespace, config: Config) -> int | None:
    preferences = TaskPreferences(config.preferences_file)

    if args.list_preferences:
        entries = preferences.list_entries()
        if not entries:
            print("No snoozed or ignored tasks.")
            return 0
        for key, rule in entries:
            detail = rule.get("wake_on") or rule.get("mode")
            print(f"{key}\n  {rule.get('title', '')}\n  {detail}")
        return 0

    if args.restore:
        if preferences.restore(args.restore):
            print(f"Restored {args.restore}")
            return 0
        print(f"No preference exists for {args.restore}")
        return 1

    if not any((args.list_items, args.snooze, args.snooze_until_change, args.ignore)):
        return None

    now = datetime.now().astimezone()
    collection = collect_tasks(config, now)
    if args.list_items:
        _print_items(collection.tasks)
        return 0

    identifier = args.snooze or args.snooze_until_change or args.ignore
    assert identifier is not None
    item = _resolve_item(collection.tasks, identifier)

    if args.snooze:
        wake_on = preferences.snooze_for_working_days(
            item,
            days=args.working_days,
            today=now.date(),
            now=now,
        )
        print(f"Snoozed {item.title} until {wake_on.isoformat()}")
    elif args.snooze_until_change:
        preferences.snooze_until_change(item, now)
        print(f"Snoozed {item.title} until its status, due date, section, or linked GitHub item changes")
    else:
        preferences.ignore(item, now)
        print(f"Ignored {item.title}")
    return 0


def build_digest(
    config: Config,
    force: Optional[str],
    dry_run: bool,
    should_notify: bool,
    should_open: bool,
) -> int:
    now = datetime.now().astimezone()
    period = _period_for(now, config, force)
    if not period and not dry_run:
        print(f"No digest due at {now.isoformat()}")
        return 0
    period = period or "preview"

    state = DigestState(config.state_file)
    state_key = f"{now.date().isoformat()}:{period}"
    if not dry_run and state.sent(state_key):
        print(f"Digest already generated for {state_key}")
        return 0

    collection = collect_tasks(config, now)
    if collection.github_warning:
        print(f"Warning: Some GitHub data could not be loaded: {collection.github_warning}")

    preferences = TaskPreferences(config.preferences_file)
    preference_result = preferences.filter(collection.tasks, now.date())
    tasks = preference_result.visible
    collection.source_statuses.append(
        SourceStatus(
            name="Local filters",
            ok=True,
            detail=(
                f"{preference_result.snoozed_count} snoozed · "
                f"{preference_result.ignored_count} ignored"
            ),
        )
    )

    current_snapshot = snapshot_tasks(tasks)
    changes = compare_snapshots(
        state.get_snapshot(),
        tasks,
        suppressed_keys=preference_result.suppressed_keys,
    )

    hidden_summary = (
        preference_result.snoozed_count,
        preference_result.ignored_count,
    )
    workspace = WorkspaceState(config.workspace_file)
    journal = ActivityJournal(config.journal_file)
    summaries = journal.summaries(now.date())
    action_token = get_or_create_action_token(config.dashboard_token_file)
    text = render_text(
        tasks,
        now,
        period,
        changes=changes,
        github_warning=collection.github_warning,
        source_statuses=collection.source_statuses,
        hidden_summary=hidden_summary,
    )
    report = render_html(
        tasks,
        now,
        period,
        config.report_file,
        changes=changes,
        github_warning=collection.github_warning,
        source_statuses=collection.source_statuses,
        hidden_summary=hidden_summary,
        action_token=action_token,
        dashboard_url=config.dashboard_url,
        refresh_minutes=config.dashboard_refresh_minutes,
        summaries=summaries,
        asana_write_enabled=config.enable_asana_write_actions,
        smart_plan_max_items=config.smart_plan_max_items,
        smart_plan_stale_waiting_limit=config.smart_plan_stale_waiting_limit,
    )
    print(text)
    print(f"\nHTML report: {report}")

    if dry_run:
        return 0

    if period in {"morning", "evening"}:
        try:
            BackupManager(Path.cwd(), config.backup_dir, config.backup_retention_count).ensure_daily(now.date())
        except Exception as exc:
            print(f"Warning: automatic backup failed: {_short_error(exc)}")
        history = save_history(report, config.history_dir, now, period)
        journal.record(period, now, tasks, changes)
        print(f"History report: {history}")

    notifications_paused = workspace.notifications_are_paused(now)
    if should_notify and not notifications_paused:
        title, body = notification_summary(tasks, period=period, changes=changes)
        notify(
            title,
            body,
            f"{period.title()} digest",
            open_url=config.dashboard_url,
            actionable=config.actionable_notifications,
            workspace_file=config.workspace_file,
            snooze_minutes=config.notification_snooze_minutes,
        )
    elif should_notify and notifications_paused:
        print("Notifications are temporarily paused.")
    if config.open_dashboard_on_schedule:
        open_location(config.dashboard_url)
    elif should_open or config.open_report:
        open_report(report)

    state.record_run(state_key, now.isoformat(), current_snapshot)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local Asana and GitHub task digest on macOS.")
    parser.add_argument("--dry-run", action="store_true", help="Print and create HTML without notifying.")
    parser.add_argument(
        "--force",
        choices=["morning", "evening"],
        help="Run immediately and label the digest as morning or evening.",
    )
    parser.add_argument("--no-notify", action="store_true", help="Do not show a macOS notification.")
    parser.add_argument("--open-report", action="store_true", help="Open the generated HTML report in your browser.")

    controls = parser.add_mutually_exclusive_group()
    controls.add_argument("--list-items", action="store_true", help="List current task keys for snoozing or ignoring.")
    controls.add_argument("--list-preferences", action="store_true", help="List snoozed and ignored tasks.")
    controls.add_argument("--snooze", metavar="TASK", help="Snooze a task key, exact URL, or unique exact title.")
    controls.add_argument("--snooze-until-change", metavar="TASK", help="Hide a task until its state changes.")
    controls.add_argument("--ignore", metavar="TASK", help="Permanently hide a task locally.")
    controls.add_argument("--restore", metavar="TASK_KEY", help="Remove a snooze or ignore rule.")
    parser.add_argument("--working-days", type=int, default=1, help="Working days for --snooze (default: 1).")

    args = parser.parse_args()
    config = Config.load()
    managed = _manage_preferences(args, config)
    if managed is not None:
        return managed
    return build_digest(
        config=config,
        force=args.force,
        dry_run=args.dry_run,
        should_notify=not args.no_notify and not args.dry_run,
        should_open=args.open_report,
    )


if __name__ == "__main__":
    raise SystemExit(main())
