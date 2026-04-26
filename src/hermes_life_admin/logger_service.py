from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging

from hermes_life_admin.analysis import AnalysisError, WeeklyAnalysisAgent, week_label
from hermes_life_admin.classifier import ClassificationAgent, ClassificationError, ImageClassification
from hermes_life_admin.routing import (
    Destination,
    image_kind,
    is_analysis_command,
    route_text,
)
from hermes_life_admin.storage import DailyStorage, SavedImage


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CaptureResult:
    destinations: tuple[Destination, ...]
    acknowledgement: str
    saved_image: SavedImage | None = None


class LoggerService:
    def __init__(
        self,
        storage: DailyStorage,
        classification_agent: ClassificationAgent,
        analysis_agent: WeeklyAnalysisAgent | None = None,
    ) -> None:
        self.storage = storage
        self.classification_agent = classification_agent
        self.analysis_agent = analysis_agent

    def weekly_review(self, now: datetime | None = None) -> str:
        """Reads the last 7 days, runs the analysis agent, writes the summary file, returns the summary text.

        Never raises — returns a user-friendly message on any failure.
        """
        if self.analysis_agent is None:
            return "Analysis is not configured."

        current = now or datetime.now(self.storage.timezone)
        label = week_label(current)
        week_data = self.storage.read_week(current)

        try:
            summary = self.analysis_agent.analyse_week(week_data, label)
        except AnalysisError as exc:
            warning = f"Weekly review failed: {exc}"
            LOGGER.warning(warning)
            self.storage.append_error_log(warning, now)
            return "Weekly review is unavailable right now."

        self.storage.write_weekly_summary(label, summary.text, now)

        return summary.text

    def log_text(self, message: str, now: datetime | None = None) -> CaptureResult:
        if is_analysis_command(message):
            if "weekly review" in message.strip().lower():
                text = self.weekly_review(now)
                return CaptureResult(destinations=(Destination.NOTES,), acknowledgement=text)
            self.storage.append_entry(Destination.NOTES, f"Command received: {message}", now)
            return CaptureResult(
                destinations=(Destination.NOTES,),
                acknowledgement="Analysis commands are not implemented yet.",
            )

        destinations = tuple(self._classify_text(message, now))
        for destination in destinations:
            self.storage.append_entry(destination, message, now)

        return CaptureResult(destinations=destinations, acknowledgement=_logged_ack(destinations))

    def log_image(
        self,
        content: bytes,
        caption: str | None = None,
        original_name: str | None = None,
        mime_type: str | None = None,
        now: datetime | None = None,
    ) -> CaptureResult:
        saved_image = self.storage.save_image(
            content=content,
            kind=image_kind(caption),
            original_name=original_name,
            mime_type=mime_type,
            now=now,
        )
        image_classification = self._classify_image(content, caption, mime_type, saved_image, now)
        destinations = tuple(image_classification.destinations)

        message = f"Image received: {saved_image.relative_path}"
        if caption:
            message = f"{message} | Caption: {caption}"
        if image_classification.note:
            message = f"{message} | Analysis: {image_classification.note}"

        for destination in destinations:
            self.storage.append_entry(destination, message, now)

        return CaptureResult(
            destinations=destinations,
            acknowledgement=_image_ack(destinations),
            saved_image=saved_image,
        )

    def _classify_text(self, message: str, now: datetime | None = None) -> list[Destination]:
        try:
            return route_text(message, self.classification_agent)
        except ClassificationError as exc:
            self._record_classification_failure(message, exc, now)
            return [Destination.NOTES]

    def _classify_image(
        self,
        content: bytes,
        caption: str | None,
        mime_type: str | None,
        saved_image: SavedImage,
        now: datetime | None = None,
    ) -> ImageClassification:
        try:
            return self.classification_agent.classify_image(content, caption, mime_type)
        except ClassificationError as exc:
            context = f"Image: {saved_image.relative_path}"
            if caption:
                context = f"{context} | Caption: {caption}"
            self._record_classification_failure(context, exc, now)
            return ImageClassification(destinations=[Destination.NOTES], image_kind="other")

    def _record_classification_failure(
        self,
        message: str,
        exc: ClassificationError,
        now: datetime | None = None,
    ) -> None:
        warning = f"Classification failed; routing to notes. Reason: {exc}"
        LOGGER.warning(warning)
        self.storage.append_error_log(f"{warning} | Message: {message}", now)


def _logged_ack(destinations: tuple[Destination, ...]) -> str:
    if len(destinations) == 1:
        return f"Logged to {destinations[0].value}."
    names = ", ".join(destination.value for destination in destinations)
    return f"Logged to {names}."


def _image_ack(destinations: tuple[Destination, ...]) -> str:
    if Destination.SLEEP in destinations:
        return "Saved Garmin screenshot."
    if Destination.MEALS in destinations:
        return "Saved meal image."
    return "Saved image."
