"""Schemas for Module 4 – shortlists and invitations."""

from datetime import date, datetime, time

from pydantic import BaseModel, Field

from app.schemas.registration import RegistrationOut


class ShortlistIn(BaseModel):
    volunteer_ids: list[str] = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=1000)


class InviteIn(BaseModel):
    volunteer_ids: list[str] | None = Field(
        default=None,
        max_length=200,
        description="Omit to invite everyone currently shortlisted for the shift.",
    )
    message: str | None = Field(default=None, max_length=1000)
    expires_in_hours: int = Field(default=72, ge=1, le=720)


class RejectedOut(BaseModel):
    volunteer_id: str
    code: str
    message: str


class ShortlistEntryOut(BaseModel):
    volunteer_id: str
    volunteer_name: str | None = None
    match_score: float | None = None
    note: str | None = None
    created_at: datetime


class ShortlistOut(BaseModel):
    added: list[ShortlistEntryOut]
    rejected: list[RejectedOut]


class InvitationShiftOut(BaseModel):
    shift_id: str
    event_id: str
    event_name: str
    event_location: str
    title: str
    shift_date: date
    start_time: time
    end_time: time


class InvitationOut(BaseModel):
    id: str
    shift_id: str
    volunteer_id: str
    volunteer_name: str | None = None
    status: str
    match_score: float | None = None
    message: str | None = None
    expires_at: datetime
    responded_at: datetime | None = None
    registration_id: str | None = None
    created_at: datetime
    shift: InvitationShiftOut | None = None


class InviteOut(BaseModel):
    invitations: list[InvitationOut]
    rejected: list[RejectedOut]


class InvitationActionOut(BaseModel):
    invitation: InvitationOut
    registration: RegistrationOut | None = None
