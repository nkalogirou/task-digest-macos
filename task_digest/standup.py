from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from typing import Any

from .journal import ActivityJournal
from .models import TaskItem
from .ui import SHARED_CSS, brand_html, navigation_html
from .priority import PRIORITY_RANK


STANDUP_CSS = SHARED_CSS + r"""
.standup-metrics { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin:20px 0 24px; }
.standup-metric { position:relative; overflow:hidden; background:var(--surface); border:1px solid var(--border); border-radius:17px; padding:16px; box-shadow:var(--shadow-sm); display:grid; gap:5px; }
.standup-metric::after { content:""; position:absolute; width:70px; height:70px; right:-25px; bottom:-34px; border-radius:50%; background:color-mix(in srgb,var(--accent) 10%,transparent); }
.standup-metric strong { font-size:26px; line-height:1; letter-spacing:-.03em; }
.standup-metric span { color:var(--muted); font-size:11px; }
.plan-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:13px; margin:22px 0; }
.plan-column { background:var(--surface); border:1px solid var(--border); border-radius:18px; padding:14px; box-shadow:var(--shadow-sm); }
.plan-column h2 { font-size:15px; margin:2px 2px 12px; }
.standup-card, .empty { background:var(--surface-muted); border:1px solid var(--border); border-radius:12px; padding:12px; margin:8px 0; }
.standup-card strong { font-size:13px; }
.standup-card p { color:var(--muted); font-size:11px; line-height:1.45; margin:5px 0 0; }
.composer { background:var(--surface); border:1px solid var(--border); border-radius:20px; padding:18px; margin-top:22px; box-shadow:var(--shadow-sm); }
.composer-head { display:flex; justify-content:space-between; align-items:center; gap:14px; margin-bottom:12px; }
.composer-head h2 { margin:0; font-size:18px; }
.format-tabs, .actions { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.format-tabs { padding:4px; border:1px solid var(--border); border-radius:12px; background:var(--surface-muted); }
.format-tabs button { border:0; background:transparent; padding:7px 11px; color:var(--muted); box-shadow:none; }
.format-tabs button.active { background:var(--surface-solid); color:var(--accent); box-shadow:var(--shadow-sm); }
textarea { width:100%; min-height:310px; margin:0 0 13px; border:1px solid var(--border); border-radius:14px; background:var(--surface-muted); color:var(--text); font:13px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace; padding:14px; resize:vertical; }
.notice { background:var(--success-soft); border:1px solid color-mix(in srgb,var(--success) 25%,var(--border)); color:var(--success); padding:12px 14px; border-radius:12px; }
.feedback { color:var(--muted); font-size:12px; min-height:20px; margin-bottom:0; }
@media(max-width:980px) { .plan-grid { grid-template-columns:1fr; } }
@media(max-width:700px) { .standup-metrics { grid-template-columns:1fr; } .composer-head { align-items:flex-start; flex-direction:column; } }
"""


@dataclass(frozen=True)
class StandupEntry:
    title: str
    detail: str = ""
    url: str | None = None
    key: str = ""


@dataclass
class StandupReport:
    report_date: date
    previous_workday: date
    yesterday: list[StandupEntry] = field(default_factory=list)
    today: list[StandupEntry] = field(default_factory=list)
    waiting: list[StandupEntry] = field(default_factory=list)

    @property
    def short_text(self) -> str:
        return _render_text(self, detailed=False)

    @property
    def detailed_text(self) -> str:
        return _render_text(self, detailed=True)


def previous_workday(value: date) -> date:
    day = value - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def _task_detail(task: TaskItem, detailed: bool = True) -> str:
    parts: list[str] = []
    if task.status:
        parts.append(task.status)
    if task.due_on:
        parts.append(f"due {task.due_on:%a %d %b}")
    if task.project:
        parts.append(task.project)
    if task.source == "github" and task.github_kind:
        labels = {
            "review_request": "review requested",
            "authored_pr": "PR needs action",
            "assigned_issue": "GitHub issue",
            "mention": "GitHub mention",
        }
        parts.append(labels.get(task.github_kind, "GitHub"))
    if task.manual_priority:
        parts.append(f"manual {task.manual_priority}")
    if detailed and task.local_note:
        parts.append(task.local_note)
    return " · ".join(parts)


