import asyncio
from pathlib import Path

import click

from kino.flags import fetch_flags
from kino.icalendar import create_calendar
from kino.models import Cinema
from kino.scraper import scrape


@click.command()
@click.option(
    "-c",
    "--cinema",
    "cinemas",
    default=[
        ("AERO", "kino.ics"),
        ("ATLAS", "kino-extra.ics"),
        ("EDISON", "kino.ics"),
        ("FLORA", "kino-extra.ics"),
        ("LUCERNA", "kino.ics"),
        ("PILOTI", "kino-extra.ics"),
        ("PRITOMNOST", "kino.ics"),
        ("SLOVANAK", "kino-extra.ics"),
        ("SVETOZOR", "kino.ics"),
    ],
    help="Cinema specification",
    type=(
        click.Choice([member.name for member in Cinema], case_sensitive=False),
        click.Path(path_type=Path, dir_okay=False),
    ),
    multiple=True,
)
def main(cinemas: list[tuple[Cinema, Path]]):
    files = {}
    for cinema, output_file in cinemas:
        files.setdefault(output_file, []).append(Cinema[cinema])

    flags = fetch_flags()
    screenings = asyncio.run(scrape())

    for output_file, cinemas in files.items():
        output_file.parent.mkdir(parents=True, exist_ok=True)
        calendar = create_calendar(
            [s for s in screenings if s.cinema in cinemas], flags
        )
        with output_file.open("w") as f:
            f.writelines(calendar.serialize_iter())


main()
