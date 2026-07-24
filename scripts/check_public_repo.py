#!/usr/bin/env python3
"""Fail when files that could be published contain private data or packaging mistakes.

Inside a Git repository, the checker inspects tracked files plus untracked files that
are *not* ignored by Git. Local runtime files such as ``.env``, logs, generated
reports, and dashboard state may therefore exist safely when covered by
``.gitignore``; they are rejected only if Git could publish them.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "build", "dist", "__pycache__", ".pytest_cache"}
SKIP_FILES = {".env"}
TEXT_SUFFIXES = {
    ".py", ".sh", ".md", ".txt", ".toml", ".yml", ".yaml", ".json",
    ".html", ".css", ".js", ".svg", ".example", "",
}

FORBIDDEN_PATTERNS = {
    "absolute macOS home path": re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    "GitHub classic token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "filled Asana token setting": re.compile(r"^ASANA_TOKEN=\S+", re.MULTILINE),
    "previous private organization marker": re.compile(r"\b" + "epig" + "nosis" + r"\b", re.IGNORECASE),
    "previous private username marker": re.compile(r"\b" + "nkalo" + "girou" + r"\b", re.IGNORECASE),
}

RUNTIME_PATHS = {
    ".env",
    "state/dashboard_token",
}
RUNTIME_PATTERNS = (
    re.compile(r"^state/[^/]+\.json$"),
    re.compile(r"^logs/[^/]+\.log$"),
    re.compile(r"^history/[^/]+\.(?:html|md)$"),
    re.compile(r"^output/[^/]+\.html$"),
    re.compile(r"^backups/[^/]+\.zip$"),
)


def _git_publishable_files() -> list[Path] | None:
    """Return tracked and non-ignored untracked files, or None outside Git."""

    if not (ROOT / ".git").exists():
        return None
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(ROOT),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    paths: list[Path] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(raw.decode("utf-8", errors="surrogateescape"))
        candidate = ROOT / relative
        if candidate.is_file():
            paths.append(candidate)
    return paths


def _fallback_files() -> list[Path]:
    """Inspect the complete distribution when no Git index is available."""

    return [path for path in ROOT.rglob("*") if path.is_file()]


def candidate_files() -> list[Path]:
    return _git_publishable_files() or _fallback_files()


def iter_text_files(paths: list[Path]):
    for path in paths:
        relative = path.relative_to(ROOT)
        if path.name in SKIP_FILES:
            continue
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if path.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        yield path


def _is_runtime_file(relative: str) -> bool:
    if relative in RUNTIME_PATHS:
        return True
    return any(pattern.fullmatch(relative) for pattern in RUNTIME_PATTERNS)


def main() -> int:
    errors: list[str] = []
    paths = candidate_files()

    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if _is_runtime_file(relative) and Path(relative).name != ".gitkeep":
            errors.append(f"runtime file could be published: {relative}")

    for path in iter_text_files(paths):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"{label}: {path.relative_to(ROOT)}")

    if errors:
        print("Public repository check failed:\n", file=sys.stderr)
        for error in sorted(set(errors)):
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("Public repository check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
