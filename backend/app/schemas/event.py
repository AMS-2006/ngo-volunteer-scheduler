"""Pydantic schemas for events (minimal – Module 1 may extend)."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class EventCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, examples=["Beach Clean-up Drive"])
    description: Optional[str] = Field(None, max_length=2000)
    location: str = Field(..., min_length=2, max_length=300, examples=["Marina Beach, Chennai"])
    start_date: date = Field(..., examples=["2026-12-05"])
    end_date: date = Field(..., examples=["2026-12-06"])

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date.")
        return self


class EventOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    location: str
    start_date: date
    end_date: date
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
