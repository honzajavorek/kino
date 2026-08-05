import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, TypedDict
from urllib.parse import urlencode, urljoin
from zoneinfo import ZoneInfo

from bs4 import Tag
from crawlee import Request
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from crawlee.router import Router
from pydantic import RootModel

from kino.models import AeroScreening, Cinema, Screening


PRAGUE_TZ = ZoneInfo("Europe/Prague")

CSFD_URL = "https://www.csfd.cz/kino/1-praha/?period=week"

AERO_PROGRAM_URL = "https://kinoaero.cz/?cinema=1&sort=sort-by-data"

AERO_API_FILM_URL = "https://kinoaero.cz/api_film"

CSFD_FILM_ID_RE = re.compile(r"/film/(\d+)")

CINEMAS = {
    "Praha - Cinema City Flora": Cinema.FLORA,
    "Praha - Cinema City Slovanský dům": Cinema.SLOVANAK,
    "Praha - Edison Filmhub": Cinema.EDISON,
    "Praha - Kino Aero": Cinema.AERO,
    "Praha - Kino Atlas": Cinema.ATLAS,
    "Praha - Kino Lucerna": Cinema.LUCERNA,
    "Praha - Kino Pilotů": Cinema.PILOTI,
    "Praha - Kino Světozor": Cinema.SVETOZOR,
    "Praha - Přítomnost Boutique Cinema": Cinema.PRITOMNOST,
}

YEAR_RE = re.compile(r"(19|20)\d{2}")

DATE_RE = re.compile(r"\d{1,2}.\d{1,2}.\d{4}")

DURATION_RE = re.compile(r"(\d+) min")


class UnexpectedStructureError(Exception):
    pass


class TimeTableScreening(TypedDict):
    cinema: str
    title: str
    starts_at: datetime


TimeTableDict = dict[str, list[TimeTableScreening]]


TimeTable = RootModel[TimeTableDict]


router = Router[BeautifulSoupCrawlingContext]()


async def scrape() -> list[Screening | AeroScreening]:
    crawler = BeautifulSoupCrawler(request_handler=router)
    await crawler.run(
        [
            CSFD_URL,
            Request.from_url(AERO_PROGRAM_URL, label="aero"),
        ]
    )
    if errors_count := crawler.statistics.state.requests_failed:
        raise RuntimeError(f"Failed requests: {errors_count}")

    dataset = await crawler.get_dataset()
    base: list[Screening] = []
    aero: list[dict[str, Any]] = []
    async for item in dataset.iterate_items():
        if "film_url" in item:
            base.append(Screening(**item))
        else:
            aero.append(item)
    return pair(base, aero)


def pair(
    base: list[Screening], aero: list[dict[str, Any]]
) -> list[Screening | AeroScreening]:
    # Keep everything from the CSFD base, then add Aero screenings which aren't
    # already there. A screening is the same when it's the same film (CSFD ID)
    # at the same time.
    known = {(csfd_film_id(s.film_url), s.starts_at) for s in base}
    screenings: list[Screening | AeroScreening] = list(base)
    for item in aero:
        screening = AeroScreening(
            cinema=Cinema.AERO,
            title=item["title"],
            screening_url=item["screening_url"],
            starts_at=item["starts_at"],
            ends_at=item["ends_at"],
            emoji="😎" if "naslepo" in item["title"].lower() else "✈️",
        )
        if (item["csfd_id"], screening.starts_at) not in known:
            screenings.append(screening)
    return screenings


def csfd_film_id(url: str) -> str | None:
    if match := CSFD_FILM_ID_RE.search(url):
        return match.group(1)
    return None


@router.default_handler
async def detault_handler(context: BeautifulSoupCrawlingContext):
    base_url = context.request.url
    timetable = defaultdict(list)
    for cinema in context.soup.select("#snippet--cinemas .updated-box-cinema"):
        if heading := cinema.select_one(".updated-box-header h2"):
            cinema_name = heading.text.strip()
        else:
            raise UnexpectedStructureError("No heading found")
        if cinema_name := CINEMAS.get(cinema_name):
            context.log.info(f"Cinema {cinema_name}")
            starts_on = None
            for div in cinema.select(
                ".update-box-sub-header, .box-content-table-cinema"
            ):
                if "update-box-sub-header" in div["class"]:
                    starts_on = parse_date(div.text)
                    context.log.info(f"Day {starts_on}")
                elif starts_on:
                    for film in div.select("tr"):
                        if link := film.select_one(".film-title-name"):
                            title, film_url = parse_link(base_url, link)
                        else:
                            raise UnexpectedStructureError("No link found")
                        if times := film.select_one(".td-time"):
                            if time_texts := parse_time_texts(times.text):
                                for time_text in time_texts:
                                    starts_at = parse_time(starts_on, time_text)
                                    context.log.info(
                                        f"Screening {starts_at} {film_url}"
                                    )
                                    timetable[film_url].append(
                                        {
                                            "cinema": cinema_name,
                                            "title": title,
                                            "starts_at": starts_at,
                                        }
                                    )
                            else:
                                raise UnexpectedStructureError("No time found")
                        else:
                            raise UnexpectedStructureError("No time found")
                else:
                    raise UnexpectedStructureError("No day set")
    await context.add_requests(
        [
            Request.from_url(film_url, user_data=to_user_data(timetable), label="film")
            for film_url in timetable
        ]
    )


