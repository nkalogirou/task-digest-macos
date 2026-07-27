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
from .ui import SHARED_CSS, brand_html, command_palette_html, command_palette_script, navigation_html

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
.title-line { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.demo-mode-badge { display: inline-flex; align-items: center; min-height: 25px; padding: 4px 9px; border: 1px solid color-mix(in srgb,var(--accent) 35%,var(--border)); border-radius: 999px; color: var(--accent); background: var(--accent-soft); font-size: 11px; font-weight: 720; letter-spacing: .02em; }
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
.dashboard-metrics { margin: 18px 0 22px; }
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4,minmax(0,1fr));
  gap: 11px;
  margin: 0;
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
.more-metrics {
  margin-top: 10px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}
.more-metrics > summary {
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  color: var(--text);
  font-size: 12px;
  font-weight: 680;
}
.more-metrics > summary::-webkit-details-marker { display: none; }
.more-metrics > summary::after {
  content: "›";
  margin-left: auto;
  color: var(--faint);
  font-size: 19px;
  line-height: 1;
  transition: transform .16s ease;
}
.more-metrics[open] > summary::after { transform: rotate(90deg); }
.more-metrics > summary span { color: var(--muted); font-size: 11px; font-weight: 520; }
.secondary-metric-grid {
  display: grid;
  grid-template-columns: repeat(4,minmax(0,1fr));
  gap: 9px;
  padding: 0 10px 10px;
}
.summary-card.compact-metric {
  min-height: 62px;
  grid-template-columns: 30px 1fr;
  column-gap: 9px;
  padding: 10px 11px;
  border-radius: 12px;
  box-shadow: none;
}
.summary-card.compact-metric .metric-icon { width: 30px; height: 30px; border-radius: 9px; font-size: 13px; }
.summary-card.compact-metric strong { font-size: 18px; }
.summary-card.compact-metric span:last-child { margin-top: 2px; font-size: 10px; }
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
.focus-section { margin: 8px 0 22px; }
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
#focus-list { display: grid; gap: 8px; }
.smart-suggestions { position: relative; z-index: 1; margin-top: 15px; border-top: 1px solid color-mix(in srgb,var(--accent) 16%,var(--border)); padding-top: 13px; }
.smart-suggestions > summary { cursor: pointer; font-weight: 680; display: flex; justify-content: space-between; gap: 12px; }
.smart-suggestions > summary span { color: var(--muted); font-size: 11px; }
.plan-help { color: var(--muted); font-size: 12px; margin: 9px 0; }
.plan-suggestion-list { display: grid; gap: 8px; }
.plan-item {
  --priority-color: var(--border-strong);
  position: relative;
  display: grid;
  gap: 7px;
  background: color-mix(in srgb,var(--surface-solid) 90%,transparent);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 12px 13px 11px 16px;
  box-shadow: var(--shadow-sm);
}
.plan-item::before { content: ""; position: absolute; left: 0; top: 10px; bottom: 10px; width: 3px; border-radius: 0 3px 3px 0; background: var(--priority-color); }
.plan-item.priority-urgent { --priority-color: var(--danger); }
.plan-item.priority-high { --priority-color: #d97706; }
.plan-item.priority-normal { --priority-color: #ca8a04; }
.plan-item.priority-new { --priority-color: var(--success); }
.plan-item.dragging { opacity: .45; }
.plan-item-main { min-width: 0; display: grid; gap: 6px; }
.plan-item-title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.plan-item h3 { min-width: 0; margin: 0; font-size: 14px; line-height: 1.35; letter-spacing: -.008em; }
.plan-item h3 a { color: var(--text); }
.plan-item-meta { display: flex; flex-wrap: wrap; gap: 5px 8px; align-items: center; color: var(--muted); font-size: 10px; }
.plan-item-meta span + span::before { content: "·"; margin-right: 8px; color: var(--faint); }
.plan-pr-summary { min-width: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 10px; }
.plan-pr-summary a { max-width: min(620px,100%); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--info); font-weight: 660; }
.plan-pr-state { display: inline-flex; align-items: center; border-radius: 999px; padding: 4px 7px; border: 1px solid var(--border); font-weight: 680; white-space: nowrap; }
.plan-pr-state.danger { color: var(--danger); background: var(--danger-soft); border-color: color-mix(in srgb,var(--danger) 20%,var(--border)); }
.plan-pr-state.warning { color: var(--warning); background: var(--warning-soft); border-color: color-mix(in srgb,var(--warning) 20%,var(--border)); }
.plan-pr-state.success { color: var(--success); background: var(--success-soft); border-color: color-mix(in srgb,var(--success) 20%,var(--border)); }
.plan-drag { color: var(--faint); cursor: grab; font-size: 16px; letter-spacing: -4px; padding-right: 3px; user-select: none; }
.plan-item .priority-control { min-width: 86px; }
.plan-item .priority-control-prefix { display: none; }
.plan-item .priority-control select { font-size: 9px; padding-block: 4px; }
.plan-item-actions { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; padding-top: 6px; border-top: 1px solid color-mix(in srgb,var(--border) 70%,transparent); }
.plan-item-actions form { display: inline-flex; margin-left: auto; }
.plan-reasons { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; min-width: 0; }
.plan-reasons span, .plan-score { font-size: 9px; color: var(--muted); background: var(--surface-muted); border: 1px solid var(--border); border-radius: 999px; padding: 4px 7px; }
.plan-score { color: var(--faint); }
.plan-open-button { border: 0; background: transparent; color: var(--accent); padding: 5px 7px; font-size: 10px; font-weight: 680; cursor: pointer; }
.plan-open-button:hover { text-decoration: underline; }
.task {
  --priority-color: var(--border-strong);
  position: relative;
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 18px 18px 16px 21px;
  margin: 10px 0;
  box-shadow: var(--shadow-sm);
  transition: transform .16s ease, border-color .16s ease, box-shadow .16s ease;
}
.task::before { content: ""; position: absolute; left: 0; top: 17px; bottom: 17px; width: 4px; border-radius: 0 4px 4px 0; background: var(--priority-color); }
.task:hover { transform: translateY(-1px); border-color: color-mix(in srgb,var(--priority-color) 30%,var(--border)); box-shadow: var(--shadow-md); }
.task.compact { cursor: grab; margin: 0; padding-block: 14px; }
.task.compact.dragging { opacity: .45; }
.task.focused { border-color: color-mix(in srgb,var(--accent) 45%,var(--border)); box-shadow: 0 0 0 3px color-mix(in srgb,var(--accent) 8%,transparent), var(--shadow-sm); }
.priority-urgent { --priority-color: var(--danger); }
.priority-high { --priority-color: #d97706; }
.priority-normal { --priority-color: #ca8a04; }
.priority-new { --priority-color: var(--success); }
.task-head { display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; }
.task-title-wrap { min-width: 0; }
.task h3 { margin: 0; font-size: 16px; line-height: 1.35; letter-spacing: -.012em; }
.task h3 a { color: var(--text); }
.task h3 a:hover { color: var(--accent); }
.priority-pill, .priority-control, .task-flag, .meta-chip {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  border: 1px solid var(--border);
  border-radius: 999px;
  white-space: nowrap;
  font-weight: 680;
}
.priority-pill { flex: 0 0 auto; padding: 5px 9px; font-size: 10px; color: var(--priority-color); background: color-mix(in srgb,var(--priority-color) 10%,var(--surface-muted)); border-color: color-mix(in srgb,var(--priority-color) 24%,var(--border)); }
.priority-control { position: relative; flex: 0 0 auto; min-width: 126px; min-height: 30px; color: var(--priority-color); background: color-mix(in srgb,var(--priority-color) 10%,var(--surface-muted)); border-color: color-mix(in srgb,var(--priority-color) 28%,var(--border)); transition: border-color .16s ease, background .16s ease, opacity .16s ease; overflow: hidden; }
.priority-control:hover, .priority-control:focus-within { border-color: color-mix(in srgb,var(--priority-color) 55%,var(--border)); background: color-mix(in srgb,var(--priority-color) 15%,var(--surface-muted)); }
.priority-control.is-saving { opacity: .62; }
.priority-control-prefix { position: absolute; left: 9px; top: 50%; transform: translateY(-50%); color: color-mix(in srgb,currentColor 68%,var(--muted)); font-size: 8px; font-weight: 760; letter-spacing: .04em; text-transform: uppercase; pointer-events: none; }
.priority-control-chevron { position: absolute; right: 8px; top: 50%; transform: translateY(-54%); color: currentColor; font-size: 11px; pointer-events: none; }
.priority-control select { width: 100%; min-width: 0; min-height: 28px; appearance: none; -webkit-appearance: none; border: 0; outline: 0; color: currentColor; background: transparent; padding: 13px 24px 3px 9px; font: inherit; font-size: 10px; font-weight: 740; cursor: pointer; }
.priority-control select:focus-visible { box-shadow: inset 0 0 0 2px color-mix(in srgb,var(--priority-color) 42%,transparent); border-radius: 999px; }
.priority-control option { color: CanvasText; background: Canvas; }
.priority-control .priority-manual-dot { position: absolute; left: 5px; top: 5px; width: 4px; height: 4px; border-radius: 50%; background: currentColor; pointer-events: none; }
.priority-control.has-manual select { padding-left: 13px; }
.task-flags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 7px; }
.task-flag { padding: 4px 8px; font-size: 10px; color: var(--accent); background: var(--accent-soft); border-color: color-mix(in srgb,var(--accent) 22%,var(--border)); }
.task-meta { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 11px; }
.meta-chip { padding: 5px 8px; font-size: 10px; color: var(--muted); background: var(--surface-muted); }
.meta-chip.tone-danger { color: var(--danger); background: var(--danger-soft); border-color: color-mix(in srgb,var(--danger) 20%,var(--border)); }
.meta-chip.tone-warning { color: var(--warning); background: var(--warning-soft); border-color: color-mix(in srgb,var(--warning) 22%,var(--border)); }
.meta-chip.tone-info { color: var(--info); background: var(--info-soft); border-color: color-mix(in srgb,var(--info) 20%,var(--border)); }
.meta-chip.tone-success { color: var(--success); background: var(--success-soft); border-color: color-mix(in srgb,var(--success) 20%,var(--border)); }
.meta-chip.tone-accent { color: var(--accent); background: var(--accent-soft); border-color: color-mix(in srgb,var(--accent) 20%,var(--border)); }
.local-note { margin: 12px 0 0!important; color: var(--text)!important; background: var(--accent-soft); border: 1px solid color-mix(in srgb,var(--accent) 18%,var(--border)); padding: 10px 12px; border-radius: 12px; display: grid; gap: 3px; }
.local-note strong { color: var(--accent); font-size: 10px; text-transform: uppercase; letter-spacing: .06em; }
.local-note span { font-size: 12px; line-height: 1.45; }
.github-list { display: grid; gap: 7px; margin-top: 12px; }
.github-item { display: grid; grid-template-columns: minmax(0,1fr) auto auto; align-items: center; gap: 8px; min-height: 38px; padding: 8px 10px; color: var(--text); background: var(--info-soft); border: 1px solid color-mix(in srgb,var(--info) 18%,var(--border)); border-radius: 12px; }
.github-item:hover { border-color: color-mix(in srgb,var(--info) 35%,var(--border)); }
.github-item-label { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--info); font-size: 11px; font-weight: 680; }
.github-item-badges { display: flex; gap: 5px; }
.github-item-badges:empty { display: none; }
.github-item-arrow { color: var(--info); font-size: 11px; }
.pr-alert, .pr-status { margin-top: 9px; padding: 10px 11px; border-radius: 11px; display: flex; flex-direction: column; gap: 3px; font-size: 12px; }
.pr-alert { background: var(--warning-soft); color: var(--warning); border: 1px solid color-mix(in srgb,var(--warning) 25%,var(--border)); }
.pr-status { background: var(--info-soft); color: var(--info); border: 1px solid color-mix(in srgb,var(--info) 18%,var(--border)); }
.pr-cockpit { margin-top: 10px; padding: 12px; border: 1px solid var(--border); border-radius: 14px; background: color-mix(in srgb,var(--surface-muted) 72%,transparent); }
.pr-cockpit.compact { padding: 9px 10px; }
.pr-cockpit-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.pr-cockpit-title { display: grid; gap: 3px; min-width: 0; }
.pr-cockpit-title strong { font-size: 12px; }
.pr-cockpit-title span { color: var(--muted); font-size: 10px; }
.pr-cockpit-state { flex: 0 0 auto; padding: 5px 8px; border-radius: 999px; font-size: 9px; font-weight: 760; letter-spacing: .05em; }
.pr-cockpit-state.blocked { color: var(--danger); background: var(--danger-soft); }
.pr-cockpit-state.waiting { color: var(--warning); background: var(--warning-soft); }
.pr-cockpit-state.ready { color: var(--success); background: var(--success-soft); }
.pr-cockpit-state.merged { color: var(--info); background: var(--info-soft); }
.pr-progress { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 7px; margin-top: 10px; }
.pr-gate { min-width: 0; padding: 8px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }
.pr-gate strong { display: block; font-size: 10px; }
.pr-gate span { display: block; margin-top: 3px; color: var(--muted); font-size: 9px; line-height: 1.35; }
.pr-gate.ready { border-color: color-mix(in srgb,var(--success) 28%,var(--border)); }
.pr-gate.blocked { border-color: color-mix(in srgb,var(--danger) 30%,var(--border)); }
.pr-gate.waiting { border-color: color-mix(in srgb,var(--warning) 30%,var(--border)); }
.pr-gate.neutral { border-color: color-mix(in srgb,var(--info) 22%,var(--border)); }
.pr-gate-meter { grid-column: 1 / -1; display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 10px; }
.pr-gate-track { flex: 1; height: 6px; overflow: hidden; border-radius: 999px; background: var(--border); }
.pr-gate-fill { height: 100%; border-radius: inherit; background: var(--accent); }
.pr-next { margin-top: 10px; padding: 9px 10px; border-radius: 10px; background: var(--accent-soft); border: 1px solid color-mix(in srgb,var(--accent) 20%,var(--border)); }
.pr-next strong { display: block; color: var(--accent); font-size: 10px; text-transform: uppercase; letter-spacing: .06em; }
.pr-next ol { margin: 6px 0 0; padding-left: 18px; color: var(--text); font-size: 11px; line-height: 1.55; }
.pr-details { margin-top: 9px; border-top: 1px solid var(--border); padding-top: 8px; }
.pr-details > summary { cursor: pointer; list-style: none; display: flex; align-items: center; justify-content: space-between; color: var(--muted); font-size: 10px; font-weight: 680; }
.pr-details > summary::-webkit-details-marker { display: none; }
.pr-details > summary::after { content: "›"; font-size: 16px; transition: transform .16s ease; }
.pr-details[open] > summary::after { transform: rotate(90deg); }
.pr-detail-body { margin-top: 8px; display: grid; gap: 8px; }
.pr-check, .pr-review, .pr-thread, .pr-scope-row, .pr-activity-row { display: grid; grid-template-columns: auto minmax(0,1fr) auto; gap: 8px; align-items: start; padding: 8px 9px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }
.pr-check-icon, .pr-review-icon { font-size: 12px; line-height: 1.3; }
.pr-detail-main { min-width: 0; }
.pr-detail-main strong { display: block; font-size: 11px; overflow-wrap: anywhere; }
.pr-detail-main p { margin: 3px 0 0!important; color: var(--muted)!important; font-size: 10px!important; line-height: 1.45; }
.pr-detail-meta { color: var(--muted); font-size: 9px; white-space: nowrap; }
.pr-detail-link { color: var(--info); font-size: 9px; font-weight: 680; white-space: nowrap; }
.pr-thread { grid-template-columns: minmax(0,1fr) auto; }
.pr-thread-location { color: var(--info); font-size: 10px; font-weight: 680; overflow-wrap: anywhere; }
.pr-thread blockquote { margin: 6px 0 0; padding-left: 9px; border-left: 2px solid var(--border); color: var(--text); font-size: 10px; line-height: 1.5; }
.pr-scope-summary { display: flex; flex-wrap: wrap; gap: 6px; }
.pr-file-list { margin: 0; padding-left: 18px; color: var(--muted); font-size: 10px; line-height: 1.55; }
.pr-activity { display: grid; gap: 6px; }
.pr-activity-row { grid-template-columns: minmax(0,1fr) auto; }
@media (max-width: 760px) {
  .pr-progress { grid-template-columns: repeat(2,minmax(0,1fr)); }
  .pr-gate-meter { grid-column: 1 / -1; }
  .pr-next-grid { grid-template-columns: 1fr; }
  .pr-cockpit.compact { grid-template-columns: 31px minmax(0,1fr); }
  .pr-compact-status { grid-column: 2; justify-items: start; grid-auto-flow: column; align-items: center; }
}
.task-quick-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.task-quick-link { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); font-size: 11px; font-weight: 650; }
.task-quick-link:hover { color: var(--accent); }
.task-details { margin-top: 13px; border-top: 1px solid var(--border); padding-top: 11px; }
.task-details > summary { cursor: pointer; list-style: none; display: flex; align-items: center; justify-content: space-between; gap: 10px; color: var(--muted); font-size: 12px; font-weight: 650; }
.task-details > summary::-webkit-details-marker { display: none; }
.task-details > summary::after { content: "›"; color: var(--faint); font-size: 20px; margin-left: auto; transition: transform .16s ease; }
.task-details[open] > summary::after { transform: rotate(90deg); }
.task-details > summary span { margin-left: 0; margin-right: 5px; font-size: 10px; font-weight: 550; }
.task-details-body { margin-top: 8px; }
.task-details-body > :first-child { margin-top: 0; }
.context-details ul { margin: 9px 0 0; padding-left: 20px; color: var(--muted); font-size: 11px; line-height: 1.5; }
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
.search-helper {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 14px;
  margin: -8px 2px 18px;
  color: var(--muted);
  font-size: 11px;
}
.search-examples { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.search-examples button {
  border: 0;
  padding: 3px 7px;
  border-radius: 7px;
  background: var(--surface-muted);
  color: var(--muted);
  font-size: 10px;
  font-weight: 650;
  box-shadow: none;
}
.search-examples button:hover { color: var(--accent); background: var(--accent-soft); transform: none; box-shadow: none; }
.search-result-count { font-weight: 650; color: var(--text); }
.reset-view { border: 0; padding: 3px 7px; border-radius: 7px; background: transparent; color: var(--muted); font-size: 10px; font-weight: 650; box-shadow: none; }
.reset-view:hover { color: var(--accent); background: var(--accent-soft); transform: none; box-shadow: none; }
.hidden-by-filter { display: none!important; }

/* Pull-request cockpit visual hierarchy */
.pr-cockpit {
  position: relative;
  overflow: hidden;
  padding: 15px;
  border-color: color-mix(in srgb,var(--border) 76%,var(--accent));
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb,var(--accent) 7%,transparent), transparent 35%),
    color-mix(in srgb,var(--surface-muted) 82%,var(--surface));
  box-shadow: inset 0 1px 0 color-mix(in srgb,var(--text) 5%,transparent);
}
.pr-cockpit::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: var(--info);
}
.pr-cockpit.blocked::before { background: var(--danger); }
.pr-cockpit.waiting::before { background: var(--warning); }
.pr-cockpit.ready::before { background: var(--success); }
.pr-cockpit.merged::before { background: var(--info); }
.pr-cockpit-head { align-items: center; }
.pr-cockpit-title { gap: 2px; }
.pr-eyebrow {
  color: var(--muted)!important;
  font-size: 9px!important;
  font-weight: 760;
  letter-spacing: .09em;
  text-transform: uppercase;
}
.pr-cockpit-title strong { font-size: 14px; letter-spacing: -.01em; }
.pr-cockpit-title > span:last-child { font-size: 11px; line-height: 1.45; }
.pr-cockpit-state {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 9px;
  letter-spacing: .035em;
  text-transform: uppercase;
}
.pr-cockpit-state > span {
  display: grid;
  place-items: center;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: color-mix(in srgb,currentColor 12%,transparent);
  font-size: 9px;
}
.pr-progress { gap: 8px; margin-top: 13px; }
.pr-gate {
  display: grid;
  grid-template-columns: 25px minmax(0,1fr);
  gap: 8px;
  align-items: center;
  min-height: 55px;
  padding: 9px 10px;
  border-color: transparent;
  background: color-mix(in srgb,var(--surface) 82%,transparent);
  box-shadow: inset 0 0 0 1px var(--border);
}
.pr-gate.ready { box-shadow: inset 0 0 0 1px color-mix(in srgb,var(--success) 30%,var(--border)); }
.pr-gate.blocked { box-shadow: inset 0 0 0 1px color-mix(in srgb,var(--danger) 34%,var(--border)); }
.pr-gate.waiting { box-shadow: inset 0 0 0 1px color-mix(in srgb,var(--warning) 34%,var(--border)); }
.pr-gate.neutral { box-shadow: inset 0 0 0 1px color-mix(in srgb,var(--info) 24%,var(--border)); }
.pr-gate-icon {
  display: grid;
  place-items: center;
  width: 25px;
  height: 25px;
  border-radius: 8px;
  color: var(--info);
  background: var(--info-soft);
  font-size: 11px;
  font-weight: 800;
}
.pr-gate.ready .pr-gate-icon { color: var(--success); background: var(--success-soft); }
.pr-gate.blocked .pr-gate-icon { color: var(--danger); background: var(--danger-soft); }
.pr-gate.waiting .pr-gate-icon { color: var(--warning); background: var(--warning-soft); }
.pr-gate strong { font-size: 11px; }
.pr-gate span:not(.pr-gate-icon) { margin-top: 2px; font-size: 10px; }
.pr-gate-meter { margin-top: 1px; }
.pr-gate-meter strong { color: var(--text); }
.pr-gate-track { height: 5px; background: color-mix(in srgb,var(--border) 78%,transparent); }
.pr-gate-fill { background: var(--accent); transition: width .25s ease; }
.pr-gate-fill.blocked { background: var(--danger); }
.pr-gate-fill.waiting { background: var(--warning); }
.pr-gate-fill.ready { background: var(--success); }
.pr-gate-fill.merged { background: var(--info); }
.pr-next-grid {
  display: grid;
  grid-template-columns: repeat(2,minmax(0,1fr));
  gap: 9px;
  margin-top: 11px;
}
.pr-next-group {
  padding: 11px 12px;
  border-radius: 12px;
  background: color-mix(in srgb,var(--surface) 88%,transparent);
  box-shadow: inset 0 0 0 1px var(--border);
}
.pr-next-group.action { box-shadow: inset 3px 0 0 var(--danger), inset 0 0 0 1px var(--border); }
.pr-next-group.waiting { box-shadow: inset 3px 0 0 var(--warning), inset 0 0 0 1px var(--border); }
.pr-next-group > strong {
  display: block;
  margin-bottom: 6px;
  color: var(--muted);
  font-size: 9px;
  font-weight: 780;
  letter-spacing: .08em;
  text-transform: uppercase;
}
.pr-next-group ul { display: grid; gap: 5px; margin: 0; padding: 0; list-style: none; }
.pr-next-group li { display: flex; align-items: baseline; justify-content: space-between; gap: 9px; font-size: 11px; line-height: 1.4; }
.pr-next-group li span { min-width: 0; }
.pr-next-group li a { flex: 0 0 auto; color: var(--info); font-size: 9px; font-weight: 700; }
.pr-detail-list { margin-top: 12px; border-top: 1px solid var(--border); }
.pr-details { margin: 0; padding: 0; border-top: 0; }
.pr-details + .pr-details { border-top: 1px solid color-mix(in srgb,var(--border) 72%,transparent); }
.pr-details > summary { min-height: 40px; padding: 9px 1px; color: var(--text); font-size: 11px; }
.pr-details > summary::after { margin-left: 4px; color: var(--faint); }
.pr-detail-count {
  margin-left: auto;
  padding: 2px 7px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted);
  background: var(--surface-muted);
  font-size: 9px;
  font-weight: 680;
}
.pr-detail-body { margin: 0 0 9px; }
.pr-check, .pr-review, .pr-thread, .pr-scope-row, .pr-activity-row {
  border-color: transparent;
  background: color-mix(in srgb,var(--surface) 82%,transparent);
  box-shadow: inset 0 0 0 1px var(--border);
}
.pr-cockpit.compact {
  display: grid;
  grid-template-columns: 31px minmax(0,1fr) auto;
  gap: 10px;
  align-items: center;
  margin-top: 9px;
  padding: 10px 11px;
  border: 0;
  border-radius: 12px;
  background: color-mix(in srgb,var(--surface-muted) 75%,transparent);
  box-shadow: inset 0 0 0 1px color-mix(in srgb,var(--border) 82%,transparent);
}
.pr-cockpit.compact::before { display: none; }
.pr-compact-icon {
  display: grid;
  place-items: center;
  width: 31px;
  height: 31px;
  border-radius: 10px;
  color: var(--info);
  background: var(--info-soft);
  font-size: 13px;
  font-weight: 800;
}
.pr-compact-icon.blocked { color: var(--danger); background: var(--danger-soft); }
.pr-compact-icon.waiting { color: var(--warning); background: var(--warning-soft); }
.pr-compact-icon.ready { color: var(--success); background: var(--success-soft); }
.pr-compact-copy { min-width: 0; display: grid; gap: 2px; }
.pr-compact-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; }
.pr-compact-copy span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--muted); font-size: 10px; }
.pr-compact-status { display: grid; justify-items: end; gap: 5px; color: var(--muted); font-size: 9px; font-weight: 650; }
.pr-compact-dots { display: flex; gap: 4px; }
.pr-compact-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--info); }
.pr-compact-dot.ready { background: var(--success); }
.pr-compact-dot.blocked { background: var(--danger); }
.pr-compact-dot.waiting { background: var(--warning); }
.pr-compact-dot.neutral { background: var(--faint); }
.task.compact {
  padding: 14px 15px 13px 19px;
  border-radius: 15px;
  box-shadow: none;
  background: color-mix(in srgb,var(--surface-raised) 94%,var(--accent-soft));
}
.task.compact:hover { transform: none; box-shadow: none; }
.task.compact .task-meta { margin-top: 8px; }
.task.compact .github-list { margin-top: 9px; }
.task.compact .github-item { min-height: 34px; padding: 7px 9px; border-radius: 10px; }
.task.compact .github-item-label { font-size: 10px; }
footer { margin-top: 28px; padding: 18px 0; color: var(--muted); font-size: 11px; line-height: 1.55; border-top: 1px solid var(--border); }
@media (max-width: 1240px) {
  .dashboard-workspace { grid-template-columns: 1fr; }
  .dashboard-secondary { position: static; grid-template-columns: repeat(2,minmax(0,1fr)); }
  .dashboard-secondary .dashboard-column-heading { grid-column: 1 / -1; }
}
@media (max-width: 1120px) {
  .summary-grid, .secondary-metric-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
}
@media (max-width: 700px) {
  .dashboard-header { position: static; margin: 0 0 18px; padding: 0; background: none; backdrop-filter: none; }
  .dashboard-controls { grid-template-columns: 1fr; }
  .filter-bar { overflow-x: auto; flex-wrap: nowrap; }
  .section-head { align-items: flex-start; flex-direction: column; }
  .plan-actions { justify-content: flex-start; }
  .task-head { align-items: flex-start; }
  .priority-pill, .priority-control { margin-top: 1px; }
  .plan-item-title-row { align-items: flex-start; }
  .plan-item-actions form { margin-left: 0; }
  .github-item { grid-template-columns: minmax(0,1fr) auto; }
  .github-item-badges { grid-column: 1 / -1; }
  .dashboard-secondary { grid-template-columns: 1fr; }
  .dashboard-secondary .dashboard-column-heading { grid-column: auto; }
  .inline-editor, .note-editor, .action-editor, .comment-editor { grid-template-columns: 1fr; }
}
@media (max-width: 440px) { .summary-grid, .secondary-metric-grid { grid-template-columns: 1fr; } }
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



