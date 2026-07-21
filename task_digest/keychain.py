from __future__ import annotations

import argparse
import getpass
import os
import subprocess
from dataclasses import dataclass

from dotenv import load_dotenv


class KeychainError(RuntimeError):
    pass


@dataclass(frozen=True)
class KeychainItem:
    service: str
    account: str


def read_secret(item: KeychainItem) -> str | None:
    """Read a generic password from the current user's macOS login keychain."""
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                item.service,
                "-a",
                item.account,
                "-w",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def store_secret(item: KeychainItem, value: str) -> None:
    if not value:
        raise KeychainError("The secret cannot be empty.")
    try:
        result = subprocess.run(
            [
                "security",
                "add-generic-password",
                "-U",
                "-s",
                item.service,
                "-a",
                item.account,
                "-w",
                value,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as exc:
        raise KeychainError("The macOS 'security' command was not found.") from exc
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "Could not store the secret").strip()
        raise KeychainError(message)


def delete_secret(item: KeychainItem) -> bool:
    try:
        result = subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-s",
                item.service,
                "-a",
                item.account,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


def resolve_asana_token(service: str, account: str) -> str:
    env_value = os.getenv("ASANA_TOKEN", "").strip()
    if env_value:
        return env_value
    value = read_secret(KeychainItem(service=service, account=account))
    if value:
        return value
    raise RuntimeError(
        "No Asana token was found. Run scripts/migrate_asana_token_to_keychain.sh "
        "or temporarily set ASANA_TOKEN in .env."
    )


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Manage Task Digest secrets in macOS Keychain.")
    parser.add_argument("action", choices=["store-asana", "delete-asana", "check-asana"])
    parser.add_argument("--service", default=os.getenv("ASANA_TOKEN_KEYCHAIN_SERVICE", "app.taskdigest.asana"))
    parser.add_argument("--account", default=os.getenv("ASANA_TOKEN_KEYCHAIN_ACCOUNT", "asana"))
    args = parser.parse_args()
    item = KeychainItem(args.service, args.account)

    if args.action == "store-asana":
        token = os.getenv("ASANA_TOKEN", "").strip() or getpass.getpass("Asana token: ").strip()
        store_secret(item, token)
        print(f"Stored the Asana token in Keychain service '{item.service}'.")
        return 0
    if args.action == "delete-asana":
        if delete_secret(item):
            print("Deleted the Asana token from Keychain.")
            return 0
        print("No matching Keychain item was found.")
        return 1
    if read_secret(item):
        print("Asana token found in Keychain.")
        return 0
    print("Asana token not found in Keychain.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
