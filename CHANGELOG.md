# Changelog

All notable changes to Task Digest are documented here.

The project follows semantic versioning for public releases.

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

## 1.0.2 - 2026-07-21

### Fixed
- Fixed native macOS builds with py2app 0.28.9+ by preventing project runtime dependencies from being passed as unsupported `install_requires` metadata.
- Removed the deprecated `setup_requires` app-build hook because py2app is installed explicitly before the build.
- Updated the project license metadata to the SPDX string format used by current setuptools.
