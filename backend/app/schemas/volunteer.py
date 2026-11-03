"""
Pydantic schemas for VolunteerProfile.

Three main schema classes:
  • VolunteerProfileCreate  – used on POST (new profile creation)
  • VolunteerProfileUpdate  – used on PATCH (partial updates, all fields optional)
  • VolunteerProfileOut     – what the API returns to callers
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Shared validators ─────────────────────────────────────────────────────────

VALID_OCCUPATION_TYPES = {
    "student",
    "working_professional",
    "self_employed",
    "retired",
    "homemaker",
    "institution",
    "other",
}

VALID_GENDERS = {"male", "female", "non_binary", "prefer_not_to_say"}

VALID_AVAILABILITY_OPTIONS = {
    "Weekday Mornings",
    "Weekday Afternoons",
    "Weekday Evenings",
    "Weekend Mornings",
    "Weekend Afternoons",
    "Weekend Evenings",
    "Any Time",
}


# ── CREATE schema ─────────────────────────────────────────────────────────────

class VolunteerProfileCreate(BaseModel):
    """
    All fields a volunteer fills in during onboarding.
    Required fields: skills + interests (core matching data).
    All others are optional but encouraged.
    """

    # 1. Personal
    phone: Optional[str] = Field(None, max_length=20, examples=["+91 98765 43210"])
    address: Optional[str] = Field(None, max_length=500, examples=["12 MG Road, Bengaluru"])
    city: Optional[str] = Field(None, max_length=100, examples=["Bengaluru"])
    state: Optional[str] = Field(None, max_length=100, examples=["Karnataka"])
    pincode: Optional[str] = Field(None, max_length=10, examples=["560001"])
    date_of_birth: Optional[date] = Field(None, examples=["2000-05-15"])
    age: Optional[int] = Field(None, ge=16, le=100, examples=[24])
    gender: Optional[str] = Field(None, examples=["male"])

    # 2. Occupation
    occupation_type: Optional[str] = Field(None, examples=["student"])
    organization_name: Optional[str] = Field(
        None, max_length=200, examples=["IIT Bengaluru"]
    )
    affiliation: Optional[str] = Field(
        None, max_length=200, examples=["NSS Unit 12"]
    )

    # 3. Interests
    interests: list[str] = Field(
        default_factory=list,
        examples=[["Healthcare", "Environment", "Education"]],
    )

    # 4. Frequency
    volunteering_frequency_per_month: Optional[int] = Field(
        None, ge=1, le=31, examples=[4]
    )

    # 5. Hours
    volunteering_hours_per_week: Optional[float] = Field(
        None, ge=0, le=168, examples=[8.0]
    )

    # 6. Travel distance
    max_travel_distance_km: Optional[float] = Field(
        None, ge=0, examples=[25.0],
        description="Max distance in km volunteer is willing to travel"
    )

    # 7. Skills
    skills: list[str] = Field(
        default_factory=list,
        examples=[["First Aid", "Teaching", "Driving"]],
    )

    # Availability
    availability: list[str] = Field(
        default_factory=list,
        examples=[["Weekend Mornings", "Weekday Evenings"]],
    )

    # Experience & bio
    experience_months: int = Field(default=0, ge=0, examples=[6])
    bio: Optional[str] = Field(None, max_length=1000, examples=["Passionate about community health."])
    profile_picture_url: Optional[str] = Field(None, max_length=500)

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        if v and v not in VALID_GENDERS:
            raise ValueError(f"gender must be one of {sorted(VALID_GENDERS)}")
        return v

    @field_validator("occupation_type")
    @classmethod
    def validate_occupation(cls, v):
        if v and v not in VALID_OCCUPATION_TYPES:
            raise ValueError(
                f"occupation_type must be one of {sorted(VALID_OCCUPATION_TYPES)}"
            )
        return v

    @field_validator("skills", "interests", mode="before")
    @classmethod
    def strip_and_deduplicate(cls, v):
        if isinstance(v, list):
            seen = set()
            result = []
            for item in v:
                clean = str(item).strip()
                if clean and clean not in seen:
                    seen.add(clean)
                    result.append(clean)
            return result
        return v


# ── UPDATE schema ─────────────────────────────────────────────────────────────

class VolunteerProfileUpdate(BaseModel):
    """
    PATCH schema – every field is optional.
    Only provided fields are updated (partial update pattern).
    """
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    pincode: Optional[str] = Field(None, max_length=10)
    date_of_birth: Optional[date] = None
    age: Optional[int] = Field(None, ge=16, le=100)
    gender: Optional[str] = None

    occupation_type: Optional[str] = None
    organization_name: Optional[str] = Field(None, max_length=200)
    affiliation: Optional[str] = Field(None, max_length=200)

    interests: Optional[list[str]] = None

    volunteering_frequency_per_month: Optional[int] = Field(None, ge=1, le=31)
    volunteering_hours_per_week: Optional[float] = Field(None, ge=0, le=168)
    max_travel_distance_km: Optional[float] = Field(None, ge=0)

    skills: Optional[list[str]] = None
    availability: Optional[list[str]] = None

    experience_months: Optional[int] = Field(None, ge=0)
    bio: Optional[str] = Field(None, max_length=1000)
    profile_picture_url: Optional[str] = Field(None, max_length=500)

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        if v and v not in VALID_GENDERS:
            raise ValueError(f"gender must be one of {sorted(VALID_GENDERS)}")
        return v

    @field_validator("occupation_type")
    @classmethod
    def validate_occupation(cls, v):
        if v and v not in VALID_OCCUPATION_TYPES:
            raise ValueError(
                f"occupation_type must be one of {sorted(VALID_OCCUPATION_TYPES)}"
            )
        return v

    @field_validator("skills", "interests", mode="before")
    @classmethod
    def strip_and_deduplicate(cls, v):
        if isinstance(v, list):
            seen = set()
            result = []
            for item in v:
                clean = str(item).strip()
                if clean and clean not in seen:
                    seen.add(clean)
                    result.append(clean)
            return result
        return v


# ── OUTPUT schema ─────────────────────────────────────────────────────────────

class VolunteerProfileOut(BaseModel):
    """The full profile returned to API callers."""
    id: str
    user_id: str

    # Personal
    phone: Optional[str]
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    pincode: Optional[str]
    date_of_birth: Optional[date]
    age: Optional[int]
    gender: Optional[str]

    # Occupation
    occupation_type: Optional[str]
    organization_name: Optional[str]
    affiliation: Optional[str]

    # Volunteering preferences
    interests: list[str]
    volunteering_frequency_per_month: Optional[int]
    volunteering_hours_per_week: Optional[float]
    max_travel_distance_km: Optional[float]
    skills: list[str]
    availability: list[str]

    # Experience
    experience_months: int
    bio: Optional[str]
    profile_picture_url: Optional[str]

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Volunteer summary (used in admin list views) ──────────────────────────────

class VolunteerSummary(BaseModel):
    """Lightweight volunteer card for list endpoints."""
    user_id: str
    full_name: str
    email: str
    city: Optional[str]
    skills: list[str]
    interests: list[str]
    experience_months: int
    max_travel_distance_km: Optional[float]
    availability: list[str]

    model_config = {"from_attributes": True}
