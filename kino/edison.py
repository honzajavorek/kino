from collections import defaultdict
from pathlib import Path
import re
import asyncio
from datetime import date, datetime, timedelta
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import click
from crawlee.beautifulsoup_crawler import (
    BeautifulSoupCrawler,
    BeautifulSoupCrawlingContext,
)
from crawlee.router import Router
from pydantic import RootModel

from kino.format_json import format_json


router = Router[BeautifulSoupCrawlingContext]()


TimeTable = RootModel[dict[str, set[datetime]]]


@click.command()
@click.option(
    "--path",
    default="edison.json",
    type=click.Path(path_type=Path),
)
def edison(path: Path):
    asyncio.run(scrape(path))
    format_json(path)


async def scrape(path: Path):
    crawler = BeautifulSoupCrawler(request_handler=router)
    await crawler.run(["https://edisonfilmhub.cz/program"])
    await crawler.export_data(path, dataset_name="edison")


@router.default_handler
async def detault_handler(context: BeautifulSoupCrawlingContext):
    timetable = defaultdict(set)
    lines = context.soup.select(".program_table .line")
    starts_on = None
    for line in lines:
        if day := line.select_one(".den"):
            match = re.search(r"(\d{1,2}).\s*(\d{1,2}).", day.text)
            starts_on = date(
                date.today().year,  # TODO next year January
                int(match.group(2)),
                int(match.group(1)),
            )
        else:
            time = line.select_one(".time")
            match = re.search(r"(\d{1,2})[:\.](\d{1,2})", time.text)
            starts_at = datetime(
                starts_on.year,
                starts_on.month,
                starts_on.day,
                int(match.group(1)),
                int(match.group(2)),
                tzinfo=ZoneInfo("Europe/Prague"),
            )
            url = urljoin(
                context.request.loaded_url,
                line.select_one(".name a")["href"],
            )
            timetable[url].add(starts_at)

    # see https://github.com/apify/crawlee-python/issues/524#issuecomment-2364353782
    timetable_json = TimeTable(timetable).model_dump_json()
    await context.enqueue_links(
        selector=".program_table .name a",
        user_data=dict(timetable=timetable_json),
        label="detail",
    )


@router.handler("detail")
async def detail_handler(context: BeautifulSoupCrawlingContext):
    context.log.info(f"Scraping {context.request.url}")

    description = context.soup.select_one(".filmy_page .desc3").text
    length_min = int(re.search(r"(\d+)\s+min", description).group(1))

    # see https://github.com/apify/crawlee-python/issues/524#issuecomment-2364353782
    timetable_json = context.request.user_data["timetable"]
    timetable = TimeTable.model_validate_json(timetable_json).model_dump()

    for starts_at in timetable[context.request.url]:
        ends_at = starts_at + timedelta(minutes=length_min)
        await context.push_data(
            {
                "url": context.request.url,
                "title": context.soup.select_one(".filmy_page h1").text.strip(),
                "csfd_url": context.soup.select_one(".filmy_page .hrefs a")["href"],
                "starts_at": starts_at.isoformat(),
                "ends_at": ends_at.isoformat(),
            },
            dataset_name="edison",
        )
