<p align="center">
  <img src="docs/assets/task-digest-banner.svg" alt="Task Digest — Your work, distilled" width="100%">
</p>

<p align="center">
  <img alt="macOS" src="https://img.shields.io/badge/macOS-13%2B-111827?logo=apple&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white">
  <img alt="Local first" src="https://img.shields.io/badge/local--first-127.0.0.1-7C3AED">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-10B981">
</p>

# Task Digest

**Task Digest is a private, local-first macOS work assistant that turns assigned Asana work and relevant GitHub activity into one prioritized daily dashboard.** It highlights what needs action, separates work that is waiting on others, builds a smart Today’s Plan, sends scheduled notifications, and keeps your notes, rules, snoozes, summaries, and history on your Mac.

<p align="center">
  <a href="#try-the-interface-with-demo-data">Try the demo</a> ·
  <a href="#choose-your-setup-path">Install locally</a> ·
  <a href="#what-task-digest-is-and-is-not">Understand the scope</a> ·
  <a href="#roadmap">View the roadmap</a>
</p>

<p align="center">
  <img src="docs/assets/dashboard-preview.svg" alt="Task Digest dashboard preview" width="100%">
</p>

## Why Task Digest?

Most task systems tell you everything that exists. Task Digest focuses on **what you should do next**.

It combines:

- assigned Asana tasks, statuses, due dates, comments, dependencies, and sections;
- GitHub review requests, assigned issues, mentions, and your pull requests that need action;
- live status for GitHub pull requests linked to Asana tasks;
- working-day age, blockers, due dates, manual priorities, and configurable rules;
- a menu-bar summary, dynamic local dashboard, stand-up generator, history, and backups.

The dashboard binds to `127.0.0.1`, the Asana token is stored in macOS Keychain, and GitHub access uses your existing `gh` authentication.

## Highlights

| Area | What it does |
|---|---|
| **Smart prioritization** | Uses due dates, working-day age, GitHub blockers, dependencies, and visual rules. |
| **Today’s Plan** | Suggests a compact daily plan that you can accept, edit, and drag into order. |
| **Command palette** | Press `⌘K` to navigate, search tasks and PRs, refresh, add notes, snooze work, or apply common filters. |
| **Action vs waiting** | Separates work you can act on from work waiting for reviewers, CI, deployment, or dependencies. |
| **GitHub awareness** | Tracks requested reviews, assigned issues, mentions, authored PR blockers, and linked PR status. |
| **Asana context** | Reads sections, custom status, comments, dependencies, dependents, due dates, and task history. |
| **Local controls** | Notes, priority overrides, snooze, ignore, follow-up suggestions, and unread markers stay local. |
| **Automation** | Weekday morning/evening notifications, menu-bar app, saved reports, stand-ups, and backups. |
| **Local-first security** | Loopback-only dashboard, Keychain credential storage, no hosted Task Digest service. |

## What Task Digest is and is not

| Capability | Task Digest | Typical task-list view |
|---|---:|---:|
| Runs entirely on your Mac | **Yes** | Varies |
| Combines Asana and selected GitHub work | **Yes** | Usually separate |
| Prioritizes by due date, age, blockers, dependencies, and rules | **Yes** | Usually limited |
| Separates actionable work from waiting work | **Yes** | Usually manual |
| Stores private notes, snoozes, focus order, and rules locally | **Yes** | Varies |
| Sends task data to a Task Digest cloud service | **No** | Not applicable |
| Replaces Asana or GitHub as the system of record | **No** | Not applicable |
| Provides multi-user collaboration or shared dashboards | **No** | Not currently |

Task Digest is best understood as a **personal decision layer** on top of Asana and GitHub. The source systems remain authoritative; Task Digest helps you decide what deserves attention now.

## How it works

```text
Asana API ───────────────┐
                         ├─> normalize → enrich → rules → priority → dashboard
GitHub CLI / GitHub API ─┘                              │
                                                       ├─> menu bar
Local state ────────────────────────────────────────────┼─> notifications
(notes, snoozes, rules, history, focus order)           └─> reports / stand-up
```

## Before you install

| Requirement | Required? | Why it is needed |
|---|---:|---|
| **macOS 13 or later** | Yes | Task Digest uses macOS Keychain, menu-bar APIs, notifications, and LaunchAgents. |
| **Python 3.11 or 3.12** | Yes for source installs | The guided setup creates an isolated virtual environment and builds the local app. |
| **Asana account + personal access token** | Yes for real task data | The token is stored in macOS Keychain, not committed to the repository. |
| **GitHub CLI (`gh`)** | Optional | Enables review requests, PR blockers, issues, mentions, and linked-PR status. |
| **Access to configured workspaces and repositories** | Yes | Task Digest can only read data your own accounts are allowed to access. |

