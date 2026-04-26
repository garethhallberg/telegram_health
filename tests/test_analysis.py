from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from hermes_life_admin.analysis import (
    AnalysisError,
    DisabledWeeklyAnalysisAgent,
    MistralWeeklyAnalysisAgent,
    WeeklySummary,
    _format_week_for_prompt,
    week_label,
)
from hermes_life_admin.logger_service import LoggerService
from hermes_life_admin.routing import Destination
from hermes_life_admin.storage import DailyStorage


# ---------------------------------------------------------------------------
# Fake agents
# ---------------------------------------------------------------------------


class FakeWeeklyAnalysisAgent:
    def __init__(self, summary_text: str = "Test weekly summary.") -> None:
        self.calls: list[tuple[dict, str]] = []
        self.summary_text = summary_text

    def analyse_week(self, week_data: dict, week_label: str) -> WeeklySummary:
        self.calls.append((week_data, week_label))
        return WeeklySummary(text=self.summary_text, week_label=week_label)


class FailingWeeklyAnalysisAgent:
    def analyse_week(self, week_data: dict, week_label: str) -> WeeklySummary:
        raise AnalysisError("test analysis failure")


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


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


def _write_daily_file(tmp_path: Path, date: str, filename: str, content: str) -> None:
    day_dir = tmp_path / "data" / "daily" / date
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / filename).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# DailyStorage.read_week() tests
# ---------------------------------------------------------------------------


def test_read_week_returns_content_for_days_with_data(tmp_path: Path) -> None:
    _write_daily_file(tmp_path, "2026-04-22", "meals.txt", "17:05 Lunch: dal\n")
    _write_daily_file(tmp_path, "2026-04-22", "training.txt", "17:11 Push day\n")
    _write_daily_file(tmp_path, "2026-04-23", "habits.txt", "15:00 No alcohol\n")
    storage = _storage(tmp_path)
    now = datetime(2026, 4, 23, 20, 0, tzinfo=ZoneInfo("Europe/London"))

    result = storage.read_week(now)

    assert "2026-04-22" in result
    assert result["2026-04-22"]["meals"] == "17:05 Lunch: dal\n"
    assert result["2026-04-22"]["training"] == "17:11 Push day\n"
    assert "2026-04-23" in result
    assert result["2026-04-23"]["habits"] == "15:00 No alcohol\n"


