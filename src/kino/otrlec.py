"""Editions of Festival otrlého diváka (Otrlec) held at Kino Aero."""

import re
from datetime import date

from bs4 import BeautifulSoup, Tag
from crawlee.http_clients import ImpitHttpClient

from kino.models import Festival


OTRLEC_URL = "https://otrlydivak.cz/akce/"

MONTHS = {
    name: number
    for number, name in enumerate(
        [
            "ledna",
            "února",
            "března",
            "dubna",
            "května",
            "června",
            "července",
            "srpna",
            "září",
            "října",
            "listopadu",
            "prosince",
        ],
        start=1,
    )
}

# e.g. "19. - 22. listopadu 2026 / kino Aero, Praha"
# or "28. února - 6. března 2022 / Kino Aero, Praha"
DATE_RANGE_RE = re.compile(
    r"^(?P<start_day>\d{1,2})\.\s*(?:(?P<start_month>\w+)\.?\s*)?-\s*"
    r"(?P<end_day>\d{1,2})\.\s*(?P<end_month>\w+)\.?\s*(?P<year>\d{4})"
    r"\s*/(?P<venue>.*)$"
)

AERO_RE = re.compile(r"\baero\b", re.IGNORECASE)


async def fetch_festivals(today: date) -> list[Festival]:
    response = await ImpitHttpClient().send_request(OTRLEC_URL)
    if response.status_code != 200:
        raise RuntimeError(f"Failed Otrlec request: HTTP {response.status_code}")
    soup = BeautifulSoup(await response.read(), "html.parser")
    return parse_festivals(soup, today)


def parse_festivals(soup: Tag, today: date) -> list[Festival]:
    """Return editions with multi-day dates at Kino Aero which haven't ended
    by today. Single screenings or editions elsewhere are left out."""
    festivals = []
    for item in soup.select(".jet-listing-grid__item"):
        if not (link := item.select_one("a.jet-engine-listing-overlay-link")):
            continue
        for field in item.select(".jet-listing-dynamic-field__content"):
            for line in field.get_text("\n").splitlines():
                if (dates := parse_aero_dates(line)) and dates[1] >= today:
                    festivals.append(
                        Festival(
                            url=str(link["href"]), starts_on=dates[0], ends_on=dates[1]
                        )
                    )
    return festivals


def parse_aero_dates(text: str) -> tuple[date, date] | None:
    """Parse a multi-day date range at Kino Aero, e.g. "19. - 22. listopadu
    2026 / kino Aero, Praha". Anything else gives None."""
    if not (match := DATE_RANGE_RE.match(text.strip())):
        return None
    if not AERO_RE.search(match["venue"]):
        return None
    year = int(match["year"])
    end_month = parse_month(match["end_month"])
    start_month = (
        parse_month(match["start_month"]) if match["start_month"] else end_month
    )
    starts_on = date(year, start_month, int(match["start_day"]))
    ends_on = date(year, end_month, int(match["end_day"]))
    return (starts_on, ends_on) if starts_on < ends_on else None


def parse_month(text: str) -> int:
    return int(text) if text.isdigit() else MONTHS[text.lower()]
