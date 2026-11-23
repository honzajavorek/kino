from datetime import date
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from kino.models import Festival
from kino.otrlec import parse_aero_dates, parse_festivals


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> BeautifulSoup:
    return BeautifulSoup((FIXTURES / name).read_text(), "html.parser")


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "19. - 22. listopadu 2026 / kino Aero, Praha",
            (date(2026, 11, 19), date(2026, 11, 22)),
        ),
        (
            "28. února - 6. března 2022 / Kino Aero, Praha",
            (date(2022, 2, 28), date(2022, 3, 6)),
        ),
        (
            "5.-10. března 2019 / kino Aero, Praha",
            (date(2019, 3, 5), date(2019, 3, 10)),
        ),
        (
            "1. - 2. 11. 2024 / kino Aero, Praha",
            (date(2024, 11, 1), date(2024, 11, 2)),
        ),
        ("12. prosince 2026 / 19:00 / kino Aero, Praha", None),
        ("2. 11. 2019 / kino Aero, Praha", None),
        ("15.-16. 3. 2024 / Kino Lumière (Bratislava, Slovensko)", None),
        ("18. června 2026 / Bio Central, Hradec Králové", None),
        ("Otrlé dny duševního zdraví i sraví.", None),
    ],
)
def test_parse_aero_dates(text: str, expected: tuple[date, date] | None):
    """Only multi-day date ranges at Kino Aero are recognized."""
    assert parse_aero_dates(text) == expected


def test_parse_festivals():
    """Multi-day Aero editions which haven't ended yet are listed, while
    single screenings, editions elsewhere, and past editions are left out."""
    festivals = parse_festivals(fixture("otrlec_akce.html"), date(2026, 3, 1))

    assert festivals == [
        Festival(
            url="https://otrlydivak.cz/akce/2026-podzimni-sklizen/",
            starts_on=date(2026, 11, 19),
            ends_on=date(2026, 11, 22),
        ),
        Festival(
            url="https://otrlydivak.cz/akce/2026-21-rocnik/",
            starts_on=date(2026, 3, 23),
            ends_on=date(2026, 3, 29),
        ),
    ]


@pytest.mark.parametrize(
    "today, expected",
    [
        (date(2026, 11, 22), ["https://otrlydivak.cz/akce/2026-podzimni-sklizen/"]),
        (date(2026, 11, 23), []),
    ],
)
def test_parse_festivals_ongoing_until_last_day(today: date, expected: list[str]):
    """A festival stays in the calendar until its last day is over."""
    festivals = parse_festivals(fixture("otrlec_akce.html"), today)

    assert [festival.url for festival in festivals] == expected


def test_parse_festivals_all_past_editions():
    """All multi-day Aero editions are recognized, the 20th one included."""
    festivals = parse_festivals(fixture("otrlec_akce.html"), date(2000, 1, 1))
    urls = [festival.url for festival in festivals]

    assert "https://otrlydivak.cz/akce/20-rocnik-2025/" in urls
    assert "https://otrlydivak.cz/akce/rocky-horror-picture-show/" not in urls
    assert "https://otrlydivak.cz/akce/otrlec-na-febiu-v-blave-2025/" not in urls


def test_festival_to_ical():
    """A festival is an all-day event spanning all its days, linking to the
    edition's page."""
    festival = Festival(
        url="https://otrlydivak.cz/akce/2026-podzimni-sklizen/",
        starts_on=date(2026, 11, 19),
        ends_on=date(2026, 11, 22),
    )
    event = festival.to_ical()

    assert event.name == "Otrlec"
    assert event.all_day
    assert event.begin.date() == date(2026, 11, 19)
    assert event.end.date() == date(2026, 11, 23)  # exclusive end
    assert event.location == "Aero"
    assert event.url == "https://otrlydivak.cz/akce/2026-podzimni-sklizen/"
    assert event.description == "https://otrlydivak.cz/akce/2026-podzimni-sklizen/"
