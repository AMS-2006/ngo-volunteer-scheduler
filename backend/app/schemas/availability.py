"""Pydantic schemas for volunteer availability windows."""

from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from app.schemas.common import normalise_time
from app.services.common import DAY_NAMES


class AvailabilityCreate(BaseModel):
    day_of_week: int = Field(
        ..., ge=0, le=6, description="0 = Monday … 6 = Sunday", examples=[5]
    )
    start_time: time = Field(..., examples=["09:00"])
    end_time: time = Field(..., examples=["13:00"])

    @field_validator("start_time", "end_time")
    @classmethod
    def _times(cls, v):
        return normalise_time(v)

    @model_validator(mode="after")
    def check_order(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time.")
        return self


class AvailabilityUpdate(BaseModel):
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None

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


class AvailabilityOut(BaseModel):
    id: str
    day_of_week: int
    start_time: time
    end_time: time
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def day_name(self) -> str:
        return DAY_NAMES[self.day_of_week]

    model_config = {"from_attributes": True}