> [!IMPORTANT]
> Task Digest is designed for **one person running it locally on one Mac**. It is not a hosted team service and it does not provide shared accounts, server-side synchronization, or centralized administration.

Asana recommends OAuth for distributed multi-user applications. This project uses a personal access token because it is a personal local tool.

## Choose your setup path

| Goal | Recommended path | Credentials required |
|---|---|---:|
| **Explore the interface first** | Run the sanitized demo or guided tour | No |
| **Install the complete local app** | Use `scripts/setup_local.sh` | Asana; GitHub optional |
| **Inspect or contribute to the code** | Use the development setup and run the dashboard directly | Only for live integrations |

<details>
<summary><strong>What the guided setup changes on your Mac</strong></summary>

The installer creates a project-local virtual environment, stores the Asana token in macOS Keychain, builds `~/Applications/Task Digest.app`, and installs user-level LaunchAgents for startup and weekday scheduling. It does not require root access and it does not install a hosted service.

</details>


## Try the interface with demo data

You can explore Task Digest before creating an Asana token or signing in to GitHub. Demo mode uses sanitized, built-in sample tasks and does not contact external services.

Start the interactive dashboard:

```bash
scripts/run_demo.sh
```

It opens at `http://127.0.0.1:8777` and includes sample Asana tasks, review requests, pull-request blockers, comments, dependencies, waiting work, and an optional investigation. A visible **Demo data** badge distinguishes it from a real workspace.

Start the guided product tour:

```bash
scripts/run_demo_tour.sh
```

The tour highlights Today’s Plan, structured search, workload metrics, task and pull-request context, waiting work, and the wider toolset. See [`docs/DEMO.md`](docs/DEMO.md) for public recording and screenshot guidance.

To generate a standalone HTML preview instead:

```bash
python -m task_digest --demo --open-report
```

Demo mode stores any temporary focus, note, or snooze changes in separate `state/demo_*` files. It never reads your Asana token or GitHub CLI credentials.

## Full local installation

### Step 1 — Clone the repository

```bash
git clone https://github.com/YOUR-USERNAME/task-digest-macos.git
cd task-digest-macos
```

### Step 2 — Install prerequisites

With Homebrew:

```bash
brew install python@3.12 gh
```

Optional notification action buttons:

```bash
brew install vjeantet/tap/alerter
```

### Step 3 — Run the guided setup

```bash
scripts/setup_local.sh
```

The setup wizard will:

1. create `.venv` and install dependencies;
2. copy `.env.example` to `.env`;
3. securely store your Asana token in macOS Keychain;
4. list your Asana workspaces and ask for the workspace GID;
5. authenticate GitHub CLI and ask which repositories to monitor;
6. run the tests;
7. build `~/Applications/Task Digest.app`;
8. install the login and weekday schedule agents.

When it finishes, open:

```text
http://127.0.0.1:8765
```

Or use the **Task Digest** item in the macOS menu bar.

> Prefer to understand every command? Follow the [manual setup guide](docs/SETUP.md).

## First-run checklist

After installation:

1. Open **System** and confirm Asana, GitHub, the app, and the scheduled digest are green.
2. Click **Test notification** and allow notifications in macOS System Settings if prompted.
3. Open **Settings** and review statuses, hidden sections, notification times, and repositories.
4. Keep **One-click Asana updates** disabled until you are comfortable with the dashboard.
5. Open **Rules** to tune how your workflow is classified.

## Main pages

| Page | Purpose |
|---|---|
| `/` | Dashboard, Today’s Plan, tasks, GitHub work, waiting work, and optional investigations |
| `/standup` | Generates editable short or detailed daily stand-up text |
| `/rules` | Visual priority, classification, visibility, and follow-up rules |
| `/relationships` | Dependency maps and recommended upstream “Start here” tasks |
| `/history` | Morning/evening reports and saved stand-ups |
| `/hidden` | Snoozed and ignored items |
| `/backups` | Create, download, and restore local backups |
| `/settings` | Manage routine configuration without editing `.env` |
| `/system` | Service health, authentication, logs, refresh, repair, and notification testing |

## Everyday use

Once installed, Terminal is normally unnecessary.

