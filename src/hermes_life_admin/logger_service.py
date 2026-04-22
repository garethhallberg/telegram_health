from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging

from hermes_life_admin.classifier import ClassificationAgent, ClassificationError
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
    def __init__(self, storage: DailyStorage, classification_agent: ClassificationAgent) -> None:
        self.storage = storage
        self.classification_agent = classification_agent

    def log_text(self, message: str, now: datetime | None = None) -> CaptureResult:
        if is_analysis_command(message):
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
        destinations = tuple(self._classify_image(caption, now))
        saved_image = self.storage.save_image(
            content=content,
            kind=image_kind(caption),
            original_name=original_name,
            mime_type=mime_type,
            now=now,
        )

        message = f"Image received: {saved_image.relative_path}"
        if caption:
            message = f"{message} | Caption: {caption}"

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

    def _classify_image(self, caption: str | None, now: datetime | None = None) -> list[Destination]:
        if not caption:
            return [Destination.NOTES]
        try:
            return route_text(caption, self.classification_agent)
        except ClassificationError as exc:
            self._record_classification_failure(caption, exc, now)
            return [Destination.NOTES]

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
