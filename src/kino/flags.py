import gettext
from typing import cast

import httpx
import pycountry
import pycountry.db
from bs4 import BeautifulSoup
from flag import flag_safe


CODES_MAPPING_CUSTOM = {
    "Anglická republika": "GB",
    "Anglické království": "GB",
    "Československo": "CZ",
    "Chorvatů a Slovinců": "HR",
    "Curacao": "CW",
    "Dánsko-norské království": "DK",
    "Demokratická republika Kongo": "CD",
    "Fed. rep. Jugoslávie": "RS",
    "Federativní státy Mikronésie": "FM",
    "Jugoslávie": "RS",
    "Kapverdy": "CV",
    "Korea": "KR",
    "Kosovo": "XK",
    "Království Jugoslávie": "RS",
    "Království Srbů, Chorvatů a Slovinců": "RS",
    "Království Srbů": "RS",
    "Kréta": "GR",
    "Maďarské království": "HU",
    "Makedonie": "MK",
    "Německá říše": "DE",
    "Německý spolek": "DE",
    "Nezávislý stát Chorvatsko": "HR",
    "Osmanská říše": "TR",
    "Palestina": "PS",
    "Papua-Nová Guinea": "PG",
    "Protektorát Čechy a Morava": "CZ",
    "Prusko": "DE",
    "Rakouské císařství": "AT",
    "Rakousko-Uhersko": "AT",
    "Ruské impérium": "RU",
    "Rusko": "RU",
    "Saint-Pierre a Miquelon": "PM",
    "Slovenský stát": "SK",
    "Sovětský svaz": "RU",
    "Srbsko a Černá Hora": "RS",
    "Svatá říše římská": "DE",
    "Švédsko-norská unie": "SE",
    "Tanzanie": "TZ",
    "Tibet": "CN",
    "Uherské království": "HU",
    "USA": "US",
    "Vatikán": "VA",
    "Velká Británie": "GB",
    "Východní Německo": "DE",
    "Západní Německo": "DE",
}


def build_codes_mapping() -> dict[str, str]:
    czech = gettext.translation("iso3166-1", pycountry.LOCALES_DIR, languages=["cs"])
    czech.install()

    countries = cast(list[pycountry.db.Country], list(pycountry.countries))
    codes_mapping_official = {
        czech.gettext(country.name): country.alpha_2 for country in countries
    }
    codes_mapping_common = {
        czech.gettext(country.common_name): country.alpha_2
        for country in countries
        if hasattr(country, "common_name")
    }
    return codes_mapping_official | codes_mapping_common | CODES_MAPPING_CUSTOM


def parse_flags(html: str, codes_mapping: dict[str, str]) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    if select := soup.select_one('select[name="country_id"]'):
        flags_mapping = {}
        missing = set()
        for option in select.find_all("option"):
            try:
                int(option["value"])
            except ValueError:
                pass  # placeholder and continents
            else:
                try:
                    code = codes_mapping[option.text]
                    flag = flag_safe(code, unsupported="error", invalid="error")
                    flags_mapping[option.text] = flag
                except KeyError:
                    missing.add(option.text)
        if missing:
            raise ValueError(f"Missing: {', '.join(missing)}")
        return flags_mapping
    else:
        raise ValueError("No select found")


def fetch_flags() -> dict[str, str]:
    codes_mapping = build_codes_mapping()
    response = httpx.get("https://www.csfd.cz/zebricky/vlastni-vyber/")
    response.raise_for_status()
    return parse_flags(response.text, codes_mapping)
