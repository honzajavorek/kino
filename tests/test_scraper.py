from kino.scraper import parse_duration, parse_time_texts


def test_parse_duration_multiple_durations():
    text = """
        USA,
        1980, 149 min
        (Director's Cut: 219 min)
    """
    assert parse_duration(text) == (149 + 219) // 2


def test_missing_duration():
    text = """
        Indie, 2025
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
