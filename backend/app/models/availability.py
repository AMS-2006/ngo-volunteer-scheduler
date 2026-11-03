"""
models/availability.py
───────────────────────
Volunteer Availability model for Module 3: Smart Shift Scheduling Engine.

Allows volunteers to specify weekly recurring availability or specific dates:
  • day_of_week: 0 = Monday ... 6 = Sunday
  • start_time & end_time: Daily available window (e.g., 08:00 to 17:00)
  • specific_date: Optional single-day override/date
"""

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Time as SQLTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class VolunteerAvailability(Base):
    __tablename__ = "volunteer_availabilities"

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── Foreign Key ───────────────────────────────────────────────────────────
    volunteer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Availability Schedule ─────────────────────────────────────────────────
    # 0 = Monday, 1 = Tuesday, 2 = Wednesday, 3 = Thursday, 4 = Friday, 5 = Saturday, 6 = Sunday
    day_of_week: Mapped[int | None] = mapped_column(
        Integer,
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="ck_day_of_week"),
        nullable=True,
        index=True,
        comment="0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun",
    )

    start_time: Mapped[time] = mapped_column(
        SQLTime, nullable=False, comment="Available start time (e.g. 08:00:00)"
    )
    end_time: Mapped[time] = mapped_column(
        SQLTime, nullable=False, comment="Available end time (e.g. 17:00:00)"
    )

    specific_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, index=True,
        comment="Optional specific date. If null, applies to recurring day_of_week"
    )

    is_recurring: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        comment="True if repeats every week on day_of_week"
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
    volunteer: Mapped["User"] = relationship("User", foreign_keys=[volunteer_id])  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<VolunteerAvailability id={self.id} volunteer={self.volunteer_id[:8]} "
            f"dow={self.day_of_week} {self.start_time}-{self.end_time}>"
        )
