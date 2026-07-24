from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .changes import DigestChanges, RemovedTask, TaskChange
from .models import SourceStatus, TaskEvent, TaskItem
from .plan import PlanCandidate, build_smart_plan
from .priority import PRIORITY_RANK, working_days_between, working_days_until
from .relationships import relationship_tree_html
from .ui import SHARED_CSS, brand_html, navigation_html

PRIORITY_ORDER = PRIORITY_RANK
PRIORITY_LABELS = {
    "urgent": "🔴 Urgent",
    "high": "🟠 High",
    "normal": "🟡 Normal",
    "new": "🟢 New",
}

_ACTION_TOKEN: str | None = None
_DASHBOARD_URL: str | None = None
_ASANA_WRITE_ENABLED = False


DASHBOARD_CSS = SHARED_CSS + r"""
.dashboard-header {
  position: sticky;
  top: 0;
  z-index: 20;
  margin: -12px -10px 22px;
  padding: 12px 10px 16px;
  background: linear-gradient(to bottom, color-mix(in srgb,var(--bg) 96%,transparent) 70%, transparent);
  backdrop-filter: blur(18px) saturate(1.2);
}
.dashboard-header .page-header { margin-bottom: 0; }
.header-status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--muted);
  font-size: 12px;
}
.header-status::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--success); box-shadow: 0 0 0 4px var(--success-soft); }
.sidebar-actions form { display: block; }
.sidebar-actions button { display: flex; align-items: center; justify-content: space-between; }
.dashboard-controls {
  display: grid;
  grid-template-columns: minmax(260px,1fr) auto;
  gap: 13px;
  align-items: center;
  margin: 18px 0;
  padding: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow-sm);
}
.search-wrap { position: relative; }
.search-wrap::before {
  content: "";
  position: absolute;
  left: 13px;
  top: 50%;
  width: 15px;
  height: 15px;
  transform: translateY(-50%);
  border: 1.8px solid var(--muted);
  border-radius: 50%;
  opacity: .75;
  pointer-events: none;
}
.search-wrap::after {
  content: "";
  position: absolute;
  left: 26px;
  top: calc(50% + 5px);
  width: 6px;
  height: 1.8px;
  background: var(--muted);
  transform: rotate(45deg);
  border-radius: 2px;
  opacity: .75;
}
input[type=search] {
  width: 100%;
  min-height: 42px;
  border: 0;
  background: transparent;
  color: var(--text);
  padding: 10px 12px 10px 39px;
  outline: none;
}
.filter-bar { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; }
.filter-bar button { border: 0; background: transparent; padding: 8px 11px; color: var(--muted); font-size: 12px; }
.filter-bar button:hover { background: var(--surface-muted); color: var(--text); box-shadow: none; transform: none; }
.filter-bar button.active { background: var(--accent-soft); color: var(--accent); }
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4,minmax(0,1fr));
  gap: 11px;
  margin: 18px 0 22px;
}
.summary-card {
  position: relative;
  display: grid;
  grid-template-columns: 38px 1fr;
  grid-template-rows: auto auto;
  column-gap: 11px;
  align-items: center;
  min-height: 82px;
  padding: 14px;
  text-align: left;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}
.summary-card::after { content: ""; position: absolute; inset: auto -22px -26px auto; width: 65px; height: 65px; border-radius: 50%; background: color-mix(in srgb,var(--metric-color,var(--accent)) 12%,transparent); }
.summary-card:hover { border-color: color-mix(in srgb,var(--metric-color,var(--accent)) 35%,var(--border)); background: var(--surface-raised); }
.metric-icon { grid-row: 1 / span 2; width: 38px; height: 38px; display: grid; place-items: center; border-radius: 12px; color: var(--metric-color,var(--accent)); background: color-mix(in srgb,var(--metric-color,var(--accent)) 12%,transparent); font-size: 16px; }
.summary-card strong { font-size: 23px; line-height: 1; letter-spacing: -.03em; }
.summary-card span:last-child { align-self: start; margin-top: 4px; color: var(--muted); font-size: 11px; font-weight: 560; }
.summary-card.tone-danger { --metric-color: var(--danger); }
.summary-card.tone-warning { --metric-color: var(--warning); }
.summary-card.tone-success { --metric-color: var(--success); }
.summary-card.tone-info { --metric-color: var(--info); }
.summary-card.tone-accent { --metric-color: var(--accent); }
.dashboard-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(340px, .9fr);
  gap: 20px;
  align-items: start;
  margin-top: 20px;
}
.dashboard-primary, .dashboard-secondary { min-width: 0; }
.dashboard-secondary {
  position: sticky;
  top: 104px;
  display: grid;
  gap: 12px;
}
.dashboard-column-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin: 0 2px 10px;
}
.dashboard-column-heading h2 { margin: 0; font-size: 17px; }
.dashboard-column-heading span { color: var(--muted); font-size: 11px; }
.dashboard-primary > :first-child, .dashboard-secondary > :first-child { margin-top: 0; }
.dashboard-secondary .meta-panel,
.dashboard-secondary .work-section,
.dashboard-secondary .optional-section { margin: 0; }
.dashboard-secondary .section-content,
.dashboard-secondary .optional-content { padding-inline: 9px; }
.meta-panel, .work-section, .optional-section {
  margin: 14px 0;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--surface);
  box-shadow: var(--shadow-sm);
}
.meta-panel > summary, .work-section > summary, .optional-section > summary {
  position: relative;
  cursor: pointer;
  list-style: none;
  padding: 17px 18px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 10px;
}
.meta-panel > summary::-webkit-details-marker, .work-section > summary::-webkit-details-marker, .optional-section > summary::-webkit-details-marker { display: none; }
.meta-panel > summary::after, .work-section > summary::after, .optional-section > summary::after {
  content: "›";
  order: 3;
  margin-left: 2px;
  color: var(--faint);
  font-size: 21px;
  line-height: 1;
  transition: transform .16s ease;
}
details[open] > summary::after { transform: rotate(90deg); }
.work-section > summary span, .optional-section > summary span { order: 2; margin-left: auto; color: var(--muted); font-size: 11px; font-weight: 650; background: var(--surface-muted); border: 1px solid var(--border); border-radius: 999px; padding: 4px 8px; }
.section-content, .optional-content { padding: 0 12px 12px; }
.source-health { display: grid; grid-template-columns: repeat(auto-fit,minmax(210px,1fr)); gap: 10px; padding: 0 14px 14px; }
.source-card { background: var(--surface-muted); border: 1px solid var(--border); border-radius: 13px; padding: 13px; display: flex; flex-direction: column; box-shadow: inset 3px 0 0 var(--success); }
.source-card.warning { box-shadow: inset 3px 0 0 var(--warning); }
.source-card span { font-size: 12px; color: var(--muted); margin-top: 4px; line-height: 1.4; }
.summary-tabs { padding: 0 14px 14px; display: grid; gap: 9px; }
.summary-tabs details { background: var(--surface-muted); border: 1px solid var(--border); border-radius: 13px; padding: 11px 13px; }
.summary-tabs summary { cursor: pointer; font-weight: 650; }
.mini-grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(92px,1fr)); gap: 8px; margin-top: 10px; }
.mini-grid div { display: flex; flex-direction: column; background: var(--surface-solid); border: 1px solid var(--border); padding: 10px; border-radius: 10px; }
.mini-grid strong { font-size: 18px; }
.mini-grid span { font-size: 10px; color: var(--muted); margin-top: 2px; }
.focus-section { margin: 24px 0; }
.plan-section { position: relative; overflow: hidden; background: linear-gradient(135deg, color-mix(in srgb,var(--accent) 8%,var(--surface)) 0%, var(--surface) 45%, color-mix(in srgb,var(--accent-2) 7%,var(--surface)) 100%); border: 1px solid color-mix(in srgb,var(--accent) 18%,var(--border)); border-radius: 22px; padding: 20px; box-shadow: var(--shadow-md); }
.plan-section::after { content: ""; position: absolute; right: -80px; top: -100px; width: 230px; height: 230px; border-radius: 50%; background: color-mix(in srgb,var(--accent) 8%,transparent); pointer-events: none; }
.section-head { position: relative; z-index: 1; display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 12px; }
.section-head h2 { margin: 0; font-size: 21px; }
.section-head span { color: var(--muted); font-size: 12px; }
.plan-subtitle { margin: 5px 0 0; color: var(--muted); font-size: 13px; line-height: 1.45; }
.plan-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
.plan-actions form { display: inline-flex; }
.plan-current-head { margin-top: 16px; }
.plan-current-head h3 { margin: 0; }
#focus-list { display: grid; gap: 9px; }
.smart-suggestions { position: relative; z-index: 1; margin-top: 15px; border-top: 1px solid color-mix(in srgb,var(--accent) 16%,var(--border)); padding-top: 13px; }
.smart-suggestions > summary { cursor: pointer; font-weight: 680; display: flex; justify-content: space-between; gap: 12px; }
.smart-suggestions > summary span { color: var(--muted); font-size: 11px; }
.plan-help { color: var(--muted); font-size: 12px; margin: 9px 0; }
.plan-suggestion-list { display: grid; gap: 10px; }
.plan-candidate { background: color-mix(in srgb,var(--surface-solid) 88%,transparent); border: 1px solid var(--border); border-radius: 15px; padding: 8px; }
.plan-candidate .task { box-shadow: none; border: 0; padding: 9px; margin: 0; cursor: default; background: transparent; }
.plan-reasons { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; padding: 4px 9px 8px; }
.plan-reasons span, .plan-reasons strong { font-size: 10px; background: var(--surface-muted); border: 1px solid var(--border); border-radius: 999px; padding: 5px 8px; }
.plan-reasons strong { margin-left: auto; color: var(--muted); font-weight: 540; }
.plan-reasons form { margin-left: 4px; }
.task {
  --priority-color: var(--border-strong);
  position: relative;
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 16px 17px 16px 20px;
  margin: 9px 0;
  box-shadow: var(--shadow-sm);
  transition: transform .16s ease, border-color .16s ease, box-shadow .16s ease;
}
.task::before { content: ""; position: absolute; left: 0; top: 16px; bottom: 16px; width: 4px; border-radius: 0 4px 4px 0; background: var(--priority-color); }
.task:hover { transform: translateY(-1px); border-color: color-mix(in srgb,var(--priority-color) 30%,var(--border)); box-shadow: var(--shadow-md); }
.task.compact { cursor: grab; margin: 0; }
.task.compact.dragging { opacity: .45; }
.task.focused { border-color: color-mix(in srgb,var(--accent) 45%,var(--border)); box-shadow: 0 0 0 3px color-mix(in srgb,var(--accent) 8%,transparent), var(--shadow-sm); }
.priority-urgent { --priority-color: var(--danger); }
.priority-high { --priority-color: #d97706; }
.priority-normal { --priority-color: #ca8a04; }
.priority-new { --priority-color: var(--success); }
.task-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.task h3 { margin: 0 0 7px; font-size: 16px; line-height: 1.35; letter-spacing: -.012em; }
.task h3 a { color: var(--text); }
.task h3 a:hover { color: var(--accent); }
.task > p { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.5; }
.badge { flex: 0 0 auto; background: var(--surface-muted); border: 1px solid var(--border); border-radius: 999px; padding: 5px 8px; color: var(--muted); font-size: 10px; font-weight: 650; white-space: nowrap; }
.local-note { margin-top: 11px!important; color: var(--text)!important; background: var(--accent-soft); border: 1px solid color-mix(in srgb,var(--accent) 18%,var(--border)); padding: 10px 11px; border-radius: 11px; }
.github { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 11px; }
.github-link { display: inline-flex; align-items: center; gap: 6px; background: var(--info-soft); border: 1px solid color-mix(in srgb,var(--info) 20%,var(--border)); color: var(--info); border-radius: 999px; padding: 6px 9px; font-size: 11px; font-weight: 680; }
.github-link::before { content: "↗"; font-size: 10px; }
.pr-alert, .pr-status { margin-top: 10px; padding: 10px 11px; border-radius: 11px; display: flex; flex-direction: column; gap: 3px; font-size: 12px; }
.pr-alert { background: var(--warning-soft); color: var(--warning); border: 1px solid color-mix(in srgb,var(--warning) 25%,var(--border)); }
.pr-status { background: var(--info-soft); color: var(--info); border: 1px solid color-mix(in srgb,var(--info) 18%,var(--border)); }
.timeline, .context-details, .comments, .task-controls, .asana-actions { margin-top: 11px; border-top: 1px solid var(--border); padding-top: 10px; }
.timeline summary, .context-details summary, .comments summary, .task-controls summary, .asana-actions > summary { cursor: pointer; color: var(--muted); font-size: 12px; font-weight: 620; }
.timeline summary { display: flex; justify-content: space-between; gap: 10px; }
.timeline summary span { font-size: 10px; background: var(--surface-muted); border: 1px solid var(--border); border-radius: 999px; padding: 2px 7px; }
.timeline ol { list-style: none; margin: 13px 0 2px; padding: 0 0 0 8px; }
.timeline-item { position: relative; display: grid; grid-template-columns: 30px 1fr; gap: 10px; padding: 0 0 15px; }
.timeline-item:not(:last-child)::after { content: ""; position: absolute; left: 14px; top: 29px; bottom: 1px; width: 1px; background: var(--border); }
.timeline-icon { width: 30px; height: 30px; border: 1px solid var(--border); border-radius: 50%; display: grid; place-items: center; background: var(--surface-muted); font-size: 12px; z-index: 1; }
.timeline-body { min-width: 0; padding-top: 2px; }
.timeline-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.timeline-head strong { font-size: 12px; }
.timeline-meta { font-size: 10px; color: var(--muted); margin-top: 2px; }
.timeline-body p { color: var(--text); font-size: 11px; margin-top: 5px; white-space: pre-wrap; }
.timeline-current { font-size: 9px; color: var(--accent); background: var(--accent-soft); border-radius: 999px; padding: 2px 6px; }
.timeline-more { font-size: 10px!important; color: var(--muted)!important; margin: 0 0 6px 48px!important; }
.asana-actions > summary { display: flex; justify-content: space-between; gap: 10px; }
.asana-actions > summary span { font-size: 10px; }
.context-grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); gap: 10px; margin-top: 9px; }
.context-grid ul, .comments ul { margin: 6px 0; padding-left: 20px; }
.relation-state { font-size: 9px; text-transform: uppercase; letter-spacing: .06em; margin-right: 7px; color: var(--muted); }
.comments ul { list-style: none; padding: 0; }
.comments li { display: flex; gap: 9px; padding: 9px 0; border-bottom: 1px solid var(--border); }
.comments time { font-size: 10px; color: var(--muted); margin-left: 8px; }
.comments p { margin-top: 3px!important; color: var(--text)!important; }
.unread-dot { width: 8px; height: 8px; background: var(--accent); border-radius: 50%; margin-top: 6px; flex: 0 0 auto; box-shadow: 0 0 0 4px var(--accent-soft); }
.control-grid, .asana-action-grid { display: grid; gap: 10px; margin-top: 10px; }
.inline-editor, .note-editor, .action-editor, .comment-editor { display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: end; }
.clear-date-form { justify-self: start; }
label { display: grid; gap: 6px; font-size: 11px; color: var(--muted); }
select, textarea, input[type=date] { width: 100%; border: 1px solid var(--border); background: var(--surface-solid); color: var(--text); padding: 9px 10px; border-radius: 10px; }
.action-link { display: inline-flex; align-items: center; }
#toast { position: fixed; right: 22px; bottom: 22px; z-index: 50; background: var(--text); color: var(--bg); padding: 12px 15px; border-radius: 12px; max-width: min(420px,calc(100vw - 44px)); display: none; box-shadow: var(--shadow-md); }
#toast.show { display: block; }
.notice, .empty, .change-summary { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 15px; color: var(--muted); }
.notice { border-left: 4px solid var(--warning); background: var(--warning-soft); color: var(--warning); }
.changes { margin: 23px 0; }
.removed { opacity: .72; }
.hidden-by-filter { display: none!important; }
footer { margin-top: 28px; padding: 18px 0; color: var(--muted); font-size: 11px; line-height: 1.55; border-top: 1px solid var(--border); }
@media (max-width: 1240px) {
  .dashboard-workspace { grid-template-columns: 1fr; }
  .dashboard-secondary { position: static; grid-template-columns: repeat(2,minmax(0,1fr)); }
  .dashboard-secondary .dashboard-column-heading { grid-column: 1 / -1; }
}
@media (max-width: 1120px) { .summary-grid { grid-template-columns: repeat(2,minmax(0,1fr)); } }
@media (max-width: 700px) {
  .dashboard-header { position: static; margin: 0 0 18px; padding: 0; background: none; backdrop-filter: none; }
  .dashboard-controls { grid-template-columns: 1fr; }
  .filter-bar { overflow-x: auto; flex-wrap: nowrap; }
  .section-head { align-items: flex-start; flex-direction: column; }
  .plan-actions { justify-content: flex-start; }
  .task-head { display: block; }
  .badge { display: inline-block; margin-top: 6px; }
  .dashboard-secondary { grid-template-columns: 1fr; }
  .dashboard-secondary .dashboard-column-heading { grid-column: auto; }
  .inline-editor, .note-editor, .action-editor, .comment-editor { grid-template-columns: 1fr; }
}
@media (max-width: 440px) { .summary-grid { grid-template-columns: 1fr; } }
"""


