import gettext
from typing import cast

import httpx
import pycountry
import pycountry.db
from bs4 import BeautifulSoup
from flag import flag_safe


CODES_MAPPING_CUSTOM = {
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


def fetch_flags() -> dict[str, str]:
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
    codes_mapping = codes_mapping_official | codes_mapping_common | CODES_MAPPING_CUSTOM

    response = httpx.get("https://www.csfd.cz/zebricky/vlastni-vyber/")
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    if select := soup.select_one('select[name="origin"]'):
        flags_mapping = {}
        missing = set()
        for option in select.find_all("option"):
            try:
                int(option["value"])
            except ValueError:
                pass  # continents
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
