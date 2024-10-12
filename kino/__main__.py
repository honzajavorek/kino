import asyncio
from pathlib import Path

import click

from kino.scraper import scrape


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


main()
