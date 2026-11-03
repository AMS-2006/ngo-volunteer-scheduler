"""
models/shift.py
───────────────
Shift model – a time-slot within an Event.

One Event → many Shifts.
One Shift → many Registrations (via the Registration model).

The Scheduling Engine (Module 3) uses start_time / end_time
to detect overlapping assignments for a volunteer.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Shift(Base):
    __tablename__ = "shifts"

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── Parent Event ──────────────────────────────────────────────────────────
    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Shift Identity ────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Human-readable label, e.g. 'Morning', 'Afternoon', 'Setup Crew'"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="What volunteers will specifically do during this shift"
    )

    # ── Timing ────────────────────────────────────────────────────────────────
    # These two fields are the key inputs to the conflict-detection algorithm.
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
        comment="Shift start datetime (UTC)"
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="Shift end datetime (UTC)"
    )

    # ── Capacity ──────────────────────────────────────────────────────────────
    required_volunteers: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint("required_volunteers >= 1", name="ck_shift_volunteers"),
        nullable=False,
        default=1,
        comment="Number of volunteers needed for this specific shift",
    )

    # Skills specifically needed for this shift (may differ from parent event)
    required_skills: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="Comma-separated skill tags specific to this shift"
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    event: Mapped["Event"] = relationship("Event", back_populates="shifts")  # noqa: F821
    registrations: Mapped[list["Registration"]] = relationship(  # noqa: F821
        "Registration", back_populates="shift", cascade="all, delete-orphan"
    )

    # ── Derived helpers (not stored, computed on access) ─────────────────────
    @property
    def confirmed_count(self) -> int:
        """Number of confirmed registrations for this shift."""
        return sum(1 for r in self.registrations if r.status == "confirmed")

    @property
    def waitlist_count(self) -> int:
        return sum(1 for r in self.registrations if r.status == "waitlisted")

    @property
    def slots_remaining(self) -> int:
        return max(0, self.required_volunteers - self.confirmed_count)

    @property
    def is_full(self) -> bool:
        return self.confirmed_count >= self.required_volunteers

    def __repr__(self) -> str:
        return (
            f"<Shift id={self.id} name='{self.name}' "
            f"{self.start_time.strftime('%H:%M')}–{self.end_time.strftime('%H:%M')}>"
        )
