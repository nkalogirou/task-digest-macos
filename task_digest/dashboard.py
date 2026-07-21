from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import threading
import time
from datetime import date, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .asana_client import AsanaClient
from .backup import BackupManager
from .changes import compare_snapshots
from .config import Config
from .diagnostics import (
    github_auth_status,
    inspect_services,
    log_files,
    next_scheduled_run,
    restart_all_services,
    restart_service,
    tail_log,
)
from .digest import (
    github_authored_prs,
    github_reviews,
    render_html,
    split_tasks,
)
from .journal import ActivityJournal
from .main import _resolve_item, collect_tasks
from .models import SourceStatus, TaskItem
from .notifier import notify
from .plan import build_smart_plan
from .preferences import TaskPreferences
from .runtime import get_or_create_action_token
from .relationships import has_relationships, relationship_tree_html
from .rules import ACTION_LABELS, CONDITION_LABELS, SOURCE_LABELS, RuleStore, describe_rule
from .settings import BOOLEAN_KEYS, EDITABLE_KEYS, read_settings, save_settings
from .standup import build_standup, render_standup_page, save_standup
from .state import DigestState
from .workspace import WorkspaceState
from .ui import SIMPLE_PAGE_CSS, brand_html, navigation_html


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], config: Config) -> None:
        super().__init__(address, DashboardHandler)
        self.config = config
        self.action_token = get_or_create_action_token(config.dashboard_token_file)
        self.cache_lock = threading.Lock()
        self.cached_html = ""
        self.cached_tasks: list[TaskItem] = []
        self.cached_statuses: list[SourceStatus] = []
        self.cached_github_warning: str | None = None
        self.cached_hidden: tuple[int, int] = (0, 0)
        self.cached_at = 0.0

    def collect_visible(self, force: bool = False) -> tuple[list[TaskItem], list[SourceStatus], str | None, tuple[int, int]]:
        ttl = max(30, self.config.dashboard_refresh_minutes * 60)
        with self.cache_lock:
            if not force and self.cached_tasks and time.time() - self.cached_at < ttl:
                return (
                    self.cached_tasks,
                    self.cached_statuses,
                    self.cached_github_warning,
                    self.cached_hidden,
                )

        now = datetime.now().astimezone()
        collection = collect_tasks(self.config, now)
        preferences = TaskPreferences(self.config.preferences_file)
        result = preferences.filter(collection.tasks, now.date())
        collection.source_statuses.append(
            SourceStatus(
                name="Local filters",
                ok=True,
                detail=f"{result.snoozed_count} snoozed · {result.ignored_count} ignored",
            )
        )
        with self.cache_lock:
            self.cached_tasks = result.visible
            self.cached_statuses = collection.source_statuses
            self.cached_github_warning = collection.github_warning
            self.cached_hidden = (result.snoozed_count, result.ignored_count)
            self.cached_at = time.time()
        return (
            result.visible,
            collection.source_statuses,
            collection.github_warning,
            (result.snoozed_count, result.ignored_count),
        )

    def render_dashboard(self, force: bool = False) -> str:
        ttl = max(30, self.config.dashboard_refresh_minutes * 60)
        with self.cache_lock:
            if not force and self.cached_html and time.time() - self.cached_at < ttl:
                return self.cached_html

        tasks, statuses, github_warning, hidden = self.collect_visible(force=force)
        now = datetime.now().astimezone()
        state = DigestState(self.config.state_file)
        changes = compare_snapshots(state.get_snapshot(), tasks)
        summaries = ActivityJournal(self.config.journal_file).summaries(now.date())
        report = render_html(
            tasks,
            now,
            "dashboard",
            self.config.report_file,
            changes=changes,
            github_warning=github_warning,
            source_statuses=statuses,
            hidden_summary=hidden,
            action_token=self.action_token,
            dashboard_url=self.config.dashboard_url,
            refresh_minutes=self.config.dashboard_refresh_minutes,
            summaries=summaries,
            asana_write_enabled=self.config.enable_asana_write_actions,
            smart_plan_max_items=self.config.smart_plan_max_items,
            smart_plan_stale_waiting_limit=self.config.smart_plan_stale_waiting_limit,
        )
        rendered = report.read_text(encoding="utf-8")
        with self.cache_lock:
            self.cached_html = rendered
            self.cached_at = time.time()
            self.cached_tasks = tasks
        return rendered

    def summary_payload(self, force: bool = False) -> dict[str, object]:
        tasks, _, _, _ = self.collect_visible(force=force)
        action, waiting, optional = split_tasks(tasks)
        focus = sorted([task for task in tasks if task.is_focused], key=lambda task: task.focus_rank or 0)
        workspace = WorkspaceState(self.config.workspace_file)
        paused_until = workspace.notifications_paused_until()
        summaries = ActivityJournal(self.config.journal_file).summaries(datetime.now().astimezone().date())
        return {
            "action": len(action),
            "waiting": len(waiting),
            "optional": len(optional),
            "reviews": len(github_reviews(tasks)),
            "pr_blockers": len(github_authored_prs(tasks)),
            "unread": sum(task.unread_updates for task in tasks),
            "focus": [
                {"key": task.key, "title": task.title, "url": task.url, "priority": task.priority}
                for task in focus[:8]
            ],
            "notifications_paused_until": paused_until.isoformat() if paused_until else None,
            "summaries": summaries,
            "updated_at": datetime.now().astimezone().isoformat(),
        }

    def diagnostics_payload(self, force_sources: bool = False) -> dict[str, object]:
        now = datetime.now().astimezone()
        services = inspect_services()
        _, statuses, github_warning, hidden = self.collect_visible(force=force_sources)
        next_run, next_period = next_scheduled_run(self.config, now)
        github_ok, github_detail = github_auth_status(self.config.github_cli_path)
        token_source = "Environment variable" if os.getenv("ASANA_TOKEN", "").strip() else "macOS Keychain"
        return {
            "services": [
                {
                    "key": item.key,
                    "name": item.name,
                    "loaded": item.loaded,
                    "state": item.state,
                    "pid": item.pid,
                    "last_exit_code": item.last_exit_code,
                    "plist_exists": item.plist_exists,
                    "ok": item.ok,
                    "detail": item.detail,
                }
                for item in services
            ],
            "next_run": next_run.isoformat(),
            "next_period": next_period,
            "source_statuses": [
                {"name": status.name, "ok": status.ok, "detail": status.detail}
                for status in statuses
            ],
            "github_warning": github_warning,
            "github_auth": {"ok": github_ok, "detail": github_detail},
            "asana_auth": {"ok": bool(self.config.asana_token), "detail": f"Token available through {token_source}"},
            "hidden": {"snoozed": hidden[0], "ignored": hidden[1]},
            "last_refresh": datetime.fromtimestamp(self.cached_at, tz=now.tzinfo).isoformat() if self.cached_at else None,
            "project_dir": str(Path.cwd()),
        }

    def invalidate(self) -> None:
        with self.cache_lock:
            self.cached_html = ""
            self.cached_tasks = []
            self.cached_statuses = []
            self.cached_github_warning = None
            self.cached_hidden = (0, 0)
            self.cached_at = 0.0


