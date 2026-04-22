from hermes_life_admin.routing import Destination, is_analysis_command, route_text
from hermes_life_admin.bot import _telegram_days


class FakeClassificationAgent:
    def __init__(self, destinations: list[Destination]) -> None:
        self.destinations = destinations

    def classify_text(self, message: str) -> list[Destination]:
        return self.destinations


def test_route_text_delegates_to_classification_agent() -> None:
    agent = FakeClassificationAgent([Destination.MEALS, Destination.HABITS])

    assert route_text("No booze tonight", agent) == [Destination.MEALS, Destination.HABITS]


def test_analysis_command_is_detected() -> None:
    assert is_analysis_command("summarise today")


def test_telegram_day_mapping_matches_python_telegram_bot() -> None:
    assert _telegram_days(("mon", "wed", "fri", "sun")) == (1, 3, 5, 0)
