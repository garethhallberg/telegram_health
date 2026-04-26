from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import dotenv_values


ROOT_DIR = Path("/Users/garethhallberg/hermes-life-admin")


@dataclass(frozen=True)
class AppConfig:
    telegram_bot_token: str
    allowed_chat_ids: frozenset[int]
    root_dir: Path
    timezone_name: str
    mistral_api_key: str | None
    mistral_model: str
    mistral_text_model: str
    mistral_vision_model: str
    mistral_ocr_model: str
    mistral_analysis_model: str
    image_analysis_enabled: bool
    calorie_estimation_enabled: bool
    workout_reminder_time: str
    evening_capture_time: str
    pre_bed_check_time: str
    weekly_review_time: str
    workout_days: tuple[str, ...]

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    @property
    def log_script(self) -> Path:
        return self.root_dir / "bin" / "log_entry.sh"

    @classmethod
    def from_env(cls, env_path: Path | str = ".env") -> "AppConfig":
        values = {**dotenv_values(env_path), **os.environ}
        root_dir = Path(values.get("HERMES_ROOT_DIR") or ROOT_DIR).expanduser()

        return cls(
            telegram_bot_token=_required(values, "TELEGRAM_BOT_TOKEN"),
            allowed_chat_ids=_parse_chat_ids(values.get("TELEGRAM_ALLOWED_CHAT_IDS", "")),
            root_dir=root_dir,
            timezone_name=values.get("HERMES_TIMEZONE") or "Europe/London",
            mistral_api_key=_optional_secret(values.get("MISTRAL_API_KEY")),
            mistral_model=values.get("MISTRAL_MODEL") or "mistral-large-latest",
            mistral_text_model=values.get("MISTRAL_TEXT_MODEL") or values.get("MISTRAL_MODEL") or "mistral-small-latest",
            mistral_vision_model=values.get("MISTRAL_VISION_MODEL") or "mistral-small-2506",
            mistral_ocr_model=values.get("MISTRAL_OCR_MODEL") or "mistral-ocr-latest",
            mistral_analysis_model=values.get("MISTRAL_ANALYSIS_MODEL") or values.get("MISTRAL_MODEL") or "mistral-large-latest",
            image_analysis_enabled=_parse_bool(values.get("IMAGE_ANALYSIS_ENABLED")),
            calorie_estimation_enabled=_parse_bool(values.get("CALORIE_ESTIMATION_ENABLED")),
            workout_reminder_time=values.get("WORKOUT_REMINDER_TIME") or "10:30",
            evening_capture_time=values.get("EVENING_CAPTURE_TIME") or "19:30",
            pre_bed_check_time=values.get("PRE_BED_CHECK_TIME") or "21:30",
            weekly_review_time=values.get("WEEKLY_REVIEW_TIME") or "18:00",
            workout_days=_parse_days(values.get("WORKOUT_DAYS") or "mon,wed,fri"),
        )


def _required(values: dict[str, str | None], name: str) -> str:
    value = values.get(name)
    if not value:
        raise ValueError(f"{name} must be set")
    return value


def _optional_secret(value: str | None) -> str | None:
    if not value or value.startswith("dummy-"):
        return None
    return value


def _parse_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_chat_ids(value: str) -> frozenset[int]:
    chat_ids: set[int] = set()
    for item in value.split(","):
        stripped = item.strip()
        if stripped:
            chat_ids.add(int(stripped))
    if not chat_ids:
        raise ValueError("TELEGRAM_ALLOWED_CHAT_IDS must include at least one chat ID")
    return frozenset(chat_ids)


def _parse_days(value: str) -> tuple[str, ...]:
    return tuple(day.strip().lower() for day in value.split(",") if day.strip())
