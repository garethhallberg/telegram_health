from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Protocol

from mistralai.client import Mistral

from hermes_life_admin.routing import Destination


TEXT_CLASSIFICATION_SYSTEM_PROMPT = """You classify personal health logging messages.

Return only JSON with this exact shape:
{"destinations":["meals"],"reason":"brief reason"}

Allowed destinations:
- meals: food, drink, cooking, meal prep, alcohol, calories, ingredients
- training: workouts, exercise, gym, sets, reps, equipment, soreness from training
- sleep: sleep, fatigue, recovery, Garmin sleep/body battery/recovery screenshots
- habits: short habit/check-in items such as no booze, steps, walk, target met
- notes: anything that does not clearly fit another category

Rules:
- Return one or more destinations.
- Use notes only when no other destination clearly applies.
- "no booze" should include both meals and habits.
- Do not invent destinations.
- Do not summarize the message.
"""

IMAGE_CLASSIFICATION_SYSTEM_PROMPT = """You classify uploaded personal health logging images.

Return only JSON with this exact shape:
{"destinations":["meals"],"image_kind":"meal","note":"short factual note"}

Allowed destinations:
- meals: food, drink, cooking, meal prep, alcohol, calories, ingredients
- training: workouts, exercise, gym screenshots, sets, reps, equipment
- sleep: sleep, fatigue, recovery, Garmin sleep/body battery/recovery screenshots
- habits: short habit/check-in evidence such as steps, walk, target met
- notes: anything that does not clearly fit another category

Allowed image_kind values:
- meal
- garmin_sleep
- garmin_body_battery
- garmin_activity
- workout
- habit
- document
- other

Rules:
- Use the image content and any caption.
- Return one or more destinations.
- Use notes only when no other destination clearly applies.
- Keep note short, factual, and under 12 words.
- Do not estimate calories.
- Do not invent precise metrics if they are not legible.
"""

ALLOWED_IMAGE_KINDS = {
    "meal",
    "garmin_sleep",
    "garmin_body_battery",
    "garmin_activity",
    "workout",
    "habit",
    "document",
    "other",
}


class ClassificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImageClassification:
    destinations: list[Destination]
    image_kind: str
    note: str | None = None


class ClassificationAgent(Protocol):
    def classify_text(self, message: str) -> list[Destination]:
        pass

    def classify_image(self, content: bytes, caption: str | None, mime_type: str | None) -> ImageClassification:
        pass


@dataclass(frozen=True)
class DisabledClassificationAgent:
    reason: str = "Mistral API key is not configured"

    def classify_text(self, message: str) -> list[Destination]:
        raise ClassificationError(self.reason)

    def classify_image(self, content: bytes, caption: str | None, mime_type: str | None) -> ImageClassification:
        raise ClassificationError(self.reason)


class MistralClassificationAgent:
    def __init__(
        self,
        api_key: str,
        text_model: str,
        vision_model: str,
        timeout_ms: int = 10_000,
    ) -> None:
        self.client = Mistral(api_key=api_key, timeout_ms=timeout_ms)
        self.text_model = text_model
        self.vision_model = vision_model

    def classify_text(self, message: str) -> list[Destination]:
        try:
            response = self.client.chat.complete(
                model=self.text_model,
                messages=[
                    {"role": "system", "content": TEXT_CLASSIFICATION_SYSTEM_PROMPT},
                    {"role": "user", "content": message},
                ],
                temperature=0.1,
                max_tokens=160,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise ClassificationError(f"Mistral classification request failed: {exc}") from exc
        content = _response_content(response)
        return _destinations_from_json(content)

    def classify_image(self, content: bytes, caption: str | None, mime_type: str | None) -> ImageClassification:
        data_url = _image_data_url(content, mime_type)
        user_text = "Classify this uploaded image for the personal logger."
        if caption:
            user_text = f"{user_text}\nCaption: {caption}"

        try:
            response = self.client.chat.complete(
                model=self.vision_model,
                messages=[
                    {"role": "system", "content": IMAGE_CLASSIFICATION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {"type": "image_url", "image_url": data_url},
                        ],
                    },
                ],
                temperature=0.1,
                max_tokens=160,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise ClassificationError(f"Mistral image classification request failed: {exc}") from exc
        response_content = _response_content(response)
        return _image_classification_from_json(response_content)


def _response_content(response: object) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError) as exc:
        raise ClassificationError("Mistral returned an unexpected response shape") from exc

    if isinstance(content, str) and content.strip():
        return content
    raise ClassificationError("Mistral returned an empty classification")


def _destinations_from_json(content: str) -> list[Destination]:
    return _destinations_from_payload(_json_payload(content))


def _image_classification_from_json(content: str) -> ImageClassification:
    payload = _json_payload(content)
    destinations = _destinations_from_payload(payload)
    image_kind = str(payload.get("image_kind") or "other").strip().lower()
    if image_kind not in ALLOWED_IMAGE_KINDS:
        image_kind = "other"
    note = payload.get("note")
    if not isinstance(note, str) or not note.strip():
        note = None
    return ImageClassification(
        destinations=destinations,
        image_kind=image_kind,
        note=_short_note(note) if note else None,
    )


def _json_payload(content: str) -> dict[str, object]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ClassificationError("Mistral returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ClassificationError("Mistral returned a non-object JSON response")
    return payload


def _destinations_from_payload(payload: dict[str, object]) -> list[Destination]:
    raw_destinations = payload.get("destinations")
    if not isinstance(raw_destinations, list):
        raise ClassificationError("Mistral response omitted destinations")

    destinations: list[Destination] = []
    for raw_destination in raw_destinations:
        try:
            destination = Destination(str(raw_destination))
        except ValueError:
            continue
        if destination not in destinations:
            destinations.append(destination)

    if not destinations:
        raise ClassificationError("Mistral returned no valid destinations")
    if len(destinations) > 1 and Destination.NOTES in destinations:
        destinations.remove(Destination.NOTES)
    return destinations


def _image_data_url(content: bytes, mime_type: str | None) -> str:
    media_type = mime_type or "image/jpeg"
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _short_note(note: str, max_words: int = 12) -> str:
    words = note.strip().split()
    return " ".join(words[:max_words])
