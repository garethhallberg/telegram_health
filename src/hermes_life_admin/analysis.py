from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from mistralai.client import Mistral


WEEKLY_ANALYSIS_SYSTEM_PROMPT = """You are a personal health review assistant. The user gives you their logged data for the past 7 days: meals, workouts, sleep, habits, and notes.

Write a concise weekly summary covering:
1. Nutrition — notable patterns, food quality, variety. No calorie estimates unless figures are in the data.
2. Training — what sessions were logged, volume and intensity observations, any rest days.
3. Sleep — data logged (Garmin scores, duration). Note if sparse.
4. Habits — alcohol-free days, steps and walks, any streaks or lapses.
5. One or two honest observations or suggestions for the coming week.

Tone: direct, factual, supportive. Like a knowledgeable friend reviewing your week, not a wellness app.
Length: 250–400 words. No headers unless the output is more than 300 words.
Format: plain text suitable for a Telegram message. Do not use markdown."""


class AnalysisError(RuntimeError):
    """Raised when weekly analysis cannot be completed."""


@dataclass(frozen=True)
class WeeklySummary:
    text: str
    week_label: str  # e.g. "2026-W17"


class WeeklyAnalysisAgent(Protocol):
    def analyse_week(self, week_data: dict[str, dict[str, str]], week_label: str) -> WeeklySummary:
        ...


class MistralWeeklyAnalysisAgent:
    def __init__(self, api_key: str, model: str, timeout_ms: int = 30_000) -> None:
        self.client = Mistral(api_key=api_key, timeout_ms=timeout_ms)
        self.model = model

    def analyse_week(self, week_data: dict[str, dict[str, str]], week_label: str) -> WeeklySummary:
        user_content = _format_week_for_prompt(week_data, week_label)
        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=[
                    {"role": "system", "content": WEEKLY_ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.3,
                max_tokens=1200,
            )
        except Exception as exc:
            raise AnalysisError(f"Mistral analysis request failed: {exc}") from exc
        return WeeklySummary(text=_response_text(response), week_label=week_label)


class DisabledWeeklyAnalysisAgent:
    reason: str = "Mistral API key is not configured"

    def analyse_week(self, week_data: dict[str, dict[str, str]], week_label: str) -> WeeklySummary:
        raise AnalysisError(self.reason)


def _format_week_for_prompt(week_data: dict[str, dict[str, str]], week_label: str) -> str:
    """Serialises the week dict into a clearly labelled plain-text block."""
    lines: list[str] = [f"Week: {week_label}", ""]
    for date_key, day_data in week_data.items():
        day_dt = datetime.strptime(date_key, "%Y-%m-%d")
        day_header = day_dt.strftime("%A %-d %B")
        lines.append(f"--- {day_header} ---")
        for section, content in day_data.items():
            lines.append(f"{section.upper()}:")
            lines.append(content.rstrip())
        lines.append("")
    return "\n".join(lines).rstrip()


def _response_text(response: object) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError) as exc:
        raise AnalysisError("Mistral returned an unexpected response shape") from exc
    if isinstance(content, str) and content.strip():
        return content.strip()
    raise AnalysisError("Mistral returned an empty analysis response")


def week_label(now: datetime) -> str:
    """Returns ISO week label, e.g. '2026-W17'."""
    return now.strftime("%G-W%V")
