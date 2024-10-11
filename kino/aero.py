import asyncio
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import click
from crawlee.beautifulsoup_crawler import (
    BeautifulSoupCrawler,
    BeautifulSoupCrawlingContext,
)
from crawlee.router import Router
from crawlee import Request
from pydantic import BaseModel, RootModel

from kino.format_json import format_json


router = Router[BeautifulSoupCrawlingContext]()


class Event(BaseModel):
    model_config = {"frozen": True}

    projection_id: int
    url: str
    name: str
    starts_at: datetime
    ends_at: datetime


TimeTable = RootModel[dict[int, list[Event]]]


@click.command()
@click.option(
    "--path",
    default="aero.json",
    type=click.Path(path_type=Path),
)
def aero(path: Path):
    asyncio.run(scrape(path))
    format_json(path)


async def scrape(path: Path):
    crawler = BeautifulSoupCrawler(request_handler=router)
    request = Request.from_url(
        url="https://kinoaero.cz/api_program",
        method="POST",
        data={
            "cinema[]": 1,
            "ef": 0,
            "m": "",
            "wp": 0,
            "filterType": "default",
            "ao": 0,
            "d": 0,
            "_locale": "cs",
        },
    )
    await crawler.run([request])
    await crawler.export_data(path, dataset_name="aero")


@router.default_handler
async def detault_handler(context: BeautifulSoupCrawlingContext):
    timetable = defaultdict(list)
    for json_ld in context.soup.select("script[type='application/ld+json']"):
        data = json.loads(json_ld.text)
        if data["@type"] != "Event":
            continue
        projection_id = int(parse_qs(urlparse(data["url"]).query)["projection"][0])
        timetable[projection_id].append(
            Event(
                projection_id=projection_id,
                url=data["url"],
                name=data["name"],
                starts_at=data["startDate"],
                ends_at=data["endDate"],
            )
        )

    # see https://github.com/apify/crawlee-python/issues/524#issuecomment-2364353782
    timetable_json = TimeTable(timetable).model_dump_json()
    await context.add_requests(
        [
            Request.from_url(
                url="https://kinoaero.cz/api_film",
                method="POST",
                data={"pr": projection_id, "_locale": "cs"},
                user_data=dict(timetable=timetable_json),
                use_extended_unique_key=True,
                label="detail",
            )
            for projection_id in timetable.keys()
        ],
    )


@router.handler("detail")
async def detail_handler(context: BeautifulSoupCrawlingContext):
    context.log.info(f"Scraping {context.request.url}")
    projection_id = int(context.request.data["pr"])
    csfd_url = context.soup.select_one('a[href*="csfd.cz/film/"]')["href"]

    # see https://github.com/apify/crawlee-python/issues/524#issuecomment-2364353782
    timetable_json = context.request.user_data["timetable"]
    timetable = TimeTable.model_validate_json(timetable_json).model_dump()

    for event in timetable[projection_id]:
        await context.push_data(
            {
                "url": event["url"],
                "title": event["name"],
                "csfd_url": csfd_url,
                "starts_at": event["starts_at"].isoformat(),
                "ends_at": event["ends_at"].isoformat(),
            },
            dataset_name="aero",
        )