def parse_link(base_url: str, tag: Tag) -> tuple[str, str]:
    return tag.text.strip(), urljoin(base_url, str(tag["href"]))


def parse_date(text: str) -> date:
    if match := DATE_RE.search(text.strip()):
        date_text = match.group()
        return datetime.strptime(date_text, "%d.%m.%Y").replace(tzinfo=PRAGUE_TZ).date()
    raise ValueError(f"No date: {text!r}")


def parse_time_texts(text: str) -> list:
    return list(filter(None, map(str.strip, text.split())))


def parse_time(starts_on: date, text: str) -> datetime:
    return datetime.combine(
        starts_on,
        datetime.strptime(text.strip(), "%H:%M").replace(tzinfo=PRAGUE_TZ).time(),
        tzinfo=PRAGUE_TZ,
    )


@router.handler("film")
async def film_handler(context: BeautifulSoupCrawlingContext):
    context.log.info(f"Film {context.request.url}")
    timetable = from_user_data(context.request.user_data)
    screenings = timetable[context.request.url]

    if origin := context.soup.select_one(".film-info-content .origin"):
        year = parse_year(origin.text)
        country = parse_country(origin.text)
    else:
        raise UnexpectedStructureError("No origin found")

    if info := context.soup.select_one(".film-info-content .origin"):
        duration = parse_duration(info.text)
    else:
        raise UnexpectedStructureError("No info found")

    if rating := context.soup.select_one(".film-rating-average"):
        rating_ptc = parse_rating_ptc(rating.text)
    else:
        rating_ptc = None

    for screening in screenings:
        await context.push_data(
            {
                "film_url": context.request.url,
                "ends_at": screening["starts_at"] + timedelta(minutes=duration),
                "rating": rating_ptc,
                "year": year,
                "country": country,
                **screening,
            }
        )


def parse_duration(text: str, default_duration: int = 140) -> int:
    durations = [int(duration.group(1)) for duration in DURATION_RE.finditer(text)]
    if not durations:
        return default_duration
    return sum(durations) // len(durations)


def parse_rating_ptc(text: str) -> int | None:
    if rating_ptc := text.strip().strip("?% "):
        return int(rating_ptc)
    return None


def parse_year(text: str) -> int:
    if match := re.search(YEAR_RE, text):
        return int(match.group())
    raise ValueError(f"No year: {text!r}")


def parse_country(text: str) -> str:
    try:
        country_text = re.split(YEAR_RE, text)[0]
        return country_text.split("/")[0].strip()
    except IndexError:
        raise ValueError(f"No country: {text!r}")


def to_user_data(timetable: TimeTableDict) -> dict[str, str]:
    # see https://github.com/apify/crawlee-python/issues/524#issuecomment-2364353782
    return {"timetable": TimeTable(timetable).model_dump_json()}


def from_user_data(user_data: dict[str, Any]) -> TimeTableDict:
    # see https://github.com/apify/crawlee-python/issues/524#issuecomment-2364353782
    return TimeTable.model_validate_json(user_data["timetable"]).model_dump()


@router.handler("aero")
async def aero_handler(context: BeautifulSoupCrawlingContext):
    context.log.info(f"Aero program {context.request.url}")
    requests = []
    for projection, screening in parse_aero_program(context.soup):
        context.log.info(f"Screening {screening['starts_at']} {projection}")
        requests.append(
            Request.from_url(
                AERO_API_FILM_URL,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                payload=urlencode({"pr": projection, "_locale": "cs"}).encode(),
                label="aero_film",
                unique_key=projection,  # all screenings share the api_film URL
                user_data=screening,
            )
        )
    await context.add_requests(requests)


def parse_aero_program(soup: Tag) -> list[tuple[str, dict[str, str]]]:
    program = []
    for row in soup.select(".program__info-row"):
        script = row.select_one('script[type="application/ld+json"]')
        element = row.select_one("[data-projection]")
        if not (script and script.string and element):
            continue  # e.g. sold out or cancelled screenings
        data = json.loads(script.string)
        program.append(
            (
                str(element["data-projection"]),
                {
                    "title": data["name"],
                    "screening_url": data["url"],
                    "starts_at": data["startDate"],
                    "ends_at": data["endDate"],
                },
            )
        )
    return program


@router.handler("aero_film")
async def aero_film_handler(context: BeautifulSoupCrawlingContext):
    context.log.info(f"Aero film {context.request.user_data['title']}")
    await context.push_data(
        {
            "title": context.request.user_data["title"],
            "screening_url": context.request.user_data["screening_url"],
            "starts_at": context.request.user_data["starts_at"],
            "ends_at": context.request.user_data["ends_at"],
            "csfd_id": parse_aero_csfd_id(context.soup),
        }
    )


def parse_aero_csfd_id(soup: Tag) -> str | None:
    # Missing link means Aero naslepo or a special event without a CSFD page.
    if link := soup.select_one('a[href*="csfd.cz/film/"]'):
        return csfd_film_id(str(link["href"]))
    return None