def _visible_github_links(item: TaskItem):
    return [link for link in item.github_links if not link.is_draft]


def sort_tasks(tasks: List[TaskItem]) -> List[TaskItem]:
    return sorted(
        tasks,
        key=lambda item: (
            PRIORITY_ORDER[item.priority],
            item.due_on is None,
            item.due_on or datetime.max.date(),
            item.title.lower(),
        ),
    )


def github_reviews(tasks: List[TaskItem]) -> List[TaskItem]:
    return [item for item in tasks if item.source == "github" and item.github_kind in {None, "review_request"}]


def github_authored_prs(tasks: List[TaskItem]) -> List[TaskItem]:
    return [item for item in tasks if item.source == "github" and item.github_kind == "authored_pr"]


def github_assigned_issues(tasks: List[TaskItem]) -> List[TaskItem]:
    return [item for item in tasks if item.source == "github" and item.github_kind == "assigned_issue"]


def github_mentions(tasks: List[TaskItem]) -> List[TaskItem]:
    return [item for item in tasks if item.source == "github" and item.github_kind == "mention"]


def split_tasks(tasks: List[TaskItem]) -> Tuple[List[TaskItem], List[TaskItem], List[TaskItem]]:
    asana_tasks = [item for item in tasks if item.source == "asana"]
    action = [item for item in asana_tasks if not item.is_optional and item.action_state == "action"]
    waiting = [item for item in asana_tasks if not item.is_optional and item.action_state == "waiting"]
    optional = [item for item in asana_tasks if item.is_optional]
    return action, waiting, optional


