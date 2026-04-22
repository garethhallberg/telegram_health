from __future__ import annotations

import pytest

from hermes_life_admin.classifier import ClassificationError, _destinations_from_json
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
