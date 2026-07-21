# Contributing

Thank you for improving Task Digest.

## Development setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The application is macOS-specific, but most unit tests do not require live Asana or GitHub credentials.

## Before opening a pull request

```bash
make check
```

Also confirm that:

- no private task data, repository names, usernames, filesystem paths, tokens, logs, or screenshots were added;
- new behavior has tests;
- user-facing changes are documented;
- destructive Asana actions remain explicit and confirmed;
- local-only controls do not accidentally write to Asana or GitHub;
- dashboard routes remain bound to loopback by default.

## Style

- Python 3.11+ type syntax is allowed.
- Prefer small, testable functions.
- Keep source integrations isolated from prioritization and presentation.
- Use UTF-8 explicitly for subprocess output and file operations.
- Avoid adding dependencies when the standard library is sufficient.
- Preserve accessible HTML controls, keyboard focus, reduced motion, and light/dark support.

## Tests

Run the complete suite:

```bash
python -m pytest -q
```

Run a specific file:

```bash
python -m pytest tests/test_rules.py -q
```

Live integration tests should not be added to the default suite. Use deterministic fixtures and fake repository/workspace names.

## Pull requests

Keep pull requests focused. Explain:

- the problem;
- the approach;
- user-visible behavior;
- security/privacy implications;
- tests performed;
- macOS version and Python version used for manual testing.

## Reporting bugs

Use the bug template and include sanitized diagnostics. Never attach `.env`, Keychain output, backup archives, or unreviewed logs.