class DashboardHandler(BaseHTTPRequestHandler):
    server: DashboardServer

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def _send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _redirect(self, location: str = "/") -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            try:
                self._send_html(self.server.render_dashboard())
            except Exception as exc:
                self._send_html(self._error_page(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if path == "/api/summary":
            try:
                self._send_json(self.server.summary_payload())
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if path == "/standup":
            query = parse_qs(urlparse(self.path).query)
            self._send_html(self._standup_page(saved=query.get("saved") == ["1"]))
            return
        if path == "/history":
            self._send_html(self._history_page())
            return
        if path == "/backups":
            self._send_html(self._backups_page())
            return
        if path.startswith("/backups/download/"):
            self._serve_backup(path.removeprefix("/backups/download/"))
            return
        if path.startswith("/history/"):
            self._serve_history(path.removeprefix("/history/"))
            return
        if path == "/hidden":
            self._send_html(self._hidden_page())
            return
        if path == "/system":
            try:
                self._send_html(self._system_page())
            except Exception as exc:
                self._send_html(self._error_page(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if path == "/settings":
            self._send_html(self._settings_page())
            return
        if path == "/rules":
            query = parse_qs(urlparse(self.path).query)
            self._send_html(self._rules_page(edit_id=(query.get("edit") or [None])[0]))
            return
        if path == "/relationships":
            self._send_html(self._relationships_page())
            return
        if path == "/api/system":
            try:
                self._send_json(self.server.diagnostics_payload())
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if path.startswith("/logs/"):
            self._serve_log(path.removeprefix("/logs/"))
            return
        if path == "/health":
            self._send_json({"ok": True})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path not in {"/action", "/api/action"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length") or "0")
        body = self.rfile.read(min(length, 262144)).decode("utf-8", errors="replace")
        values = {key: items[-1] for key, items in parse_qs(body, keep_blank_values=True).items() if items}
        if values.get("token") != self.server.action_token:
            if path.startswith("/api/"):
                self._send_json({"error": "Invalid action token"}, HTTPStatus.FORBIDDEN)
            else:
                self.send_error(HTTPStatus.FORBIDDEN, "Invalid dashboard action token")
            return
        try:
            result = self._apply_action(values)
        except Exception as exc:
            if path.startswith("/api/"):
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            else:
                self._send_html(self._error_page(exc), HTTPStatus.BAD_REQUEST)
            return
        self.server.invalidate()
        if path.startswith("/api/"):
            self._send_json({"ok": True, "result": result})
        else:
            return_to = values.get("return_to", "")
            return_path = urlparse(return_to).path
            safe_return = return_to if return_path in {"/", "/hidden", "/system", "/settings", "/standup", "/backups", "/rules", "/relationships"} else ""
            if not safe_return:
                safe_return = "/hidden" if values.get("action") == "restore" else "/"
            self._redirect(safe_return)

    def _apply_action(self, values: dict[str, str]) -> object:
        action = values.get("action", "")
        key = values.get("key", "")
        workspace = WorkspaceState(self.server.config.workspace_file)
        now = datetime.now().astimezone()

        if action == "refresh":
            return "refreshed"
        if action == "pause_notifications":
            return {"paused_until": workspace.pause_notifications(now, self.server.config.notification_snooze_minutes).isoformat()}
        if action == "resume_notifications":
            workspace.resume_notifications()
            return "resumed"
        if action == "save_note":
            workspace.set_note(key, values.get("note", ""))
            return "note saved"
        if action == "set_priority":
            workspace.set_priority(key, values.get("priority"))
            return "priority saved"
        if action == "toggle_focus":
            return {"focused": workspace.toggle_focus(key, now)}
        if action == "focus_order":
            workspace.set_focus_order([value for value in values.get("keys", "").split(",") if value])
            return "focus reordered"
        if action == "accept_smart_plan":
            tasks, _, _, _ = self.server.collect_visible(force=True)
            plan = build_smart_plan(
                tasks,
                now.date(),
                max_items=self.server.config.smart_plan_max_items,
                stale_waiting_limit=self.server.config.smart_plan_stale_waiting_limit,
            )
            workspace.accept_smart_plan(plan.keys, now)
            return f"smart plan accepted with {len(plan.keys)} item(s)"
        if action == "clear_plan":
            workspace.clear_focus()
            return "today's plan cleared"
        if action == "mark_read":
            workspace.mark_updates_read(key, now)
            return "updates marked read"
        if action == "restart_service":
            service_key = values.get("service", "")
            restart_service(service_key, delayed=service_key == "dashboard")
            return f"{service_key} restart requested"
        if action == "restart_all":
            restart_all_services()
            return "all services restart requested"
        if action == "test_notification":
            notify(
                "Task Digest diagnostics",
                "The notification system is working.",
                "System test",
                open_url=self.server.config.dashboard_url + "/system",
                actionable=self.server.config.actionable_notifications,
                workspace_file=self.server.config.workspace_file,
                snooze_minutes=self.server.config.notification_snooze_minutes,
            )
            return "test notification sent"
        if action == "open_logs":
            logs_dir = Path.cwd() / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["open", str(logs_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "logs opened"
        if action == "save_settings":
            submitted = {key: values.get(key, "false" if key in BOOLEAN_KEYS else "") for key in EDITABLE_KEYS}
            save_settings(submitted, Path.cwd() / ".env")
            self._schedule_settings_reload()
            return "settings saved; services are restarting"
        if action == "save_standup":
            tasks, _, _, _ = self.server.collect_visible(force=True)
            report = build_standup(tasks, ActivityJournal(self.server.config.journal_file), now.date())
            return {"saved": str(save_standup(report, self.server.config.history_dir))}
        if action == "create_backup":
            manager = BackupManager(Path.cwd(), self.server.config.backup_dir, self.server.config.backup_retention_count)
            backup = manager.create("manual", now)
            return {"created": backup.name}
        if action == "restore_backup":
            name = values.get("backup", "").strip()
            manager = BackupManager(Path.cwd(), self.server.config.backup_dir, self.server.config.backup_retention_count)
            safety = manager.restore(name, now)
            self._schedule_settings_reload()
            return {"restored": name, "safety_backup": safety.name}
        if action == "save_rule":
            enabled = values.get("enabled", "true").casefold() in {"1", "true", "yes", "on"}
            rule = RuleStore(self.server.config.rules_file).save(
                {
                    "id": values.get("rule_id", ""),
                    "name": values.get("name", ""),
                    "enabled": enabled,
                    "source": values.get("source", "all"),
                    "project": values.get("project", ""),
                    "repository": values.get("repository", ""),
                    "condition": values.get("condition", "always"),
                    "condition_value": values.get("condition_value", ""),
                    "action": values.get("rule_action", "set_priority"),
                    "action_value": values.get("action_value", ""),
                }
            )
            return f"rule saved: {rule.name}"
        if action == "delete_rule":
            if not RuleStore(self.server.config.rules_file).delete(values.get("rule_id", "")):
                raise RuntimeError("Rule not found.")
            return "rule deleted"
        if action == "toggle_rule":
            rule = RuleStore(self.server.config.rules_file).toggle(values.get("rule_id", ""))
            return f"rule {'enabled' if rule.enabled else 'disabled'}"
        if action == "move_rule":
            RuleStore(self.server.config.rules_file).move(values.get("rule_id", ""), values.get("direction", "up"))
            return "rule reordered"
        if action.startswith("asana_"):
            return self._apply_asana_action(action, key, values, now)

        preferences = TaskPreferences(self.server.config.preferences_file)
        if action == "restore":
            if not preferences.restore(key):
                raise RuntimeError(f"No hidden rule exists for {key}")
            workspace.record_event(key, "Restored to dashboard", when=now)
            return "restored"

        tasks, _, _, _ = self.server.collect_visible(force=False)
        item = _resolve_item(tasks, key)
        if action == "snooze_1":
            until = preferences.snooze_for_working_days(item, 1, now.date(), now)
            workspace.record_event(key, "Snoozed until tomorrow", until.isoformat(), now)
            return until.isoformat()
        if action == "snooze_3":
            until = preferences.snooze_for_working_days(item, 3, now.date(), now)
            workspace.record_event(key, "Snoozed for 3 working days", until.isoformat(), now)
            return until.isoformat()
        if action == "until_change":
            preferences.snooze_until_change(item, now)
            workspace.record_event(key, "Snoozed until task changes", when=now)
            return "snoozed until change"
        if action == "ignore":
            preferences.ignore(item, now)
            workspace.record_event(key, "Ignored locally", when=now)
            return "ignored"
        raise RuntimeError(f"Unsupported dashboard action: {action}")


    def _apply_asana_action(
        self,
        action: str,
        key: str,
        values: dict[str, str],
        now: datetime,
    ) -> str:
        if not self.server.config.enable_asana_write_actions:
            raise RuntimeError("Asana write actions are disabled in Settings.")
        collection = collect_tasks(self.server.config, now)
        item = _resolve_item(collection.tasks, key)
        if item.source != "asana" or not item.key.startswith("asana:"):
            raise RuntimeError("This action is available only for Asana tasks.")
        task_gid = item.key.removeprefix("asana:").strip()
        if not task_gid:
            raise RuntimeError("The Asana task ID is missing.")

        client = AsanaClient(self.server.config.asana_token)
        workspace = WorkspaceState(self.server.config.workspace_file)
        try:
            if action == "asana_complete":
                client.complete_task(task_gid)
                workspace.record_event(key, "Marked complete in Asana", when=now)
                return "Task marked complete in Asana"
            if action == "asana_unassign":
                client.set_assignee(task_gid, None)
                workspace.record_event(key, "Unassigned yourself in Asana", when=now)
                return "You were unassigned from the Asana task"
            if action == "asana_due_date":
                raw_due = values.get("due_on", "").strip()
                due_on = date.fromisoformat(raw_due) if raw_due else None
                client.set_due_on(task_gid, due_on)
                workspace.record_event(key, "Asana due date changed", due_on.isoformat() if due_on else "Cleared", now)
                return f"Asana due date set to {due_on.isoformat()}" if due_on else "Asana due date cleared"
            if action == "asana_comment":
                comment = values.get("comment", "").strip()
                if not comment:
                    raise RuntimeError("Write a comment before posting.")
                if len(comment) > 5000:
                    raise RuntimeError("Asana comments are limited to 5,000 characters in Task Digest.")
                client.add_comment(task_gid, comment)
                preview = comment[:120] + ("…" if len(comment) > 120 else "")
                workspace.record_event(key, "Comment posted to Asana", preview, now)
                return "Comment posted to Asana"
            if action == "asana_move_section":
                raw_section = values.get("section", "").strip()
                try:
                    scope, section_gid = raw_section.split(":", 1)
                except ValueError as exc:
                    raise RuntimeError("Choose an Asana section.") from exc
                allowed = {(option.scope, option.gid) for option in item.asana_sections}
                if (scope, section_gid) not in allowed:
                    raise RuntimeError("That section is no longer available for this task.")
                client.move_task_to_section(task_gid, section_gid, scope)
                selected = next((option.label for option in item.asana_sections if option.scope == scope and option.gid == section_gid), section_gid)
                workspace.record_event(key, "Moved task in Asana", selected, now)
                return "Task moved to the selected Asana section"
            if action == "asana_set_status":
                field_gid = values.get("field_gid", "").strip()
                option_gid = values.get("option_gid", "").strip()
                if not item.status_source or item.status_source.kind != "custom_field" or item.status_source.gid != field_gid:
                    raise RuntimeError("The task status field changed; refresh and try again.")
                allowed = {option.gid for option in item.asana_status_options}
                if option_gid not in allowed:
                    raise RuntimeError("Choose an available Asana status.")
                client.set_enum_status(task_gid, field_gid, option_gid)
                selected = next((option.name for option in item.asana_status_options if option.gid == option_gid), option_gid)
                workspace.record_event(key, "Asana status updated", selected, now)
                return "Asana status updated"
        finally:
            client.close()
        raise RuntimeError(f"Unsupported Asana action: {action}")

    def _schedule_settings_reload(self) -> None:
        script = Path.cwd() / "scripts" / "apply_settings.sh"
        if not script.is_file():
            raise RuntimeError(f"Settings reload script is missing: {script}")
        subprocess.Popen(
            [str(script)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


    def _standup_page(self, saved: bool = False) -> str:
        tasks, _, _, _ = self.server.collect_visible(force=False)
        report = build_standup(
            tasks,
            ActivityJournal(self.server.config.journal_file),
            datetime.now().astimezone().date(),
        )
        return render_standup_page(
            report,
            self.server.action_token,
            self.server.config.dashboard_url,
            saved=saved,
        )

    def _settings_page(self) -> str:
        values = read_settings(Path.cwd() / ".env")
        token = html.escape(self.server.action_token, quote=True)

        def text_field(key: str, label: str, help_text: str = "", input_type: str = "text") -> str:
            value = html.escape(values.get(key, ""), quote=True)
            helper = f'<small>{html.escape(help_text)}</small>' if help_text else ""
            return (
                f'<label class="setting-field"><span>{html.escape(label)}</span>'
                f'<input type="{input_type}" name="{html.escape(key, quote=True)}" value="{value}">{helper}</label>'
            )

        def number_field(key: str, label: str, minimum: int, maximum: int, help_text: str = "") -> str:
            value = html.escape(values.get(key, ""), quote=True)
            helper = f'<small>{html.escape(help_text)}</small>' if help_text else ""
            return (
                f'<label class="setting-field"><span>{html.escape(label)}</span>'
                f'<input type="number" min="{minimum}" max="{maximum}" name="{html.escape(key, quote=True)}" value="{value}">{helper}</label>'
            )

        def checkbox(key: str, label: str, help_text: str = "") -> str:
            checked = " checked" if values.get(key, "").casefold() in {"1", "true", "yes", "on"} else ""
            helper = f'<small>{html.escape(help_text)}</small>' if help_text else ""
            return (
                '<label class="setting-switch">'
                f'<input type="checkbox" name="{html.escape(key, quote=True)}" value="true"{checked}>'
                f'<span><strong>{html.escape(label)}</strong>{helper}</span></label>'
            )

        schedule = (
            '<details class="settings-group" open><summary><span>Schedule and notifications</span><small>Timing, refresh and alert behaviour</small></summary><div class="settings-body">'
            '<div class="settings-grid">'
            + text_field("MORNING_TIME", "Morning digest", "Uses your Mac’s current timezone.", "time")
            + text_field("EVENING_TIME", "Evening digest", "Uses your Mac’s current timezone.", "time")
            + number_field("SCHEDULE_WINDOW_MINUTES", "Schedule tolerance", 1, 120, "Minutes around each scheduled time accepted by manual runners.")
            + number_field("NOTIFICATION_SNOOZE_MINUTES", "Notification snooze", 5, 1440, "Minutes used by the notification Snooze action.")
            + number_field("DASHBOARD_REFRESH_MINUTES", "Dashboard refresh", 1, 120, "Minutes between automatic dashboard refreshes.")
            + number_field("MENU_REFRESH_MINUTES", "Menu-bar refresh", 1, 120, "Minutes between menu-bar updates.")
            + '</div><div class="switch-list">'
            + checkbox("ACTIONABLE_NOTIFICATIONS", "Notification action buttons", "Show Open Dashboard and Snooze where supported.")
            + checkbox("OPEN_DASHBOARD_ON_SCHEDULE", "Open dashboard at scheduled times", "Also opens the browser at the configured morning and evening times.")
            + checkbox("OPEN_REPORT", "Open generated report after a run", "Mostly useful for manual runs.")
            + '</div></div></details>'
        )
        classification = (
            '<details class="settings-group"><summary><span>Task classification</span><small>Decide what is actionable, waiting, optional or hidden</small></summary><div class="settings-body"><div class="settings-grid settings-grid-wide">'
            + text_field("EXCLUDE_SECTIONS", "Hidden Asana sections", "Comma-separated, for example Drafts,Backlog.")
            + text_field("OPTIONAL_SECTIONS", "Optional Asana sections", "Shown collapsed and excluded from action counts.")
            + text_field("ACTION_STATUSES", "Needs-action statuses", "Comma-separated Asana status names.")
            + text_field("WAITING_STATUSES", "Waiting statuses", "Comma-separated Asana status names.")
            + '</div><div class="settings-grid">'
            + number_field("STALE_WAITING_DAYS", "Stale waiting threshold", 1, 60, "Working days before a follow-up is suggested.")
            + number_field("SMART_PLAN_MAX_ITEMS", "Today's plan size", 1, 10, "Maximum number of items in the smart daily plan.")
            + number_field("SMART_PLAN_STALE_WAITING_LIMIT", "Waiting follow-ups in plan", 0, 5, "Maximum stale waiting items included as follow-up suggestions.")
            + number_field("RECENT_COMMENT_LIMIT", "Recent comments per task", 0, 20, "Set to 0 to hide comment previews.")
            + '</div><div class="switch-list">'
            + checkbox("INCLUDE_ASANA_DEPENDENCIES", "Dependencies and blockers", "Load Asana dependencies and dependents.")
            + '</div></div></details>'
        )
        github = (
            '<details class="settings-group"><summary><span>GitHub</span><small>Repositories, review requests and PR signals</small></summary><div class="settings-body"><div class="settings-grid settings-grid-wide">'
            + text_field("GITHUB_REPOSITORIES", "Repositories", "Comma-separated owner/repository values.")
            + text_field("GITHUB_CLI_PATH", "GitHub CLI path", "Leave blank for automatic detection. Typical Apple Silicon path: /opt/homebrew/bin/gh.")
            + '</div><div class="switch-list">'
            + checkbox("INCLUDE_GITHUB_REVIEWS", "Reviews requested from you")
            + checkbox("INCLUDE_GITHUB_AUTHORED_PRS", "Your PRs needing action")
            + checkbox("INCLUDE_GITHUB_ASSIGNED_ISSUES", "Issues assigned to you")
            + checkbox("INCLUDE_GITHUB_MENTIONS", "Direct mentions")
            + checkbox("INCLUDE_LINKED_PR_STATUS", "Live status for PRs linked to Asana")
            + '</div><details class="settings-nested"><summary>Result limits</summary><div class="settings-grid">'
            + number_field("GITHUB_REVIEW_LIMIT", "Review limit", 1, 200)
            + number_field("GITHUB_PR_LIMIT", "PR limit", 1, 200)
            + number_field("GITHUB_ISSUE_LIMIT", "Issue limit", 1, 200)
            + number_field("GITHUB_MENTION_LIMIT", "Mention limit", 1, 200)
            + '</div></details></div></details>'
        )
        asana = (
            '<details class="settings-group"><summary><span>Asana source</span><small>Workspace and optional project scope</small></summary><div class="settings-body"><div class="settings-grid settings-grid-wide">'
            + text_field("ASANA_WORKSPACE_GID", "Workspace GID", "The Asana workspace to query.")
            + text_field("ASANA_PROJECT_GIDS", "Limit to project GIDs", "Optional comma-separated project GIDs; blank includes all assigned tasks in the workspace.")
            + '</div><div class="switch-list">'
            + checkbox("ENABLE_ASANA_WRITE_ACTIONS", "One-click Asana updates", "Allow confirmed completion, due date, comment, assignment and section/status actions from task cards.")
            + '</div><p class="settings-note">The Asana token remains in macOS Keychain and is never displayed here.</p></div></details>'
        )
        backups = (
            '<details class="settings-group"><summary><span>Backups</span><small>Protect local preferences, notes and report history</small></summary><div class="settings-body"><div class="settings-grid">'
            + text_field("BACKUP_DIR", "Backup folder", "Relative paths are stored inside the project folder.")
            + number_field("BACKUP_RETENTION_COUNT", "Backups to keep", 1, 365, "Older archives are removed automatically.")
            + '</div><p class="settings-note">The Asana token and dashboard action token are never included in backups.</p></div></details>'
        )
        content = (
            '<p class="lead">Change routine configuration here instead of editing <code>.env</code>. Saving validates the values, rewrites the schedule, and restarts Task Digest services.</p>'
            '<form class="settings-form" method="post" action="/action">'
            f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="action" value="save_settings"><input type="hidden" name="return_to" value="/settings">'
            + schedule + classification + github + asana + backups
            + '<div class="settings-save"><button class="primary" type="submit">Save settings and restart</button><span>The dashboard may reconnect for a few seconds.</span></div></form>'
        )
        return self._simple_page("Settings", content)


    def _backups_page(self) -> str:
        manager = BackupManager(Path.cwd(), self.server.config.backup_dir, self.server.config.backup_retention_count)
        token = html.escape(self.server.action_token, quote=True)
        cards: list[str] = []
        for backup in manager.list():
            name = html.escape(backup.name, quote=True)
            created = html.escape(backup.created_at.strftime("%A, %d %B %Y at %H:%M"))
            reason = html.escape(backup.reason.title())
            cards.append(
                '<article class="backup-card">'
                f'<div><strong>{created}</strong><span>{reason} · {html.escape(backup.size_label)}</span></div>'
                '<div class="backup-actions">'
                f'<a href="/backups/download/{name}">Download</a>'
                '<form method="post" action="/action" class="restore-form">'
                f'<input type="hidden" name="token" value="{token}">'
                '<input type="hidden" name="action" value="restore_backup">'
                '<input type="hidden" name="return_to" value="/backups">'
                f'<input type="hidden" name="backup" value="{name}">'
                '<button class="danger" type="submit">Restore</button></form></div></article>'
            )
        rows = ''.join(cards) or '<p>No backups yet. Create one now, or wait for the next scheduled morning/evening run.</p>'
        content = (
            '<p class="lead">Backups contain settings, focus order, notes, snoozes, local activity and saved reports. They do not contain your Asana token, dashboard token, logs or virtual environment.</p>'
            '<div class="backup-toolbar"><form method="post" action="/action">'
            f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="action" value="create_backup"><input type="hidden" name="return_to" value="/backups">'
            '<button class="primary" type="submit">Create backup now</button></form>'
            f'<span>Keeping the newest {self.server.config.backup_retention_count} backup(s)</span></div>'
            + rows
            + '<script>document.querySelectorAll(".restore-form").forEach(form=>form.addEventListener("submit",event=>{if(!confirm("Restore this backup? Current settings and local state will be saved to a safety backup first.")){event.preventDefault();}}));</script>'
        )
        return self._simple_page("Backup and restore", content)

    def _serve_backup(self, name: str) -> None:
        try:
            backup = BackupManager(Path.cwd(), self.server.config.backup_dir, self.server.config.backup_retention_count).get(name)
        except (ValueError, FileNotFoundError):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        payload = backup.path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f'attachment; filename="{backup.name}"')
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _rules_page(self, edit_id: str | None = None) -> str:
        store = RuleStore(self.server.config.rules_file)
        rules = store.list()
        token = html.escape(self.server.action_token, quote=True)

        editing = next((rule for rule in rules if rule.id == edit_id), None)

        def options(values: dict[str, str], selected: str = "") -> str:
            return "".join(
                f'<option value="{html.escape(key, quote=True)}"{" selected" if key == selected else ""}>{html.escape(label)}</option>'
                for key, label in values.items()
            )

        def field(value: str) -> str:
            return html.escape(value, quote=True)

        cards: list[str] = []
        for index, rule in enumerate(rules):
            css = "" if rule.enabled else " disabled"
            state = "Enabled" if rule.enabled else "Disabled"
            escaped_id = html.escape(rule.id, quote=True)
            cards.append(
                f'<article class="rule-card{css}"><div class="rule-card-head"><div><h3>{html.escape(rule.name)}</h3>'
                f'<p>{html.escape(describe_rule(rule))}</p></div><span class="badge">{state}</span></div>'
                '<div class="rule-actions">'
                f'<a class="button" href="/rules?edit={escaped_id}">Edit</a>'
                '<form method="post" action="/action">'
                f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="return_to" value="/rules">'
                f'<input type="hidden" name="rule_id" value="{escaped_id}"><input type="hidden" name="action" value="toggle_rule">'
                f'<button type="submit">{"Disable" if rule.enabled else "Enable"}</button></form>'
                '<form method="post" action="/action">'
                f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="return_to" value="/rules">'
                f'<input type="hidden" name="rule_id" value="{escaped_id}"><input type="hidden" name="action" value="move_rule"><input type="hidden" name="direction" value="up">'
                f'<button type="submit"{" disabled" if index == 0 else ""}>Move up</button></form>'
                '<form method="post" action="/action">'
                f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="return_to" value="/rules">'
                f'<input type="hidden" name="rule_id" value="{escaped_id}"><input type="hidden" name="action" value="move_rule"><input type="hidden" name="direction" value="down">'
                f'<button type="submit"{" disabled" if index == len(rules) - 1 else ""}>Move down</button></form>'
                '<form method="post" action="/action" data-confirm="Delete this rule?">'
                f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="return_to" value="/rules">'
                f'<input type="hidden" name="rule_id" value="{escaped_id}"><input type="hidden" name="action" value="delete_rule">'
                '<button class="danger" type="submit">Delete</button></form></div></article>'
            )

        base_rules = (
            '<div class="rule-examples">'
            f'<div class="rule-example"><strong>Hidden sections</strong><br>{html.escape(", ".join(sorted(self.server.config.excluded_sections)) or "None")}</div>'
            f'<div class="rule-example"><strong>Optional sections</strong><br>{html.escape(", ".join(sorted(self.server.config.optional_sections)) or "None")}</div>'
            f'<div class="rule-example"><strong>Needs action statuses</strong><br>{html.escape(", ".join(sorted(self.server.config.action_statuses)) or "None")}</div>'
            f'<div class="rule-example"><strong>Waiting statuses</strong><br>{html.escape(", ".join(sorted(self.server.config.waiting_statuses)) or "None")}</div>'
            '</div>'
        )
        examples = (
            '<div class="rule-examples">'
            '<div class="rule-example"><strong>Stale review</strong><br>When waiting age is at least 5 days, suggest follow-up.</div>'
            '<div class="rule-example"><strong>Failing checks</strong><br>When a linked PR has failing checks, set priority to Urgent.</div>'
            '<div class="rule-example"><strong>Project-specific</strong><br>Scope a rule to one Asana project or GitHub repository.</div>'
            '</div>'
        )
        current = editing
        builder_title = "Edit rule" if current else "Add a rule"
        builder = (
            '<form class="rule-builder" method="post" action="/action" id="rule-builder">'
            f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="return_to" value="/rules">'
            f'<input type="hidden" name="action" value="save_rule"><input type="hidden" name="rule_id" value="{field(current.id if current else "")}">'
            f'<input type="hidden" name="enabled" value="{str(current.enabled if current else True).lower()}">'
            '<div class="rule-builder-grid">'
            f'<label class="wide">Rule name<input name="name" required value="{field(current.name if current else "")}" placeholder="Example: Escalate failing checks"></label>'
            f'<label>Applies to<select name="source">{options(SOURCE_LABELS, current.source if current else "all")}</select></label>'
            f'<label>Asana project scope<input name="project" value="{field(current.project if current else "")}" placeholder="Optional exact project name"></label>'
            f'<label>GitHub repository scope<input name="repository" value="{field(current.repository if current else "")}" placeholder="Optional owner/repository"></label>'
            f'<label>When<select name="condition" id="rule-condition">{options(CONDITION_LABELS, current.condition if current else "always")}</select></label>'
            f'<label id="condition-value-wrap">Condition value<input name="condition_value" id="condition-value" value="{field(current.condition_value if current else "")}" placeholder="Status, section, priority, or working days"></label>'
            f'<label>Then<select name="rule_action" id="rule-action">{options(ACTION_LABELS, current.action if current else "set_priority")}</select></label>'
            f'<label id="action-value-wrap">Action value<input name="action_value" id="action-value" value="{field(current.action_value if current else "")}" placeholder="urgent, waiting, or note text"></label>'
            '</div><div class="rule-actions" style="margin-top:15px">'
            f'<button class="primary" type="submit">{"Save changes" if current else "Add rule"}</button>'
            + ('<a class="button" href="/rules">Cancel</a>' if current else '')
            + '</div></form>'
        )
        script = '''<script>
const valueConditions = new Set(['status_is','section_is','age_at_least','waiting_age_at_least','priority_is']);
const valueActions = new Set(['set_priority','set_state','add_note']);
const condition = document.getElementById('rule-condition');
const ruleAction = document.getElementById('rule-action');
const conditionWrap = document.getElementById('condition-value-wrap');
const actionWrap = document.getElementById('action-value-wrap');
function syncRuleFields(){ conditionWrap.hidden=!valueConditions.has(condition.value); actionWrap.hidden=!valueActions.has(ruleAction.value); }
condition.addEventListener('change',syncRuleFields); ruleAction.addEventListener('change',syncRuleFields); syncRuleFields();
document.querySelectorAll('[data-confirm]').forEach(form=>form.addEventListener('submit',event=>{if(!confirm(form.dataset.confirm))event.preventDefault();}));
</script>'''
        content = (
            '<p class="lead">Rules run from top to bottom after live Asana and GitHub data is loaded. Later rules can override earlier ones; manual priority overrides still win last.</p>'
            + '<h2>Base workflow rules</h2>' + base_rules
            + '<h2>Examples</h2>' + examples
            + '<h2>Your rules</h2>'
            + ('<div class="rule-list">' + ''.join(cards) + '</div>' if cards else '<p class="empty">No custom rules yet. Your existing status and due-date logic continues to work.</p>')
            + f'<h2>{html.escape(builder_title)}</h2>' + builder + script
        )
        return self._simple_page("Rule editor", content)

    def _relationships_page(self) -> str:
        tasks, _, _, _ = self.server.collect_visible(force=False)
        related = [task for task in tasks if task.source == "asana" and has_relationships(task)]
        cards: list[str] = []
        for task in related:
            title = html.escape(task.title)
            if task.url:
                title = f'<a href="{html.escape(task.url, quote=True)}">{title}</a>'
            details = []
            if task.project:
                details.append(task.project)
            if task.status:
                details.append(task.status)
            details.append(f"{len([item for item in task.dependencies if not item.completed])} open blocker(s)")
            cards.append(
                f'<article class="relationship-page-card"><h3>{title}</h3><p>{html.escape(" · ".join(details))}</p>'
                f'{relationship_tree_html(task, expanded=True)}</article>'
            )
        blockers = sum(len([dependency for dependency in task.dependencies if not dependency.completed]) for task in related)
        content = (
            '<div class="system-summary">'
            f'<article><strong>Connected tasks</strong><span>{len(related)} task(s) with dependencies or dependents</span></article>'
            f'<article><strong>Open blockers</strong><span>{blockers} incomplete upstream task(s)</span></article>'
            '</div>'
            '<p class="lead">Each map reads from upstream blockers to the current task and then to work it unblocks. “Start here” highlights the first actionable item in the chain.</p>'
            + ('<div class="relationship-page-grid">' + ''.join(cards) + '</div>' if cards else '<p class="empty">No current Asana tasks have dependencies or dependents.</p>')
        )
        return self._simple_page("Task relationships", content)

    def _history_page(self) -> str:
        directory = Path(self.server.config.history_dir).expanduser().resolve()
        files = sorted(
            [*directory.glob("*.html"), *directory.glob("*.md")],
            key=lambda item: item.name,
            reverse=True,
        ) if directory.exists() else []
        rows = "".join(
            f'<li><a href="/history/{html.escape(path.name, quote=True)}">{html.escape(path.stem.replace("-", " "))}</a></li>'
            for path in files
        ) or "<li>No saved reports yet. Scheduled morning and evening runs will appear here.</li>"
        return self._simple_page("Report history", f'<ul class="history">{rows}</ul>')

    def _serve_history(self, name: str) -> None:
        safe_name = Path(name).name
        if safe_name != name or Path(safe_name).suffix not in {".html", ".md"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        path = Path(self.server.config.history_dir).expanduser().resolve() / safe_name
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".md":
            self._send_html(self._simple_page(path.stem.replace("-", " ").title(), f'<pre class="standup-history">{html.escape(text)}</pre>'))
        else:
            self._send_html(text)

    def _system_page(self) -> str:
        payload = self.server.diagnostics_payload()
        token = html.escape(self.server.action_token, quote=True)
        service_cards = []
        for service in payload["services"]:
            icon = "✅" if service["ok"] else "⚠️"
            css = "ok" if service["ok"] else "warning"
            pid = f" · PID {service['pid']}" if service.get("pid") else ""
            service_cards.append(
                f'<article class="system-card {css}"><div><strong>{icon} {html.escape(str(service["name"]))}</strong>'
                f'<span>{html.escape(str(service["detail"]))}{pid}</span></div>'
                '<form method="post" action="/action">'
                f'<input type="hidden" name="token" value="{token}">'
                '<input type="hidden" name="action" value="restart_service"><input type="hidden" name="return_to" value="/system">'
                f'<input type="hidden" name="service" value="{html.escape(str(service["key"]), quote=True)}">'
                '<button type="submit">Restart</button></form></article>'
            )
        source_cards = []
        for source in payload["source_statuses"]:
            icon = "✅" if source["ok"] else "⚠️"
            css = "ok" if source["ok"] else "warning"
            source_cards.append(
                f'<article class="system-card {css}"><div><strong>{icon} {html.escape(str(source["name"]))}</strong>'
                f'<span>{html.escape(str(source["detail"]))}</span></div></article>'
            )
        for name, auth in (("Asana authentication", payload["asana_auth"]), ("GitHub authentication", payload["github_auth"])):
            icon = "✅" if auth["ok"] else "⚠️"
            css = "ok" if auth["ok"] else "warning"
            source_cards.append(
                f'<article class="system-card {css}"><div><strong>{icon} {html.escape(name)}</strong>'
                f'<span>{html.escape(str(auth["detail"]))}</span></div></article>'
            )
        logs = []
        for key, label, path in log_files(Path.cwd()):
            preview = html.escape(tail_log(path, 18))
            logs.append(
                f'<details class="log-panel"><summary>{html.escape(label)}</summary>'
                f'<pre>{preview}</pre><a href="/logs/{html.escape(key, quote=True)}">Open full log</a></details>'
            )
        next_dt = datetime.fromisoformat(str(payload["next_run"]))
        last_refresh = payload.get("last_refresh")
        last_refresh_text = "Not refreshed in this process yet"
        if last_refresh:
            last_refresh_text = datetime.fromisoformat(str(last_refresh)).strftime("%A %H:%M:%S")
        controls = (
            '<div class="system-actions">'
            '<form method="post" action="/action">'
            f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="action" value="refresh"><input type="hidden" name="return_to" value="/system">'
            '<button class="primary" type="submit">Refresh task data</button></form>'
            '<form method="post" action="/action">'
            f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="action" value="test_notification"><input type="hidden" name="return_to" value="/system">'
            '<button type="submit">Test notification</button></form>'
            '<form method="post" action="/action">'
            f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="action" value="open_logs"><input type="hidden" name="return_to" value="/system">'
            '<button type="submit">Open logs folder</button></form>'
            '<form method="post" action="/action">'
            f'<input type="hidden" name="token" value="{token}"><input type="hidden" name="action" value="restart_all"><input type="hidden" name="return_to" value="/system">'
            '<button class="danger" type="submit">Restart all services</button></form></div>'
        )
        content = (
            '<div class="system-summary">'
            f'<article><strong>Next notification</strong><span>{html.escape(str(payload["next_period"]))} · {next_dt:%A %d %B at %H:%M}</span></article>'
            f'<article><strong>Last data refresh</strong><span>{html.escape(last_refresh_text)}</span></article>'
            f'<article><strong>Local filters</strong><span>{payload["hidden"]["snoozed"]} snoozed · {payload["hidden"]["ignored"]} ignored</span></article>'
            '</div>' + controls + '<h2>Background services</h2><div class="system-grid">' + ''.join(service_cards) + '</div>'
            '<h2>Data and authentication</h2><div class="system-grid">' + ''.join(source_cards) + '</div>'
            '<h2>Recent logs</h2>' + ''.join(logs)
        )
        return self._simple_page("System status", content)

    def _serve_log(self, key: str) -> None:
        paths = {item_key: path for item_key, _label, path in log_files(Path.cwd())}
        path = paths.get(key)
        if path is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        text = tail_log(path, 1000)
        payload = text.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _hidden_page(self) -> str:
        preferences = TaskPreferences(self.server.config.preferences_file)
        entries = preferences.list_entries()
        token = html.escape(self.server.action_token, quote=True)
        cards = []
        for key, rule in entries:
            title = html.escape(str(rule.get("title") or key))
            detail = html.escape(str(rule.get("wake_on") or rule.get("mode") or "hidden"))
            escaped_key = html.escape(key, quote=True)
            cards.append(
                '<article class="hidden-card">'
                f'<strong>{title}</strong><span>{detail}</span>'
                '<form method="post" action="/action">'
                f'<input type="hidden" name="token" value="{token}">'
                f'<input type="hidden" name="key" value="{escaped_key}">'
                '<input type="hidden" name="action" value="restore">'
                '<button type="submit">Restore</button></form></article>'
            )
        content = "".join(cards) or "<p>No snoozed or ignored tasks.</p>"
        return self._simple_page("Hidden tasks", content)

    def _simple_page(self, title: str, content: str) -> str:
        subtitle_map = {
            "Settings": "Configure scheduling, classification, integrations and local behavior.",
            "Rule editor": "Create ordered project- and repository-aware automation rules.",
            "Task relationships": "See blockers, current work and downstream tasks as connected maps.",
            "System status": "See service health, authentication, refresh status and recent logs.",
            "Report history": "Review saved morning, evening and stand-up reports.",
            "Backup and restore": "Protect local preferences, notes, focus order and report history.",
            "Hidden tasks": "Review snoozed and ignored items and restore them when needed.",
            "Dashboard error": "Task Digest could not render this page.",
        }
        subtitle = subtitle_map.get(title, "Task Digest workspace")
        sidebar = f'<aside class="app-sidebar">{brand_html()}{navigation_html()}</aside>'
        return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{SIMPLE_PAGE_CSS}</style></head>
<body><div class="app-shell">{sidebar}<main class="app-main"><div class="app-content">
<header class="page-header"><div class="page-title-wrap"><span class="eyebrow">Task Digest</span><h1>{html.escape(title)}</h1><p class="page-subtitle">{html.escape(subtitle)}</p></div></header>
{content}
</div></main></div>
<script>document.querySelectorAll('[data-nav-path]').forEach(link=>{{const path=link.dataset.navPath;const active=path==='/'?location.pathname==='/':location.pathname.startsWith(path);link.classList.toggle('active',active);if(active)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');}});</script>
</body></html>'''

    def _error_page(self, exc: Exception) -> str:
        return self._simple_page("Dashboard error", f'<p>{html.escape(str(exc))}</p><p>Check <code>logs/dashboard.stderr.log</code>.</p>')


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local Task Digest dashboard.")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    config = Config.load()
    host = args.host or config.dashboard_host
    port = args.port or config.dashboard_port
    server = DashboardServer((host, port), config)
    print(f"Task Digest dashboard: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
