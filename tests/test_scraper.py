from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from kino.models import AeroScreening, Cinema, Screening
from kino.scraper import (
    PRAGUE_TZ,
    csfd_film_id,
    pair,
    parse_aero_csfd_id,
    parse_aero_program,
    parse_country,
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


def test_parse_duration_multiple_durations():
    text = """
        Itálie / USA \n1979  102 min (Alternativní 180 min)\n\n\t\t\t\t\t\t
    """
    assert parse_duration(text) == (102 + 180) // 2


def test_missing_duration():
    text = """
        Velká Británie / Kypr \n2026 \n\n\t\t\t\t\t\t
    """
    assert parse_duration(text) == 140


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


def test_parse_country():
    text = """
        USA \n2026  94 min \n\n\t\t\t\t\t\t
    """
    assert parse_country(text) == "USA"


def test_parse_country_multiple():
    text = """
        Česko / Slovinsko / Polsko / Slovensko / Chorvatsko / Francie \n2025  110 min \n\n\t\t\t\t\t\t
    """
    assert parse_country(text) == "Česko"


def test_csfd_film_id():
    assert csfd_film_id("https://www.csfd.cz/film/1703542-title/prehled/") == "1703542"
    assert csfd_film_id("https://www.csfd.cz/film/1703542") == "1703542"


def test_csfd_film_id_missing():
    assert csfd_film_id("https://kinoaero.cz/?projection=50303") is None


def test_parse_aero_program():
    program = parse_aero_program(fixture("aero_program.html"))
    projections = [projection for projection, _ in program]
    titles = [screening["title"] for _, screening in program]
    assert projections == ["50303", "52659"]
    assert titles == ["Aero naslepo", "Přísahám, že za to nemůžu"]
    assert program[0][1] == {
        "title": "Aero naslepo",
        "screening_url": "https://kinoaero.cz/?projection=50303",
        "starts_at": "2026-08-05T20:30:00+02:00",
        "ends_at": "2026-08-05T22:30:00+02:00",
    }


def test_parse_aero_csfd_id():
    assert parse_aero_csfd_id(fixture("aero_film.html")) == "1703542"


def test_parse_aero_csfd_id_missing():
    assert parse_aero_csfd_id(fixture("aero_film_no_csfd.html")) is None


def screening(**kwargs) -> Screening:
    return Screening(
        cinema=Cinema.AERO,
        title="Film",
        film_url="https://www.csfd.cz/film/111-film/prehled/",
        year=2026,
        country="USA",
        starts_at=datetime(2026, 8, 6, 18, 0, tzinfo=PRAGUE_TZ),
        ends_at=datetime(2026, 8, 6, 20, 0, tzinfo=PRAGUE_TZ),
        rating=80,
        **kwargs,
    )


def aero_item(**kwargs) -> dict:
    return {
        "title": "Film",
        "screening_url": "https://kinoaero.cz/?projection=1",
        "starts_at": "2026-08-06T18:00:00+02:00",
        "ends_at": "2026-08-06T20:00:00+02:00",
        "csfd_id": "111",
        **kwargs,
    }


def test_pair_keeps_base_when_already_present():
    # Same film (CSFD id 111) at the same time is already in the base.
    result = pair([screening()], [aero_item()])
    assert result == [screening()]


def test_pair_adds_missing_aero_screening():
    result = pair([screening()], [aero_item(starts_at="2026-08-07T18:00:00+02:00")])
    assert len(result) == 2
    assert isinstance(result[1], AeroScreening)
    assert result[1].emoji == "✈️"


def test_pair_adds_naslepo_with_smiley():
    result = pair([], [aero_item(title="Aero naslepo", csfd_id=None)])
    assert len(result) == 1
    assert result[0].emoji == "😎"


def test_pair_adds_special_without_link_as_generic():
    result = pair(
        [], [aero_item(title="Dejvické divadlo: Ucpanej systém", csfd_id=None)]
    )
    assert result[0].emoji == "✈️"
