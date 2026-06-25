from pathlib import Path

from kino.flags import build_codes_mapping, parse_flags


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_parse_flags_finds_country_select():
    html = (FIXTURES_DIR / "csfd_vlastni_vyber.html").read_text(encoding="utf-8")
    codes_mapping = build_codes_mapping()

    flags_mapping = parse_flags(html, codes_mapping)

    # the page lists hundreds of countries, so we should get plenty of flags
    assert len(flags_mapping) > 200
    assert flags_mapping["USA"] == "🇺🇸"
    assert flags_mapping["Česko"] == "🇨🇿"
    # continents and the placeholder option must be skipped
    assert "Evropa" not in flags_mapping
    assert "-všechny-" not in flags_mapping
