# Architecture

## Runtime overview

Task Digest is a Python application with four main layers:

1. **Source clients** retrieve Asana and GitHub data.
2. **Normalization and enrichment** convert source objects into common `TaskItem` models.
3. **Decision logic** applies dependencies, classification, priority, user rules, snoozes, and local overrides.
4. **Presentation and automation** render the dashboard/reports, menu bar, notifications, history, and backups.

## Key modules

| Module | Responsibility |
|---|---|
| `asana_client.py` | Asana tasks, stories, comments, sections, custom fields, dependencies, and write actions |
| `github_client.py` | Review requests, authored PR blockers, assigned issues, mentions, and linked PR enrichment |
| `models.py` | Shared normalized models |
| `enrichment.py` | Action/waiting classification and linked context |
| `priority.py` | Working-day age and automatic priority |
| `rules.py` | Ordered user-defined rule engine |
| `relationships.py` | Dependency relationship maps and upstream “Start here” selection |
| `plan.py` | Smart Today’s Plan recommendations |
| `dashboard.py` / `ui.py` | Local HTTP server, routes, actions, and HTML UI |
| `menubar.py` / `app.py` | macOS menu-bar application and embedded dashboard process |
| `state.py`, `workspace.py`, `preferences.py` | Local snapshots, notes, focus, read markers, snooze, and ignore state |
| `journal.py`, `standup.py` | Daily/weekly activity and stand-up generation |
| `backup.py` | Sanitized local backup and restore |
| `diagnostics.py` | Service, authentication, and log health |

## Native app and scheduling

`setup_app.py` uses py2app to build `Task Digest.app`. A user Launch Agent starts it at login. A separate calendar Launch Agent invokes `scripts/run_digest.sh` at the configured weekday times.

The app bundle is created locally for the architecture of the Python interpreter used to build it and is ad-hoc signed. It is not a prebuilt or notarized distribution.

## Local HTTP dashboard

The dashboard uses Python’s local HTTP server components and binds to `127.0.0.1` by default. Mutating dashboard actions require a locally generated action token.

## State model

Tracked source code is separate from local runtime data:

```text
state/digest_state.json       morning/evening comparison snapshot
state/task_preferences.json   snooze and ignore preferences
state/workspace.json          notes, focus order, overrides, read markers, timeline
state/activity_log.json       daily/weekly journal
state/task_rules.json         visual rules
```

All of these are ignored by Git and included in sanitized local backups where appropriate.
