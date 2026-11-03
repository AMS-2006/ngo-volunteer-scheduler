"""
models/event.py
───────────────
Event model – a volunteering activity created by an NGO admin.

Each Event contains one or more Shifts (time slots).
Features covered (Module 1):
  • Title, description, location
  • Event dates (start + end)
  • Total volunteers required across all shifts
  • Status lifecycle: DRAFT → PUBLISHED → COMPLETED / CANCELLED
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class EventStatus:
    DRAFT = "draft"
    PUBLISHED = "published"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Event(Base):
    __tablename__ = "events"

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── Ownership ────────────────────────────────────────────────────────────
    ngo_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ngos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="The NGO that owns this event",
    )

    # Also track which admin user created it (for audit trail)
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin user who created the event",
    )

    # ── Core Event Details ────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True,
        comment="Short descriptive title, e.g. 'Bengaluru Lake Cleanup'"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Full description of the event, goals, and what volunteers will do"
    )

    # ── Location ──────────────────────────────────────────────────────────────
    location_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        comment="Venue name, e.g. 'Jakkur Lake'"
    )
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Google Maps / coordinates (optional, useful for distance-based matching)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)

    # ── Dates ─────────────────────────────────────────────────────────────────
    event_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
        comment="Primary date/start of the event"
    )
    event_end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="End date for multi-day events"
    )

    # ── Volunteer Requirements ─────────────────────────────────────────────────
    total_volunteers_required: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint("total_volunteers_required >= 1", name="ck_event_volunteers"),
        nullable=False,
        default=1,
        comment="Total volunteers needed across all shifts",
    )

    # Skills/interests required for this event (comma-separated tags)
    required_skills: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="Comma-separated skill tags, e.g. 'First Aid, Driving'"
    )
    cause_category: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True,
        comment="Event cause category, e.g. Environment, Healthcare"
    )

    # ── Status Lifecycle ──────────────────────────────────────────────────────
    # DRAFT      → created but not visible to volunteers yet
    # PUBLISHED  → visible on volunteer portal, registrations open
    # COMPLETED  → event has occurred
    # CANCELLED  → event was called off
    status: Mapped[str] = mapped_column(
        Enum(
            "draft",
            "published",
            "completed",
            "cancelled",
            name="event_status_enum",
        ),
        nullable=False,
        default="draft",
        index=True,
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
    ngo: Mapped["NGO"] = relationship("NGO", back_populates="events")  # noqa: F821
    creator: Mapped["User"] = relationship(  # noqa: F821
        "User", foreign_keys=[created_by]
    )
    shifts: Mapped[list["Shift"]] = relationship(  # noqa: F821
        "Shift", back_populates="event", cascade="all, delete-orphan",
        order_by="Shift.start_time"
    )

    @property
    def name(self) -> str:
        return self.title

    @name.setter
    def name(self, val: str):
        self.title = val

    @property
    def location(self) -> str:
        return self.location_name or self.city or ""

    @property
    def start_date(self):
        return self.event_date.date()

    @property
    def end_date(self):
        return (self.event_end_date or self.event_date).date()

    def __repr__(self) -> str:
        return f"<Event id={self.id} title='{self.title}' status={self.status}>"