def test_read_week_omits_days_with_no_directory(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    now = datetime(2026, 4, 25, 12, 0, tzinfo=ZoneInfo("Europe/London"))

    result = storage.read_week(now)

    assert result == {}


def test_read_week_covers_exactly_7_days(tmp_path: Path) -> None:
    _write_daily_file(tmp_path, "2026-04-19", "meals.txt", "Day 7\n")
    _write_daily_file(tmp_path, "2026-04-25", "meals.txt", "Day 1\n")
    _write_daily_file(tmp_path, "2026-04-18", "meals.txt", "Day 8 — should be excluded\n")
    storage = _storage(tmp_path)
    now = datetime(2026, 4, 25, 12, 0, tzinfo=ZoneInfo("Europe/London"))

    result = storage.read_week(now)

    assert "2026-04-19" in result
    assert "2026-04-25" in result
    assert "2026-04-18" not in result


def test_read_week_returns_dates_in_chronological_order(tmp_path: Path) -> None:
    _write_daily_file(tmp_path, "2026-04-22", "notes.txt", "a\n")
    _write_daily_file(tmp_path, "2026-04-24", "notes.txt", "b\n")
    storage = _storage(tmp_path)
    now = datetime(2026, 4, 25, 12, 0, tzinfo=ZoneInfo("Europe/London"))

    result = storage.read_week(now)
    keys = list(result.keys())

    assert keys == sorted(keys)


def test_read_week_omits_missing_files_within_a_day(tmp_path: Path) -> None:
    _write_daily_file(tmp_path, "2026-04-22", "meals.txt", "dinner\n")
    # training.txt not written
    storage = _storage(tmp_path)
    now = datetime(2026, 4, 22, 20, 0, tzinfo=ZoneInfo("Europe/London"))

    result = storage.read_week(now)

    assert "meals" in result["2026-04-22"]
    assert "training" not in result["2026-04-22"]


# ---------------------------------------------------------------------------
# LoggerService.weekly_review() tests
# ---------------------------------------------------------------------------


def test_weekly_review_runs_agent_and_writes_summary_file(tmp_path: Path) -> None:
    _write_daily_file(tmp_path, "2026-04-22", "meals.txt", "17:05 Dal\n")
    agent = FakeWeeklyAnalysisAgent("Great week overall.")
    service = LoggerService(_storage(tmp_path), _fake_classification_agent(), agent)
    now = datetime(2026, 4, 25, 18, 0, tzinfo=ZoneInfo("Europe/London"))

    result = service.weekly_review(now)

    assert result == "Great week overall."
    assert len(agent.calls) == 1
    week_data, label = agent.calls[0]
    assert "2026-04-22" in week_data
    summary_file = tmp_path / "data" / "weekly_summaries" / f"{label}-summary.txt"
    assert summary_file.exists()
    assert summary_file.read_text(encoding="utf-8") == "Great week overall."


def test_weekly_review_returns_failure_message_on_analysis_error(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = LoggerService(_storage(tmp_path), _fake_classification_agent(), FailingWeeklyAnalysisAgent())
    now = datetime(2026, 4, 25, 18, 0, tzinfo=ZoneInfo("Europe/London"))

    result = service.weekly_review(now)

    assert "unavailable" in result.lower()
    error_log = (tmp_path / "logs" / "error.log").read_text(encoding="utf-8")
    assert "test analysis failure" in error_log
    assert "Weekly review failed" in caplog.text


def test_weekly_review_returns_not_configured_when_no_agent(tmp_path: Path) -> None:
    service = LoggerService(_storage(tmp_path), _fake_classification_agent(), analysis_agent=None)
    now = datetime(2026, 4, 25, 18, 0, tzinfo=ZoneInfo("Europe/London"))

    result = service.weekly_review(now)

    assert "not configured" in result.lower()


def test_disabled_agent_raises_analysis_error() -> None:
    agent = DisabledWeeklyAnalysisAgent()
    with pytest.raises(AnalysisError):
        agent.analyse_week({}, "2026-W17")


# ---------------------------------------------------------------------------
# _format_week_for_prompt() tests
# ---------------------------------------------------------------------------


def test_format_week_for_prompt_includes_day_headers_and_sections() -> None:
    week_data = {
        "2026-04-22": {
            "meals": "17:05 Dal\n18:00 Salad\n",
            "training": "17:11 Push day\n",
        },
        "2026-04-23": {
            "habits": "15:00 No alcohol\n",
        },
    }

    result = _format_week_for_prompt(week_data, "2026-W17")

    assert "Week: 2026-W17" in result
    assert "Wednesday 22 April" in result
    assert "MEALS:" in result
    assert "17:05 Dal" in result
    assert "TRAINING:" in result
    assert "Thursday 23 April" in result
    assert "HABITS:" in result
    assert "15:00 No alcohol" in result


def test_format_week_for_prompt_omits_empty_sections() -> None:
    week_data = {"2026-04-22": {"meals": "dinner\n"}}

    result = _format_week_for_prompt(week_data, "2026-W17")

    assert "TRAINING:" not in result
    assert "SLEEP:" not in result


# ---------------------------------------------------------------------------
# week_label() tests
# ---------------------------------------------------------------------------


def test_week_label_returns_iso_week() -> None:
    dt = datetime(2026, 4, 25, 18, 0, tzinfo=ZoneInfo("Europe/London"))
    assert week_label(dt) == "2026-W17"


def test_week_label_year_boundary() -> None:
    dt = datetime(2026, 1, 1, 0, 0, tzinfo=ZoneInfo("Europe/London"))
    assert week_label(dt) == "2026-W01"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_classification_agent():
    from hermes_life_admin.classifier import ClassificationError, ImageClassification

    class _Fake:
        def classify_text(self, message: str) -> list[Destination]:
            return [Destination.NOTES]

        def classify_image(self, content: bytes, caption: str | None, mime_type: str | None) -> ImageClassification:
            raise ClassificationError("not used in these tests")

    return _Fake()