def _working_day_phrase(days: int) -> str:
    unit = "working day" if days == 1 else "working days"
    return f"{days} {unit}"


def _age_description(item: TaskItem) -> str:
    if item.source == "github":
        if item.github_kind == "authored_pr":
            return "Needs action since today" if item.age_working_days == 0 else f"Needs action for {_working_day_phrase(item.age_working_days)}"
        if item.github_kind == "assigned_issue":
            return "Assigned on GitHub today" if item.age_working_days == 0 else f"Assigned on GitHub {_working_day_phrase(item.age_working_days)} ago"
        if item.github_kind == "mention":
            return "Mentioned today" if item.age_working_days == 0 else f"Mentioned {_working_day_phrase(item.age_working_days)} ago"
        return "Review requested today" if item.age_working_days == 0 else f"Review requested {_working_day_phrase(item.age_working_days)} ago"
    if item.age_basis == "status" and item.status:
        return f"{item.status} since today" if item.age_working_days == 0 else f"{item.status} for {_working_day_phrase(item.age_working_days)}"
    return "Assigned to task today" if item.age_working_days == 0 else f"Assigned to task {_working_day_phrase(item.age_working_days)} ago"


def _due_description(item: TaskItem, today: date) -> str | None:
    if not item.due_on:
        return None
    if item.due_on < today:
        overdue = working_days_between(item.due_on, today)
        return "Overdue" if overdue == 0 else f"Overdue by {_working_day_phrase(overdue)}"
    if item.due_on == today:
        return "Due today"
    if item.due_on == today + timedelta(days=1):
        return "Due tomorrow"
    remaining = working_days_until(today, item.due_on)
    date_label = item.due_on.strftime("%a, %d %b")
    return f"Due {date_label}" if remaining == 0 else f"Due {date_label} · in {_working_day_phrase(remaining)}"


def _details(item: TaskItem, today: date) -> List[str]:
    details: List[str] = [_age_description(item)]
    if item.status and item.github_kind == "authored_pr":
        details.append(f"Blockers: {item.status}")
    elif item.status and item.age_basis != "status":
        details.append(f"Current status: {item.status}")
    due = _due_description(item, today)
    if due:
        details.append(due)
    if item.waiting_reason:
        details.append(item.waiting_reason)
    if item.project:
        details.append(item.project)
    visible_links = _visible_github_links(item)
    if visible_links:
        details.append(f"{len(visible_links)} linked GitHub item(s)")
    if item.unread_updates:
        details.append(f"{item.unread_updates} new update(s)")
    if item.manual_priority:
        details.append(f"Manual priority: {item.manual_priority.title()}")
    details.extend(item.notes)
    return details


def _due_now_count(tasks: list[TaskItem], today: date) -> int:
    return sum(1 for item in tasks if item.due_on and item.due_on <= today)


def _due_soon_count(tasks: list[TaskItem], today: date) -> int:
    return sum(
        1
        for item in tasks
        if item.due_on and item.due_on > today and working_days_until(today, item.due_on) <= 1
    )


def _github_link_label(link: Any) -> str:
    kind = "PR" if link.kind == "pull" else "Issue"
    base = f"{kind} #{link.number} · {link.owner}/{link.repo}"
    title = str(link.title or "").strip()
    if title and "github.com/" not in title.lower():
        title = title[:90] + ("…" if len(title) > 90 else "")
        return f"{base} — {title}"
    return base


def _render_task_text(item: TaskItem, today: date) -> list[str]:
    link_text = f" — {item.url}" if item.url else ""
    lines = [f"• {item.title} ({' · '.join(_details(item, today))}){link_text}"]
    for link in _visible_github_links(item):
        suffix = ""
        if link.action_reasons:
            suffix = " · ACTION: " + " · ".join(link.action_reasons)
        elif link.pending_reviewers:
            suffix = " · waiting for " + ", ".join(link.pending_reviewers)
        lines.append(f"  ↳ Linked GitHub {_github_link_label(link)}{suffix} — {link.url}")
    for dependency in item.dependencies:
        state = "done" if dependency.completed else "blocking"
        lines.append(f"  ↳ Dependency ({state}): {dependency.title}")
    return lines


def _source_status_text(source_statuses: list[SourceStatus] | None) -> list[str]:
    if not source_statuses:
        return []
    lines = ["\nSource health"]
    for status in source_statuses:
        icon = "✅" if status.ok else "⚠️"
        lines.append(f"{icon} {status.name}: {status.detail}")
    return lines


