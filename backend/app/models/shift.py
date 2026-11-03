"""
Shift model – a time slot inside an event that volunteers sign up for.

A shift is always a single-day interval [start_time, end_time) on `shift_date`
(no overnight shifts), which keeps overlap detection and availability matching
simple and exact.

`status` is a *derived-but-stored* field kept in sync by the capacity service:
  open      – confirmed volunteers < capacity
  full      – confirmed volunteers >= capacity
  cancelled – shift withdrawn by an admin
The live remaining-slot count is always computed from registrations.
"""

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ShiftStatus:
    OPEN = "open"
    FULL = "full"
    CANCELLED = "cancelled"


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_shift_time_order"),
        CheckConstraint("capacity >= 1", name="ck_shift_capacity"),
        Index("ix_shifts_date_time", "shift_date", "start_time", "end_time"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    shift_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(
        Enum("open", "full", "cancelled", name="shift_status_enum"),
        nullable=False,
        default=ShiftStatus.OPEN,
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

    # NOTE: intentionally lazy-loaded. `SELECT ... FOR UPDATE` on a shift must not
    # carry an outer join (PostgreSQL rejects locking the nullable side).
    event: Mapped["Event"] = relationship("Event", back_populates="shifts")  # noqa: F821
    registrations: Mapped[list["Registration"]] = relationship(  # noqa: F821
        "Registration", back_populates="shift", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Shift id={self.id} {self.shift_date} {self.start_time}-{self.end_time}>"
