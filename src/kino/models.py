from datetime import datetime
from enum import StrEnum

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
