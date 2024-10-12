import asyncio
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import click
import ics
from crawlee import Request
from crawlee.beautifulsoup_crawler import (
    BeautifulSoupCrawler,
    BeautifulSoupCrawlingContext,
)
from crawlee.router import Router
from pydantic import BaseModel, RootModel


CINEMAS = {
    "Praha - Kino Aero": "Aero",
    "Praha - Přítomnost Boutique Cinema": "Přítomnost",
    "Praha - Edison Filmhub": "Edison",
}

DATE_RE = re.compile(r"\d{1,2}.\d{1,2}.\d{4}")

LENGTH_RE = re.compile(r"(\d+) min")


class TimeTableScreening(TypedDict):
    cinema: str
    title: str
    starts_at: datetime


TimeTableDict = dict[str, list[TimeTableScreening]]

TimeTable = RootModel[TimeTableDict]


class Screening(BaseModel):
    cinema: str
    title: str
    film_url: str
    starts_at: datetime
    ends_at: datetime
    rating: int | None

    def to_event(self) -> ics.Event:
        return ics.Event(
            name=f"{self.title} ({self.rating} %)" if self.rating else self.title,
            begin=self.starts_at,
            end=self.ends_at,
            location=self.cinema,
            url=self.film_url,
            description=self.film_url,
        )


router = Router[BeautifulSoupCrawlingContext]()


@click.command()
@click.option(
    "-o",
    "--output",
    "output_file",
    default="kino.ics",
    help="Output file",
    type=click.Path(path_type=Path),
)
def main(output_file: Path):
    output_file.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(scrape(output_file))


async def scrape(output_file: Path):
    crawler = BeautifulSoupCrawler(request_handler=router)
    await crawler.run(["https://www.csfd.cz/kino/1-praha/?period=week"])
    dataset = await crawler.get_dataset()

    calendar = ics.Calendar()
    async for item in dataset.iterate_items():
        calendar.events.add(Screening(**item).to_event())

    crawler.log.info(f"Saving {len(calendar.events)} events")
    with output_file.open("w") as f:
        f.writelines(calendar.serialize_iter())


@router.default_handler
async def detault_handler(context: BeautifulSoupCrawlingContext):
    base_url = context.request.url
    timetable = defaultdict(list)
    for cinema in context.soup.select("#cinemas .box"):
        cinema_name = cinema.select_one(".box-header h2").text.strip()
        if cinema_name := CINEMAS.get(cinema_name):
            context.log.info(f"Cinema {cinema_name}")
            starts_on = None
            for div in cinema.select(".box-sub-header, .box-content-table-cinema"):
                if "box-sub-header" in div["class"]:
                    date_text = DATE_RE.search(div.text.strip()).group()
                    starts_on = datetime.strptime(date_text, "%d.%m.%Y").date()
                    context.log.info(f"Day {starts_on}")
                else:
                    for film in div.select("tr"):
                        link = film.select_one(".film-title-name")
                        title = link.text.strip()
                        time_text = film.select_one(".td-time").text.strip()
                        starts_at = datetime.combine(
                            starts_on,
                            datetime.strptime(time_text, "%H:%M").time(),
                            tzinfo=ZoneInfo("Europe/Prague"),
                        )
                        film_url = urljoin(base_url, link["href"])
                        context.log.info(f"Screening {starts_at} {film_url}")
                        timetable[film_url].append(
                            TimeTableScreening(
                                cinema=cinema_name, starts_at=starts_at, title=title
                            )
                        )
    await context.add_requests(
        [
            Request.from_url(film_url, user_data=to_user_data(timetable), label="film")
            for film_url in timetable
        ]
    )


@router.handler("film")
async def film_handler(context: BeautifulSoupCrawlingContext):
    context.log.info(f"Film {context.request.url}")
    info = context.soup.select_one(".film-info-content .origin")
    lengths = [int(length.group(1)) for length in LENGTH_RE.finditer(info.text)]
    avg_length = sum(lengths) // len(lengths)

    if (
        rating := context.soup.select_one(".film-rating-average")
        .text.strip()
        .strip("?% ")
    ):
        rating = int(rating)
    else:
        rating = None

    timetable = from_user_data(context.request.user_data)
    for timetable_screening in timetable[context.request.url]:
        ends_at = timetable_screening["starts_at"] + timedelta(minutes=avg_length)
        await context.push_data(
            {
                "film_url": context.request.url,
                "ends_at": ends_at,
                "rating": rating,
                **timetable_screening,
            }
        )


def to_user_data(timetable: TimeTableDict) -> dict[str, str]:
    # see https://github.com/apify/crawlee-python/issues/524#issuecomment-2364353782
    return {"timetable": TimeTable(timetable).model_dump_json()}


def from_user_data(user_data: dict[str, Any]) -> TimeTableDict:
    # see https://github.com/apify/crawlee-python/issues/524#issuecomment-2364353782
    return TimeTable.model_validate_json(user_data["timetable"]).model_dump()
