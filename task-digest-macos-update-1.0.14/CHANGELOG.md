# Changelog

All notable changes to Task Digest are documented here.

The project follows semantic versioning for public releases.

## [1.0.14] - 2026-07-24

### Changed

- Clarify installation requirements and what the guided setup changes on macOS.
- Add separate paths for demo exploration, full local installation, and development.
- Explain how Task Digest differs from a conventional task list and what it intentionally does not replace.
- Add a concise public roadmap and improve README navigation and scanability.

## [1.0.12] - 2026-07-24

### Added

- Credential-free guided product tour for the sanitized demo dashboard.
- A dedicated demo-tour launcher and public recording guide.
- Keyboard navigation and accessible tour controls for presenting the core workflow.

## [1.0.11] - 2026-07-24

### Added

- Credential-free demo mode with realistic, sanitized Asana and GitHub sample data.
- Interactive demo dashboard on `127.0.0.1:8777` via `scripts/run_demo.sh`.
- Static demo report generation through `python -m task_digest --demo`.
- Visible Demo data badge and isolated demo state files for safe screenshots and product tours.

## [1.0.10] - 2026-07-24

### Added

- Preserve expanded task details, dashboard panels, and per-page scroll position across automatic refreshes.
- Add a Reset view control and command-palette action for restoring the default dashboard layout.

### Changed

- Persist dashboard search and work filters across browser and app restarts instead of only for the current tab session.
- Migrate existing session-only search and filter preferences automatically.

## [1.0.9] - 2026-07-24

### Added

- Add a global Command-K command palette for navigation and common dashboard actions.
- Search dashboard tasks and pull requests directly from the command palette.
- Add structured dashboard search filters for status, project, repository, PR number, source, priority, and states such as failing, waiting, overdue, focused, and unread.
- Add command-palette flows for private notes, snoozing, refresh, Today’s Plan, and common work filters.

### Changed

- Persist the current dashboard search and view filter for the browser session.
- Show a unique-result count and clickable smart-search examples beneath the dashboard search bar.

## [1.0.8] - 2026-07-24

### Changed

- Group sidebar destinations into Work, Organize, Review, and System sections.
- Rename the final navigation item to System status for clearer intent.
- Preserve the compact icon-only navigation layout on smaller windows.

## [1.0.6] - 2026-07-24

### Changed

- Redesign task cards with always-visible priority, status, age, due-date, project, and update badges.
- Present linked GitHub items as structured rows with compact live-status badges.
- Add clear Open in Asana, Open on GitHub, and Open linked PR actions.
- Move timelines, relationships, comments, notes, and write controls into one collapsed Details & actions area.

## [1.0.5] - 2026-07-24

### Fixed

- Make the dashboard-layout patch cumulative by including the automatic-backup date fix.
- Allow ignored local runtime files such as `.env`, logs, generated reports, and dashboard state to coexist with a public development checkout.
- Make the public-repository checker reject runtime files only when Git could publish them.

## [1.0.4] - 2026-07-24

### Changed

- Widen the dashboard content area for large displays.
- Add a responsive two-column workspace with the work queue on the left and GitHub, source health, summaries, and optional context on the right.
- Keep the dashboard single-column on narrower windows and mobile screens.

## [1.0.3] - 2026-07-24

### Fixed

- Make automatic daily backups use the requested date, preventing duplicate backups and date-dependent test failures.

## [1.0.2] - 2026-07-21

### Fixed

- Fixed native macOS builds with py2app 0.28.9+ by preventing project runtime dependencies from being passed as unsupported `install_requires` metadata.
- Removed the deprecated `setup_requires` app-build hook because py2app is installed explicitly before the build.
- Updated the project license metadata to the SPDX string format used by current setuptools.

## [1.0.1] - 2026-07-21

### Fixed

- First-run setup can now import the local `task_digest` package when the Asana workspace helper is executed directly.
- Setup exports the repository root through `PYTHONPATH` for all bundled helper scripts.

## [1.0.0] - 2026-07-21

### Added

- Local macOS menu-bar application and loopback dashboard.
- Asana task ingestion, comments, sections, status history, dependencies, and optional write actions.
- GitHub review requests, authored PR blockers, assigned issues, mentions, and linked PR status through GitHub CLI.
- Working-day priority, action/waiting classification, optional work, draft filtering, and visual rules.
- Smart Today’s Plan with drag-and-drop ordering.
- Scheduled morning and evening notifications and reports.
- Stand-up generator, daily/weekly summaries, activity timelines, history, and backups.
- Local notes, snooze, ignore, priority overrides, read markers, and relationship maps.
- Settings, diagnostics, repair controls, privacy safeguards, and public setup documentation.