def _meta_chip(label: str, tone: str = "neutral", title: str | None = None) -> str:
    title_attr = f' title="{escape(title, quote=True)}"' if title else ""
    return f'<span class="meta-chip tone-{escape(tone, quote=True)}"{title_attr}>{escape(label)}</span>'


def _task_meta_html(item: TaskItem, today: date) -> str:
    chips: list[str] = []
    if item.status:
        tone = "danger" if item.github_kind == "authored_pr" else ("warning" if item.action_state == "waiting" else "info")
        chips.append(_meta_chip(item.status, tone, "Current status"))

    if item.age_basis == "status" and item.status:
        age = "Today" if item.age_working_days == 0 else _working_day_phrase(item.age_working_days)
        chips.append(_meta_chip(age, "neutral", f"Time in {item.status}"))
    else:
        chips.append(_meta_chip(_age_description(item), "neutral", "Task age"))

    due = _due_description(item, today)
    if due:
        if item.due_on and item.due_on <= today:
            tone = "danger"
        elif item.due_on and working_days_until(today, item.due_on) <= 1:
            tone = "warning"
        else:
            tone = "info"
        chips.append(_meta_chip(due, tone, "Due date"))

    if item.project:
        chips.append(_meta_chip(item.project, "neutral", "Project or repository"))
    if item.unread_updates:
        chips.append(_meta_chip(f"{item.unread_updates} new", "accent", "Unread updates"))
    if item.manual_priority:
        chips.append(_meta_chip(f"Manual: {item.manual_priority.title()}", "accent", "Manual priority override"))
    return f'<div class="task-meta">{"".join(chips)}</div>' if chips else ""


