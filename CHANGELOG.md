# Changelog

All notable changes to Task Digest are documented here.

The project follows semantic versioning for public releases.

## [1.0.20] - 2026-07-27

### Fixed

- Ship the GitHub PR cockpit model and client changes as a cumulative update so incremental installations cannot end up with a new renderer and an older `GitHubLink` model.
- Restore detailed check enrichment, including failed-check names, for repositories updated through the patch series.
- Add a regression test covering the detailed PR cockpit fields on `GitHubLink`.

## [1.0.19] - 2026-07-27

### Fixed

- Update the PR cockpit rendering test to match the compact merge-readiness label introduced in v1.0.16.
- Prevent a stale test expectation from reporting a false failure after applying cumulative UI patches.

## [1.0.18] - 2026-07-27

### Changed

- Make the inline priority selector visibly interactive with a persistent Priority label and dropdown chevron.
- Remove the duplicated priority editor from Actions & notes so priority is changed in one place only.
- Replace full task cards in Today’s Plan with short, purpose-built plan rows.
- Limit smart-plan reasons, collapse GitHub state into one compact PR line, and keep full cockpit details in the main work queue.
- Add View details controls that jump from a plan row to the complete task card.

## [1.0.17] - 2026-07-27

### Added

- Add an accessible priority dropdown directly in every dashboard task-card header.
- Save manual priority overrides immediately without opening Details & actions.
- Include an Automatic option that restores computed priority while showing the current effective value.

### Changed

- Style the priority selector as the existing priority tag and reload after changes so sorting, metrics, and Today’s Plan stay consistent.

## [1.0.16] - 2026-07-24

### Changed

- Redesign the GitHub pull-request cockpit with calmer surfaces, semantic merge-gate icons, and clearer blocked, waiting, and ready states.
- Split pull-request guidance into Your actions and Waiting on so author work is visually distinct from reviewer or CI dependencies.
- Make cockpit actions directly link to the relevant failed check, unresolved review conversation, or pull request.
- Keep Today’s Plan lightweight with a compact PR-health strip instead of the complete detailed cockpit.
- Replace generic Action required labels with the most useful concrete blocker, such as changes requested, failing checks, or an outdated branch.
- Remove duplicated unread-update badges from task cards.

## [1.0.15] - 2026-07-24

### Added

- Add an in-dashboard pull-request cockpit for Asana-linked GitHub PRs.
- Show merge gates for CI, reviews, unresolved conversations, and merge conflicts.
- Derive a deterministic Next actions list from failed checks, review feedback, branch state, and reviewer progress.
- Display detailed CI states and failure summaries, reviewer progress, unresolved review-thread excerpts, change scope, and recent PR activity.
- Link directly to individual checks, reviews, and unresolved comments when GitHub provides a URL.

### Changed

- Include detailed GitHub blocker state in snooze-until-change fingerprints and evening change snapshots.
- Keep detailed PR enrichment best-effort so missing GraphQL/check permissions do not break the dashboard.

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