- Click the menu-bar item for a quick overview.
- Open the dashboard to accept or reorder Today’s Plan.
- Press **⌘K** anywhere to open the command palette; press **/** on the dashboard to focus search.
- Expand task cards for comments, dependencies, activity, local notes, and controls.
- Use **Snooze**, **Until change**, or **Ignore** to reduce noise.
- Use **Mark updates read** for Task Digest’s local unread tracking.
- Generate your stand-up from current and recent work.
- Use the 10:00 full digest and 17:30 change digest as daily checkpoints.

### Smart search

Dashboard search supports ordinary text plus structured filters:

```text
is:failing
is:waiting
is:unread
status:"In Review"
project:"Release Sprint"
repo:acme-inc/web-app
pr:142
source:github
priority:urgent
```

Filters can be combined, for example `repo:acme-inc/web-app is:failing`.

## Safety and privacy

Task Digest is intentionally local-first:

- the dashboard listens on `127.0.0.1` by default;
- the Asana token is stored in the macOS login Keychain;
- GitHub credentials remain managed by GitHub CLI;
- `.env`, state, logs, history, backups, and generated reports are ignored by Git;
- local notes, focus order, rules, snoozes, and read markers are not sent to Asana or GitHub;
- write actions are disabled by default in the public configuration.

Read [Privacy and security](docs/PRIVACY.md) before changing the dashboard host or enabling Asana write actions.

## Configuration

Most configuration is available from **Settings**. The `.env.example` file documents every option.

Common settings:

```dotenv
ASANA_WORKSPACE_GID=1234567890123456
GITHUB_REPOSITORIES=acme-inc/web-app,acme-inc/api
INCLUDE_GITHUB_REVIEWS=true
INCLUDE_GITHUB_AUTHORED_PRS=true
INCLUDE_GITHUB_ASSIGNED_ISSUES=true
INCLUDE_GITHUB_MENTIONS=true
INCLUDE_LINKED_PR_STATUS=true

EXCLUDE_SECTIONS=Drafts
OPTIONAL_SECTIONS=Investigations
ACTION_STATUSES=Pending,In Development,To Do,Ready
WAITING_STATUSES=In Review,In Deployment,Blocked,Waiting

MORNING_TIME=10:00
EVENING_TIME=17:30
STALE_WAITING_DAYS=5
ENABLE_ASANA_WRITE_ACTIONS=false
```

## Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/check_public_repo.py
```

The public-repository checker inspects files that Git could publish. Ignored local
runtime files such as `.env`, logs, generated reports, and dashboard state may
remain in a development checkout without failing the check.

Run a local preview without installing the native app:

```bash
cp .env.example .env
# Configure .env and Keychain first
python -m task_digest --dry-run
python -m task_digest.dashboard
```

Useful commands:

```bash
make test        # run tests
make check       # tests + public-repo hygiene check
make install     # build/install the macOS app and scheduler
make uninstall   # remove background components, preserve local data
```

See [Architecture](docs/ARCHITECTURE.md) and [Contributing](CONTRIBUTING.md) for more detail.

## Project structure

```text
task_digest/       application, integrations, dashboard, rules, and local state
scripts/           setup, installation, scheduling, diagnostics, and utilities
tests/             unit and rendering tests
docs/              setup, privacy, architecture, troubleshooting, and assets
state/              local JSON state (ignored, except .gitkeep)
history/            saved reports and stand-ups (ignored, except .gitkeep)
logs/               local logs (ignored, except .gitkeep)
```

## Roadmap

The project is usable today, but several public-release improvements are still planned:

- [ ] Publish sanitized screenshots of the current interface.
- [ ] Produce a short product demo using the built-in guided tour.
- [ ] Add a signed and notarized downloadable macOS release.
- [ ] Improve rule import/export and reusable rule presets.
- [ ] Add optional public-holiday calendars to working-day calculations.
- [ ] Add more task providers without weakening the local-first privacy model.
- [ ] Expand accessibility testing and keyboard-only workflows.

Release-pipeline work is developed separately until it is ready for public distribution. See the repository issues and draft pull requests for current experiments.

## Limitations

- macOS only.
- Working-day calculations exclude weekends, not public holidays.
- GitHub data is limited to the configured repositories and permissions of the active `gh` account.
- Asana history and comments are limited to what the token can access.
- “Unread” is local Task Digest state, not Asana’s inbox read state.
- The native app is built and ad-hoc signed locally; it is not notarized for distribution.

## Uninstall

```bash
scripts/uninstall_all.sh
```

This removes Task Digest background services and the installed app while preserving the project directory and local state. To remove the Asana token too:

```bash
python -m task_digest.keychain delete-asana
```

## Contributing and security

Contributions are welcome. Please read:

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

Before publishing your fork, follow the [public repository checklist](docs/PUBLISHING.md).

## License

Task Digest is available under the [MIT License](LICENSE).