def _render_full_text(
    tasks: List[TaskItem],
    now: datetime,
    period: str,
    github_warning: str | None = None,
    source_statuses: list[SourceStatus] | None = None,
    hidden_summary: tuple[int, int] | None = None,
) -> str:
    heading = f"Your task digest — {period.title()} — {now:%A, %d %B}"
    action, waiting, optional = split_tasks(tasks)
    reviews, authored = github_reviews(tasks), github_authored_prs(tasks)
    issues, mentions = github_assigned_issues(tasks), github_mentions(tasks)
    focus = [task for task in tasks if task.is_focused]
    lines = [
        heading,
        f"\nSummary: {len(focus)} focus · {len(action)} need action · {len(reviews)} review(s) · "
        f"{len(authored)} blocked PR(s) · {len(waiting)} waiting · "
        f"{sum(task.unread_updates for task in tasks)} new update(s)",
    ]
    if focus:
        lines.append("\n🎯 Today's focus")
        for item in sorted(focus, key=lambda task: task.focus_rank or 0):
            lines.extend(_render_task_text(item, now.date()))
    lines.append("\n✅ Needs action")
    if action:
        for item in sort_tasks(action):
            lines.extend(_render_task_text(item, now.date()))
    else:
        lines.append("No tasks currently require your action.")
    for title, items, empty in [
        ("\n🛠️ Your PRs needing action", authored, "None of your open PRs currently have requested changes, failing checks, or merge conflicts."),
        ("\n👀 GitHub reviews required", reviews, "No reviews currently requested from you."),
        ("\n📌 GitHub issues assigned to you", issues, "No open GitHub issues are currently assigned to you."),
        ("\n💬 GitHub mentions", mentions, "No open GitHub issues or PRs currently mention you."),
    ]:
        lines.append(title)
        if github_warning:
            lines.append(f"GitHub data unavailable: {github_warning}")
        elif items:
            for item in sort_tasks(items):
                lines.extend(_render_task_text(item, now.date()))
        else:
            lines.append(empty)
    if waiting:
        lines.append("\n🕒 Waiting on others")
        for item in sort_tasks(waiting):
            lines.extend(_render_task_text(item, now.date()))
    if optional:
        lines.append(f"\n🔎 Optional investigations ({len(optional)})")
        for item in sort_tasks(optional):
            lines.extend(_render_task_text(item, now.date()))
    if hidden_summary:
        lines.append(f"\nHidden locally: {hidden_summary[0]} snoozed · {hidden_summary[1]} ignored")
    lines.extend(_source_status_text(source_statuses))
    return "\n".join(lines)


def _change_text(change: TaskChange, today: date, kind: str) -> list[str]:
    old = change.old
    if kind == "status":
        before = old.get("status") or "No status"
        after = change.task.status or "No status"
        note = "GitHub/waiting state changed" if before == after else f"{before} → {after}"
    elif kind == "priority":
        note = f"{str(old.get('priority') or 'new').title()} → {change.task.priority.title()}"
    else:
        before = old.get("due_on") or "No due date"
        after = change.task.due_on.isoformat() if change.task.due_on else "No due date"
        note = f"{before} → {after}"
    line = f"• {change.task.title}: {note}"
    if change.task.url:
        line += f" — {change.task.url}"
    return [line]


def _removed_text(item: RemovedTask) -> str:
    link = f" — {item.url}" if item.url else ""
    if item.source == "github":
        labels = {
            "authored_pr": "GitHub PR no longer needs action",
            "review_request": "GitHub review no longer required",
            "assigned_issue": "GitHub issue no longer assigned or open",
            "mention": "GitHub mention no longer open",
        }
        return f"• {labels.get(item.github_kind, 'GitHub item removed')}: {item.title}{link}"
    status = f" · last status: {item.status}" if item.status else ""
    return f"• {item.title}{status}{link}"


def _render_evening_text(
    tasks: List[TaskItem],
    now: datetime,
    changes: DigestChanges,
    github_warning: str | None = None,
    source_statuses: list[SourceStatus] | None = None,
    hidden_summary: tuple[int, int] | None = None,
) -> str:
    lines = [f"Your task digest — Evening changes — {now:%A, %d %B}", f"\nSummary: {changes.change_count} change(s)"]
    if changes.change_count == 0:
        lines.append("\nNo task changes since the previous digest.")
    if changes.new:
        lines.append("\n🆕 New")
        for item in sort_tasks(changes.new):
            lines.extend(_render_task_text(item, now.date()))
    if changes.status_changed:
        lines.append("\n🔄 Status changed")
        for change in changes.status_changed:
            lines.extend(_change_text(change, now.date(), "status"))
    if changes.due_changed:
        lines.append("\n📅 Due date changed")
        for change in changes.due_changed:
            lines.extend(_change_text(change, now.date(), "due"))
    if changes.removed:
        lines.append("\n✅ Completed or removed")
        lines.extend(_removed_text(item) for item in changes.removed)
    lines.append(_render_full_text(tasks, now, "evening", github_warning, source_statuses, hidden_summary))
    return "\n".join(lines)


def render_text(
    tasks: List[TaskItem],
    now: datetime,
    period: str,
    changes: DigestChanges | None = None,
    github_warning: str | None = None,
    source_statuses: list[SourceStatus] | None = None,
    hidden_summary: tuple[int, int] | None = None,
) -> str:
    if period == "evening" and changes and changes.baseline_available:
        return _render_evening_text(tasks, now, changes, github_warning, source_statuses, hidden_summary)
    return _render_full_text(tasks, now, period, github_warning, source_statuses, hidden_summary)


def _hidden_input(name: str, value: str) -> str:
    return f'<input type="hidden" name="{escape(name, quote=True)}" value="{escape(value, quote=True)}">'


def _post_form(action: str, key: str, label: str, css: str = "") -> str:
    if not _ACTION_TOKEN or not _DASHBOARD_URL:
        return ""
    return (
        f'<form method="post" action="{escape(_DASHBOARD_URL + "/action", quote=True)}">'
        + _hidden_input("token", _ACTION_TOKEN)
        + _hidden_input("key", key)
        + _hidden_input("action", action)
        + f'<button class="{escape(css, quote=True)}" type="submit">{escape(label)}</button></form>'
    )


def _asana_write_form(action: str, item: TaskItem, label: str, *, css: str = "", confirm: str = "") -> str:
    if not _ACTION_TOKEN or not _DASHBOARD_URL:
        return ""
    confirm_attr = f' data-confirm="{escape(confirm, quote=True)}"' if confirm else ""
    return (
        f'<form method="post" action="{escape(_DASHBOARD_URL + "/action", quote=True)}" class="asana-write-form"{confirm_attr}>'
        + _hidden_input("token", _ACTION_TOKEN)
        + _hidden_input("key", item.key)
        + _hidden_input("action", action)
        + f'<button class="{escape(css, quote=True)}" type="submit">{escape(label)}</button></form>'
    )


