"""
VolunteerAvailability model – structured weekly availability windows.

Each row says: "on <day_of_week> I am free from <start_time> to <end_time>".
day_of_week follows Python's date.weekday(): 0 = Monday … 6 = Sunday.

This complements (does not replace) the coarse free-text labels stored in
VolunteerProfile.availability ("Weekend Mornings", …). The scheduling engine
only trusts these precise windows when deciding whether a volunteer may be
assigned to a shift.
"""

import uuid
from datetime import datetime, time, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


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

    def __repr__(self) -> str:
        return (
            f"<VolunteerAvailability volunteer={self.volunteer_id} "
            f"day={self.day_of_week} {self.start_time}-{self.end_time}>"
        )
