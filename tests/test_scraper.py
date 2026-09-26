import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from bs4 import BeautifulSoup

from kino import scraper
from kino.models import AeroScreening, Cinema, Screening
from kino.scraper import (
    PRAGUE_TZ,
    UnexpectedStructureError,
    build_screening_item,
    csfd_film_id,
    pair,
    parse_aero_csfd_id,
    parse_aero_program,
    parse_country,
    parse_csfd_timetable,
    parse_duration,
    parse_time_texts,
    parse_year,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> BeautifulSoup:
    return BeautifulSoup((FIXTURES / name).read_text(), "html.parser")


def test_parse_year():
    text = """
        Česko / Slovensko / Itálie \n2025  103 min \n\n\t\t\t\t\t\t
    """

    assert parse_year(text) == 2025


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Itálie / USA \n1979  102 min (Alternativní 180 min)", (102 + 180) // 2),
        ("Velká Británie / Kypr \n2026", 140),
    ],
)
def test_parse_duration(text: str, expected: int):
    assert parse_duration(text) == expected


def test_parse_time_texts():
    text = """
        10:00
        12:30
        15:00
        17:30
        20:00
    """

    assert parse_time_texts(text) == [
        "10:00",
        "12:30",
        "15:00",
        "17:30",
        "20:00",
    ]


def test_parse_csfd_timetable_groups_films_and_times():
    timetable = parse_csfd_timetable(
        fixture("csfd_program.html"), "https://www.csfd.cz/kino/1-praha/"
    )

    assert timetable == {
        "https://www.csfd.cz/film/111-film/prehled/": [
            {
                "cinema": Cinema.AERO,
                "title": "Film",
                "starts_at": datetime(2026, 8, 5, 18, 0, tzinfo=PRAGUE_TZ),
            },
            {
                "cinema": Cinema.AERO,
                "title": "Film",
                "starts_at": datetime(2026, 8, 5, 20, 30, tzinfo=PRAGUE_TZ),
            },
        ],
        "https://www.csfd.cz/film/222-film/prehled/": [
            {
                "cinema": Cinema.AERO,
                "title": "Další film",
                "starts_at": datetime(2026, 8, 6, 19, 0, tzinfo=PRAGUE_TZ),
            }
        ],
    }


@pytest.mark.parametrize(
    "fragment, message",
    [
        ('<div class="updated-box-cinema"></div>', "No heading found"),
        (
            '<div class="updated-box-cinema"><div class="updated-box-header"><h2>Praha - Kino Aero</h2></div><div class="box-content-table-cinema"></div></div>',
            "No day set",
        ),
        (
            '<div class="updated-box-cinema"><div class="updated-box-header"><h2>Praha - Kino Aero</h2></div><div class="update-box-sub-header">5.8.2026</div><div class="box-content-table-cinema"><tr><td class="td-time">18:00</td></tr></div></div>',
            "No link found",
        ),
        (
            '<div class="updated-box-cinema"><div class="updated-box-header"><h2>Praha - Kino Aero</h2></div><div class="update-box-sub-header">5.8.2026</div><div class="box-content-table-cinema"><tr><a class="film-title-name" href="/film/1/">Film</a></tr></div></div>',
            "No time found",
        ),
    ],
)
def test_parse_csfd_timetable_preserves_structure_errors(fragment: str, message: str):
    soup = BeautifulSoup(f'<div id="snippet--cinemas">{fragment}</div>', "html.parser")

    with pytest.raises(UnexpectedStructureError, match=message):
        parse_csfd_timetable(soup, "https://www.csfd.cz/kino/1-praha/")


def test_build_screening_item_keeps_calendar_fields():
    starts_at = datetime(2026, 8, 5, 18, 0, tzinfo=PRAGUE_TZ)

    item = build_screening_item(
        "https://www.csfd.cz/film/111-film/prehled/",
        {"cinema": Cinema.AERO, "title": "Film", "starts_at": starts_at},
        {"duration": 120, "rating": 80, "year": 2026, "country": "USA"},
    )

    assert item == {
        "film_url": "https://www.csfd.cz/film/111-film/prehled/",
        "ends_at": starts_at + timedelta(minutes=120),
        "rating": 80,
        "year": 2026,
        "country": "USA",
        "cinema": Cinema.AERO,
        "title": "Film",
        "starts_at": starts_at,
    }