def _task_context_html(item: TaskItem) -> str:
    rows: list[str] = []
    for note in item.notes:
        rows.append(f'<li>{escape(note)}</li>')
    if item.rule_matches:
        rows.append(f'<li>Matched rule: {escape(item.rule_matches[-1])}</li>')
    if not rows:
        return ""
    return f'<details class="context-details"><summary>Context <span>{len(rows)}</span></summary><ul>{"".join(rows)}</ul></details>'


def _task_quick_actions(item: TaskItem) -> str:
    links: list[str] = []
    if item.url:
        label = "Open in Asana" if item.source == "asana" else "Open on GitHub"
        links.append(f'<a class="task-quick-link" href="{escape(item.url, quote=True)}">{label}<span aria-hidden="true">↗</span></a>')
    visible = _visible_github_links(item)
    if item.source == "asana" and visible:
        links.append(f'<a class="task-quick-link" href="{escape(visible[0].url, quote=True)}">Open linked PR<span aria-hidden="true">↗</span></a>')
    return f'<div class="task-quick-actions">{"".join(links)}</div>' if links else ""


def _task_secondary_html(item: TaskItem) -> str:
    content = (
        _task_context_html(item)
        + _timeline_html(item)
        + _relations_html(item)
        + _comments_html(item)
        + _asana_write_controls(item)
        + _task_controls(item)
    )
    if not content:
        return ""
    return f'<details class="task-details"><summary>Details &amp; actions <span>Expand</span></summary><div class="task-details-body">{content}</div></details>'