def _asana_write_controls(item: TaskItem) -> str:
    if not _ASANA_WRITE_ENABLED or item.source != "asana" or not _ACTION_TOKEN or not _DASHBOARD_URL:
        return ""
    action_url = escape(_DASHBOARD_URL + "/action", quote=True)
    token = escape(_ACTION_TOKEN, quote=True)
    key = escape(item.key, quote=True)
    due_value = item.due_on.isoformat() if item.due_on else ""

    section_groups: dict[str, list[str]] = {}
    for option in item.asana_sections:
        group = "My Tasks" if option.scope == "my_tasks" else (option.project_name or "Project")
        value = escape(f"{option.scope}:{option.gid}", quote=True)
        section_groups.setdefault(group, []).append(
            f'<option value="{value}">{escape(option.name)}</option>'
        )
    section_select = ""
    if section_groups:
        options = ['<option value="">Choose section…</option>']
        for group, rows in section_groups.items():
            options.append(f'<optgroup label="{escape(group, quote=True)}">{"".join(rows)}</optgroup>')
        section_select = f'''
<form method="post" action="{action_url}" class="asana-write-form action-editor" data-confirm="Move this task to the selected Asana section?">
  <input type="hidden" name="token" value="{token}"><input type="hidden" name="key" value="{key}"><input type="hidden" name="action" value="asana_move_section">
  <label>Move to section<select name="section" required>{''.join(options)}</select></label><button type="submit">Move</button>
</form>'''

    status_select = ""
    if item.status_source and item.status_source.kind == "custom_field" and item.status_source.gid and item.asana_status_options:
        options = ['<option value="">Choose status…</option>'] + [
            f'<option value="{escape(option.gid, quote=True)}"{(" selected" if item.status == option.name else "")}>{escape(option.name)}</option>'
            for option in item.asana_status_options
        ]
        status_select = f'''
<form method="post" action="{action_url}" class="asana-write-form action-editor" data-confirm="Change this task’s Asana status?">
  <input type="hidden" name="token" value="{token}"><input type="hidden" name="key" value="{key}"><input type="hidden" name="action" value="asana_set_status">
  <input type="hidden" name="field_gid" value="{escape(item.status_source.gid, quote=True)}">
  <label>Set status<select name="option_gid" required>{''.join(options)}</select></label><button type="submit">Update</button>
</form>'''

    github_button = ""
    visible_links = _visible_github_links(item)
    if visible_links:
        github_button = f'<a class="action-link" href="{escape(visible_links[0].url, quote=True)}">Open linked GitHub</a>'
    task_button = f'<a class="action-link" href="{escape(item.url, quote=True)}">Open in Asana</a>' if item.url else ""

    return f'''
<details class="asana-actions">
  <summary>Update in Asana <span>Changes sync immediately</span></summary>
  <div class="asana-action-grid">
    <div class="button-row">
      {task_button}{github_button}
      {_asana_write_form("asana_complete", item, "Mark complete", css="primary", confirm="Mark this Asana task complete? It will disappear from the active digest.")}
      {_asana_write_form("asana_unassign", item, "Unassign me", css="danger", confirm="Unassign yourself from this Asana task? It will disappear from your digest.")}
    </div>
    <form method="post" action="{action_url}" class="asana-write-form action-editor">
      <input type="hidden" name="token" value="{token}"><input type="hidden" name="key" value="{key}"><input type="hidden" name="action" value="asana_due_date">
      <label>Due date<input type="date" name="due_on" value="{escape(due_value, quote=True)}"></label><button type="submit">Save date</button>
    </form>
    <form method="post" action="{action_url}" class="asana-write-form clear-date-form" data-confirm="Clear this task’s Asana due date?">
      <input type="hidden" name="token" value="{token}"><input type="hidden" name="key" value="{key}"><input type="hidden" name="action" value="asana_due_date"><input type="hidden" name="due_on" value="">
      <button type="submit">Clear due date</button>
    </form>
    {status_select}{section_select}
    <form method="post" action="{action_url}" class="asana-write-form comment-editor">
      <input type="hidden" name="token" value="{token}"><input type="hidden" name="key" value="{key}"><input type="hidden" name="action" value="asana_comment">
      <label>Add Asana comment<textarea name="comment" rows="2" maxlength="5000" required placeholder="Write a comment as yourself…"></textarea></label><button type="submit">Post comment</button>
    </form>
  </div>
</details>'''


def _task_controls(item: TaskItem) -> str:
    if not _ACTION_TOKEN or not _DASHBOARD_URL:
        return ""
    action_url = escape(_DASHBOARD_URL + "/action", quote=True)
    token = escape(_ACTION_TOKEN, quote=True)
    key = escape(item.key, quote=True)
    focus_label = "Remove from focus" if item.is_focused else "Add to focus"
    selected = item.manual_priority or ""
    options = ['<option value="">Automatic priority</option>'] + [
        f'<option value="{value}"{(" selected" if selected == value else "")}>{label}</option>'
        for value, label in (("urgent", "Urgent"), ("high", "High"), ("normal", "Normal"), ("new", "New"))
    ]
    note = escape(item.local_note)
    mark_read = _post_form("mark_read", item.key, f"Mark {item.unread_updates} update(s) read") if item.unread_updates else ""
    return f'''
<details class="task-controls">
  <summary>Actions & notes</summary>
  <div class="control-grid">
    <div class="button-row">
      {_post_form("toggle_focus", item.key, focus_label, "primary")}
      {_post_form("snooze_1", item.key, "Tomorrow")}
      {_post_form("snooze_3", item.key, "3 workdays")}
      {_post_form("until_change", item.key, "Until change")}
      {_post_form("ignore", item.key, "Ignore", "danger")}
      {mark_read}
    </div>
    <form method="post" action="{action_url}" class="inline-editor">
      <input type="hidden" name="token" value="{token}">
      <input type="hidden" name="key" value="{key}">
      <input type="hidden" name="action" value="set_priority">
      <label>Priority override<select name="priority">{''.join(options)}</select></label>
      <button type="submit">Save priority</button>
    </form>
    <form method="post" action="{action_url}" class="note-editor">
      <input type="hidden" name="token" value="{token}">
      <input type="hidden" name="key" value="{key}">
      <input type="hidden" name="action" value="save_note">
      <label>Private local note<textarea name="note" rows="2" placeholder="Add context only you can see…">{note}</textarea></label>
      <button type="submit">Save note</button>
    </form>
  </div>
</details>'''


def _relations_html(item: TaskItem) -> str:
    return relationship_tree_html(item)

def _comments_html(item: TaskItem) -> str:
    if not item.recent_comments:
        return ""
    rows = []
    for comment in item.recent_comments:
        unread = '<span class="unread-dot" title="New since last marked read"></span>' if comment.unread else ""
        text = escape(comment.text[:500] + ("…" if len(comment.text) > 500 else ""))
        rows.append(
            f'<li>{unread}<div><strong>{escape(comment.author)}</strong>'
            f'<time>{comment.created_at.astimezone():%d %b, %H:%M}</time><p>{text}</p></div></li>'
        )
    badge = f' <span>{item.unread_updates} new</span>' if item.unread_updates else ""
    return f'<details class="comments"><summary>Recent comments{badge}</summary><ul>{"".join(rows)}</ul></details>'



def _timeline_events(item: TaskItem) -> list[TaskEvent]:
    events = list(item.timeline_events)
    kinds = {event.kind for event in events}
    if item.assigned_at and "assignment" not in kinds:
        if item.source == "github":
            if item.github_kind == "review_request":
                title = "Review requested from you"
            elif item.github_kind == "assigned_issue":
                title = "Issue assigned to you"
            elif item.github_kind == "mention":
                title = "You were mentioned"
            else:
                title = "GitHub action became required"
            source = "github"
        else:
            title = "Assigned to you"
            source = "asana"
        events.append(TaskEvent(f"synthetic:assigned:{item.key}", source, "assignment", title, item.assigned_at))
    if item.status_changed_at and item.status and "status" not in kinds:
        events.append(TaskEvent(f"synthetic:status:{item.key}", "asana", "status", f"Moved to {item.status}", item.status_changed_at))

    unique: dict[str, TaskEvent] = {}
    for event in events:
        unique[event.id] = event

    def sort_key(event: TaskEvent) -> tuple[int, float, str]:
        if event.created_at is None:
            return (1, 0.0, event.title.casefold())
        try:
            stamp = event.created_at.timestamp()
        except (OSError, ValueError):
            stamp = 0.0
        return (0, -stamp, event.title.casefold())

    return sorted(unique.values(), key=sort_key)


