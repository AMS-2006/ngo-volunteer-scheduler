"""
models/registration.py
───────────────────────
Registration model – links a Volunteer to a Shift.

This is the central table consumed by:
  • Module 3 (Scheduling Engine)  – conflict detection, capacity management,
                                    waitlist promotion
  • Module 5 (Coverage Dashboard) – staffing gap calculation
  • Module 6 (Reminders)          – notification triggers
  • Module 7 (Attendance)         – participation history

Status flow:
  CONFIRMED  → volunteer successfully registered for the shift
  WAITLISTED → shift was full; volunteer placed on waitlist
  CANCELLED  → volunteer or admin cancelled the registration
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Registration(Base):
    __tablename__ = "registrations"

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── Foreign Keys ──────────────────────────────────────────────────────────
    shift_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    volunteer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Unique constraint: one registration per volunteer per shift ───────────
    __table_args__ = (
        # Enforced at DB level to prevent duplicate registrations
        __import__("sqlalchemy").UniqueConstraint(
            "shift_id", "volunteer_id", name="uq_registration_shift_volunteer"
        ),
    )

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        Enum(
            "confirmed",
            "waitlisted",
            "cancelled",
            name="registration_status_enum",
        ),
        nullable=False,
        default="confirmed",
        index=True,
    )

    # Waitlist position (only relevant when status = 'waitlisted')
    waitlist_position: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Position in waitlist queue; NULL for confirmed registrations"
    )

    # ── Cancellation reason (optional, for record keeping) ───────────────────
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    registered_at: Mapped[datetime] = mapped_column(
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
    shift: Mapped["Shift"] = relationship("Shift", back_populates="registrations")  # noqa: F821
    volunteer: Mapped["User"] = relationship("User", foreign_keys=[volunteer_id])  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<Registration shift={self.shift_id[:8]} "
            f"volunteer={self.volunteer_id[:8]} status={self.status}>"
        )
