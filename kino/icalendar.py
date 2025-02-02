from typing import Iterable

from ics import Calendar, Event

from kino.models import Screening


def create_calendar(screenings: Iterable[Screening], flags: dict[str, str]) -> Calendar:
    calendar = Calendar()
    for screening in screenings:
        calendar.events.add(create_event(screening, flags))
    return calendar


def create_event(screening: Screening, flags: dict[str, str]) -> Event:
    name = (
        f"{rating_to_emoji(screening.rating)} {screening.title}"
        if screening.rating
        else screening.title
    )
    return Event(
        name=f"{name} ({flags[screening.country]} {screening.year})",
        begin=screening.starts_at,
        end=screening.ends_at,
        location=str(screening.cinema),
        url=screening.film_url,
        description=screening.film_url,
    )


def rating_to_emoji(rating: int) -> str:
    if rating < 30:
        return "⚫️"
    if rating < 70:
        return "🔵"
    if rating < 90:
        return "🔴"
    return "🟡"
