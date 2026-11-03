"""
Module 4 tables – Smart Volunteer Matching & Invitations.

  shift_requirements      per-shift skill / interest / location needs (1:1 with shifts)
  event_matching_profiles per-event categories used for interest + experience relevance
  volunteer_shortlists    NGO shortlist of recommended volunteers for a shift
  volunteer_invitations   invitation lifecycle (PENDING/ACCEPTED/DECLINED/EXPIRED/CANCELLED)

An invitation is NOT a registration: accepting one must go through the Module 3
registration service (availability, conflicts, capacity). `registration_id` links
the resulting confirmed registration once that succeeds.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class InvitationStatus:
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

    ALL = (PENDING, ACCEPTED, DECLINED, EXPIRED, CANCELLED)


class ShiftRequirement(Base):
    __tablename__ = "shift_requirements"

    shift_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shifts.id", ondelete="CASCADE"), primary_key=True
    )
    required_skills: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), nullable=False, default=list, server_default="{}"
    )
    optional_skills: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), nullable=False, default=list, server_default="{}"
    )
    interest_tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), nullable=False, default=list, server_default="{}"
    )
    skills_mandatory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    required_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class EventMatchingProfile(Base):
    __tablename__ = "event_matching_profiles"

    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    categories: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), nullable=False, default=list, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class VolunteerShortlist(Base):
    __tablename__ = "volunteer_shortlists"
    __table_args__ = (
        UniqueConstraint("shift_id", "volunteer_id", name="uq_shortlist_shift_volunteer"),
        Index("ix_shortlist_volunteer", "volunteer_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    shift_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    volunteer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    shortlisted_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class VolunteerInvitation(Base):
    __tablename__ = "volunteer_invitations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','ACCEPTED','DECLINED','EXPIRED','CANCELLED')",
            name="ck_invitation_status",
        ),
        # At most one PENDING invitation per (shift, volunteer).
        Index(
            "uq_invitations_pending_shift_volunteer",
            "shift_id",
            "volunteer_id",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
        Index("ix_invitations_volunteer_status", "volunteer_id", "status"),
        Index("ix_invitations_shift_status", "shift_id", "status"),
        Index("ix_invitations_pending_expiry", "expires_at", postgresql_where=text("status = 'PENDING'")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    shift_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False
    )
    volunteer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    invited_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=InvitationStatus.PENDING
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registration_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("registrations.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )
