from __future__ import annotations

from pathlib import Path

from setuptools import setup

ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip() or "1"

OPTIONS = {
    "argv_emulation": False,
    "packages": [
        "task_digest",
        "rumps",
        "dotenv",
        "httpx",
        "httpcore",
        "anyio",
        "certifi",
        "idna",
        "h11",
    ],
    "includes": ["AppKit", "Foundation", "objc"],
    "plist": {
        "CFBundleName": "Task Digest",
        "CFBundleDisplayName": "Task Digest",
        "CFBundleIdentifier": "app.taskdigest.macos",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
    },
}

setup(
    name="task-digest-macos",
    version=VERSION,
    description="A local-first macOS dashboard for Asana and GitHub work.",
    license="MIT",
    python_requires=">=3.11,<3.13",
    app=["Task Digest.py"],
    options={"py2app": OPTIONS},
)
