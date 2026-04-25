from __future__ import annotations

import pytest

from hermes_life_admin.classifier import (
    ClassificationError,
    _destinations_from_json,
    _image_classification_from_json,
    _image_data_url,
)
from hermes_life_admin.routing import Destination


def test_destinations_from_json_parses_allowed_destinations() -> None:
    assert _destinations_from_json('{"destinations":["meals","habits"],"reason":"no booze"}') == [
        Destination.MEALS,
        Destination.HABITS,
    ]


def test_destinations_from_json_removes_notes_when_specific_destination_exists() -> None:
    assert _destinations_from_json('{"destinations":["notes","meals"],"reason":"food"}') == [Destination.MEALS]


def test_destinations_from_json_rejects_empty_result() -> None:
    with pytest.raises(ClassificationError):
        _destinations_from_json('{"destinations":[],"reason":"unclear"}')


def test_image_data_url_encodes_content() -> None:
    assert _image_data_url(b"abc", "image/png") == "data:image/png;base64,YWJj"


def test_image_classification_from_json_parses_note_and_kind() -> None:
    result = _image_classification_from_json(
        '{"destinations":["sleep"],"image_kind":"garmin_sleep","note":"Garmin sleep panel"}'
    )

    assert result.destinations == [Destination.SLEEP]
    assert result.image_kind == "garmin_sleep"
    assert result.note == "Garmin sleep panel"


def test_image_classification_from_json_sanitizes_kind_and_note() -> None:
    result = _image_classification_from_json(
        '{"destinations":["meals"],"image_kind":"invented","note":"one two three four five six seven eight nine ten eleven twelve thirteen"}'
    )

    assert result.image_kind == "other"
    assert result.note == "one two three four five six seven eight nine ten eleven twelve"