def _waiting_detail(task: TaskItem) -> str:
    parts: list[str] = []
    if task.waiting_reason:
        parts.append(task.waiting_reason)
    elif task.status:
        parts.append(task.status)
    if task.stale_waiting:
        parts.append("follow-up suggested")
    if task.age_working_days:
        unit = "working day" if task.age_working_days == 1 else "working days"
        parts.append(f"{task.age_working_days} {unit}")
    if task.project:
        parts.append(task.project)
    return " · ".join(parts)


def _event_detail(event: dict[str, Any]) -> str:
    kind = str(event.get("kind") or "")
    labels = {
        "completed": "Completed",
        "review_completed": "Review completed",
        "pr_merged": "PR merged",
        "status_changed": "Status changed",
        "cleared": "No longer active",
        "new": "New item",
    }
    detail = labels.get(kind, kind.replace("_", " ").title())
    old_status = str(event.get("old_status") or "").strip()
    new_status = str(event.get("new_status") or "").strip()
    if kind == "status_changed" and (old_status or new_status):
        detail = f"{old_status or 'No status'} → {new_status or 'No status'}"
    return detail


def _candidate_action_tasks(tasks: list[TaskItem]) -> list[TaskItem]:
    return [
        task
        for task in tasks
        if not task.is_optional
        and (
            (task.source == "asana" and task.action_state == "action")
            or task.source == "github"
        )
    ]


def _action_sort_key(task: TaskItem) -> tuple[int, int, bool, date, int, str]:
    focused = task.focus_rank is not None
    return (
        0 if focused else 1,
        task.focus_rank if task.focus_rank is not None else 9999,
        task.due_on is None,
        task.due_on or date.max,
        PRIORITY_RANK.get(task.priority, 99),
        task.title.casefold(),
    )


def _waiting_sort_key(task: TaskItem) -> tuple[int, int, str]:
    return (0 if task.stale_waiting else 1, -task.age_working_days, task.title.casefold())


def build_standup(
    tasks: list[TaskItem],
    journal: ActivityJournal,
    report_date: date,
    today_limit: int = 5,
    waiting_limit: int = 5,
) -> StandupReport:
    previous = previous_workday(report_date)
    events = journal.events_between(previous, previous)
    yesterday: list[StandupEntry] = []
    relevant_kinds = {"completed", "review_completed", "pr_merged", "status_changed", "cleared"}
    for event in events:
        if str(event.get("kind") or "") not in relevant_kinds:
            continue
        yesterday.append(
            StandupEntry(
                title=str(event.get("title") or "Untitled item"),
                detail=_event_detail(event),
                url=str(event.get("url") or "") or None,
                key=str(event.get("key") or ""),
            )
        )

    today_tasks = sorted(_candidate_action_tasks(tasks), key=_action_sort_key)
    today = [
        StandupEntry(task.title, _task_detail(task), task.url, task.key)
        for task in today_tasks[: max(1, today_limit)]
    ]

    waiting_tasks = sorted(
        [task for task in tasks if task.source == "asana" and not task.is_optional and task.action_state == "waiting"],
        key=_waiting_sort_key,
    )
    waiting = [
        StandupEntry(task.title, _waiting_detail(task), task.url, task.key)
        for task in waiting_tasks[: max(1, waiting_limit)]
    ]
    return StandupReport(report_date, previous, yesterday, today, waiting)


def _render_section(label: str, entries: list[StandupEntry], detailed: bool) -> list[str]:
    lines = [label]
    if not entries:
        lines.append("• None")
        return lines
    for entry in entries:
        line = f"• {entry.title}"
        if detailed and entry.detail:
            line += f" — {entry.detail}"
        if detailed and entry.url:
            line += f" — {entry.url}"
        lines.append(line)
    return lines


def _render_text(report: StandupReport, detailed: bool) -> str:
    sections = [
        _render_section("Yesterday", report.yesterday, detailed),
        _render_section("Today", report.today, detailed),
        _render_section("Blocked / waiting", report.waiting, detailed),
    ]
    return "\n\n".join("\n".join(section) for section in sections)


