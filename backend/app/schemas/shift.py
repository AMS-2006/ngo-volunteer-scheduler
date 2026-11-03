"""Pydantic schemas for shifts."""

from datetime import date, time
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import normalise_time


class ShiftCreate(BaseModel):
    event_id: str
    title: str = Field(..., min_length=2, max_length=200, examples=["Morning registration desk"])
    shift_date: date = Field(..., examples=["2026-12-05"])
    start_time: time = Field(..., examples=["09:00"])
    end_time: time = Field(..., examples=["12:00"])
    capacity: int = Field(..., ge=1, le=1000, examples=[10])

    @field_validator("start_time", "end_time")
    @classmethod
    def _times(cls, v):
        return normalise_time(v)

    @model_validator(mode="after")
    def check_order(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time (shifts cannot span midnight).")
        return self


class ShiftUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=200)
    shift_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    capacity: Optional[int] = Field(None, ge=1, le=1000)

    @field_validator("start_time", "end_time")
    @classmethod
    def _times(cls, v):
        return normalise_time(v) if v is not None else v

    @model_validator(mode="after")
    def check_order(self):
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("end_time must be after start_time.")
        return self


class MyRegistrationInfo(BaseModel):
    registration_id: str
    status: str
    waitlist_position: Optional[int] = None


class ShiftOut(BaseModel):
    id: str
    event_id: str
    event_name: str
    event_location: str
    title: str
    shift_date: date
    start_time: time
    end_time: time
    capacity: int
    registered_count: int
    remaining_slots: int
    waitlist_count: int
    is_full: bool
    status: str
    my_registration: Optional[MyRegistrationInfo] = None
