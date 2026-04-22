from __future__ import annotations

import mimetypes
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from hermes_life_admin.routing import Destination


@dataclass(frozen=True)
class SavedImage:
    path: Path
    relative_path: str


class DailyStorage:
    def __init__(self, root_dir: Path, log_script: Path, timezone: ZoneInfo) -> None:
        self.root_dir = root_dir
        self.log_script = log_script
        self.timezone = timezone

    def append_entry(
        self,
        destination: Destination,
        message: str,
        now: datetime | None = None,
    ) -> Path:
        timestamp = self._timestamp(now)
        target = self.daily_dir(now) / destination.filename
        entry = f"{timestamp} {message.strip()}"
        subprocess.run(
            [str(self.log_script), str(target), entry],
            check=True,
            cwd=str(self.root_dir),
        )
        return target

    def save_image(
        self,
        content: bytes,
        kind: str,
        original_name: str | None = None,
        mime_type: str | None = None,
        now: datetime | None = None,
    ) -> SavedImage:
        image_dir = self.daily_dir(now) / "images"
        image_dir.mkdir(parents=True, exist_ok=True)

        extension = _extension(original_name, mime_type)
        path = self._next_asset_path(image_dir, kind, extension)
        path.write_bytes(content)

        relative_path = path.relative_to(self.daily_dir(now)).as_posix()
        return SavedImage(path=path, relative_path=relative_path)

    def append_error_log(self, message: str, now: datetime | None = None) -> Path:
        logs_dir = self.root_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        target = logs_dir / "error.log"
        timestamp = self._error_timestamp(now)
        with target.open("a", encoding="utf-8") as file:
            file.write(f"{timestamp} {message.strip()}\n")
        return target

    def daily_dir(self, now: datetime | None = None) -> Path:
        return self.root_dir / "data" / "daily" / self._date_string(now)

    def _date_string(self, now: datetime | None = None) -> str:
        current = now or datetime.now(self.timezone)
        return current.astimezone(self.timezone).strftime("%Y-%m-%d")

    def _timestamp(self, now: datetime | None = None) -> str:
        current = now or datetime.now(self.timezone)
        return current.astimezone(self.timezone).strftime("%H:%M")

    def _error_timestamp(self, now: datetime | None = None) -> str:
        current = now or datetime.now(self.timezone)
        return current.astimezone(self.timezone).isoformat(timespec="seconds")

    def _next_asset_path(self, directory: Path, kind: str, extension: str) -> Path:
        safe_kind = "".join(char if char.isalnum() or char == "_" else "_" for char in kind)
        index = 1
        while True:
            candidate = directory / f"{safe_kind}_{index:02d}{extension}"
            if not candidate.exists():
                return candidate
            index += 1


def _extension(original_name: str | None, mime_type: str | None) -> str:
    if original_name:
        suffix = Path(original_name).suffix.lower()
        if suffix:
            return suffix
    if mime_type:
        guessed = mimetypes.guess_extension(mime_type)
        if guessed:
            return guessed
    return ".jpg"
