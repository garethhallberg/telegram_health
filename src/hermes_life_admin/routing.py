import re
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hermes_life_admin.classifier import ClassificationAgent


class Destination(StrEnum):
    MEALS = "meals"
    TRAINING = "training"
    SLEEP = "sleep"
    HABITS = "habits"
    NOTES = "notes"

    @property
    def filename(self) -> str:
        return f"{self.value}.txt"


MEAL_CUES = {
    "breakfast",
    "lunch",
    "dinner",
    "snack",
    "ate",
    "drank",
    "yoghurt",
    "yogurt",
    "rice",
    "lentils",
    "eggs",
    "toast",
    "dal",
    "curry",
    "no booze",
    "alcohol",
}

TRAINING_CUES = {
    "gym",
    "workout",
    "leg day",
    "squats",
    "curls",
    "press",
    "deadlift",
    "pull-up",
    "pullup",
    "completed",
    "session",
}

SLEEP_CUES = {
    "sleep",
    "slept",
    "woke up",
    "body battery",
    "garmin",
    "recovery",
    "fatigue",
}

HABIT_CUES = {
    "no booze",
    "steps",
    "walk",
    "target met",
    "habit",
}

ANALYSIS_COMMANDS = {
    "summarise today",
    "summarize today",
    "weekly review",
    "estimate calories",
}


def route_text(message: str, classification_agent: "ClassificationAgent") -> list[Destination]:
    return classification_agent.classify_text(message)


def is_analysis_command(message: str) -> bool:
    text = message.strip().lower()
    return any(command in text for command in ANALYSIS_COMMANDS)


def image_kind(caption: str | None) -> str:
    text = (caption or "").lower()
    if _contains_any(text, {"garmin"}) and _contains_any(text, {"sleep"}):
        return "garmin_sleep"
    if _contains_any(text, {"garmin"}) and _contains_any(text, {"body battery"}):
        return "garmin_body_battery"
    if _contains_any(text, {"breakfast", "lunch", "dinner", "meal", "food", "ate"}):
        return "meal"
    if _contains_any(text, {"garmin"}):
        return "garmin"
    return "image"


def _contains_any(text: str, cues: set[str]) -> bool:
    return any(_contains_cue(text, cue) for cue in cues)


def _contains_cue(text: str, cue: str) -> bool:
    if " " in cue:
        return cue in text
    return re.search(rf"(?<![a-z0-9]){re.escape(cue)}(?![a-z0-9])", text) is not None
