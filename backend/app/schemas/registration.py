"""
schemas/registration.py
────────────────────────
Pydantic schemas for Module 3: Smart Shift Scheduling Engine.
Covers:
  • Shift registration requests & responses
  • Availability configuration schemas
  • Waitlist status and remaining slot representations
"""

from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ── Availability Schemas ──────────────────────────────────────────────────────

class AvailabilityCreate(BaseModel):
    """
    Define a weekly recurring or date-specific availability window for a volunteer.
    day_of_week: 0 = Monday, ..., 6 = Sunday.
    """
    day_of_week: Optional[int] = Field(None, ge=0, le=6, examples=[5], description="0=Mon, 6=Sun")
    start_time: time = Field(..., examples=["08:00:00"])
    end_time: time = Field(..., examples=["17:00:00"])
    specific_date: Optional[date] = Field(None, examples=["2026-11-15"])
    is_recurring: bool = Field(True, description="True for weekly recurring schedule")

    @model_validator(mode="after")
    def validate_window(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly after start_time")
        if self.day_of_week is None and self.specific_date is None:
            raise ValueError("Either day_of_week or specific_date must be provided.")
        return self


class AvailabilityOut(BaseModel):
    id: str
    volunteer_id: str
    day_of_week: Optional[int]
    start_time: time
    end_time: time
    specific_date: Optional[date]
    is_recurring: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Registration Schemas ──────────────────────────────────────────────────────

class RegistrationCreate(BaseModel):
    """Request payload to register for a shift."""
    shift_id: str = Field(..., min_length=1, description="UUID of the shift to join")


class RegistrationCancel(BaseModel):
    """Optional payload when cancelling a registration."""
    cancellation_reason: Optional[str] = Field(None, max_length=500)


class ShiftBrief(BaseModel):
    """Brief shift details embedded in registration outputs."""
    id: str
    event_id: str
    name: str
    start_time: datetime
    end_time: datetime
    required_volunteers: int
    required_skills: Optional[str] = None
    event_title: Optional[str] = None
    location_name: Optional[str] = None
    city: Optional[str] = None

    model_config = {"from_attributes": True}


class RegistrationOut(BaseModel):
    """Response returned upon registration or status query."""
    id: str
    shift_id: str
    volunteer_id: str
    status: str  # 'confirmed' | 'waitlisted' | 'cancelled'
    waitlist_position: Optional[int] = None
    cancellation_reason: Optional[str] = None
    registered_at: datetime
    updated_at: datetime
    shift: Optional[ShiftBrief] = None
    message: Optional[str] = None

    model_config = {"from_attributes": True}


class ShiftWithAvailability(BaseModel):
    """Available shift card with remaining slots and volunteer compatibility."""
    id: str
    event_id: str
    event_title: str
    location_name: Optional[str]
    city: Optional[str]
    name: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    required_volunteers: int
    confirmed_count: int
    waitlist_count: int
    slots_remaining: int
    is_full: bool
    user_status: Optional[str] = None  # None | 'confirmed' | 'waitlisted'
    has_conflict: bool = False
    conflict_reason: Optional[str] = None
    is_available: bool = True
