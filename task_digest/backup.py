from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


_BACKUP_NAME_RE = re.compile(r"^task-digest-backup-(\d{8})-(\d{6})-([a-z0-9-]+)\.zip$")
_ALLOWED_STATE_FILES = {
    "digest_state.json",
    "task_preferences.json",
    "workspace.json",
    "activity_log.json",
    "task_rules.json",
}
_ALLOWED_HISTORY_SUFFIXES = {".html", ".md"}


@dataclass(frozen=True)
class BackupInfo:
    name: str
    path: Path
    created_at: datetime
    reason: str
    size_bytes: int

    @property
    def size_label(self) -> str:
        size = float(self.size_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{self.size_bytes} B"


class BackupManager:
    """Create and restore safe local backups.

    Backups intentionally exclude the Asana token, dashboard action token, logs,
    generated output, virtual environments, and the packaged application.
    """

    def __init__(
        self,
        project_dir: str | Path,
        backup_dir: str | Path = "backups",
        retention_count: int = 30,
    ) -> None:
        self.project_dir = Path(project_dir).expanduser().resolve()
        raw_dir = Path(backup_dir).expanduser()
        self.backup_dir = raw_dir.resolve() if raw_dir.is_absolute() else (self.project_dir / raw_dir).resolve()
        self.retention_count = max(1, retention_count)

    def create(self, reason: str = "manual", now: datetime | None = None) -> BackupInfo:
        now = now or datetime.now().astimezone()
        slug = self._slug(reason)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        name = f"task-digest-backup-{now:%Y%m%d-%H%M%S}-{slug}.zip"
        destination = self.backup_dir / name
        manifest = {
            "format": 1,
            "created_at": now.isoformat(),
            "reason": reason,
            "project_version": self._read_version(),
            "includes": [],
            "excludes": [
                "Asana token (macOS Keychain)",
                "dashboard action token",
                "logs",
                "generated output",
                "virtual environment",
            ],
        }
        fd, temporary_name = tempfile.mkstemp(prefix=name + ".", suffix=".tmp", dir=str(self.backup_dir))
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                settings = self._sanitized_env()
                if settings is not None:
                    archive.writestr(".env", settings)
                    manifest["includes"].append(".env")
                version = self.project_dir / "VERSION"
                if version.is_file():
                    archive.write(version, "VERSION")
                    manifest["includes"].append("VERSION")
                state_dir = self.project_dir / "state"
                for filename in sorted(_ALLOWED_STATE_FILES):
                    source = state_dir / filename
                    if source.is_file():
                        arcname = f"state/{filename}"
                        archive.write(source, arcname)
                        manifest["includes"].append(arcname)
                history_dir = self.project_dir / "history"
                if history_dir.is_dir():
                    for source in sorted(history_dir.iterdir()):
                        if source.is_file() and source.suffix.casefold() in _ALLOWED_HISTORY_SUFFIXES:
                            arcname = f"history/{source.name}"
                            archive.write(source, arcname)
                            manifest["includes"].append(arcname)
                archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        self.prune()
        return self.info(destination)

    def ensure_daily(self, today: date | None = None) -> BackupInfo | None:
        today = today or datetime.now().astimezone().date()
        prefix = f"task-digest-backup-{today:%Y%m%d}-"
        for item in self.backup_dir.glob(prefix + "*-automatic.zip") if self.backup_dir.exists() else ():
            if item.is_file():
                return None

        # Use the requested date when naming the backup. This keeps the method
        # deterministic for tests and also handles callers that deliberately
        # create a backup for a date other than the wall-clock date.
        local_now = datetime.now().astimezone()
        backup_time = local_now.replace(
            year=today.year,
            month=today.month,
            day=today.day,
        )
        return self.create("automatic", now=backup_time)

    def list(self) -> list[BackupInfo]:
        if not self.backup_dir.exists():
            return []
        items: list[BackupInfo] = []
        for path in self.backup_dir.glob("task-digest-backup-*.zip"):
            if not path.is_file():
                continue
            try:
                items.append(self.info(path))
            except ValueError:
                continue
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def get(self, name: str) -> BackupInfo:
        safe_name = Path(name).name
        if safe_name != name:
            raise ValueError("Invalid backup name.")
        path = (self.backup_dir / safe_name).resolve()
        if path.parent != self.backup_dir or not path.is_file():
            raise FileNotFoundError(f"Backup not found: {safe_name}")
        return self.info(path)

    def restore(self, name: str, now: datetime | None = None) -> BackupInfo:
        backup = self.get(name)
        with tempfile.TemporaryDirectory(prefix="task-digest-restore-") as temporary_name:
            temporary = Path(temporary_name)
            with zipfile.ZipFile(backup.path, "r") as archive:
                self._validate_archive(archive)
                archive.extractall(temporary)
            # A safety backup is created only after the selected archive has been
            # validated and extracted, so retention pruning cannot remove it mid-restore.
            safety = self.create("before-restore", now=now)
            env = temporary / ".env"
            if env.is_file():
                self._atomic_copy(env, self.project_dir / ".env")
            for filename in _ALLOWED_STATE_FILES:
                source = temporary / "state" / filename
                if source.is_file():
                    self._atomic_copy(source, self.project_dir / "state" / filename)
            history = temporary / "history"
            if history.is_dir():
                destination = self.project_dir / "history"
                destination.mkdir(parents=True, exist_ok=True)
                for source in history.iterdir():
                    if source.is_file() and source.suffix.casefold() in _ALLOWED_HISTORY_SUFFIXES:
                        self._atomic_copy(source, destination / source.name)
        return safety

    def prune(self) -> None:
        backups = self.list()
        for item in backups[self.retention_count :]:
            item.path.unlink(missing_ok=True)

    def info(self, path: Path) -> BackupInfo:
        match = _BACKUP_NAME_RE.fullmatch(path.name)
        if not match:
            raise ValueError(f"Unrecognized backup filename: {path.name}")
        stamp = datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S").astimezone()
        reason = match.group(3).replace("-", " ")
        return BackupInfo(
            name=path.name,
            path=path,
            created_at=stamp,
            reason=reason,
            size_bytes=path.stat().st_size,
        )

    def _read_version(self) -> str | None:
        path = self.project_dir / "VERSION"
        return path.read_text(encoding="utf-8").strip() if path.is_file() else None

    def _sanitized_env(self) -> str | None:
        path = self.project_dir / ".env"
        if not path.is_file():
            return None
        output: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("ASANA_TOKEN="):
                continue
            output.append(line)
        return "\n".join(output).rstrip() + "\n"

    def _validate_archive(self, archive: zipfile.ZipFile) -> None:
        names = set(archive.namelist())
        if "manifest.json" not in names:
            raise ValueError("This is not a Task Digest backup: manifest.json is missing.")
        allowed = {"manifest.json", ".env", "VERSION"}
        allowed.update(f"state/{name}" for name in _ALLOWED_STATE_FILES)
        for name in names:
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Backup contains an unsafe path.")
            if name in allowed:
                continue
            if len(path.parts) == 2 and path.parts[0] == "history" and path.suffix.casefold() in _ALLOWED_HISTORY_SUFFIXES:
                continue
            raise ValueError(f"Backup contains an unsupported file: {name}")

    @staticmethod
    def _atomic_copy(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=destination.name + ".", dir=str(destination.parent))
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            shutil.copy2(source, temporary)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        return slug[:40] or "manual"
