from __future__ import annotations

from html import escape


NAV_ITEMS = (
    ("/", "Overview", "overview"),
    ("/standup", "Stand-up", "standup"),
    ("/history", "History", "history"),
    ("/backups", "Backups", "backups"),
    ("/hidden", "Hidden", "hidden"),
    ("/rules", "Rules", "rules"),
    ("/relationships", "Relationships", "relationships"),
    ("/settings", "Settings", "settings"),
    ("/system", "System", "system"),
)


_ICON_PATHS = {
    "overview": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "standup": '<path d="M12 3v18M7 7h7.5a3.5 3.5 0 0 1 0 7H9.5a3.5 3.5 0 0 0 0 7H17"/>',
    "history": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2M3 12H1"/>',
    "backups": '<path d="M12 3v12M7.5 10.5 12 15l4.5-4.5M4 19h16"/>',
    "hidden": '<path d="M3 12s3.2-6 9-6 9 6 9 6-3.2 6-9 6-9-6-9-6Z"/><path d="m4 4 16 16"/>',
    "rules": '<path d="M4 7h10M18 7h2M4 17h2M10 17h10M14 5v4M6 15v4"/>',
    "relationships": '<circle cx="12" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="19" r="2"/><path d="M12 7v5M12 12 6 17M12 12l6 5"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2H10v-.2a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/>',
    "system": '<circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/>',
}


def icon_svg(name: str) -> str:
    path = _ICON_PATHS.get(name, _ICON_PATHS["overview"])
    return (
        '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>'
    )


def navigation_html(base: str = "", active_path: str | None = None) -> str:
    links: list[str] = []
    for path, label, icon in NAV_ITEMS:
        active = " active" if active_path == path else ""
        aria = ' aria-current="page"' if active else ""
        href = f"{base}{path}" if path != "/" else f"{base}/"
        links.append(
            f'<a class="app-nav-link{active}" href="{escape(href, quote=True)}" data-nav-path="{escape(path, quote=True)}"{aria}>'
            f'{icon_svg(icon)}<span>{escape(label)}</span></a>'
        )
    return '<nav class="app-nav" aria-label="Primary">' + "".join(links) + "</nav>"


def brand_html() -> str:
    return (
        '<a class="app-brand" href="/">'
        '<span class="brand-mark" aria-hidden="true">TD</span>'
        '<span class="brand-copy"><strong>Task Digest</strong><small>Personal work assistant</small></span>'
        '</a>'
    )


