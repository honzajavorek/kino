from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from kino.models import is_workday_screening, rating_to_emoji


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


@pytest.mark.parametrize(
    "starts_at, ends_at, expected",
    [
        (datetime(2026, 11, 2, 10, 0), datetime(2026, 11, 2, 12, 0), True),
        (datetime(2026, 11, 2, 13, 30), datetime(2026, 11, 2, 15, 29), True),
        (datetime(2026, 11, 2, 13, 30), datetime(2026, 11, 2, 15, 30), False),
        (datetime(2026, 11, 2, 14, 0), datetime(2026, 11, 2, 16, 0), False),
        (datetime(2026, 11, 7, 10, 0), datetime(2026, 11, 7, 12, 0), False),
        (datetime(2026, 11, 8, 10, 0), datetime(2026, 11, 8, 12, 0), False),
        (datetime(2026, 11, 17, 10, 0), datetime(2026, 11, 17, 12, 0), False),
        (datetime(2026, 12, 24, 10, 0), datetime(2026, 12, 24, 12, 0), False),
    ],
)
def test_is_workday_screening(starts_at: datetime, ends_at: datetime, expected: bool):
    """Only screenings on Czech working days which end before 15:30 qualify;
    weekends (7th, 8th Nov) and public holidays (17th Nov, 24th Dec) don't."""
    tz = ZoneInfo("Europe/Prague")
    assert (
        is_workday_screening(starts_at.replace(tzinfo=tz), ends_at.replace(tzinfo=tz))
        is expected
    )
