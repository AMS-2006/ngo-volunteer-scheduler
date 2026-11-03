"""
Registration model – links a volunteer (User) to a shift.

State model:
  CONFIRMED   – holds one of the shift's capacity slots
  WAITLISTED  – queued (FIFO by `queue_seq`) for a slot on a full shift
  CANCELLED   – withdrawn; kept for history, ignored by every rule

Integrity guarantees enforced by the database (not just the app):
  • A volunteer can have at most ONE active (CONFIRMED/WAITLISTED) row per shift
    (partial unique index). Cancelled rows never block re-registration.
  • `queue_seq` is an identity column → strictly increasing → FIFO ordering that
    cannot tie or be reordered by clock skew.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RegistrationStatus:
    CONFIRMED = "CONFIRMED"
    WAITLISTED = "WAITLISTED"
    CANCELLED = "CANCELLED"

    ACTIVE = (CONFIRMED, WAITLISTED)


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        # One active registration per (shift, volunteer); cancelled rows are exempt.
        Index(
            "uq_registrations_active_volunteer_shift",
            "shift_id",
            "volunteer_id",
            unique=True,
            postgresql_where=text("status IN ('CONFIRMED', 'WAITLISTED')"),
        ),
        # Capacity counts + FIFO waitlist scans.
        Index("ix_registrations_shift_status_queue", "shift_id", "status", "queue_seq"),
        # "My shifts" + conflict detection.
        Index("ix_registrations_volunteer_status", "volunteer_id", "status"),
    )
    # Fetch the server-generated queue_seq straight after INSERT (RETURNING).
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    shift_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False
    )
    volunteer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[str] = mapped_column(
        Enum("CONFIRMED", "WAITLISTED", "CANCELLED", name="registration_status_enum"),
        nullable=False,
    )

    # Monotonic ordering key for the FIFO waitlist.
    queue_seq: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    shift: Mapped["Shift"] = relationship("Shift", back_populates="registrations")  # noqa: F821
    volunteer: Mapped["User"] = relationship("User")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<Registration id={self.id} shift={self.shift_id} "
            f"volunteer={self.volunteer_id} status={self.status}>"
        )
