from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from hermes_life_admin.classifier import ClassificationError
from hermes_life_admin.logger_service import LoggerService
from hermes_life_admin.routing import Destination
from hermes_life_admin.storage import DailyStorage


class FakeClassificationAgent:
    def __init__(self, destinations: list[Destination]) -> None:
        self.destinations = destinations

    def classify_text(self, message: str) -> list[Destination]:
        return self.destinations


class FailingClassificationAgent:
    def classify_text(self, message: str) -> list[Destination]:
        raise ClassificationError("test classification failure")


def test_log_text_appends_to_each_routed_file(tmp_path: Path) -> None:
    service = LoggerService(_storage(tmp_path), FakeClassificationAgent([Destination.MEALS, Destination.HABITS]))
    now = datetime(2026, 4, 22, 21, 45, tzinfo=ZoneInfo("Europe/London"))

    result = service.log_text("No booze tonight", now=now)

    assert result.destinations == (Destination.MEALS, Destination.HABITS)
    assert _read(tmp_path, "meals.txt") == "21:45 No booze tonight\n"
    assert _read(tmp_path, "habits.txt") == "21:45 No booze tonight\n"


def test_analysis_command_is_logged_to_notes_and_stubbed(tmp_path: Path) -> None:
    service = LoggerService(_storage(tmp_path), FakeClassificationAgent([Destination.MEALS]))
    now = datetime(2026, 4, 22, 18, 0, tzinfo=ZoneInfo("Europe/London"))

    result = service.log_text("weekly review", now=now)

    assert result.acknowledgement == "Analysis commands are not implemented yet."
    assert _read(tmp_path, "notes.txt") == "18:00 Command received: weekly review\n"


def test_salad_message_routes_to_meals_when_agent_classifies_it(tmp_path: Path) -> None:
    service = LoggerService(_storage(tmp_path), FakeClassificationAgent([Destination.MEALS]))
    now = datetime(2026, 4, 22, 18, 8, tzinfo=ZoneInfo("Europe/London"))
    message = "Making a salad with a few roasted baby potatoes, cottage cheese, homemade coleslaw, tomatoes and cucumber"

    result = service.log_text(message, now=now)

    assert result.destinations == (Destination.MEALS,)
    assert _read(tmp_path, "meals.txt") == f"18:08 {message}\n"


def test_classification_failure_routes_to_notes_and_writes_error_log(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = LoggerService(_storage(tmp_path), FailingClassificationAgent())
    now = datetime(2026, 4, 22, 18, 8, tzinfo=ZoneInfo("Europe/London"))

    result = service.log_text("Making a salad", now=now)

    assert result.destinations == (Destination.NOTES,)
    assert _read(tmp_path, "notes.txt") == "18:08 Making a salad\n"
    error_log = (tmp_path / "logs" / "error.log").read_text(encoding="utf-8")
    assert "Classification failed; routing to notes" in error_log
    assert "test classification failure" in error_log
    assert "Classification failed; routing to notes" in caplog.text


def test_log_image_saves_file_and_appends_reference(tmp_path: Path) -> None:
    service = LoggerService(_storage(tmp_path), FakeClassificationAgent([Destination.SLEEP]))
    now = datetime(2026, 4, 22, 7, 10, tzinfo=ZoneInfo("Europe/London"))

    result = service.log_image(
        content=b"image bytes",
        caption="Garmin sleep screenshot",
        original_name="sleep.png",
        mime_type="image/png",
        now=now,
    )

    assert result.saved_image is not None
    assert result.saved_image.relative_path == "images/garmin_sleep_01.png"
    assert result.saved_image.path.read_bytes() == b"image bytes"
    assert _read(tmp_path, "sleep.txt") == (
        "07:10 Image received: images/garmin_sleep_01.png | Caption: Garmin sleep screenshot\n"
    )


def _storage(tmp_path: Path) -> DailyStorage:
    script = tmp_path / "log_entry.sh"
    script.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        "FILE=\"$1\"\n"
        "ENTRY=\"$2\"\n"
        "mkdir -p \"$(dirname \"$FILE\")\"\n"
        "printf \"%s\\n\" \"$ENTRY\" >> \"$FILE\"\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return DailyStorage(tmp_path, script, ZoneInfo("Europe/London"))


def _read(tmp_path: Path, filename: str) -> str:
    return (tmp_path / "data" / "daily" / "2026-04-22" / filename).read_text(encoding="utf-8")
