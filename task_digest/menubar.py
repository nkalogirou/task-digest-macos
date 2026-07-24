from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

from .bootstrap import is_bundled
from .config import Config
from .runtime import get_or_create_action_token


def _get_json(url: str, timeout: float = 20.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        value = json.loads(response.read().decode("utf-8"))
    return value if isinstance(value, dict) else {}


def _post_action(config: Config, token: str, action: str, **values: str) -> dict[str, Any]:
    data = {"token": token, "action": action, **values}
    request = urllib.request.Request(
        config.dashboard_url + "/api/action",
        data=urllib.parse.urlencode(data).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        value = json.loads(response.read().decode("utf-8"))
    return value if isinstance(value, dict) else {}


def main() -> int:
    try:
        import rumps
    except ImportError as exc:  # pragma: no cover - macOS runtime only
        raise RuntimeError("The menu bar requires rumps. Run: pip install -r requirements.txt") from exc

    config = Config.load()
    token = get_or_create_action_token(config.dashboard_token_file)

    class TaskDigestMenu(rumps.App):
        def __init__(self) -> None:
            super().__init__("Task Digest", title="✓…", quit_button=None)
            self.open_item = rumps.MenuItem("Open dashboard", callback=self.open_dashboard)
            self.standup_item = rumps.MenuItem("Stand-up", callback=self.open_standup)
            self.settings_item = rumps.MenuItem("Settings", callback=self.open_settings)
            self.rules_item = rumps.MenuItem("Rules", callback=self.open_rules)
            self.relationships_item = rumps.MenuItem("Relationships", callback=self.open_relationships)
            self.history_item = rumps.MenuItem("History", callback=self.open_history)
            self.backups_item = rumps.MenuItem("Backups", callback=self.open_backups)
            self.system_item = rumps.MenuItem("System status", callback=self.open_system)
            self.refresh_item = rumps.MenuItem("Refresh now", callback=self.refresh_now)
            self.focus_menu = rumps.MenuItem("Today’s focus")
            self.daily_menu = rumps.MenuItem("Today")
            self.weekly_menu = rumps.MenuItem("This week")
            self.pause_item = rumps.MenuItem("Pause notifications 1 hour", callback=self.pause_notifications)
            self.resume_item = rumps.MenuItem("Resume notifications", callback=self.resume_notifications)
            self.quit_item = rumps.MenuItem("Quit Task Digest menu", callback=self.quit_app)
            self.menu = [
                self.open_item,
                self.standup_item,
                self.settings_item,
                self.rules_item,
                self.relationships_item,
                self.history_item,
                self.backups_item,
                self.system_item,
                self.refresh_item,
                None,
                self.focus_menu,
                self.daily_menu,
                self.weekly_menu,
                None,
                self.pause_item,
                self.resume_item,
                None,
                self.quit_item,
            ]
            self.timer = rumps.Timer(self.refresh, max(60, config.menu_refresh_minutes * 60))
            self.timer.start()
            self.scheduler_timer = None
            self._last_scheduler_minute = ""
            if is_bundled():
                self.scheduler_timer = rumps.Timer(self.run_scheduler, 60)
                self.scheduler_timer.start()
            self.refresh(None)
            if is_bundled():
                self.run_scheduler(None)

        def _replace_submenu(self, menu: Any, rows: list[Any]) -> None:
            try:
                menu.clear()
            except Exception:
                pass
            if not rows:
                row = rumps.MenuItem("None", callback=lambda _sender: None)
                menu.add(row)
                return
            for row in rows:
                menu.add(row)

        def open_dashboard(self, _sender: Any) -> None:
            webbrowser.open(config.dashboard_url)

        def open_standup(self, _sender: Any) -> None:
            webbrowser.open(config.dashboard_url + "/standup")

        def open_settings(self, _sender: Any) -> None:
            webbrowser.open(config.dashboard_url + "/settings")

        def open_rules(self, _sender: Any) -> None:
            webbrowser.open(config.dashboard_url + "/rules")

        def open_relationships(self, _sender: Any) -> None:
            webbrowser.open(config.dashboard_url + "/relationships")

        def open_history(self, _sender: Any) -> None:
            webbrowser.open(config.dashboard_url + "/history")

        def open_backups(self, _sender: Any) -> None:
            webbrowser.open(config.dashboard_url + "/backups")

        def open_system(self, _sender: Any) -> None:
            webbrowser.open(config.dashboard_url + "/system")

        def refresh_now(self, _sender: Any) -> None:
            try:
                _post_action(config, token, "refresh")
            except Exception:
                pass
            self.refresh(None)

        def run_scheduler(self, _sender: Any) -> None:
            marker = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M")
            if marker == self._last_scheduler_minute:
                return
            self._last_scheduler_minute = marker
            env = dict(os.environ)
            env["TASK_DIGEST_DATA_DIR"] = str(Path.cwd())
            try:
                subprocess.Popen(
                    [sys.executable, "--run-digest"],
                    cwd=str(Path.cwd()),
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except OSError:
                pass

        def pause_notifications(self, _sender: Any) -> None:
            try:
                _post_action(config, token, "pause_notifications")
            finally:
                self.refresh(None)

        def resume_notifications(self, _sender: Any) -> None:
            try:
                _post_action(config, token, "resume_notifications")
            finally:
                self.refresh(None)

        def quit_app(self, _sender: Any) -> None:
            rumps.quit_application()

        def refresh(self, _sender: Any) -> None:
            try:
                payload = _get_json(config.dashboard_url + "/api/summary")
            except (OSError, urllib.error.URLError, json.JSONDecodeError):
                self.title = "✓!"
                self._replace_submenu(self.focus_menu, [rumps.MenuItem("Dashboard unavailable")])
                return

            action = int(payload.get("action") or 0)
            reviews = int(payload.get("reviews") or 0)
            unread = int(payload.get("unread") or 0)
            self.title = f"✓{action} 👀{reviews}" + (f" •{unread}" if unread else "")

            focus_rows = []
            for item in payload.get("focus", []) or []:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "Untitled")
                url = str(item.get("url") or config.dashboard_url)
                focus_rows.append(rumps.MenuItem(title[:60], callback=lambda _s, target=url: webbrowser.open(target)))
            self._replace_submenu(self.focus_menu, focus_rows)

            summaries = payload.get("summaries") or {}
            daily = summaries.get("daily", {}) if isinstance(summaries, dict) else {}
            weekly = summaries.get("weekly", {}) if isinstance(summaries, dict) else {}
            daily_rows = [
                rumps.MenuItem(f"Completed: {int(daily.get('completed', 0) or 0)}"),
                rumps.MenuItem(f"New: {int(daily.get('new', 0) or 0)}"),
                rumps.MenuItem(f"Reviews done: {int(daily.get('reviews_completed', 0) or 0)}"),
            ]
            weekly_rows = [
                rumps.MenuItem(f"Completed: {int(weekly.get('completed', 0) or 0)}"),
                rumps.MenuItem(f"PRs merged: {int(weekly.get('prs_merged', 0) or 0)}"),
                rumps.MenuItem(f"Reviews done: {int(weekly.get('reviews_completed', 0) or 0)}"),
            ]
            self._replace_submenu(self.daily_menu, daily_rows)
            self._replace_submenu(self.weekly_menu, weekly_rows)

            paused = payload.get("notifications_paused_until")
            self.pause_item.title = "Notifications paused" if paused else "Pause notifications 1 hour"
            self.resume_item.title = "Resume notifications" if paused else "Notifications active"

    TaskDigestMenu().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
