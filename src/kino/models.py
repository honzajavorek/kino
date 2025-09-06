from datetime import datetime
from enum import StrEnum

from ics import Event
from pydantic import BaseModel


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


class SecretScreening(BaseModel):
    cinema: Cinema
    title: str
    screening_url: str
    starts_at: datetime
    ends_at: datetime

    def to_ical(self, flags: dict[str, str]) -> Event:
        return Event(
            name=f"😎 {self.title}",
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
