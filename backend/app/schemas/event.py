"""
schemas/event.py
────────────────
Pydantic schemas for Event CRUD.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

VALID_STATUSES = {"draft", "published", "completed", "cancelled"}


class ShiftInline(BaseModel):
    """Compact shift summary embedded inside EventOut."""
    id: str
    name: str
    start_time: datetime
    end_time: datetime
    required_volunteers: int
    confirmed_count: int = 0
    slots_remaining: int = 0
    model_config = {"from_attributes": True}


# ── CREATE ────────────────────────────────────────────────────────────────────
class EventCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200,
                       examples=["Bengaluru Lake Cleanup"])
    description: Optional[str] = Field(None, max_length=3000)

    # Location
    location_name: Optional[str] = Field(None, max_length=200, examples=["Jakkur Lake"])
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100, examples=["Bengaluru"])
    state: Optional[str] = Field(None, max_length=100)
    pincode: Optional[str] = Field(None, max_length=10)
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Dates
    event_date: datetime = Field(..., examples=["2026-11-15T08:00:00+05:30"])
    event_end_date: Optional[datetime] = Field(None, examples=["2026-11-15T16:00:00+05:30"])

    # Volunteer requirements
    total_volunteers_required: int = Field(..., ge=1, examples=[30])
    required_skills: Optional[str] = Field(None, max_length=500,
                                            examples=["First Aid, Communication"])
    cause_category: Optional[str] = Field(None, max_length=100, examples=["Environment"])

    # Status defaults to 'draft'; admin explicitly publishes
    status: str = Field(default="draft", examples=["draft"])

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        return v

    @model_validator(mode="after")
    def validate_dates(self):
        if self.event_end_date and self.event_end_date <= self.event_date:
            raise ValueError("event_end_date must be after event_date")
        return self


# ── UPDATE ────────────────────────────────────────────────────────────────────
class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = None
    location_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    event_date: Optional[datetime] = None
    event_end_date: Optional[datetime] = None
    total_volunteers_required: Optional[int] = Field(None, ge=1)
    required_skills: Optional[str] = None
    cause_category: Optional[str] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        return v


# ── OUTPUT ────────────────────────────────────────────────────────────────────
class EventOut(BaseModel):
    id: str
    ngo_id: str
    created_by: Optional[str]
    title: str
    description: Optional[str]
    location_name: Optional[str]
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    pincode: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    event_date: datetime
    event_end_date: Optional[datetime]
    total_volunteers_required: int
    required_skills: Optional[str]
    cause_category: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    shifts: list[ShiftInline] = []

    model_config = {"from_attributes": True}


class EventSummary(BaseModel):
    """Lightweight card for list views and public portal."""
    id: str
    title: str
    location_name: Optional[str]
    city: Optional[str]
    event_date: datetime
    total_volunteers_required: int
    status: str
    cause_category: Optional[str]
    shift_count: int = 0

    model_config = {"from_attributes": True}


class EventUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    location: Optional[str] = Field(None, min_length=2, max_length=300)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
