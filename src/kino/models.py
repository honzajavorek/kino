from datetime import datetime, time
from enum import StrEnum

from czech_holidays import czech_holidays
from ics import Event
from pydantic import BaseModel


WORKDAY_ENDS_AT = time(15, 30)


class Cinema(StrEnum):
    AERO = "Aero"
    ATLAS = "Atlas"
    EDISON = "Edison"
    FLORA = "Flora"
    LUCERNA = "Lucerna"
    PILOTI = "Piloti"
    PRITOMNOST = "Přítomnost"
    SLOVANAK = "Slovaňák"
    SVETOZOR = "Světozor"


class Screening(BaseModel):
    cinema: Cinema
    title: str
    film_url: str
    year: int
    country: str
    starts_at: datetime
    ends_at: datetime
    rating: int | None

    def to_ical(self, flags: dict[str, str]) -> Event:
        name = (
            f"{rating_to_emoji(self.rating)} {self.title}"
            if self.rating
            else self.title
        )
        return Event(
            name=f"{name} ({flags[self.country]} {self.year})",
            begin=self.starts_at,
            end=self.ends_at,
            location=str(self.cinema),
            url=self.film_url,
            description=self.film_url,
        )


class AeroScreening(BaseModel):
    """A Kino Aero screening without matching CSFD data (e.g. Aero naslepo
    or a special event). Carries its own emoji: 😎 for naslepo, ✈️ otherwise."""

    cinema: Cinema
    title: str
    screening_url: str
    starts_at: datetime
    ends_at: datetime
    emoji: str

    def to_ical(self, flags: dict[str, str]) -> Event:
        return Event(
            name=f"{self.emoji} {self.title}",
            begin=self.starts_at,
            end=self.ends_at,
            location=str(self.cinema),
            url=self.screening_url,
            description=self.screening_url,
        )


def rating_to_emoji(rating: int) -> str:
    if rating < 30:
        return "⚫️"
    if rating < 70:
        return "🔵"
    if rating < 90:
        return "🔴"
    return "🟡"


def is_workday_screening(starts_at: datetime, ends_at: datetime) -> bool:
    """Tells whether a screening fits a Czech working day, i.e. it's not on
    a weekend nor a public holiday, and it ends by WORKDAY_ENDS_AT."""
    day = starts_at.date()
    if day.weekday() >= 5:
        return False
    if day in {holiday.date for holiday in czech_holidays(day.year)}:
        return False
    return ends_at.date() == day and ends_at.time() <= WORKDAY_ENDS_AT
