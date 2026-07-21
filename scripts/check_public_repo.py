#!/usr/bin/env python3
"""Fail when common private-data or packaging mistakes are present."""

from __future__ import annotations

import re
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

RUNTIME_FILES = [
    ROOT / ".env",
    ROOT / "state" / "dashboard_token",
]
RUNTIME_GLOBS = [
    "state/*.json",
    "logs/*.log",
    "history/*.html",
    "history/*.md",
    "output/*.html",
    "backups/*.zip",
]


def iter_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name in SKIP_FILES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        yield path


def main() -> int:
    errors: list[str] = []
    for path in RUNTIME_FILES:
        if path.exists():
            errors.append(f"local runtime file exists: {path.relative_to(ROOT)}")
    for pattern in RUNTIME_GLOBS:
        for path in ROOT.glob(pattern):
            if path.name != ".gitkeep":
                errors.append(f"local runtime file exists: {path.relative_to(ROOT)}")

    for path in iter_text_files():
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
