from kino.scraper import parse_country, parse_duration, parse_time_texts, parse_year


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
