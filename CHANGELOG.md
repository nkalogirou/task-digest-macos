# Changelog

All notable changes to Task Digest are documented here.

The project follows semantic versioning for public releases.

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