SHARED_CSS = r"""
:root {
  --bg: #f4f6fa;
  --surface: rgba(255,255,255,.88);
  --surface-solid: #ffffff;
  --surface-muted: #f7f8fb;
  --surface-raised: #ffffff;
  --text: #172033;
  --muted: #6d7585;
  --faint: #9299a7;
  --border: #e1e5ec;
  --border-strong: #cfd5df;
  --accent: #4f46e5;
  --accent-2: #7c3aed;
  --accent-soft: #eeedff;
  --accent-text: #ffffff;
  --success: #16835d;
  --success-soft: #e9f8f1;
  --warning: #a16207;
  --warning-soft: #fff7df;
  --danger: #c0344b;
  --danger-soft: #fff0f2;
  --info: #2563eb;
  --info-soft: #edf4ff;
  --shadow-sm: 0 1px 2px rgba(18,24,40,.04), 0 4px 12px rgba(18,24,40,.04);
  --shadow-md: 0 12px 30px rgba(18,24,40,.08);
  --radius-sm: 10px;
  --radius-md: 16px;
  --radius-lg: 22px;
  color-scheme: light;
}
@media(prefers-color-scheme:dark) {
  :root {
    --bg: #0e1118;
    --surface: rgba(24,28,38,.9);
    --surface-solid: #181c26;
    --surface-muted: #202531;
    --surface-raised: #1d2230;
    --text: #f3f5f9;
    --muted: #a1a9b8;
    --faint: #7d8594;
    --border: #2f3542;
    --border-strong: #414958;
    --accent: #8b82ff;
    --accent-2: #b084ff;
    --accent-soft: #29264e;
    --accent-text: #0d1020;
    --success: #6fd2aa;
    --success-soft: #19382d;
    --warning: #f0bf64;
    --warning-soft: #3c311c;
    --danger: #ff8fa1;
    --danger-soft: #43242b;
    --info: #8db6ff;
    --info-soft: #1e3150;
    --shadow-sm: none;
    --shadow-md: 0 18px 40px rgba(0,0,0,.28);
    color-scheme: dark;
  }
}
* { box-sizing: border-box; }
html { min-height: 100%; background: var(--bg); }
body {
  min-height: 100%;
  margin: 0;
  background:
    radial-gradient(circle at 85% -10%, color-mix(in srgb, var(--accent) 10%, transparent), transparent 30rem),
    radial-gradient(circle at 10% 5%, color-mix(in srgb, var(--accent-2) 7%, transparent), transparent 26rem),
    var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: none; }
button, input, textarea, select { font: inherit; }
button, .button, .action-link {
  appearance: none;
  border: 1px solid var(--border);
  background: var(--surface-solid);
  color: var(--text);
  border-radius: 11px;
  padding: 9px 13px;
  cursor: pointer;
  font-weight: 620;
  line-height: 1.15;
  transition: transform .16s ease, border-color .16s ease, background .16s ease, box-shadow .16s ease;
}
button:hover, .button:hover, .action-link:hover {
  border-color: var(--border-strong);
  background: var(--surface-muted);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}
button:active, .button:active, .action-link:active { transform: translateY(0); }
button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible, summary:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--accent) 28%, transparent);
  outline-offset: 2px;
}
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button.primary:hover { background: color-mix(in srgb, var(--accent) 88%, #000); border-color: transparent; }
button.danger { color: var(--danger); }
form { margin: 0; }
.app-shell { min-height: 100vh; display: grid; grid-template-columns: 248px minmax(0,1fr); }
.app-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  padding: 22px 16px 18px;
  border-right: 1px solid var(--border);
  background: color-mix(in srgb, var(--surface) 88%, transparent);
  backdrop-filter: blur(24px) saturate(1.25);
  display: flex;
  flex-direction: column;
  gap: 24px;
  z-index: 30;
}
.app-brand {
  display: flex;
  align-items: center;
  gap: 11px;
  color: var(--text);
  padding: 4px 6px;
}
.brand-mark {
  width: 39px;
  height: 39px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: -.02em;
  box-shadow: 0 8px 18px color-mix(in srgb, var(--accent) 25%, transparent);
}
.brand-copy { min-width: 0; display: grid; gap: 1px; }
.brand-copy strong { font-size: 15px; letter-spacing: -.01em; }
.brand-copy small { color: var(--muted); font-size: 11px; white-space: nowrap; }
.app-nav { display: grid; gap: 5px; }
.app-nav-link {
  display: flex;
  align-items: center;
  gap: 11px;
  min-height: 42px;
  padding: 9px 11px;
  border-radius: 12px;
  color: var(--muted);
  font-size: 14px;
  font-weight: 600;
  transition: color .16s ease, background .16s ease, transform .16s ease;
}
.app-nav-link:hover { color: var(--text); background: var(--surface-muted); }
.app-nav-link.active { color: var(--accent); background: var(--accent-soft); }
.nav-icon { width: 19px; height: 19px; flex: 0 0 auto; }
.sidebar-actions { margin-top: auto; display: grid; gap: 8px; }
.sidebar-actions button, .sidebar-actions .button { width: 100%; text-align: left; }
.sidebar-note {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.45;
  padding: 10px 11px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface-muted);
}
.app-main { min-width: 0; padding: 32px 36px 80px; }
.app-content { width: min(1480px, 100%); margin: 0 auto; }
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
  margin-bottom: 24px;
}
.page-title-wrap { min-width: 0; }
.eyebrow {
  display: block;
  margin-bottom: 7px;
  color: var(--accent);
  font-size: 11px;
  font-weight: 760;
  letter-spacing: .11em;
  text-transform: uppercase;
}
h1 { margin: 0; font-size: clamp(29px, 3vw, 38px); line-height: 1.08; letter-spacing: -.035em; }
h2 { letter-spacing: -.02em; }
.page-subtitle, .subtle, .lead { color: var(--muted); }
.page-subtitle { margin: 8px 0 0; font-size: 14px; line-height: 1.5; }
.page-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
.surface {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
code { background: var(--surface-muted); border: 1px solid var(--border); border-radius: 7px; padding: 2px 6px; }

.rule-list { display: grid; gap: 12px; margin: 20px 0; }
.rule-card { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 16px 17px; box-shadow: var(--shadow-sm); display: grid; gap: 10px; }
.rule-card.disabled { opacity: .58; }
.rule-card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.rule-card h3 { margin: 0; font-size: 15px; }
.rule-card .badge { flex: 0 0 auto; background: var(--surface-muted); border: 1px solid var(--border); border-radius: 999px; padding: 5px 8px; color: var(--muted); font-size: 10px; font-weight: 650; white-space: nowrap; }
.rule-card p { margin: 4px 0 0; color: var(--muted); font-size: 12px; line-height: 1.5; }
.rule-actions { display: flex; flex-wrap: wrap; gap: 7px; }
.rule-builder { background: var(--surface); border: 1px solid var(--border); border-radius: 18px; padding: 19px; box-shadow: var(--shadow-sm); }
.rule-builder-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 15px; }
.rule-builder .wide { grid-column: 1 / -1; }
.rule-builder label { display: grid; gap: 7px; color: var(--text); font-size: 12px; font-weight: 650; }
.rule-builder input, .rule-builder select { width: 100%; min-width: 0; min-height: 43px; border: 1px solid var(--border); background: var(--surface-solid); color: var(--text); border-radius: 11px; padding: 9px 11px; }
.rule-examples { display: grid; grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); gap: 10px; margin: 18px 0; }
.rule-example { background: var(--surface-muted); border: 1px solid var(--border); border-radius: 13px; padding: 13px; color: var(--muted); font-size: 12px; line-height: 1.45; }
.relationship-view { margin-top: 11px; border-top: 1px solid var(--border); padding-top: 10px; }
.relationship-view > summary { cursor: pointer; color: var(--muted); font-size: 12px; font-weight: 650; }
.relationship-callout { margin: 11px 0; background: var(--accent-soft); color: var(--text); border: 1px solid color-mix(in srgb,var(--accent) 20%,var(--border)); border-radius: 11px; padding: 10px 12px; font-size: 12px; }
.relationship-tree { display: grid; justify-items: stretch; gap: 8px; padding: 3px 0 5px; }
.relation-lane { display: grid; grid-template-columns: 92px minmax(0,1fr); align-items: start; gap: 10px; }
.lane-label { color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .08em; padding-top: 11px; }
.relation-nodes { display: grid; gap: 7px; }
.relation-node { background: var(--surface-muted); border: 1px solid var(--border); border-radius: 12px; padding: 10px 12px; display: grid; gap: 3px; }
.relation-node strong { font-size: 12px; }
.relation-node.current { background: var(--info-soft); border-color: color-mix(in srgb,var(--info) 28%,var(--border)); }
.relation-node.recommended { box-shadow: inset 4px 0 0 var(--accent); }
.relation-node.done { opacity: .55; }
.relation-role { color: var(--muted); font-size: 9px; text-transform: uppercase; letter-spacing: .07em; }
.relation-arrow { color: var(--faint); padding-left: 122px; font-size: 15px; }
.relation-empty { color: var(--muted); font-size: 12px; padding: 10px 12px; border: 1px dashed var(--border); border-radius: 12px; }
.relationship-page-grid { display: grid; gap: 14px; margin-top: 18px; }
.relationship-page-card { background: var(--surface); border: 1px solid var(--border); border-radius: 18px; padding: 17px; box-shadow: var(--shadow-sm); }
.relationship-page-card h3 { margin: 0; font-size: 16px; }
.relationship-page-card > p { color: var(--muted); font-size: 12px; margin: 5px 0 0; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; animation: none !important; }
}
@media (max-width: 920px) {
  .app-shell { display: block; }
  .app-sidebar {
    position: sticky;
    height: auto;
    top: 0;
    padding: 10px 14px;
    border-right: 0;
    border-bottom: 1px solid var(--border);
    flex-direction: row;
    align-items: center;
    gap: 12px;
    overflow-x: auto;
  }
  .app-brand { padding: 0; flex: 0 0 auto; }
  .brand-copy { display: none; }
  .brand-mark { width: 34px; height: 34px; border-radius: 10px; }
  .app-nav { display: flex; gap: 4px; }
  .app-nav-link { min-height: 36px; padding: 8px 9px; white-space: nowrap; }
  .app-nav-link span { display: none; }
  .sidebar-actions, .sidebar-note { display: none; }
  .app-main { padding: 24px 18px 64px; }
}
@media (max-width: 700px) {
  .rule-builder-grid { grid-template-columns: 1fr; }
  .rule-builder .wide { grid-column: auto; }
  .relation-lane { grid-template-columns: 1fr; gap: 4px; }
  .lane-label { padding-top: 0; }
  .relation-arrow { padding-left: 18px; }
}
@media (max-width: 620px) {
  .page-header { align-items: stretch; flex-direction: column; gap: 14px; }
  .page-actions { justify-content: flex-start; }
  .app-main { padding-inline: 14px; }
}
"""