def _task_search_attributes(item: TaskItem, today: date) -> str:
    repositories = sorted({f"{link.owner}/{link.repo}" for link in item.github_links})
    pr_numbers = sorted({str(link.number) for link in item.github_links if link.kind == "pull"})
    github_text: list[str] = []
    flags = {item.source, item.action_state, item.priority}
    if item.unread_updates:
        flags.add("unread")
    if item.is_focused:
        flags.add("focused")
    if item.due_on and item.due_on < today:
        flags.add("overdue")
    if item.stale_waiting:
        flags.add("stale")
    if any(not dependency.completed for dependency in item.dependencies):
        flags.add("blocked")
    if item.github_kind == "review_request":
        flags.add("review")
    for link in item.github_links:
        github_text.extend([
            link.title or "",
            *link.action_reasons,
            *link.failed_checks,
            *link.pending_reviewers,
        ])
        reasons = " ".join(link.action_reasons).casefold()
        if link.failed_checks or "check" in reasons or "failing" in reasons:
            flags.add("failing")
        if "changes requested" in reasons:
            flags.add("changes-requested")
        if "conflict" in reasons:
            flags.add("conflict")
    searchable = " ".join(
        value for value in [
            item.title,
            item.status or "",
            item.section or "",
            item.project or "",
            item.local_note,
            *item.notes,
            *repositories,
            *pr_numbers,
            *github_text,
        ] if value
    ).casefold()
    values = {
        "data-priority": item.priority,
        "data-status": (item.status or item.section or "").casefold(),
        "data-project": (item.project or "").casefold(),
        "data-repository": " ".join(repositories).casefold(),
        "data-pr": " ".join(pr_numbers),
        "data-source": item.source,
        "data-flags": " ".join(sorted(flags)),
        "data-search": searchable,
    }
    return " ".join(f'{name}="{escape(value, quote=True)}"' for name, value in values.items())