def save_standup(report: StandupReport, history_dir: str) -> Path:
    directory = Path(history_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"standup-{report.report_date.isoformat()}.md"
    body = (
        f"# Stand-up — {report.report_date:%A, %d %B %Y}\n\n"
        f"{report.detailed_text}\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def render_standup_page(
    report: StandupReport,
    action_token: str,
    dashboard_url: str,
    saved: bool = False,
) -> str:
    base = dashboard_url.rstrip("/")
    token = escape(action_token, quote=True)

    def cards(entries: list[StandupEntry], empty: str) -> str:
        if not entries:
            return f'<p class="empty">{escape(empty)}</p>'
        rows: list[str] = []
        for entry in entries:
            title = escape(entry.title)
            if entry.url:
                title = f'<a href="{escape(entry.url, quote=True)}" target="_blank" rel="noreferrer">{title}</a>'
            detail = f'<p>{escape(entry.detail)}</p>' if entry.detail else ""
            rows.append(f'<article class="standup-card"><strong>{title}</strong>{detail}</article>')
        return "".join(rows)

    saved_notice = '<p class="notice success">Stand-up saved to report history.</p>' if saved else ""
    short_text = escape(report.short_text)
    detailed_text = escape(report.detailed_text)
    sidebar = f'<aside class="app-sidebar">{brand_html()}{navigation_html(base, active_path="/standup")}</aside>'
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stand-up generator</title><style>{STANDUP_CSS}</style></head>
<body><div class="app-shell">{sidebar}<main class="app-main"><div class="app-content">
<header class="page-header"><div class="page-title-wrap"><span class="eyebrow">Daily update</span><h1>Stand-up generator</h1><p class="page-subtitle">Prepared from the previous working day, your current focus and work waiting on others.</p></div></header>{saved_notice}
<div class="standup-metrics"><article class="standup-metric"><strong>{len(report.yesterday)}</strong><span>Yesterday updates</span></article><article class="standup-metric"><strong>{len(report.today)}</strong><span>Today items</span></article><article class="standup-metric"><strong>{len(report.waiting)}</strong><span>Blocked / waiting</span></article></div>
<div class="plan-grid"><section class="plan-column"><h2>Yesterday · {report.previous_workday:%a %d %b}</h2>{cards(report.yesterday, "No recorded completions or changes.")}</section><section class="plan-column"><h2>Today</h2>{cards(report.today, "No actionable tasks selected.")}</section><section class="plan-column"><h2>Blocked / waiting</h2>{cards(report.waiting, "Nothing is currently waiting on others.")}</section></div>
<section class="composer"><div class="composer-head"><h2>Ready to share</h2><div class="format-tabs"><button type="button" class="active" data-format="short">Short</button><button type="button" data-format="detailed">Detailed</button></div></div><textarea id="standup-text" aria-label="Generated stand-up text">{short_text}</textarea><div class="actions"><button class="primary" type="button" id="copy-text">Copy to clipboard</button><button type="button" id="reset-text">Reset text</button><form method="post" action="{base}/action"><input type="hidden" name="token" value="{token}"><input type="hidden" name="action" value="save_standup"><input type="hidden" name="return_to" value="/standup?saved=1"><button type="submit">Save to history</button></form><a class="action-link" href="{base}/history">Open history</a></div><p id="feedback" class="feedback" aria-live="polite"></p></section>
<script>
const variants={{short:{short_text!r},detailed:{detailed_text!r}}};let current='short';const area=document.getElementById('standup-text');const feedback=document.getElementById('feedback');document.querySelectorAll('[data-format]').forEach(button=>button.addEventListener('click',()=>{{current=button.dataset.format;document.querySelectorAll('[data-format]').forEach(item=>item.classList.toggle('active',item===button));area.value=variants[current];feedback.textContent='';}}));document.getElementById('reset-text').addEventListener('click',()=>{{area.value=variants[current];feedback.textContent='Generated text restored.';}});document.getElementById('copy-text').addEventListener('click',async()=>{{try{{await navigator.clipboard.writeText(area.value);feedback.textContent='Copied.';}}catch(error){{area.select();document.execCommand('copy');feedback.textContent='Copied.';}}}});
</script></div></main></div></body></html>'''

