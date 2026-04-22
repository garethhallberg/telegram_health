from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from mistralai.client import Mistral

from hermes_life_admin.routing import Destination


CLASSIFICATION_SYSTEM_PROMPT = """You classify personal health logging messages.

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


class ClassificationError(RuntimeError):
    pass


class ClassificationAgent(Protocol):
    def classify_text(self, message: str) -> list[Destination]:
        pass


@dataclass(frozen=True)
class DisabledClassificationAgent:
    reason: str = "Mistral API key is not configured"

    def classify_text(self, message: str) -> list[Destination]:
        raise ClassificationError(self.reason)


class MistralClassificationAgent:
    def __init__(self, api_key: str, model: str, timeout_ms: int = 10_000) -> None:
        self.client = Mistral(api_key=api_key, timeout_ms=timeout_ms)
        self.model = model

    def classify_text(self, message: str) -> list[Destination]:
        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=[
                    {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
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


def _response_content(response: object) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError) as exc:
        raise ClassificationError("Mistral returned an unexpected response shape") from exc

    if isinstance(content, str) and content.strip():
        return content
    raise ClassificationError("Mistral returned an empty classification")


def _destinations_from_json(content: str) -> list[Destination]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ClassificationError("Mistral returned invalid JSON") from exc

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
