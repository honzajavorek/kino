import pytest

from kino.icalendar import rating_to_emoji


@pytest.mark.parametrize(
    "rating, expected",
    [
        (1, "⚫️"),
        (29, "⚫️"),
        (30, "🔵"),
        (69, "🔵"),
        (70, "🔴"),
        (89, "🔴"),
        (90, "🟡"),
        (100, "🟡"),
    ],
)
def test_rating_to_emoji(rating: int, expected: str):
    assert rating_to_emoji(rating) == expected
