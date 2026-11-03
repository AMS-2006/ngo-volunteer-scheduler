"""
models/ngo.py
─────────────
NGO (Non-Governmental Organisation) profile model.

Every NGO Admin user owns exactly one NGO record.
Events are created under an NGO.

Fields (from spec):
  1. Name & address of the NGO
  2. Affiliation type  (private, government, autonomous, international, trust)
  3. Proof of existence  (registration certificate URL / document reference)
  4. Number of active members / paid staff
  5. Cause / primary focus area
  6. Typical frequency of events
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


class NGO(Base):
    __tablename__ = "ngos"

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── Owning Admin ──────────────────────────────────────────────────────────
    # One-to-one: each admin account manages exactly one NGO.
    admin_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # ────────────────────────────────────────────────────────────────────────
    # 1. NAME & ADDRESS
    # ────────────────────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True,
        comment="Official registered name of the NGO"
    )
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ────────────────────────────────────────────────────────────────────────
    # 2. AFFILIATION TYPE
    # ────────────────────────────────────────────────────────────────────────
    affiliation: Mapped[str | None] = mapped_column(
        Enum(
            "private",           # Privately funded / self-sustaining
            "government",        # Funded or backed by government
            "autonomous",        # Autonomous body (e.g. university linked)
            "international",     # Branch of an international organisation
            "trust",             # Registered charitable trust
            "society",           # Registered society
            "other",
            name="ngo_affiliation_enum",
        ),
        nullable=True,
        comment="Legal/operational affiliation type",
    )

    # ────────────────────────────────────────────────────────────────────────
    # 3. PROOF OF EXISTENCE
    #    URL to the uploaded registration certificate, 80G/12A certificate,
    #    FCRA registration, etc.  Storage handled externally (S3/Cloudinary).
    # ────────────────────────────────────────────────────────────────────────
    registration_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="Official registration / CIN number"
    )
    proof_document_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="URL to scanned registration certificate or equivalent proof"
    )
    year_established: Mapped[int | None] = mapped_column(
        Integer,
        CheckConstraint("year_established >= 1800 AND year_established <= 2100",
                        name="ck_ngo_year"),
        nullable=True,
    )

    # ────────────────────────────────────────────────────────────────────────
    # 4. ACTIVE MEMBERS / STAFF COUNT
    # ────────────────────────────────────────────────────────────────────────
    active_member_count: Mapped[int | None] = mapped_column(
        Integer,
        CheckConstraint("active_member_count >= 0", name="ck_ngo_members"),
        nullable=True,
        comment="Number of paid staff or core working members",
    )

    # ────────────────────────────────────────────────────────────────────────
    # 5. CAUSE / PRIMARY FOCUS
    # ────────────────────────────────────────────────────────────────────────
    cause: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        comment="Primary cause the NGO works towards (e.g. Environment, Healthcare)"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Full description of the NGO's mission and work"
    )

    # ────────────────────────────────────────────────────────────────────────
    # 6. FREQUENCY OF EVENTS
    # ────────────────────────────────────────────────────────────────────────
    event_frequency: Mapped[str | None] = mapped_column(
        Enum(
            "daily",
            "weekly",
            "fortnightly",
            "monthly",
            "quarterly",
            "occasionally",
            name="ngo_event_frequency_enum",
        ),
        nullable=True,
        comment="How often the NGO typically organises volunteering events",
    )

    # ── Status ────────────────────────────────────────────────────────────────
    is_verified: Mapped[bool] = mapped_column(
        default=False,
        comment="Set to True once proof documents are verified by platform admin"
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
    admin: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="ngo", foreign_keys=[admin_user_id]
    )
    events: Mapped[list["Event"]] = relationship(  # noqa: F821
        "Event", back_populates="ngo", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<NGO id={self.id} name='{self.name}'>"
