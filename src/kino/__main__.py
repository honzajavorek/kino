import asyncio
from pathlib import Path

import click
from ics import Calendar, Event

from kino.flags import fetch_flags
from kino.models import Cinema, is_family_film, is_workday_screening
from kino.scraper import scrape


@click.command()
@click.option(
    "-c",
    "--cinema",
    "cinemas",
    default=[
        ("AERO", "kino.ics"),
        ("EDISON", "kino-extra.ics"),
        ("FLORA", "kino-multi.ics"),
        ("LUCERNA", "kino-extra.ics"),
        ("PRITOMNOST", "kino.ics"),
        ("SLOVANAK", "kino-multi.ics"),
        ("SVETOZOR", "kino-extra.ics"),
    ],
    help="Cinema specification",
    type=(
        click.Choice([member.name for member in Cinema], case_sensitive=False),
        click.Path(path_type=Path, dir_okay=False),
    ),
    multiple=True,
)
@click.option(
    "--workday",
    "workday_file",
    default="kino-workday.ics",
    help="Output file for screenings of all the cinemas on workdays ending by 15:30, except family films",
    type=click.Path(path_type=Path, dir_okay=False),
)
def main(cinemas: list[tuple[Cinema, Path]], workday_file: Path):
    files = {}
    for cinema, output_file in cinemas:
        files.setdefault(output_file, []).append(Cinema[cinema])

    flags = asyncio.run(fetch_flags())
    screenings = asyncio.run(scrape())

    for output_file, output_cinemas in files.items():
        write_calendar(
            output_file,
            [
                screening.to_ical(flags)
                for screening in screenings
                if screening.cinema in output_cinemas
            ],
        )

    all_cinemas = {
        cinema for output_cinemas in files.values() for cinema in output_cinemas
    }
    write_calendar(
        workday_file,
        [
            screening.to_ical(flags)
            for screening in screenings
            if screening.cinema in all_cinemas
            and is_workday_screening(screening.starts_at, screening.ends_at)
            and not is_family_film(screening)
        ],
    )


def write_calendar(output_file: Path, events: list[Event]) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    calendar = Calendar(events=events)
    with output_file.open("w") as f:
        f.writelines(calendar.serialize_iter())


main()