def test_cached_and_fetched_film_produce_identical_screenings(monkeypatch):
    film_url = "https://www.csfd.cz/film/111-film/prehled/"
    metadata = {"duration": 120, "rating": 80, "year": 2026, "country": "USA"}
    cache = SimpleNamespace(
        get=lambda url: metadata if url == film_url else None,
        set=Mock(),
    )
    monkeypatch.setattr(scraper, "film_cache", cache)
    cached = SimpleNamespace(
        page=SimpleNamespace(
            content=AsyncMock(return_value=(FIXTURES / "csfd_program.html").read_text())
        ),
        request=SimpleNamespace(url="https://www.csfd.cz/kino/1-praha/"),
        push_data=AsyncMock(),
        add_requests=AsyncMock(),
        log=SimpleNamespace(info=Mock()),
    )

    asyncio.run(scraper.default_handler(cached))

    timetable = parse_csfd_timetable(fixture("csfd_program.html"), cached.request.url)
    fetched = SimpleNamespace(
        page=SimpleNamespace(
            content=AsyncMock(
                return_value='<div class="film-info-content"><div class="origin">USA 2026 120 min</div></div><div class="film-rating-average">80 %</div>'
            )
        ),
        request=SimpleNamespace(
            url=film_url,
            user_data=scraper.to_user_data({film_url: timetable[film_url]}),
        ),
        push_data=AsyncMock(),
        log=SimpleNamespace(info=Mock()),
    )

    asyncio.run(scraper.film_handler(fetched))

    assert [call.args[0] for call in cached.push_data.await_args_list] == [
        call.args[0] for call in fetched.push_data.await_args_list
    ]
    assert len(cached.add_requests.await_args.args[0]) == 1
    assert cache.set.call_args.args == (film_url, metadata)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("USA \n2026  94 min", "USA"),
        ("Česko / Slovinsko / Polsko / Slovensko / Francie \n2025  110 min", "Česko"),
    ],
)
def test_parse_country(text: str, expected: str):
    assert parse_country(text) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.csfd.cz/film/1703542-title/prehled/", "1703542"),
        ("https://www.csfd.cz/film/1703542", "1703542"),
        ("https://kinoaero.cz/?projection=50303", None),
    ],
)
def test_csfd_film_id(url: str, expected: str | None):
    assert csfd_film_id(url) == expected


def test_parse_aero_program():
    program = parse_aero_program(fixture("aero_program.html"))

    assert program == [
        (
            "50303",
            {
                "title": "Aero naslepo",
                "screening_url": "https://kinoaero.cz/?projection=50303",
                "starts_at": "2026-08-05T20:30:00+02:00",
                "ends_at": "2026-08-05T22:30:00+02:00",
                "emoji": "😎",
            },
        ),
        (
            "52659",
            {
                "title": "Přísahám, že za to nemůžu",
                "screening_url": "https://kinoaero.cz/?projection=52659",
                "starts_at": "2026-08-06T13:30:00+02:00",
                "ends_at": "2026-08-06T15:31:00+02:00",
                "emoji": "✈️",
            },
        ),
    ]


@pytest.mark.parametrize(
    "name, expected",
    [
        ("aero_film.html", "1703542"),
        ("aero_film_no_csfd.html", None),
    ],
)
def test_parse_aero_csfd_id(name: str, expected: str | None):
    assert parse_aero_csfd_id(fixture(name)) == expected


def screening(**kwargs) -> Screening:
    return Screening(
        **{
            "cinema": Cinema.AERO,
            "title": "Film",
            "film_url": "https://www.csfd.cz/film/111-film/prehled/",
            "year": 2026,
            "country": "USA",
            "starts_at": datetime(2026, 8, 6, 18, 0, tzinfo=PRAGUE_TZ),
            "ends_at": datetime(2026, 8, 6, 20, 0, tzinfo=PRAGUE_TZ),
            "rating": 80,
            **kwargs,
        }
    )


def aero_item(**kwargs) -> dict:
    return {
        "title": "Film",
        "screening_url": "https://kinoaero.cz/?projection=1",
        "starts_at": "2026-08-06T18:00:00+02:00",
        "ends_at": "2026-08-06T20:00:00+02:00",
        "emoji": "✈️",
        "csfd_id": "111",
        **kwargs,
    }


def test_pair_keeps_base_when_already_present():
    base = screening(film_url="https://www.csfd.cz/film/111-film/prehled/")
    aero = aero_item(csfd_id="111", starts_at="2026-08-06T18:00:00+02:00")

    result = pair([base], [aero])

    assert result == [base]


def test_pair_adds_screening_missing_from_base():
    # Same film (CSFD id 111) but a screening time the base doesn't have.
    aero = aero_item(csfd_id="111", starts_at="2026-08-07T18:00:00+02:00")

    result = pair([screening()], [aero])

    assert len(result) == 2
    assert isinstance(result[1], AeroScreening)


@pytest.mark.parametrize("emoji", ["😎", "✈️"])
def test_pair_keeps_aero_emoji(emoji: str):
    # Screenings without a CSFD link are always added, keeping their emoji.
    result = pair([], [aero_item(csfd_id=None, emoji=emoji)])

    assert result == [
        AeroScreening(
            cinema=Cinema.AERO,
            title="Film",
            screening_url="https://kinoaero.cz/?projection=1",
            starts_at=datetime(2026, 8, 6, 18, 0, tzinfo=PRAGUE_TZ),
            ends_at=datetime(2026, 8, 6, 20, 0, tzinfo=PRAGUE_TZ),
            emoji=emoji,
        )
    ]
