import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, TypedDict
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import Tag
from crawlee import Request
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from crawlee.router import Router
from pydantic import RootModel

from kino.models import Cinema, Screening


CSFD_URL = "https://www.csfd.cz/kino/1-praha/?period=week"

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


async def scrape() -> list[Screening]:
    crawler = BeautifulSoupCrawler(request_handler=router)
    await crawler.run([CSFD_URL])
    dataset = await crawler.get_dataset()
    return [Screening(**item) async for item in dataset.iterate_items()]


@router.default_handler
async def detault_handler(context: BeautifulSoupCrawlingContext):
    base_url = context.request.url
    timetable = defaultdict(list)
    for cinema in context.soup.select("#cinemas .box"):
        if heading := cinema.select_one(".box-header h2"):
            cinema_name = heading.text.strip()
        else:
            raise UnexpectedStructureError("No heading found")
        if cinema_name := CINEMAS.get(cinema_name):
            context.log.info(f"Cinema {cinema_name}")
            starts_on = None
            for div in cinema.select(".box-sub-header, .box-content-table-cinema"):
                if "box-sub-header" in div["class"]:
                    starts_on = parse_date(div.text)
                    context.log.info(f"Day {starts_on}")
                elif starts_on:
                    for film in div.select("tr"):
                        if link := film.select_one(".film-title-name"):
                            title, film_url = parse_link(base_url, link)
                        else:
                            raise UnexpectedStructureError("No link found")
                        if time := film.select_one(".td-time"):
                            time_text = time.text.strip()
                            starts_at = parse_time(starts_on, time_text)
                        else:
                            raise UnexpectedStructureError("No time found")
                        context.log.info(f"Screening {starts_at} {film_url}")
                        timetable[film_url].append(
                            {
                                "cinema": cinema_name,
                                "title": title,
                                "starts_at": starts_at,
                            }
                        )
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
        return datetime.strptime(date_text, "%d.%m.%Y").date()
    raise ValueError(f"No date: {text!r}")


def parse_time(starts_on: date, text: str) -> datetime:
    return datetime.combine(
        starts_on,
        datetime.strptime(text.strip(), "%H:%M").time(),
        tzinfo=ZoneInfo("Europe/Prague"),
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


def parse_duration(text: str) -> int:
    durations = [int(duration.group(1)) for duration in DURATION_RE.finditer(text)]
    return sum(durations) // len(durations)


def parse_rating_ptc(text: str) -> int | None:
    if rating_ptc := text.strip().strip("?% "):
        return int(rating_ptc)
    return None


def parse_year(text: str) -> int:
    if match := re.search(r"(19|20)\d{2}", text):
        return int(match.group())
    raise ValueError(f"No year: {text!r}")


def parse_country(text: str) -> str:
    try:
        return re.split(r"[/,]", text)[0].strip()
    except IndexError:
        raise ValueError(f"No country: {text!r}")


def to_user_data(timetable: TimeTableDict) -> dict[str, str]:
    # see https://github.com/apify/crawlee-python/issues/524#issuecomment-2364353782
    return {"timetable": TimeTable(timetable).model_dump_json()}


def from_user_data(user_data: dict[str, Any]) -> TimeTableDict:
    # see https://github.com/apify/crawlee-python/issues/524#issuecomment-2364353782
    return TimeTable.model_validate_json(user_data["timetable"]).model_dump()
