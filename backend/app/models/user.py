"""
User model – authentication credentials and role for every account.
A single User row is shared between Admin and Volunteer accounts.
role = 'admin'     → NGO coordinator (has one NGO profile)
role = 'volunteer' → individual volunteer (has one VolunteerProfile)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class User(Base):
    __tablename__ = "users"

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── Auth Fields ───────────────────────────────────────────────────────────
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # ── Identity ──────────────────────────────────────────────────────────────
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)

    # ── Role ─────────────────────────────────────────────────────────────────
    role: Mapped[str] = mapped_column(
        Enum("admin", "volunteer", name="user_role_enum"),
        nullable=False,
        default="volunteer",
    )

    # ── Status ────────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

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
    # Admin → NGO (one-to-one)
    ngo: Mapped["NGO"] = relationship(  # noqa: F821
        "NGO",
        back_populates="admin",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="NGO.admin_user_id",
    )

    # Volunteer → Profile (one-to-one)
    volunteer_profile: Mapped["VolunteerProfile"] = relationship(  # noqa: F821
        "VolunteerProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
