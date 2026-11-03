"""Pydantic schemas for registrations (confirm / waitlist / cancel / roster)."""

from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel

from app.schemas.shift import ShiftOut


class RegistrationOut(BaseModel):
    id: str
    shift_id: str
    volunteer_id: str
    status: str
    waitlist_position: Optional[int] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None


class ShiftBrief(BaseModel):
    shift_id: str
    event_id: str
    event_name: str
    event_location: str
    title: str
    shift_date: date
    start_time: time
    end_time: time
    shift_status: str


class RegistrationDetailOut(RegistrationOut):
    shift: ShiftBrief


class CancelResponse(BaseModel):
    message: str
    registration: RegistrationOut
    waitlist_promoted: bool = False


class RosterEntryOut(BaseModel):
    registration_id: str
    volunteer_id: str
    full_name: str
    email: str
    status: str
    waitlist_position: Optional[int] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None


class WaitlistProcessResponse(BaseModel):
    promoted_count: int
    shift: ShiftOut