def _duration_label(start: datetime | None, end: datetime | None) -> str:
    if not start or not end:
        return ""
    seconds = max(0, int((end - start).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours, remainder = divmod(minutes, 60)
    return f"{hours}h {remainder}m" if remainder else f"{hours}h"


def _timestamp_label(value: datetime | None) -> str:
    if not value:
        return "Unknown"
    local = value.astimezone() if value.tzinfo else value
    return local.strftime("%a %d %b · %H:%M")


def _pr_gate_data(link: Any) -> list[tuple[str, str, str, bool]]:
    failed = sum(1 for check in link.checks if check.bucket == "fail")
    pending = sum(1 for check in link.checks if check.bucket == "pending")
    passed = sum(1 for check in link.checks if check.bucket == "pass")
    if failed:
        checks = ("Checks", f"{failed} failing · {passed} passed", "blocked", False)
    elif pending or link.checks_pending:
        checks = ("Checks", f"{pending or 1} running · {passed} passed", "waiting", False)
    elif link.checks:
        checks = ("Checks", f"{passed} passed", "ready", True)
    else:
        checks = ("Checks", "No checks reported", "neutral", True)

    if link.review_decision == "CHANGES_REQUESTED":
        reviews = ("Reviews", "Changes requested", "blocked", False)
    elif link.review_decision == "APPROVED":
        reviews = ("Reviews", f"{link.approvals or 1} approved", "ready", True)
    elif link.pending_reviewers:
        reviews = ("Reviews", f"{len(link.pending_reviewers)} pending", "waiting", False)
    else:
        reviews = ("Reviews", "Review required", "waiting", False)

    unresolved = len(link.unresolved_threads)
    conversations = (
        "Conversations",
        "All resolved" if unresolved == 0 else f"{unresolved} unresolved",
        "ready" if unresolved == 0 else "blocked",
        unresolved == 0,
    )

    if link.mergeable == "CONFLICTING" or link.merge_state_status == "DIRTY":
        merge = ("Merge", "Conflicts", "blocked", False)
    elif link.merge_state_status == "BEHIND":
        merge = ("Merge", "Behind base", "waiting", False)
    elif link.mergeable == "MERGEABLE":
        merge = ("Merge", "No conflicts", "ready", True)
    else:
        merge = ("Merge", "Calculating", "neutral", False)
    return [checks, reviews, conversations, merge]


def _pr_primary_issue(link: Any) -> str:
    if link.failed_checks:
        count = len(link.failed_checks)
        return f"{count} failing check{'s' if count != 1 else ''}"
    if link.review_decision == "CHANGES_REQUESTED":
        return "Changes requested"
    if link.unresolved_threads:
        count = len(link.unresolved_threads)
        return f"{count} unresolved conversation{'s' if count != 1 else ''}"
    if link.mergeable == "CONFLICTING" or link.merge_state_status == "DIRTY":
        return "Merge conflicts"
    if link.merge_state_status == "BEHIND":
        return f"Branch behind {link.base_ref_name or 'base'}"
    if link.checks_pending:
        return "Checks running"
    if link.pending_reviewers:
        count = len(link.pending_reviewers)
        return f"{count} review{'s' if count != 1 else ''} pending"
    if link.review_decision == "APPROVED" and link.mergeable == "MERGEABLE":
        return "Ready to merge"
    return "Pull request status"


def _pr_summary_parts(link: Any) -> list[str]:
    parts: list[str] = []
    if link.failed_checks:
        count = len(link.failed_checks)
        parts.append(f"{count} check{'s' if count != 1 else ''} failing")
    if link.review_decision == "CHANGES_REQUESTED":
        parts.append("Changes requested")
    unresolved = len(link.unresolved_threads)
    if unresolved:
        parts.append(f"{unresolved} unresolved conversation{'s' if unresolved != 1 else ''}")
    if link.mergeable == "CONFLICTING" or link.merge_state_status == "DIRTY":
        parts.append("Merge conflicts")
    elif link.merge_state_status == "BEHIND":
        parts.append(f"Branch behind {link.base_ref_name or 'base'}")
    if not parts and link.checks_pending:
        parts.append("Checks running")
    if not parts and link.pending_reviewers:
        count = len(link.pending_reviewers)
        parts.append(f"{count} review{'s' if count != 1 else ''} pending")
    if not parts and link.review_decision == "APPROVED" and link.mergeable == "MERGEABLE":
        parts.append("All merge gates ready")
    return parts


def _pr_action_groups(link: Any) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    your_actions: list[tuple[str, str]] = []
    waiting: list[tuple[str, str]] = []
    if link.failed_checks:
        names = ", ".join(link.failed_checks[:3])
        if len(link.failed_checks) > 3:
            names += f" +{len(link.failed_checks) - 3} more"
        failed_url = next((check.url for check in link.checks if check.bucket == "fail" and check.url), link.url)
        your_actions.append((f"Fix failed checks: {names}", failed_url))
    if link.unresolved_threads:
        count = len(link.unresolved_threads)
        thread_url = next((thread.url for thread in link.unresolved_threads if thread.url), link.url)
        your_actions.append((f"Address {count} unresolved review {'thread' if count == 1 else 'threads'}", thread_url))
    if link.mergeable == "CONFLICTING" or link.merge_state_status == "DIRTY":
        your_actions.append(("Resolve merge conflicts with the base branch", link.url))
    elif link.merge_state_status == "BEHIND":
        your_actions.append((f"Update the branch from {link.base_ref_name or 'the base branch'}", link.url))
    if link.review_decision == "CHANGES_REQUESTED":
        your_actions.append(("Push updates and re-request review", link.url))
    if link.pending_reviewers:
        reviewers = ", ".join("@" + name for name in link.pending_reviewers[:4])
        waiting.append((f"Review from {reviewers}", link.url))
    if link.checks_pending and not link.failed_checks:
        waiting.append(("Continuous integration to finish", link.url))
    if link.state == "MERGED" or link.merged_at:
        your_actions.append(("Update or complete the linked Asana task", link.url))
    elif link.state == "CLOSED" or link.closed_at:
        your_actions.append(("Confirm whether the linked Asana task should remain open", link.url))
    if not your_actions and not waiting and link.review_decision == "APPROVED" and link.mergeable == "MERGEABLE":
        waiting.append(("Ready to merge", link.url))
    return your_actions, waiting


def _check_detail_html(check: Any) -> str:
    bucket = str(check.bucket or "").casefold()
    icon = {"pass": "✓", "fail": "✕", "pending": "…", "cancel": "–", "skipping": "↷"}.get(bucket, "•")
    detail = check.summary or check.description or (check.workflow and f"Workflow: {check.workflow}") or ""
    duration = _duration_label(check.started_at, check.completed_at)
    meta = " · ".join(part for part in (str(check.state or "").replace("_", " ").title(), duration) if part)
    link_html = f'<a class="pr-detail-link" href="{escape(check.url, quote=True)}">Open check ↗</a>' if check.url else ""
    return (
        f'<div class="pr-check"><span class="pr-check-icon" aria-hidden="true">{icon}</span>'
        f'<div class="pr-detail-main"><strong>{escape(check.name)}</strong>'
        f'{f"<p>{escape(detail)}</p>" if detail else ""}</div>'
        f'<div>{f"<div class=\"pr-detail-meta\">{escape(meta)}</div>" if meta else ""}{link_html}</div></div>'
    )


def _review_detail_html(review: Any) -> str:
    state = str(review.state or "PENDING").upper()
    icon = {"APPROVED": "✓", "CHANGES_REQUESTED": "✕", "PENDING": "…", "COMMENTED": "💬", "DISMISSED": "–"}.get(state, "•")
    label = state.replace("_", " ").title()
    if review.requested and state != "PENDING":
        label += " · re-review pending"
    elif review.requested:
        label = "Review pending"
    body = f'<p>{escape(review.body)}</p>' if review.body else ""
    link_html = f'<a class="pr-detail-link" href="{escape(review.url, quote=True)}">Open review ↗</a>' if review.url else ""
    return (
        f'<div class="pr-review"><span class="pr-review-icon" aria-hidden="true">{icon}</span>'
        f'<div class="pr-detail-main"><strong>@{escape(review.reviewer)} · {escape(label)}</strong>{body}</div>'
        f'<div><div class="pr-detail-meta">{escape(_timestamp_label(review.submitted_at)) if review.submitted_at else ""}</div>{link_html}</div></div>'
    )


def _thread_detail_html(thread: Any) -> str:
    location = thread.path + (f":{thread.line}" if thread.line else "")
    link_html = f'<a class="pr-detail-link" href="{escape(thread.url, quote=True)}">Open comment ↗</a>' if thread.url else ""
    return (
        '<div class="pr-thread"><div>'
        f'<div class="pr-thread-location">{escape(location)}</div>'
        f'<div class="pr-detail-meta">@{escape(thread.author)} · {escape(_timestamp_label(thread.created_at))}</div>'
        f'<blockquote>{escape(thread.body)}</blockquote></div>{link_html}</div>'
    )


def _github_cockpit_html(link: Any, *, compact: bool = False) -> str:
    has_data = any((
        link.state,
        link.review_decision,
        link.checks,
        link.reviews,
        link.unresolved_threads,
        link.action_reasons,
        link.changed_files,
        link.commit_count,
    ))
    if not has_data:
        return ""

    gates = _pr_gate_data(link)
    ready = sum(1 for _, _, _, is_ready in gates if is_ready)
    if link.state == "MERGED" or link.merged_at:
        state_label, state_tone, state_icon = "Merged", "merged", "✓"
    elif link.state == "CLOSED" or link.closed_at:
        state_label, state_tone, state_icon = "Closed", "blocked", "×"
    elif link.action_reasons:
        state_label, state_tone, state_icon = "Blocked", "blocked", "!"
    elif link.checks_pending or link.pending_reviewers:
        state_label, state_tone, state_icon = "Waiting", "waiting", "…"
    else:
        state_label, state_tone, state_icon = "Ready", "ready", "✓"

    percent = int(ready / len(gates) * 100)
    meter = (
        '<div class="pr-gate-meter">'
        f'<span><strong>{ready}/{len(gates)}</strong> merge gates ready</span>'
        '<span class="pr-gate-track" aria-hidden="true">'
        f'<span class="pr-gate-fill {state_tone}" style="width:{percent}%"></span></span></div>'
    )
    summary_parts = _pr_summary_parts(link)
    summary = " · ".join(summary_parts) or "Status is up to date"

    if compact:
        dots = "".join(
            f'<span class="pr-compact-dot {tone}" title="{escape(label + ": " + detail, quote=True)}"></span>'
            for label, detail, tone, _ in gates
        )
        return (
            f'<div class="pr-cockpit compact {state_tone}">'
            f'<span class="pr-compact-icon {state_tone}" aria-hidden="true">{state_icon}</span>'
            '<div class="pr-compact-copy">'
            f'<strong>{escape(_pr_primary_issue(link))}</strong><span>{escape(summary)}</span></div>'
            f'<div class="pr-compact-status"><span>{ready}/{len(gates)} ready</span><span class="pr-compact-dots">{dots}</span></div>'
            '</div>'
        )

    head = (
        '<div class="pr-cockpit-head"><div class="pr-cockpit-title">'
        '<span class="pr-eyebrow">Pull request health</span>'
        f'<strong>Merge readiness</strong><span>{escape(summary)}</span>'
        f'</div><span class="pr-cockpit-state {state_tone}"><span aria-hidden="true">{state_icon}</span>{state_label}</span></div>'
    )

    gate_icons = {"ready": "✓", "blocked": "!", "waiting": "…", "neutral": "•"}
    gate_html = "".join(
        f'<div class="pr-gate {tone}"><span class="pr-gate-icon" aria-hidden="true">{gate_icons.get(tone, "•")}</span>'
        f'<div><strong>{escape(label)}</strong><span>{escape(detail)}</span></div></div>'
        for label, detail, tone, _ in gates
    )

    your_actions, waiting_actions = _pr_action_groups(link)
    groups: list[str] = []
    if your_actions:
        rows = "".join(
            f'<li><span>{escape(label)}</span><a href="{escape(url, quote=True)}">Open ↗</a></li>'
            for label, url in your_actions
        )
        groups.append(f'<div class="pr-next-group action"><strong>Your actions</strong><ul>{rows}</ul></div>')
    if waiting_actions:
        rows = "".join(
            f'<li><span>{escape(label)}</span><a href="{escape(url, quote=True)}">View ↗</a></li>'
            for label, url in waiting_actions
        )
        groups.append(f'<div class="pr-next-group waiting"><strong>Waiting on</strong><ul>{rows}</ul></div>')
    next_html = f'<div class="pr-next-grid">{"".join(groups)}</div>' if groups else ""

    check_rows = "".join(_check_detail_html(check) for check in link.checks)
    checks = (
        '<details class="pr-details"><summary><span>Checks</span>'
        f'<span class="pr-detail-count">{len(link.checks)}</span></summary><div class="pr-detail-body">'
        f'{check_rows or "<p class=\"subtle\">No detailed checks were reported.</p>"}</div></details>'
    )
    review_rows = "".join(_review_detail_html(review) for review in link.reviews)
    reviews = (
        '<details class="pr-details"><summary><span>Review progress</span>'
        f'<span class="pr-detail-count">{len(link.reviews)}</span></summary><div class="pr-detail-body">'
        f'{review_rows or "<p class=\"subtle\">No reviewer activity was reported.</p>"}</div></details>'
    )
    thread_rows = "".join(_thread_detail_html(thread) for thread in link.unresolved_threads[:8])
    more_threads = len(link.unresolved_threads) - 8
    if more_threads > 0:
        thread_rows += f'<p class="subtle">Plus {more_threads} more unresolved thread(s).</p>'
    threads = (
        '<details class="pr-details"><summary><span>Unresolved feedback</span>'
        f'<span class="pr-detail-count">{len(link.unresolved_threads)}</span></summary><div class="pr-detail-body">'
        f'{thread_rows or "<p class=\"subtle\">All review conversations are resolved.</p>"}</div></details>'
    )

    scope_chips = "".join((
        _meta_chip(f"{link.changed_files} files", "info"),
        _meta_chip(f"+{link.additions}", "success"),
        _meta_chip(f"−{link.deletions}", "danger"),
        _meta_chip(f"{link.commit_count} commits", "neutral"),
    ))
    file_list = "".join(f'<li>{escape(path)}</li>' for path in link.top_files)
    scope = (
        '<details class="pr-details"><summary><span>Change scope</span><span class="pr-detail-count">'
        f'{link.changed_files}</span></summary><div class="pr-detail-body">'
        f'<div class="pr-scope-summary">{scope_chips}</div>'
        f'{f"<ul class=\"pr-file-list\">{file_list}</ul>" if file_list else ""}</div></details>'
    )

    activity_rows = []
    if link.last_commit_at:
        activity_rows.append(("Last push", _timestamp_label(link.last_commit_at)))
    if link.last_review_at:
        activity_rows.append(("Last reviewer activity", _timestamp_label(link.last_review_at)))
    if link.updated_at:
        activity_rows.append(("PR updated", _timestamp_label(link.updated_at)))
    activity = (
        '<details class="pr-details"><summary><span>PR activity</span>'
        f'<span class="pr-detail-count">{len(activity_rows)}</span></summary><div class="pr-detail-body pr-activity">'
        + "".join(
            f'<div class="pr-activity-row"><strong>{escape(label)}</strong><span class="pr-detail-meta">{escape(value)}</span></div>'
            for label, value in activity_rows
        )
        + "</div></details>"
    ) if activity_rows else ""

    return (
        f'<section class="pr-cockpit {state_tone}">{head}<div class="pr-progress">{gate_html}{meter}</div>'
        f'{next_html}<div class="pr-detail-list">{checks}{reviews}{threads}{scope}{activity}</div></section>'
    )


def _priority_control(item: TaskItem, *, compact: bool = False) -> str:
    """Render a clearly interactive priority selector in live dashboards."""
    if not _ACTION_TOKEN or not _DASHBOARD_URL:
        return f'<span class="priority-pill tone-{item.priority}">{escape(item.priority.title())}</span>'

    selected = item.manual_priority or ""
    automatic_label = f"{item.priority.title()} · Auto"
    choices = [("", automatic_label), ("urgent", "Urgent"), ("high", "High"), ("normal", "Normal"), ("new", "New")]
    options = "".join(
        f'<option value="{value}"{(" selected" if selected == value else "")}>{escape(label)}</option>'
        for value, label in choices
    )
    manual_class = " has-manual" if item.manual_priority else ""
    compact_class = " compact-priority" if compact else ""
    manual_dot = '<span class="priority-manual-dot" aria-hidden="true"></span>' if item.manual_priority else ""
    label = f"Change priority for {item.title}"
    return (
        f'<form method="post" action="{escape(_DASHBOARD_URL + "/action", quote=True)}" '
        f'class="priority-control tone-{item.priority}{manual_class}{compact_class}" data-priority-form draggable="false" '
        f'title="{escape(label, quote=True)}">'
        f'<input type="hidden" name="token" value="{escape(_ACTION_TOKEN, quote=True)}">'
        f'<input type="hidden" name="key" value="{escape(item.key, quote=True)}">'
        '<input type="hidden" name="action" value="set_priority">'
        f'{manual_dot}<span class="priority-control-prefix">Priority</span>'
        f'<select name="priority" aria-label="{escape(label, quote=True)}" '
        f'data-effective-priority="{escape(item.priority, quote=True)}" draggable="false">{options}</select>'
        '<span class="priority-control-chevron" aria-hidden="true">⌄</span>'
        '</form>'
    )

def _task_card(item: TaskItem, today: date, badge: str | None = None, compact: bool = False) -> str:
    title = escape(item.title)
    if item.url:
        title = f'<a href="{escape(item.url, quote=True)}">{title}</a>'

    github_rows: list[str] = []
    cockpit_rows: list[str] = []
    for link in _visible_github_links(item):
        state_badges: list[str] = []
        if link.action_reasons:
            state_badges.append(_meta_chip(_pr_primary_issue(link), "danger"))
        else:
            if link.pending_reviewers:
                state_badges.append(_meta_chip(f"{len(link.pending_reviewers)} review pending", "warning"))
            if link.checks_pending:
                state_badges.append(_meta_chip("CI running", "info"))
            if link.approvals:
                state_badges.append(_meta_chip(f"{link.approvals} approved", "success"))
        github_rows.append(
            f'<a class="github-item" href="{escape(link.url, quote=True)}">'
            f'<span class="github-item-label">{escape(_github_link_label(link))}</span>'
            f'<span class="github-item-badges">{"".join(state_badges)}</span>'
            '<span class="github-item-arrow" aria-hidden="true">↗</span></a>'
        )
        cockpit = _github_cockpit_html(link, compact=compact)
        if cockpit:
            cockpit_rows.append(cockpit)

    badge_value = badge or ("Follow-up suggested" if item.stale_waiting else None)
    if item.rule_matches and not badge_value:
        badge_value = f"Rule: {item.rule_matches[-1]}"

    flags = f'<span class="task-flag">{escape(badge_value)}</span>' if badge_value else ""
    note_html = f'<p class="local-note"><strong>Private note</strong><span>{escape(item.local_note)}</span></p>' if item.local_note else ""
    focused = " focused" if item.is_focused else ""
    compact_class = " compact" if compact else ""
    draggable = ' draggable="true"' if compact else ""
    group = "github" if item.source == "github" else ("waiting" if item.action_state == "waiting" else "action")

    search_attributes = _task_search_attributes(item, today)
    return (
        f'<article class="task priority-{item.priority}{focused}{compact_class}" data-key="{escape(item.key, quote=True)}" '
        f'data-group="{group}" data-title="{escape(item.title.casefold(), quote=True)}" {search_attributes}{draggable}>'
        '<div class="task-head">'
        f'<div class="task-title-wrap"><h3>{title}</h3><div class="task-flags">{flags}</div></div>'
        f'{_priority_control(item)}</div>'
        f'{_task_meta_html(item, today)}{note_html}'
        + (f'<div class="github-list">{"".join(github_rows)}</div>' if github_rows else "")
        + "".join(cockpit_rows)
        + ("" if compact else _task_quick_actions(item))
        + ("" if compact else _task_secondary_html(item))
        + "</article>"
    )


def _summary_card(value: int, label: str, icon: str, tone: str, *, compact: bool = False) -> str:
    compact_class = " compact-metric" if compact else ""
    return (
        f'<button type="button" class="summary-card tone-{tone}{compact_class}" '
        f'data-filter="{escape(label.casefold(), quote=True)}" aria-label="Filter by {escape(label, quote=True)}">'
        f'<span class="metric-icon" aria-hidden="true">{icon}</span><strong>{value}</strong><span>{escape(label)}</span></button>'
    )


def _summary_cards(tasks: list[TaskItem], today: date) -> str:
    action, waiting, optional = split_tasks(tasks)
    reviews, authored = github_reviews(tasks), github_authored_prs(tasks)
    focus = [item for item in tasks if item.is_focused]
    unread = sum(item.unread_updates for item in tasks)
    primary_metrics = [
        (len(action), "Need action", "!", "danger"),
        (len(reviews), "Reviews", "✓", "info"),
        (len(waiting), "Waiting", "…", "warning"),
        (unread, "New updates", "•", "accent"),
    ]
    secondary_metrics = [
        (_due_now_count(action, today), "Due / overdue", "◷", "warning"),
        (len(authored), "PR blockers", "↗", "danger"),
        (len(optional), "Investigations", "?", "success"),
        (len(focus), "Plan items", "◎", "accent"),
    ]
    primary = "".join(_summary_card(*metric) for metric in primary_metrics)
    secondary = "".join(_summary_card(*metric, compact=True) for metric in secondary_metrics)
    return (
        '<section class="dashboard-metrics" aria-label="Work summary">'
        f'<div class="summary-grid primary-metrics">{primary}</div>'
        '<details class="more-metrics"><summary>More metrics '
        '<span>Due dates, PR blockers, investigations and plan size</span></summary>'
        f'<div class="secondary-metric-grid">{secondary}</div></details></section>'
    )


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


def _plan_meta_parts(item: TaskItem, today: date) -> list[str]:
    parts: list[str] = []
    if item.status:
        parts.append(item.status)
    if item.age_working_days is not None:
        day_label = "working day" if item.age_working_days == 1 else "working days"
        parts.append(f"{item.age_working_days} {day_label}")
    due = _due_description(item, today)
    if due:
        parts.append(due)
    if item.project:
        parts.append(item.project)
    if item.unread_updates:
        parts.append(f"{item.unread_updates} unread")
    return parts[:4]


def _plan_pr_summary(item: TaskItem) -> str:
    links = _visible_github_links(item)
    if not links:
        return ""
    link = links[0]
    label = f"PR #{link.number}" if link.number else "Linked GitHub item"
    state = ""
    tone = "success"
    if link.action_reasons:
        state = _pr_primary_issue(link)
        tone = "danger"
    elif link.pending_reviewers:
        state = f"{len(link.pending_reviewers)} review pending"
        tone = "warning"
    elif link.checks_pending:
        state = "CI running"
        tone = "warning"
    elif link.approvals:
        state = f"{link.approvals} approved"
    state_html = f'<span class="plan-pr-state {tone}">{escape(state)}</span>' if state else ""
    return (
        '<div class="plan-pr-summary">'
        f'<a href="{escape(link.url, quote=True)}">{escape(label)} · {escape(link.owner + "/" + link.repo)}</a>'
        f'{state_html}</div>'
    )


def _plan_task_card(
    item: TaskItem,
    today: date,
    *,
    candidate: PlanCandidate | None = None,
    draggable: bool = False,
) -> str:
    title = escape(item.title)
    if item.url:
        title = f'<a href="{escape(item.url, quote=True)}">{title}</a>'
    meta = "".join(f'<span>{escape(part)}</span>' for part in _plan_meta_parts(item, today))
    drag_attr = ' draggable="true"' if draggable else ""
    drag_handle = '<span class="plan-drag" title="Drag to reorder" aria-label="Drag to reorder">⋮⋮</span>' if draggable else ""
    details = f'<button type="button" class="plan-open-button" data-plan-open="{escape(item.key, quote=True)}">View details</button>'
    if candidate is not None:
        visible_reasons = list(candidate.reasons[:2])
        if len(candidate.reasons) > 2:
            visible_reasons.append(f"+{len(candidate.reasons) - 2} more")
        reasons = "".join(f'<span>{escape(reason)}</span>' for reason in visible_reasons)
        footer = (
            f'<div class="plan-reasons">{reasons}</div>'
            f'{details}{_post_form("toggle_focus", item.key, "Add to plan", "primary")}'
        )
    else:
        footer = f'{drag_handle}{details}'
    return (
        f'<article class="plan-item priority-{item.priority}" data-key="{escape(item.key, quote=True)}"{drag_attr}>'
        '<div class="plan-item-title-row">'
        f'<h3>{title}</h3>{_priority_control(item, compact=True)}</div>'
        f'<div class="plan-item-meta">{meta}</div>{_plan_pr_summary(item)}'
        f'<div class="plan-item-actions">{footer}</div></article>'
    )


def _plan_candidate_card(candidate: PlanCandidate, today: date) -> str:
    return _plan_task_card(candidate.task, today, candidate=candidate)


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
            f'<div id="focus-list">{"".join(_plan_task_card(item, today, draggable=True) for item in focus)}</div>'
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
        '<div class="dashboard-workspace">'
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
    demo_mode: bool = False,
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
    demo_badge = '<span class="demo-mode-badge">Demo data</span>' if demo_mode else ''
    auto_refresh = f'<script>setTimeout(()=>window.location.reload(),{max(1, refresh_minutes) * 60000});</script>' if dashboard_url else ""
    meta = _source_status_html(source_statuses) + _summary_panel(summaries)
    focus_html = _focus_section(tasks, now.date(), smart_plan_max_items, smart_plan_stale_waiting_limit)
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
<body><div class="app-shell">{sidebar}<main class="app-main"><div class="app-content"><header class="dashboard-header"><div class="page-header"><div class="page-title-wrap"><span class="eyebrow">Overview</span><div class="title-line"><h1>Your task digest</h1>{demo_badge}</div><p class="page-subtitle">{escape(subtitle)} · {now:%A, %d %B %Y at %H:%M}</p></div><div class="header-status">Auto-refresh every {max(1, refresh_minutes)} min</div></div></header>
{focus_html}
<div class="dashboard-controls"><div class="search-wrap"><input id="task-search" type="search" placeholder="Search tasks, PRs, projects…" aria-label="Search tasks"></div><div class="filter-bar"><button type="button" class="active" data-view="all">All</button><button type="button" data-view="action">Action</button><button type="button" data-view="github">GitHub</button><button type="button" data-view="waiting">Waiting</button><button type="button" data-view="unread">Updates</button></div></div>
<div class="search-helper"><span id="search-result-count" class="search-result-count">Showing all tasks</span><span class="search-examples">Try <button type="button" data-search-example="is:failing">is:failing</button><button type="button" data-search-example="is:waiting">is:waiting</button><button type="button" data-search-example="status:&quot;In Review&quot;">status:In Review</button><button type="button" data-search-example="repo:">repo:</button><button type="button" data-search-example="pr:">pr:</button><button type="button" id="reset-dashboard-state" class="reset-view">Reset view</button></span></div>
{_summary_cards(tasks, now.date())}{main_content}
<div id="toast" role="status" aria-live="polite"></div>
<footer>{len(action)} need action · {len(authored)} PR blocker(s) · {len(reviews)} review(s) · {len(issues)} assigned issue(s) · {len(mentions)} mention(s) · {len(waiting)} waiting · {len(optional)} investigation(s) · {snoozed} snoozed · {ignored} ignored. Draft tasks are hidden.</footer>
</div></main></div>
{command_palette_html()}
{command_palette_script((dashboard_url or "").rstrip("/"))}
<script>
const token={token!r};const base={base!r};
document.querySelectorAll('[data-nav-path]').forEach(link=>{{const path=link.dataset.navPath;const active=path==='/'?location.pathname==='/'||location.pathname.endsWith('task-digest.html'):location.pathname.startsWith(path);link.classList.toggle('active',active);if(active)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');}});
const search=document.getElementById('task-search');
const resultCount=document.getElementById('search-result-count');
const resetDashboardState=document.getElementById('reset-dashboard-state');
const allCards=[...document.querySelectorAll('.task')];
const uiStorage={{
  get(key){{try{{return localStorage.getItem(key)}}catch(_error){{return null}}}},
  set(key,value){{try{{localStorage.setItem(key,value)}}catch(_error){{}}}},
  remove(key){{try{{localStorage.removeItem(key)}}catch(_error){{}}}}
}};
const viewKey='taskDigest.ui.view';
const searchKey='taskDigest.ui.search';
const detailsKey='taskDigest.ui.details';
const scrollKey='taskDigest.ui.scroll:'+location.pathname;
let skipUiStateSave=false;
let view=uiStorage.get(viewKey)||sessionStorage.getItem('taskDigest.view')||'all';
search.value=uiStorage.get(searchKey)||sessionStorage.getItem('taskDigest.search')||'';
uiStorage.set(viewKey,view);uiStorage.set(searchKey,search.value);sessionStorage.removeItem('taskDigest.view');sessionStorage.removeItem('taskDigest.search');
function readDetailsState(){{try{{return JSON.parse(uiStorage.get(detailsKey)||'{{}}')}}catch(_error){{return {{}}}}}}
const detailsState=readDetailsState();
function persistentDetailsKey(details,index){{
  const taskKey=details.closest('.task')?.dataset.key||'';
  const sectionId=details.id||details.closest('[id]')?.id||'';
  const classes=[...details.classList].sort().join('.')||'details';
  const summary=(details.querySelector(':scope > summary')?.textContent||'').trim().replace(/\\s+/g,' ').slice(0,80);
  return [location.pathname,taskKey||sectionId||'page',classes,summary||index].join('|');
}}
document.querySelectorAll('details').forEach((details,index)=>{{
  const key=persistentDetailsKey(details,index);details.dataset.uiStateKey=key;
  if(Object.prototype.hasOwnProperty.call(detailsState,key))details.open=Boolean(detailsState[key]);
  details.addEventListener('toggle',()=>{{detailsState[key]=details.open;uiStorage.set(detailsKey,JSON.stringify(detailsState));}});
}});
if('scrollRestoration' in history)history.scrollRestoration='manual';
requestAnimationFrame(()=>requestAnimationFrame(()=>{{const y=Number(uiStorage.get(scrollKey));if(Number.isFinite(y)&&y>0)window.scrollTo({{top:y,left:0,behavior:'instant'}});}}));
window.addEventListener('beforeunload',()=>{{if(!skipUiStateSave)uiStorage.set(scrollKey,String(window.scrollY));}});
function tokenizeQuery(raw){{return (raw.match(/[^\\s:]+:"[^"]*"|"[^"]*"|\\S+/g)||[]).map(token=>token.replace(/^"|"$/g,''));}}
function includesValue(card,name,value){{return (card.dataset[name]||'').toLowerCase().includes(value.toLowerCase());}}
function matchesQuery(card,raw){{
  const tokens=tokenizeQuery(raw);
  const flags=new Set((card.dataset.flags||'').split(/\\s+/).filter(Boolean));
  const searchText=((card.dataset.search||'')+' '+card.textContent).toLowerCase();
  return tokens.every(token=>{{
    const separator=token.indexOf(':');
    if(separator>0){{
      const field=token.slice(0,separator).toLowerCase();
      const value=token.slice(separator+1).replace(/^"|"$/g,'').toLowerCase();
      if(field==='is')return !value||flags.has(value)||(value==='github'&&card.dataset.group==='github')||(value==='action'&&card.dataset.group==='action')||(value==='waiting'&&card.dataset.group==='waiting');
      if(field==='repo')return includesValue(card,'repository',value);
      if(field==='project')return includesValue(card,'project',value);
      if(field==='status')return includesValue(card,'status',value);
      if(field==='pr')return includesValue(card,'pr',value.replace(/^#/,''));
      if(field==='source')return includesValue(card,'source',value);
      if(field==='priority')return includesValue(card,'priority',value);
    }}
    return searchText.includes(token.toLowerCase());
  }});
}}
function viewMatches(card){{const flags=new Set((card.dataset.flags||'').split(/\\s+/).filter(Boolean));return view==='all'||view===card.dataset.group||(view==='unread'&&flags.has('unread'));}}
function setView(next){{view=next;uiStorage.set(viewKey,view);document.querySelectorAll('[data-view]').forEach(button=>button.classList.toggle('active',button.dataset.view===view));applyFilters();}}
function applyFilters(){{
  const query=search.value.trim();uiStorage.set(searchKey,query);
  allCards.forEach(card=>card.classList.toggle('hidden-by-filter',!(viewMatches(card)&&matchesQuery(card,query))));
  document.querySelectorAll('.work-section,.optional-section').forEach(section=>{{const cards=[...section.querySelectorAll('.task')];section.classList.toggle('hidden-by-filter',Boolean(cards.length&&cards.every(card=>card.classList.contains('hidden-by-filter'))));}});
  const visibleKeys=new Set(allCards.filter(card=>!card.classList.contains('hidden-by-filter')).map(card=>card.dataset.key));
  const totalKeys=new Set(allCards.map(card=>card.dataset.key));
  resultCount.textContent=query||view!=='all'?`${{visibleKeys.size}} of ${{totalKeys.size}} task${{totalKeys.size===1?'':'s'}} shown`:`Showing all ${{totalKeys.size}} task${{totalKeys.size===1?'':'s'}}`;
}}
search.addEventListener('input',applyFilters);
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>setView(button.dataset.view)));
document.querySelectorAll('[data-search-example]').forEach(button=>button.addEventListener('click',()=>{{search.value=button.dataset.searchExample||'';search.focus();applyFilters();}}));
resetDashboardState?.addEventListener('click',()=>{{skipUiStateSave=true;[viewKey,searchKey,detailsKey,scrollKey].forEach(key=>uiStorage.remove(key));sessionStorage.removeItem('taskDigest.view');sessionStorage.removeItem('taskDigest.search');location.reload();}});
document.addEventListener('keydown',event=>{{if(event.key==='/'&&!event.metaKey&&!event.ctrlKey&&!event.altKey&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)){{event.preventDefault();search.focus();search.select();}}}});
document.querySelectorAll('.summary-card').forEach(button=>button.addEventListener('click',()=>{{const label=button.dataset.filter||'';if(label.includes('waiting'))setView('waiting');else if(label.includes('review')||label.includes('pr'))setView('github');else if(label.includes('update'))setView('unread');else if(label.includes('action')||label.includes('due'))setView('action');else setView('all');}}));
document.querySelectorAll('[data-view]').forEach(button=>button.classList.toggle('active',button.dataset.view===view));
applyFilters();
const list=document.getElementById('focus-list');if(list){{let dragged=null;list.querySelectorAll('.plan-item').forEach(card=>{{card.addEventListener('dragstart',()=>{{dragged=card;card.classList.add('dragging')}});card.addEventListener('dragend',async()=>{{card.classList.remove('dragging');const keys=[...list.querySelectorAll('.plan-item')].map(x=>x.dataset.key);const body=new URLSearchParams({{token,action:'focus_order',keys:keys.join(',')}});await fetch(base+'/api/action',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body}});}});}});list.addEventListener('dragover',event=>{{event.preventDefault();const after=[...list.querySelectorAll('.plan-item:not(.dragging)')].find(el=>event.clientY<=el.getBoundingClientRect().top+el.offsetHeight/2);if(dragged){{if(after)list.insertBefore(dragged,after);else list.appendChild(dragged);}}}});}}
const toast=document.getElementById('toast');function showToast(message,error=false){{if(!toast)return;toast.textContent=message;toast.style.background=error?'var(--danger)':'var(--text)';toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),4000);}}
function revealCard(key,target='card'){{
  const cards=allCards.filter(card=>card.dataset.key===key);const card=cards.find(item=>!item.classList.contains('compact'))||cards[0];if(!card)return;
  search.value='';setView('all');
  let parent=card.parentElement;while(parent){{if(parent.tagName==='DETAILS')parent.open=true;parent=parent.parentElement;}}
  if(target==='note'){{card.querySelector('.task-details')?.setAttribute('open','');card.querySelector('.task-controls')?.setAttribute('open','');}}
  card.scrollIntoView({{behavior:'smooth',block:'center'}});card.classList.remove('palette-target');requestAnimationFrame(()=>card.classList.add('palette-target'));
  if(target==='note')setTimeout(()=>card.querySelector('textarea[name="note"]')?.focus(),450);
}}
document.querySelectorAll('[data-plan-open]').forEach(button=>button.addEventListener('click',()=>revealCard(button.dataset.planOpen||'')));
async function postDashboardAction(action,key=''){{
  const body=new URLSearchParams({{token,action,key}});const response=await fetch(base+'/api/action',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body}});const payload=await response.json();if(!response.ok)throw new Error(payload.error||'Action failed');showToast(String(payload.result||'Task Digest updated'));return payload;
}}
const palette=window.TaskDigestCommandPalette;
if(palette){{
  const uniqueCards=[...new Map(allCards.filter(card=>!card.classList.contains('compact')).map(card=>[card.dataset.key,card])).values()];
  const taskItems=uniqueCards.map(card=>({{id:'task:'+card.dataset.key,label:card.querySelector('h3')?.textContent.trim()||card.dataset.title,detail:[card.dataset.status,card.dataset.project,card.dataset.repository].filter(Boolean).join(' · '),keywords:(card.dataset.search||'')+' '+card.dataset.flags,icon:card.dataset.source==='github'?'GH':'A',group:'Tasks',run:()=>revealCard(card.dataset.key)}}));
  palette.replaceGroup('Tasks',taskItems);
  const pickerItems=handler=>uniqueCards.map(card=>({{id:'picker:'+card.dataset.key,label:card.querySelector('h3')?.textContent.trim()||card.dataset.title,detail:[card.dataset.status,card.dataset.project,card.dataset.repository].filter(Boolean).join(' · '),keywords:card.dataset.search||'',icon:card.dataset.source==='github'?'GH':'A',keepOpen:true,run:()=>handler(card)}}));
  const chooseNoteTask=()=>palette.setMode('note-task',pickerItems(card=>{{palette.close();revealCard(card.dataset.key,'note');}}),'Choose a task for a private note…');
  const chooseSnoozeTask=()=>palette.setMode('snooze-task',pickerItems(card=>{{const key=card.dataset.key;const title=card.querySelector('h3')?.textContent.trim()||card.dataset.title;palette.setMode('snooze-choice',[
    {{id:'snooze:1',label:'Until tomorrow',detail:title,icon:'1d',run:async()=>{{try{{await postDashboardAction('snooze_1',key);palette.close();setTimeout(()=>location.reload(),500);}}catch(error){{showToast(error.message,true);}}}}}},
    {{id:'snooze:3',label:'For 3 working days',detail:title,icon:'3d',run:async()=>{{try{{await postDashboardAction('snooze_3',key);palette.close();setTimeout(()=>location.reload(),500);}}catch(error){{showToast(error.message,true);}}}}}},
    {{id:'snooze:change',label:'Until the task changes',detail:title,icon:'↻',run:async()=>{{try{{await postDashboardAction('until_change',key);palette.close();setTimeout(()=>location.reload(),500);}}catch(error){{showToast(error.message,true);}}}}}}
  ],`Snooze ${{title}}…`); }}),'Choose a task to snooze…');
  palette.register([
    {{id:'dashboard:search',label:'Search tasks and pull requests',detail:'Use text or filters such as is:failing, status: and repo:',keywords:'find filter query',icon:'⌕',group:'Suggested',run:()=>{{search.focus();search.select();}}}},
    {{id:'dashboard:plan',label:"Open Today’s Plan",detail:'Jump to the ordered focus list',keywords:'focus smart plan today',icon:'◎',group:'Suggested',run:()=>document.getElementById('todays-plan')?.scrollIntoView({{behavior:'smooth',block:'start'}})}},
    {{id:'dashboard:failing',label:'Show pull requests with failing checks',detail:'Applies the is:failing smart filter',keywords:'ci tests checks broken github',icon:'!',group:'Suggested',run:()=>{{search.value='is:failing';setView('all');search.focus();}}}},
    {{id:'dashboard:note',label:'Add a private note to a task…',detail:'Choose a task, then jump to its local note editor',keywords:'annotate context memo',icon:'✎',group:'Actions',keepOpen:true,run:chooseNoteTask}},
    {{id:'dashboard:snooze',label:'Snooze a task…',detail:'Hide until tomorrow, for three workdays, or until it changes',keywords:'later defer hide',icon:'◷',group:'Actions',keepOpen:true,run:chooseSnoozeTask}},
    {{id:'dashboard:refresh',label:'Refresh task data',detail:'Reload Asana and GitHub now',keywords:'sync reload update',icon:'↻',group:'Actions',run:async()=>{{try{{await postDashboardAction('refresh');setTimeout(()=>location.reload(),400);}}catch(error){{showToast(error.message,true);}}}}}},
    {{id:'dashboard:action',label:'Show tasks that need action',detail:'Filter the dashboard to actionable work',keywords:'do active',icon:'✓',group:'Filters',run:()=>setView('action')}},
    {{id:'dashboard:waiting',label:'Show work waiting on others',detail:'Filter the dashboard to waiting items',keywords:'blocked pending',icon:'◷',group:'Filters',run:()=>setView('waiting')}},
    {{id:'dashboard:github',label:'Show GitHub work',detail:'Reviews, pull requests, issues and mentions',keywords:'pr review issue mention',icon:'GH',group:'Filters',run:()=>setView('github')}},
    {{id:'dashboard:updates',label:'Show unread updates',detail:'Tasks with new comments or state changes',keywords:'comments unread new',icon:'•',group:'Filters',run:()=>setView('unread')}},
    {{id:'dashboard:reset-view',label:'Reset dashboard view',detail:'Clear search, filters, expanded panels and saved scroll position',keywords:'clear restore default layout state',icon:'↺',group:'Actions',run:()=>resetDashboardState?.click()}}
  ]);
}}
document.querySelectorAll('[data-priority-form]').forEach(form=>{{
  const select=form.querySelector('select[name="priority"]');if(!select)return;
  ['pointerdown','mousedown','touchstart'].forEach(name=>select.addEventListener(name,event=>event.stopPropagation(),{{passive:true}}));
  select.addEventListener('change',async()=>{{
    const previous=select.dataset.previousValue??select.defaultValue;select.disabled=true;form.classList.add('is-saving');
    try{{
      const body=new URLSearchParams(new FormData(form));
      const response=await fetch(base+'/api/action',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body}});
      const payload=await response.json();if(!response.ok)throw new Error(payload.error||'Priority update failed');
      select.dataset.previousValue=select.value;showToast(select.value?`Priority set to ${{select.options[select.selectedIndex].text}}`:'Automatic priority restored');
      setTimeout(()=>window.location.reload(),450);
    }}catch(error){{select.value=previous;select.disabled=false;form.classList.remove('is-saving');showToast(error.message||String(error),true);}}
  }});
  select.dataset.previousValue=select.value;
}}));
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
