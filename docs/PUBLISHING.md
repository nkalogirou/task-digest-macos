# Public repository checklist

Use this checklist before publishing a fork.

## Suggested repository metadata

- **Name:** `task-digest-macos`
- **Description:** `A local-first macOS dashboard that turns Asana tasks and GitHub activity into a prioritized daily work digest.`
- **Topics:** `macos`, `asana`, `github`, `productivity`, `menu-bar`, `dashboard`, `python`, `local-first`, `task-management`

## Pre-publish checks

```bash
python -m pytest -q
python scripts/check_public_repo.py
git status --short
```

Confirm that none of these are tracked:

```bash
git ls-files .env state history logs output backups
```

Only `.gitkeep` placeholders should appear under runtime directories.

Review the entire repository for:

- private organization/repository names;
- employee names or usernames;
- real task titles, comments, URLs, workspace GIDs, and project GIDs;
- screenshots containing private data;
- absolute `/Users/...` paths;
- tokens, authentication codes, `.env`, logs, backups, and generated reports.

## Create and push the repository

```bash
git init
git add .
git commit -m "Initial public release"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/task-digest-macos.git
git push -u origin main
```

## Recommended GitHub settings

- Enable branch protection for `main`.
- Require the CI workflow to pass before merging.
- Enable Dependabot alerts and security updates.
- Enable private vulnerability reporting.
- Disable wiki/projects if they are not used.
- Add a repository social preview image based on `docs/assets/task-digest-banner.svg`.

## Release

Create a `v1.0.0` tag after the public repository has passed CI:

```bash
git tag -a v1.0.0 -m "Task Digest 1.0.0"
git push origin v1.0.0
```
