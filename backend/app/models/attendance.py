"""
models/attendance.py
────────────────────
Module 7: Attendance & Volunteer History

Attendance model linking a confirmed Volunteer Registration to their actual participation.
Tracks:
  • Status: PRESENT, ABSENT, LATE
  • Check-in & Check-out timestamps
  • Recorded-by coordinator reference
  • Notes & hours
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class AttendanceStatus:
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    ALL = (PRESENT, ABSENT, LATE)


class Attendance(Base):
    __tablename__ = "attendance_records"

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── Foreign Keys ──────────────────────────────────────────────────────────
    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shift_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    registration_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("registrations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    volunteer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        Enum("present", "absent", "late", name="attendance_status_enum"),
        nullable=False,
        default=AttendanceStatus.PRESENT,
        index=True,
    )

    # ── Tracking Timestamps ───────────────────────────────────────────────────
    check_in_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Recorded check-in time",
    )
    check_out_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Recorded check-out time",
    )

    # Cached or calculated hours completed (for fast historical aggregations)
    hours_awarded: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Volunteering hours credited for this shift",
    )

    # ── Audit Trail ───────────────────────────────────────────────────────────
    recorded_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User ID of coordinator who recorded/updated this entry",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional remarks or performance notes",
    )

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

    # ── Constraints ───────────────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("shift_id", "volunteer_id", name="uq_attendance_shift_volunteer"),
        CheckConstraint("hours_awarded >= 0.0", name="ck_attendance_hours_non_negative"),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    event: Mapped["Event"] = relationship("Event", foreign_keys=[event_id])  # noqa: F821
    shift: Mapped["Shift"] = relationship("Shift", foreign_keys=[shift_id])  # noqa: F821
    registration: Mapped["Registration"] = relationship("Registration", foreign_keys=[registration_id])  # noqa: F821
    volunteer: Mapped["User"] = relationship("User", foreign_keys=[volunteer_id])  # noqa: F821
    recorder: Mapped["User"] = relationship("User", foreign_keys=[recorded_by])  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<Attendance id={self.id[:8]} volunteer={self.volunteer_id[:8]} "
            f"shift={self.shift_id[:8]} status={self.status} hours={self.hours_awarded}>"
        )
