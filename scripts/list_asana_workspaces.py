#!/usr/bin/env python3
"""List the Asana workspaces visible to the token stored in macOS Keychain."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# When this file is executed directly, Python puts ``scripts/`` on sys.path
# rather than the repository root. Add the root explicitly so the local
# ``task_digest`` package can always be imported during first-run setup.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from dotenv import load_dotenv

from task_digest.keychain import resolve_asana_token


def main() -> int:
    load_dotenv()
    service = os.getenv("ASANA_TOKEN_KEYCHAIN_SERVICE", "app.taskdigest.asana")
    account = os.getenv("ASANA_TOKEN_KEYCHAIN_ACCOUNT", "asana")
    token = resolve_asana_token(service, account)

    response = httpx.get(
        "https://app.asana.com/api/1.0/workspaces",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    response.raise_for_status()
    workspaces = response.json().get("data", [])
    if not workspaces:
        print("No Asana workspaces were returned for this account.")
        return 1

    print("Available Asana workspaces:\n")
    for workspace in workspaces:
        print(f"  {workspace.get('name', 'Unnamed workspace')}: {workspace.get('gid', '')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Could not list Asana workspaces: {exc}", file=sys.stderr)
        raise SystemExit(1)
