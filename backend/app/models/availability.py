"""
VolunteerAvailability model – structured weekly availability windows.

Each row says: "on <day_of_week> I am free from <start_time> to <end_time>".
day_of_week follows Python's date.weekday(): 0 = Monday … 6 = Sunday.

Complements coarse labels with precise windows for conflict and assignment checks.
"""

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class VolunteerAvailability(Base):
    __tablename__ = "volunteer_availability"
    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_availability_day"),
        CheckConstraint("end_time > start_time", name="ck_availability_time_order"),
        Index("ix_availability_volunteer_day", "volunteer_id", "day_of_week"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    volunteer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    specific_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_recurring: Mapped[bool] = mapped_column(default=True, nullable=True)

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

    volunteer: Mapped["User"] = relationship("User", foreign_keys=[volunteer_id])  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<VolunteerAvailability volunteer={self.volunteer_id} "
            f"day={self.day_of_week} {self.start_time}-{self.end_time}>"
        )
