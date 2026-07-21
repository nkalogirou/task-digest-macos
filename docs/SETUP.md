# Local setup guide

This guide explains every step required to run Task Digest on a Mac. The guided `scripts/setup_local.sh` script performs the same steps interactively.

## 1. Prerequisites

Task Digest currently supports macOS only.

Install Python 3.12 and GitHub CLI with Homebrew:

```bash
brew install python@3.12 gh
```

Verify them:

```bash
python3.12 --version
gh --version
```

Task Digest supports Python 3.11 and 3.12.

## 2. Clone the repository

```bash
git clone https://github.com/YOUR-USERNAME/task-digest-macos.git
cd task-digest-macos
```

## 3. Create the virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## 4. Create local configuration

```bash
cp .env.example .env
```

Never commit `.env`. It is already ignored by `.gitignore`.

## 5. Create and store the Asana token

Create a personal access token from the [Asana developer console](https://developers.asana.com/docs/personal-access-token). Treat it like a password.

Store it directly in macOS Keychain:

```bash
python -m task_digest.keychain store-asana
```

The prompt hides the token while you paste it.

Verify storage:

```bash
python -m task_digest.keychain check-asana
```

List the workspaces visible to the token:

```bash
python scripts/list_asana_workspaces.py
```

Copy the GID for the desired workspace into `.env`:

```dotenv
ASANA_WORKSPACE_GID=1234567890123456
```

Optionally limit Task Digest to specific projects:

```dotenv
ASANA_PROJECT_GIDS=1111111111111111,2222222222222222
```

Leave it blank to include all incomplete tasks assigned to you in the workspace.

## 6. Authenticate GitHub CLI

GitHub documents this browser flow in the [`gh auth login` manual](https://cli.github.com/manual/gh_auth_login).

```bash
gh auth login --web --git-protocol https --skip-ssh-key
```

Confirm the active account:

```bash
gh auth status
```

If your organization uses SSO or restricts OAuth applications, you may need to authorize GitHub CLI for the organization.

Add repositories and enable the GitHub sources you want in `.env`:

```dotenv
GITHUB_REPOSITORIES=acme-inc/web-app,acme-inc/api
INCLUDE_GITHUB_REVIEWS=true
INCLUDE_GITHUB_AUTHORED_PRS=true
INCLUDE_GITHUB_ASSIGNED_ISSUES=true
INCLUDE_GITHUB_MENTIONS=true
INCLUDE_LINKED_PR_STATUS=true
```

The public defaults keep GitHub sources disabled until repositories are configured. To use Asana without GitHub, leave the repository list blank and keep all of those values `false`.

## 7. Review the safe defaults

The public configuration starts with Asana write actions disabled:

```dotenv
ENABLE_ASANA_WRITE_ACTIONS=false
```

After you have verified the app and permissions, you may enable it from Settings. This allows completing tasks, changing due dates/statuses/sections, commenting, and unassigning through the dashboard.

Keep the dashboard local:

```dotenv
DASHBOARD_HOST=127.0.0.1
```

Do not change it to `0.0.0.0` unless you add proper network authentication and understand the risk.

## 8. Run the tests

```bash
python -m pytest -q
python scripts/check_public_repo.py
```

## 9. Preview the data

```bash
python -m task_digest --dry-run
open output/task-digest.html
```

This fetches current data and creates a report without sending a notification.

## 10. Build and install

```bash
scripts/install_all.sh
```

This installs:

- `~/Applications/Task Digest.app`;
- a login Launch Agent for the native menu-bar app and dashboard;
- a weekday scheduler using the morning/evening times in `.env`.

The app is built locally using py2app and ad-hoc signed.

Open the dashboard:

```bash
open http://127.0.0.1:8765
```

## 11. Enable notifications

Test immediately from the System page or with:

```bash
scripts/test_notification.sh
```

If no popup appears, open **System Settings → Notifications** and allow notifications for the helper shown there.

For notification action buttons:

```bash
brew install vjeantet/tap/alerter
```

## 12. Verify installation

Open:

```text
http://127.0.0.1:8765/system
```

Confirm:

- Task Digest app is running;
- scheduled digest is loaded;
- Asana authentication is valid;
- GitHub authentication is valid or intentionally disabled;
- latest source refresh succeeded.

## Updating a clone

```bash
git pull
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
scripts/install_all.sh
```

Your `.env`, Keychain token, notes, rules, history, and local state remain outside tracked source files.

## Uninstalling

```bash
scripts/uninstall_all.sh
```

Remove the Keychain token separately:

```bash
python -m task_digest.keychain delete-asana
```
