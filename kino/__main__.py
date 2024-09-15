import click

from kino.aero import aero
from kino.edison import edison


@click.group()
def main():
    pass


main.add_command(aero)
main.add_command(edison)


main()
