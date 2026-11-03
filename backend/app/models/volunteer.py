"""
VolunteerProfile model – stores the extended personal, professional,
and volunteering-preference data for every volunteer.

One-to-one with User (a User with role='volunteer' has exactly one profile).

Fields cover all 7 specified volunteer detail categories:
  1. Name, address, age
  2. Occupation type (working / student / institution)
  3. Fields of interest
  4. Volunteering frequency per month
  5. Volunteering hours per week
  6. Maximum travel distance (km)
  7. Skills
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class VolunteerProfile(Base):
    __tablename__ = "volunteer_profiles"

    # ── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── FK to User ───────────────────────────────────────────────────────────
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,          # One profile per user
        nullable=False,
        index=True,
    )

    # ────────────────────────────────────────────────────────────────────────
    # 1. PERSONAL INFORMATION
    # ────────────────────────────────────────────────────────────────────────
    # full_name is stored on User; phone and address are profile-specific.

    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Street / area / city / state / pincode stored as a single text field.
    # Teams can normalise to separate columns if needed.
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)

    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    # age is derived from date_of_birth; stored for quick filtering
    age: Mapped[int | None] = mapped_column(
        Integer,
        CheckConstraint("age >= 16 AND age <= 100", name="ck_volunteer_age"),
        nullable=True,
    )

    gender: Mapped[str | None] = mapped_column(
        Enum("male", "female", "non_binary", "prefer_not_to_say", name="gender_enum"),
        nullable=True,
    )

    # ────────────────────────────────────────────────────────────────────────
    # 2. OCCUPATION / BACKGROUND
    # ────────────────────────────────────────────────────────────────────────
    occupation_type: Mapped[str | None] = mapped_column(
        Enum(
            "student",
            "working_professional",
            "self_employed",
            "retired",
            "homemaker",
            "institution",   # e.g. an NCC/NSS unit, college club
            "other",
            name="occupation_type_enum",
        ),
        nullable=True,
    )

    # Institution / company / college name (whichever applies)
    organization_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # NSS / NCC / other affiliation
    affiliation: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ────────────────────────────────────────────────────────────────────────
    # 3. FIELDS OF INTEREST
    #    Stored as a PostgreSQL text array.
    #    Example values: Healthcare, Education, Environment, Animal Welfare,
    #                    Disaster Relief, Women Empowerment, Senior Care, etc.
    # ────────────────────────────────────────────────────────────────────────
    interests: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
        default=list,
        server_default="{}",
    )

    # ────────────────────────────────────────────────────────────────────────
    # 4. VOLUNTEERING FREQUENCY
    #    How many times per month the volunteer expects to participate.
    # ────────────────────────────────────────────────────────────────────────
    volunteering_frequency_per_month: Mapped[int | None] = mapped_column(
        Integer,
        CheckConstraint(
            "volunteering_frequency_per_month >= 1 AND volunteering_frequency_per_month <= 31",
            name="ck_frequency",
        ),
        nullable=True,
        comment="Estimated number of volunteering sessions per month (1–31)",
    )

    # ────────────────────────────────────────────────────────────────────────
    # 5. VOLUNTEERING HOURS PER WEEK
    # ────────────────────────────────────────────────────────────────────────
    volunteering_hours_per_week: Mapped[float | None] = mapped_column(
        Float,
        CheckConstraint(
            "volunteering_hours_per_week >= 0 AND volunteering_hours_per_week <= 168",
            name="ck_hours_per_week",
        ),
        nullable=True,
        comment="Hours per week the volunteer can commit (0–168)",
    )

    # ────────────────────────────────────────────────────────────────────────
    # 6. TRAVEL DISTANCE PREFERENCE
    #    Maximum distance in kilometres the volunteer is willing to travel.
    # ────────────────────────────────────────────────────────────────────────
    max_travel_distance_km: Mapped[float | None] = mapped_column(
        Float,
        CheckConstraint(
            "max_travel_distance_km >= 0",
            name="ck_travel_distance",
        ),
        nullable=True,
        comment="Maximum distance (km) volunteer is willing to travel from home",
    )

    # ────────────────────────────────────────────────────────────────────────
    # 7. SKILLS
    #    Stored as a PostgreSQL text array.
    #    Example values: First Aid, Teaching, Driving, Photography,
    #                    Web Development, Data Entry, Cooking, etc.
    # ────────────────────────────────────────────────────────────────────────
    skills: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
        default=list,
        server_default="{}",
    )

    # ────────────────────────────────────────────────────────────────────────
    # AVAILABILITY SCHEDULE
    #    Stored as a text array of free-form day/time labels.
    #    Example values: "Weekday Mornings", "Weekend Afternoons", etc.
    #    The scheduling engine will use this for conflict-free recommendations.
    # ────────────────────────────────────────────────────────────────────────
    availability: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
        default=list,
        server_default="{}",
        comment="e.g. ['Weekday Mornings', 'Weekend Afternoons']",
    )

    # ────────────────────────────────────────────────────────────────────────
    # EXPERIENCE & BIO
    # ────────────────────────────────────────────────────────────────────────
    experience_months: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint("experience_months >= 0", name="ck_experience"),
        nullable=False,
        default=0,
        comment="Total months of volunteering experience",
    )

    bio: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Short self-introduction or personal statement",
    )

    # Profile picture URL (hosted externally / object storage)
    profile_picture_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ────────────────────────────────────────────────────────────────────────
    # TIMESTAMPS
    # ────────────────────────────────────────────────────────────────────────
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
    user: Mapped["User"] = relationship("User", back_populates="volunteer_profile")  # noqa: F821

    def __repr__(self) -> str:
        return f"<VolunteerProfile id={self.id} user_id={self.user_id}>"
