from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DigestState:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.sent_data: dict[str, str] = {}
        self.snapshot_data: dict[str, dict[str, Any]] = {}
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return

        if isinstance(raw, dict) and ("sent" in raw or "snapshot" in raw):
            sent = raw.get("sent") or {}
            snapshot = raw.get("snapshot") or {}
            if isinstance(sent, dict):
                self.sent_data = {str(key): str(value) for key, value in sent.items()}
            if isinstance(snapshot, dict):
                self.snapshot_data = {
                    str(key): value for key, value in snapshot.items() if isinstance(value, dict)
                }
        elif isinstance(raw, dict):
            # Backward compatibility with the original flat sent-state file.
            self.sent_data = {str(key): str(value) for key, value in raw.items()}

    def sent(self, key: str) -> bool:
        return key in self.sent_data

    def get_snapshot(self) -> dict[str, dict[str, Any]]:
        return dict(self.snapshot_data)

    def record_run(
        self,
        key: str,
        timestamp: str,
        snapshot: dict[str, dict[str, Any]],
    ) -> None:
        self.sent_data[key] = timestamp
        self.snapshot_data = snapshot
        payload = {"sent": self.sent_data, "snapshot": self.snapshot_data}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