SIMPLE_PAGE_CSS = SHARED_CSS + r"""
.page-card, .history, .settings-group, .system-card, .hidden-card, .backup-card, .log-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-sm);
}
.history { list-style: none; margin: 0; padding: 8px; border-radius: var(--radius-lg); }
.history li { border-bottom: 1px solid var(--border); }
.history li:last-child { border-bottom: 0; }
.history a { display: block; padding: 13px 15px; border-radius: 11px; color: var(--text); }
.history a:hover { background: var(--surface-muted); color: var(--accent); }
.hidden-card { border-radius: var(--radius-md); padding: 16px 18px; margin: 10px 0; display: grid; gap: 7px; }
.hidden-card span { color: var(--muted); font-size: 13px; }
.system-summary, .system-grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); gap: 12px; margin: 18px 0 28px; }
.system-summary article, .system-card { border-radius: var(--radius-md); padding: 17px; display: flex; justify-content: space-between; gap: 14px; align-items: center; }
.system-summary article { display: grid; }
.system-summary strong { font-size: 14px; }
.system-summary span, .system-card span { display: block; color: var(--muted); font-size: 12px; margin-top: 5px; line-height: 1.45; }
.system-card.ok { box-shadow: inset 4px 0 0 var(--success), var(--shadow-sm); }
.system-card.warning { box-shadow: inset 4px 0 0 var(--warning), var(--shadow-sm); }
.system-actions { display: flex; flex-wrap: wrap; gap: 9px; margin: 18px 0 30px; }
.log-panel { border-radius: var(--radius-md); padding: 14px 16px; margin: 10px 0; }
.log-panel summary { cursor: pointer; font-weight: 680; }
pre { white-space: pre-wrap; word-break: break-word; background: var(--surface-muted); border: 1px solid var(--border); border-radius: 12px; padding: 14px; max-height: 360px; overflow: auto; font-size: 12px; }
.lead { max-width: 780px; line-height: 1.55; }
.settings-form { display: grid; gap: 15px; margin-top: 24px; }
.settings-group { border-radius: var(--radius-lg); overflow: hidden; }
.settings-group > summary { cursor: pointer; padding: 18px 20px; font-weight: 720; list-style: none; display: grid; grid-template-columns: auto 1fr; column-gap: 12px; align-items: center; }
.settings-group > summary::-webkit-details-marker { display: none; }
.settings-group > summary::before { content: "›"; font-size: 22px; grid-row: 1 / span 2; align-self: center; color: var(--muted); transition: transform .15s ease; }
.settings-group[open] > summary::before { transform: rotate(90deg); }
.settings-group > summary > span { font-size: 16px; }
.settings-group > summary > small { font-weight: 450; color: var(--muted); font-size: 12px; margin-top: 3px; }
.settings-body { padding: 20px; border-top: 1px solid var(--border); background: color-mix(in srgb, var(--surface-solid) 75%, transparent); }
.settings-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 20px 18px; }
.settings-grid + .settings-grid, .settings-grid + .switch-list { margin-top: 20px; }
.settings-grid-wide { grid-template-columns: 1fr; }
.setting-field { display: grid; gap: 8px; min-width: 0; color: var(--text); font-size: 14px; }
.setting-field > span { font-weight: 680; }
.setting-field small, .setting-switch small, .settings-save span, .settings-note { color: var(--muted); font-size: 12px; line-height: 1.45; }
.setting-field input {
  display: block; width: 100%; min-width: 0; min-height: 44px;
  border: 1px solid var(--border); border-radius: 12px; background: var(--surface-solid); color: var(--text); padding: 10px 12px; outline: none;
}
.setting-field input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in srgb,var(--accent) 20%,transparent); }
.switch-list { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 11px; }
.setting-switch { display: flex; gap: 12px; align-items: flex-start; background: var(--surface-muted); border: 1px solid var(--border); border-radius: 13px; padding: 14px 15px; min-width: 0; }
.setting-switch input { margin-top: 3px; accent-color: var(--accent); }
.setting-switch span { display: grid; gap: 4px; min-width: 0; }
.settings-nested { margin-top: 20px; border-top: 1px solid var(--border); padding-top: 15px; }
.settings-nested summary { cursor: pointer; font-weight: 680; padding: 4px 0 10px; }
.settings-note { background: var(--info-soft); border: 1px solid color-mix(in srgb,var(--info) 20%,var(--border)); border-radius: 12px; padding: 13px 14px; margin: 20px 0 0; }
.settings-save { position: sticky; bottom: 14px; display: flex; align-items: center; justify-content: space-between; gap: 14px; background: color-mix(in srgb,var(--surface-solid) 88%,transparent); backdrop-filter: blur(18px); border: 1px solid var(--border); box-shadow: var(--shadow-md); border-radius: 16px; padding: 13px 15px; z-index: 2; }
.standup-history { max-height: none; font-size: 14px; line-height: 1.65; background: var(--surface); border: 1px solid var(--border); }
.backup-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 14px; margin: 20px 0; color: var(--muted); }
.backup-card { border-radius: var(--radius-md); padding: 15px 17px; margin: 10px 0; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.backup-card > div:first-child { display: grid; gap: 5px; }
.backup-card span { color: var(--muted); font-size: 12px; }
.backup-actions { display: flex; align-items: center; gap: 8px; }
.backup-actions form { margin: 0; }
@media (max-width: 700px) {
  .backup-toolbar, .backup-card { align-items: flex-start; flex-direction: column; }
  .settings-grid, .switch-list { grid-template-columns: 1fr; }
  .settings-save { align-items: flex-start; flex-direction: column; }
}
"""