def _timeline_html(item: TaskItem) -> str:
    events = _timeline_events(item)
    if not events:
        return ""
    visible = events[:14]
    icons = {
        "assignment": "👤",
        "status": "↻",
        "comment": "💬",
        "dependency": "⛓",
        "github": "◖",
        "due_date": "◷",
        "local": "⌂",
        "system": "•",
    }
    rows: list[str] = []
    for event in visible:
        icon = icons.get(event.kind, "•")
        title = escape(event.title)
        if event.url:
            title = f'<a href="{escape(event.url, quote=True)}">{title}</a>'
        if event.created_at:
            when = event.created_at.astimezone().strftime("%a %d %b · %H:%M") if event.created_at.tzinfo else event.created_at.strftime("%a %d %b · %H:%M")
        else:
            when = "Current"
        meta = [event.source.title(), when]
        if event.actor:
            meta.append(event.actor)
        current = '<span class="timeline-current">Current</span>' if event.current else ""
        detail = f'<p>{escape(event.detail)}</p>' if event.detail else ""
        rows.append(
            '<li class="timeline-item">'
            f'<span class="timeline-icon" aria-hidden="true">{icon}</span>'
            '<div class="timeline-body">'
            f'<div class="timeline-head"><strong>{title}</strong>{current}</div>'
            f'<div class="timeline-meta">{escape(" · ".join(meta))}</div>{detail}</div></li>'
        )
    more = f'<p class="timeline-more">Showing the newest 14 of {len(events)} events.</p>' if len(events) > 14 else ""
    return (
        f'<details class="timeline"><summary>Activity timeline <span>{len(events)}</span></summary>'
        f'<ol>{"".join(rows)}</ol>{more}</details>'
    )


def _task_card(item: TaskItem, today: date, badge: str | None = None, compact: bool = False) -> str:
    title = escape(item.title)
    if item.url:
        title = f'<a href="{escape(item.url, quote=True)}">{title}</a>'
    detail = escape(" · ".join(_details(item, today)))
    github_links = []
    alerts = []
    for link in _visible_github_links(item):
        github_links.append(
            f'<a class="github-link" href="{escape(link.url, quote=True)}">{escape(_github_link_label(link))}</a>'
        )
        if link.action_reasons:
            alerts.append(
                '<div class="pr-alert"><strong>⚠ GitHub action required</strong>'
                f'<span>{escape(" · ".join(link.action_reasons))}</span></div>'
            )
        elif link.pending_reviewers or link.checks_pending or link.approvals:
            status: list[str] = []
            if link.pending_reviewers:
                status.append("Reviewers: " + ", ".join("@" + name for name in link.pending_reviewers))
            if link.checks_pending:
                status.append("CI running")
            if link.approvals:
                status.append(f"{link.approvals} approval(s)")
            alerts.append(f'<div class="pr-status"><span>{escape(" · ".join(status))}</span></div>')
    badge_value = badge or ("Follow-up suggested" if item.stale_waiting else None)
    if item.unread_updates:
        badge_value = f"{item.unread_updates} new update(s)" if not badge_value else badge_value
    if item.rule_matches and not badge_value:
        badge_value = f"Rule: {item.rule_matches[-1]}"
    badge_html = f'<span class="badge">{escape(badge_value)}</span>' if badge_value else ""
    note_html = f'<p class="local-note">📝 {escape(item.local_note)}</p>' if item.local_note else ""
    focused = " focused" if item.is_focused else ""
    compact_class = " compact" if compact else ""
    draggable = ' draggable="true"' if compact else ""
    group = "github" if item.source == "github" else ("waiting" if item.action_state == "waiting" else "action")
    return (
        f'<article class="task priority-{item.priority}{focused}{compact_class}" data-key="{escape(item.key, quote=True)}" '
        f'data-group="{group}" data-title="{escape(item.title.casefold(), quote=True)}"{draggable}>'
        f'<div class="task-head"><h3>{title}</h3>{badge_html}</div><p>{detail}</p>{note_html}'
        + (f'<div class="github">{"".join(github_links)}</div>' if github_links else "")
        + "".join(alerts)
        + ("" if compact else _timeline_html(item) + _relations_html(item) + _comments_html(item) + _asana_write_controls(item) + _task_controls(item))
        + "</article>"
    )


def _summary_cards(tasks: list[TaskItem], today: date) -> str:
    action, waiting, optional = split_tasks(tasks)
    reviews, authored = github_reviews(tasks), github_authored_prs(tasks)
    focus = [item for item in tasks if item.is_focused]
    unread = sum(item.unread_updates for item in tasks)
    metrics = [
        (len(focus), "Today’s plan", "◎", "accent"),
        (len(action), "Need action", "!", "danger"),
        (_due_now_count(action, today), "Due / overdue", "◷", "warning"),
        (len(reviews), "Reviews", "✓", "info"),
        (len(authored), "PR blockers", "↗", "danger"),
        (unread, "New updates", "•", "accent"),
        (len(waiting), "Waiting", "…", "warning"),
        (len(optional), "Investigations", "?", "success"),
    ]
    return '<div class="summary-grid">' + "".join(
        f'<button type="button" class="summary-card tone-{tone}" data-filter="{escape(label.casefold(), quote=True)}" aria-label="Filter by {escape(label, quote=True)}">'
        f'<span class="metric-icon" aria-hidden="true">{icon}</span><strong>{value}</strong><span>{escape(label)}</span></button>'
        for value, label, icon, tone in metrics
    ) + "</div>"


def _source_status_html(source_statuses: list[SourceStatus] | None) -> str:
    if not source_statuses:
        return ""
    cards = []
    for status in source_statuses:
        css = "ok" if status.ok else "warning"
        icon = "✅" if status.ok else "⚠️"
        cards.append(
            f'<div class="source-card {css}"><strong>{icon} {escape(status.name)}</strong><span>{escape(status.detail)}</span></div>'
        )
    return f'<details class="meta-panel"><summary>Source health</summary><div class="source-health">{"".join(cards)}</div></details>'


def _summary_panel(summaries: dict[str, Any] | None) -> str:
    if not summaries:
        return ""
    daily = summaries.get("daily", {})
    weekly = summaries.get("weekly", {})
    latest = summaries.get("latest_counts", {})

    def grid(values: dict[str, Any], labels: list[tuple[str, str]]) -> str:
        return '<div class="mini-grid">' + "".join(
            f'<div><strong>{int(values.get(key, 0) or 0)}</strong><span>{label}</span></div>'
            for key, label in labels
        ) + "</div>"

    labels = [
        ("completed", "Completed"),
        ("new", "New"),
        ("status_changed", "Status moves"),
        ("reviews_completed", "Reviews done"),
        ("prs_merged", "PRs merged"),
        ("cleared", "Cleared"),
    ]
    current = grid(latest, [("action", "Action"), ("waiting", "Waiting"), ("focus", "Focus"), ("unread", "Updates")])
    return (
        '<details class="meta-panel"><summary>Daily & weekly summaries</summary>'
        '<div class="summary-tabs">'
        f'<details open><summary>Today</summary>{grid(daily, labels)}</details>'
        f'<details><summary>This week</summary>{grid(weekly, labels)}</details>'
        f'<details><summary>Latest snapshot</summary>{current}</details>'
        '</div></details>'
    )


def _plan_candidate_card(candidate: PlanCandidate, today: date) -> str:
    reason_chips = "".join(f'<span>{escape(reason)}</span>' for reason in candidate.reasons)
    add_button = _post_form("toggle_focus", candidate.task.key, "Add to plan")
    return (
        '<div class="plan-candidate">'
        + _task_card(candidate.task, today, compact=True)
        + f'<div class="plan-reasons">{reason_chips}<strong>Score {candidate.score}</strong>{add_button}</div></div>'
    )


