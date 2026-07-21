# Troubleshooting

Start with the **System** page:

```text
http://127.0.0.1:8765/system
```

It shows service status, authentication, latest refresh, and recent logs.

## Dashboard does not open

```bash
scripts/install_all.sh
open http://127.0.0.1:8765
cat logs/app.stderr.log
```

Confirm the native app service:

```bash
launchctl print "gui/$(id -u)/app.taskdigest.macos"
```

## Menu-bar item is missing

```bash
open "$HOME/Applications/Task Digest.app"
cat logs/app.stderr.log
```

Check **System Settings → General → Login Items & Extensions** and allow Task Digest in the background.

## Asana token not found

```bash
python -m task_digest.keychain check-asana
python -m task_digest.keychain store-asana
```

## Asana returns 401 or 403

- Recreate or re-store the token.
- Confirm the token belongs to the expected Asana user.
- Confirm the user can access the workspace/project/task.
- Organization administrators may restrict personal access tokens.

## GitHub shows zero items unexpectedly

```bash
gh auth status
gh api user --jq .login
gh repo view OWNER/REPOSITORY
```

Confirm the repository list in Settings. Organization SSO or OAuth restrictions may require additional authorization.

## GitHub CLI not detected in the app

Set the full path in `.env` or Settings:

```dotenv
GITHUB_CLI_PATH=/opt/homebrew/bin/gh
```

Intel Homebrew commonly uses `/usr/local/bin/gh`.

## Notifications do not appear

```bash
scripts/test_notification.sh
```

Enable notifications in macOS System Settings. For action buttons:

```bash
brew install vjeantet/tap/alerter
```

## Scheduler is not loaded

```bash
scripts/install_launch_agent.sh
launchctl print "gui/$(id -u)/app.taskdigest.scheduler"
cat logs/launchd.stderr.log
```

## Reset the generated report

```bash
rm -f output/task-digest.html
python -m task_digest --dry-run
open output/task-digest.html
```

## Clean reinstall without deleting local state

```bash
scripts/uninstall_all.sh
scripts/install_all.sh
```

## Full local reset

Back up anything you want to keep first. Then remove generated state:

```bash
rm -f state/*.json state/dashboard_token
rm -f history/*.html history/*.md
rm -f logs/*.log output/*.html
```
