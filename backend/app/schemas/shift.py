"""
schemas/shift.py
────────────────
Pydantic schemas for Shift CRUD.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class MyRegistrationInfo(BaseModel):
    registration_id: str
    status: str
    waitlist_position: Optional[int] = None


# ── CREATE ────────────────────────────────────────────────────────────────────
class ShiftCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100,
                      examples=["Morning", "Afternoon", "Evening"])
    description: Optional[str] = Field(None, max_length=1000)
    start_time: datetime = Field(..., examples=["2026-11-15T08:00:00+05:30"])
    end_time: datetime = Field(..., examples=["2026-11-15T11:00:00+05:30"])
    required_volunteers: int = Field(..., ge=1, examples=[10])
    required_skills: Optional[str] = Field(None, max_length=500,
                                            examples=["First Aid"])

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


# ── UPDATE ────────────────────────────────────────────────────────────────────
class ShiftUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    required_volunteers: Optional[int] = Field(None, ge=1)
    required_skills: Optional[str] = None


# ── OUTPUT ────────────────────────────────────────────────────────────────────
class ShiftOut(BaseModel):
    id: str
    event_id: str
    name: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    required_volunteers: int
    required_skills: Optional[str]
    # Derived coverage data (computed from registrations)
    confirmed_count: int = 0
    waitlist_count: int = 0
    slots_remaining: int = 0
    is_full: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