def _focus_section(
    tasks: list[TaskItem],
    today: date,
    max_items: int = 5,
    stale_waiting_limit: int = 1,
) -> str:
    focus = sorted([item for item in tasks if item.is_focused], key=lambda item: item.focus_rank or 0)
    plan = build_smart_plan(tasks, today, max_items=max_items, stale_waiting_limit=stale_waiting_limit)
    suggestions = [candidate for candidate in plan.candidates if not candidate.task.is_focused]
    accept_label = "Refresh smart plan" if focus else "Use suggested plan"
    controls = '<div class="plan-actions">' + _post_form("accept_smart_plan", "", accept_label, "primary")
    if focus:
        controls += _post_form("clear_plan", "", "Clear plan", "danger")
    controls += '</div>'

    current = ''
    if focus:
        current = (
            '<div class="section-head plan-current-head"><h3>Current plan</h3><span>Drag to reorder</span></div>'
            f'<div id="focus-list">{"".join(_task_card(item, today, compact=True) for item in focus)}</div>'
        )

    if suggestions:
        suggestion_cards = ''.join(_plan_candidate_card(candidate, today) for candidate in suggestions)
        open_attr = ' open' if not focus else ''
        suggestion_block = (
            f'<details class="smart-suggestions"{open_attr}><summary>Smart suggestions <span>{len(plan.candidates)} recommended</span></summary>'
            f'<p class="plan-help">Ranked from due dates, GitHub blockers, requested reviews, priority, unread updates and stale follow-ups.</p>'
            f'<div class="plan-suggestion-list">{suggestion_cards}</div></details>'
        )
    elif focus:
        suggestion_block = '<p class="plan-help">Your current plan already contains the strongest available recommendations.</p>'
    else:
        suggestion_block = '<p class="empty">No actionable recommendations are available right now.</p>'

    return (
        '<section class="focus-section plan-section"><div class="section-head"><div><h2>🧭 Today\'s plan</h2>'
        f'<p class="plan-subtitle">Choose up to {plan.max_items} focused items. Accepted smart plans reset the next day.</p></div>'
        f'{controls}</div>{current}{suggestion_block}</section>'
    )


def _section(title: str, items: list[TaskItem], today: date, empty: str, css: str, open_by_default: bool = False) -> str:
    open_attr = " open" if open_by_default else ""
    content = "".join(_task_card(item, today) for item in sort_tasks(items)) or f'<p class="empty">{escape(empty)}</p>'
    return f'<details class="work-section {escape(css, quote=True)}"{open_attr}><summary>{title}<span>{len(items)}</span></summary><div class="section-content">{content}</div></details>'


def _change_card(change: TaskChange, today: date, kind: str) -> str:
    old = change.old
    if kind == "status":
        before = old.get("status") or "No status"
        after = change.task.status or "No status"
        note = "GitHub/waiting state changed" if before == after else f"{before} → {after}"
    elif kind == "priority":
        note = f"{str(old.get('priority') or 'new').title()} → {change.task.priority.title()}"
    else:
        before = old.get("due_on") or "No due date"
        after = change.task.due_on.isoformat() if change.task.due_on else "No due date"
        note = f"{before} → {after}"
    return _task_card(change.task, today, badge=note)


def _removed_card(item: RemovedTask) -> str:
    title = escape(item.title)
    if item.url:
        title = f'<a href="{escape(item.url, quote=True)}">{title}</a>'
    label = "Completed or removed"
    if item.github_kind == "review_request":
        label = "Review no longer required"
    elif item.github_kind == "authored_pr":
        label = "PR action cleared"
    return f'<article class="task removed"><div class="task-head"><h3>{title}</h3><span class="badge">{label}</span></div></article>'


def _main_content(
    tasks: list[TaskItem],
    now: datetime,
    changes: DigestChanges | None,
    period: str,
    github_warning: str | None,
    meta_html: str = "",
    smart_plan_max_items: int = 5,
    smart_plan_stale_waiting_limit: int = 1,
) -> str:
    action, waiting, optional = split_tasks(tasks)
    reviews, authored = github_reviews(tasks), github_authored_prs(tasks)
    issues, mentions = github_assigned_issues(tasks), github_mentions(tasks)
    focus = _focus_section(tasks, now.date(), smart_plan_max_items, smart_plan_stale_waiting_limit)
    primary_parts: list[str] = []
    secondary_parts: list[str] = []
    if period == "evening" and changes and changes.baseline_available:
        change_parts = [f'<div class="change-summary"><strong>{changes.change_count}</strong> change(s) since the previous digest</div>']
        if changes.new:
            change_parts.append('<details class="work-section" open><summary>🆕 New<span>' + str(len(changes.new)) + '</span></summary><div class="section-content">' + ''.join(_task_card(item, now.date(), badge="New") for item in sort_tasks(changes.new)) + '</div></details>')
        if changes.status_changed:
            change_parts.append('<details class="work-section"><summary>🔄 Status changed<span>' + str(len(changes.status_changed)) + '</span></summary><div class="section-content">' + ''.join(_change_card(change, now.date(), "status") for change in changes.status_changed) + '</div></details>')
        if changes.due_changed:
            change_parts.append('<details class="work-section"><summary>📅 Due date changed<span>' + str(len(changes.due_changed)) + '</span></summary><div class="section-content">' + ''.join(_change_card(change, now.date(), "due") for change in changes.due_changed) + '</div></details>')
        if changes.removed:
            change_parts.append('<details class="work-section"><summary>✅ Completed today / no longer active<span>' + str(len(changes.removed)) + '</span></summary><div class="section-content">' + ''.join(_removed_card(item) for item in changes.removed) + '</div></details>')
        primary_parts.append('<section class="changes"><h2>Evening changes</h2>' + ''.join(change_parts) + '</section>')
    primary_parts.append(_section("📌 Still needs action" if period == "evening" else "✅ Needs action", action, now.date(), "No tasks currently require your action.", "needs-action", True))
    primary_parts.append(_section("🕒 Waiting on others", waiting, now.date(), "Nothing is currently waiting on others.", "waiting", True))

    if meta_html:
        secondary_parts.append(meta_html)
    warning = f'<p class="notice">Some GitHub data could not be loaded: {escape(github_warning)}</p>' if github_warning else ""
    secondary_parts.append(warning + _section("🛠️ Your PRs needing action", authored, now.date(), "None of your open PRs currently have requested changes, failing checks, or merge conflicts.", "github-authored"))
    secondary_parts.append(_section("👀 GitHub reviews required", reviews, now.date(), "No reviews currently requested from you.", "github-reviews"))
    secondary_parts.append(_section("📌 GitHub issues assigned to you", issues, now.date(), "No open GitHub issues are currently assigned to you.", "github-issues"))
    secondary_parts.append(_section("💬 GitHub mentions", mentions, now.date(), "No open GitHub issues or PRs currently mention you.", "github-mentions"))
    optional_content = "".join(_task_card(item, now.date()) for item in sort_tasks(optional)) or '<p class="empty">No optional investigations.</p>'
    secondary_parts.append(f'<details class="optional-section"><summary>🔎 Investigations <span>{len(optional)} optional</span></summary><div class="optional-content">{optional_content}</div></details>')

    primary_label = f"{len(action)} action · {len(waiting)} waiting"
    secondary_label = f"{len(authored) + len(reviews) + len(issues) + len(mentions)} GitHub item(s)"
    return (
        focus
        + '<div class="dashboard-workspace">'
        + '<section class="dashboard-primary"><div class="dashboard-column-heading"><h2>Work queue</h2>'
        + f'<span>{escape(primary_label)}</span></div>{"".join(primary_parts)}</section>'
        + '<aside class="dashboard-secondary"><div class="dashboard-column-heading"><h2>Attention & context</h2>'
        + f'<span>{escape(secondary_label)}</span></div>{"".join(secondary_parts)}</aside>'
        + '</div>'
    )


def render_html(
    tasks: List[TaskItem],
    now: datetime,
    period: str,
    output_path: str,
    changes: DigestChanges | None = None,
    github_warning: str | None = None,
    source_statuses: list[SourceStatus] | None = None,
    hidden_summary: tuple[int, int] | None = None,
    action_token: str | None = None,
    dashboard_url: str | None = None,
    refresh_minutes: int = 5,
    summaries: dict[str, Any] | None = None,
    asana_write_enabled: bool = False,
    smart_plan_max_items: int = 5,
    smart_plan_stale_waiting_limit: int = 1,
) -> Path:
    global _ACTION_TOKEN, _DASHBOARD_URL, _ASANA_WRITE_ENABLED
    _ACTION_TOKEN = action_token
    _DASHBOARD_URL = dashboard_url.rstrip("/") if dashboard_url else None
    _ASANA_WRITE_ENABLED = asana_write_enabled
    action, waiting, optional = split_tasks(tasks)
    reviews, authored = github_reviews(tasks), github_authored_prs(tasks)
    issues, mentions = github_assigned_issues(tasks), github_mentions(tasks)
    snoozed, ignored = hidden_summary or (0, 0)
    subtitle = "Evening changes" if period == "evening" and changes and changes.baseline_available else period.title()
    token = escape(action_token or "", quote=True)
    base = escape((dashboard_url or "").rstrip("/"), quote=True)
    sidebar_actions = ""
    if dashboard_url and action_token:
        sidebar_actions = f'''
<div class="sidebar-actions">
  <form method="post" action="{base}/action">{_hidden_input("token", action_token)}<input type="hidden" name="action" value="refresh"><button type="submit">Refresh now <span aria-hidden="true">↻</span></button></form>
  <form method="post" action="{base}/action">{_hidden_input("token", action_token)}<input type="hidden" name="action" value="pause_notifications"><button type="submit">Pause alerts <span aria-hidden="true">1h</span></button></form>
  <p class="sidebar-note">Runs locally on your Mac. Drafts stay hidden and your credentials remain in Keychain.</p>
</div>'''
    sidebar = f'<aside class="app-sidebar">{brand_html()}{navigation_html(base, active_path="/")}{sidebar_actions}</aside>'
    auto_refresh = f'<script>setTimeout(()=>window.location.reload(),{max(1, refresh_minutes) * 60000});</script>' if dashboard_url else ""
    meta = _source_status_html(source_statuses) + _summary_panel(summaries)
    main_content = _main_content(
        tasks,
        now,
        changes,
        period,
        github_warning,
        meta,
        smart_plan_max_items,
        smart_plan_stale_waiting_limit,
    )

    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Your task digest</title>
<style>{DASHBOARD_CSS}</style></head>
<body><div class="app-shell">{sidebar}<main class="app-main"><div class="app-content"><header class="dashboard-header"><div class="page-header"><div class="page-title-wrap"><span class="eyebrow">Overview</span><h1>Your task digest</h1><p class="page-subtitle">{escape(subtitle)} · {now:%A, %d %B %Y at %H:%M}</p></div><div class="header-status">Auto-refresh every {max(1, refresh_minutes)} min</div></div></header>
<div class="dashboard-controls"><div class="search-wrap"><input id="task-search" type="search" placeholder="Search tasks, PRs, projects…" aria-label="Search tasks"></div><div class="filter-bar"><button type="button" class="active" data-view="all">All</button><button type="button" data-view="action">Action</button><button type="button" data-view="github">GitHub</button><button type="button" data-view="waiting">Waiting</button><button type="button" data-view="unread">Updates</button></div></div>
{_summary_cards(tasks, now.date())}{main_content}
<div id="toast" role="status" aria-live="polite"></div>
<footer>{len(action)} need action · {len(authored)} PR blocker(s) · {len(reviews)} review(s) · {len(issues)} assigned issue(s) · {len(mentions)} mention(s) · {len(waiting)} waiting · {len(optional)} investigation(s) · {snoozed} snoozed · {ignored} ignored. Draft tasks are hidden.</footer>
</div></main></div>
<script>
const token={token!r};const base={base!r};
document.querySelectorAll('[data-nav-path]').forEach(link=>{{const path=link.dataset.navPath;const active=path==='/'?location.pathname==='/'||location.pathname.endsWith('task-digest.html'):location.pathname.startsWith(path);link.classList.toggle('active',active);if(active)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');}});
const search=document.getElementById('task-search');let view='all';
function applyFilters(){{const q=(search.value||'').toLowerCase();document.querySelectorAll('.task').forEach(card=>{{const text=(card.dataset.title||'')+' '+card.textContent.toLowerCase();const group=card.dataset.group||'';const unread=card.textContent.includes('new update');const okView=view==='all'||view===group||(view==='unread'&&unread);card.classList.toggle('hidden-by-filter',!(okView&&text.includes(q)));}})}}
search.addEventListener('input',applyFilters);document.querySelectorAll('[data-view]').forEach(btn=>btn.addEventListener('click',()=>{{view=btn.dataset.view;document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b===btn));applyFilters();}}));
document.querySelectorAll('.summary-card').forEach(btn=>btn.addEventListener('click',()=>{{const label=btn.dataset.filter||'';if(label.includes('waiting'))view='waiting';else if(label.includes('review')||label.includes('pr'))view='github';else if(label.includes('update'))view='unread';else if(label.includes('action')||label.includes('due'))view='action';else view='all';document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));applyFilters();}}));
const list=document.getElementById('focus-list');if(list){{let dragged=null;list.querySelectorAll('.task').forEach(card=>{{card.addEventListener('dragstart',()=>{{dragged=card;card.classList.add('dragging')}});card.addEventListener('dragend',async()=>{{card.classList.remove('dragging');const keys=[...list.querySelectorAll('.task')].map(x=>x.dataset.key);const body=new URLSearchParams({{token,action:'focus_order',keys:keys.join(',')}});await fetch(base+'/api/action',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body}});}});}});list.addEventListener('dragover',event=>{{event.preventDefault();const after=[...list.querySelectorAll('.task:not(.dragging)')].find(el=>event.clientY<=el.getBoundingClientRect().top+el.offsetHeight/2);if(dragged){{if(after)list.insertBefore(dragged,after);else list.appendChild(dragged);}}}});}}
const toast=document.getElementById('toast');function showToast(message,error=false){{if(!toast)return;toast.textContent=message;toast.style.background=error?'var(--danger)':'var(--text)';toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),4000);}}
document.querySelectorAll('.asana-write-form').forEach(form=>form.addEventListener('submit',async event=>{{event.preventDefault();const question=form.dataset.confirm;if(question&&!window.confirm(question))return;const button=form.querySelector('button[type=submit]');if(button)button.disabled=true;try{{const body=new URLSearchParams(new FormData(form));const response=await fetch(base+'/api/action',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body}});const payload=await response.json();if(!response.ok)throw new Error(payload.error||'Asana update failed');showToast(String(payload.result||'Asana updated'));setTimeout(()=>window.location.reload(),700);}}catch(error){{showToast(error.message||String(error),true);if(button)button.disabled=false;}}}}));
</script>{auto_refresh}</body></html>'''
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def notification_summary(tasks: List[TaskItem], period: str = "morning", changes: DigestChanges | None = None) -> tuple[str, str]:
    action, waiting, optional = split_tasks(tasks)
    reviews, authored = github_reviews(tasks), github_authored_prs(tasks)
    issues, mentions = github_assigned_issues(tasks), github_mentions(tasks)
    unread = sum(task.unread_updates for task in tasks)
    if period == "evening" and changes and changes.baseline_available:
        return f"Evening Digest: {changes.change_count} change(s)", f"Still action {len(action)} · PRs {len(authored)} · Reviews {len(reviews)} · Updates {unread}"
    due_now = _due_now_count(action, datetime.now().astimezone().date())
    title = f"Task Digest: {len(action)} need action · {len(authored)} PR blocker(s) · {len(reviews)} review(s)"
    body = f"Issues {len(issues)} · Mentions {len(mentions)} · Due/overdue {due_now} · Waiting {len(waiting)} · Investigations {len(optional)}"
    return title, body
