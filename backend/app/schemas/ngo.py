"""
schemas/ngo.py
──────────────
Pydantic schemas for NGO profile creation, update, and output.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

VALID_AFFILIATIONS = {
    "private", "government", "autonomous", "international", "trust", "society", "other"
}
VALID_FREQUENCIES = {
    "daily", "weekly", "fortnightly", "monthly", "quarterly", "occasionally"
}


class NGOCreate(BaseModel):
    """Create NGO profile (called immediately after admin registration)."""
    # 1. Name & address
    name: str = Field(..., min_length=2, max_length=200, examples=["Green Earth Foundation"])
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100, examples=["Bengaluru"])
    state: Optional[str] = Field(None, max_length=100, examples=["Karnataka"])
    pincode: Optional[str] = Field(None, max_length=10)
    website: Optional[str] = Field(None, max_length=300, examples=["https://greenearth.org"])
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=20)

    # 2. Affiliation
    affiliation: Optional[str] = Field(None, examples=["trust"])

    # 3. Proof of existence
    registration_number: Optional[str] = Field(None, max_length=100, examples=["MH/123/2010"])
    proof_document_url: Optional[str] = Field(None, max_length=500)
    year_established: Optional[int] = Field(None, ge=1800, le=2100, examples=[2015])

    # 4. Active members
    active_member_count: Optional[int] = Field(None, ge=0, examples=[25])

    # 5. Cause
    cause: Optional[str] = Field(None, max_length=200, examples=["Environment"])
    description: Optional[str] = Field(None, max_length=2000)

    # 6. Event frequency
    event_frequency: Optional[str] = Field(None, examples=["monthly"])

    @field_validator("affiliation")
    @classmethod
    def validate_affiliation(cls, v):
        if v and v not in VALID_AFFILIATIONS:
            raise ValueError(f"affiliation must be one of {sorted(VALID_AFFILIATIONS)}")
        return v

    @field_validator("event_frequency")
    @classmethod
    def validate_frequency(cls, v):
        if v and v not in VALID_FREQUENCIES:
            raise ValueError(f"event_frequency must be one of {sorted(VALID_FREQUENCIES)}")
        return v


class NGOUpdate(BaseModel):
    """PATCH – all fields optional."""
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    website: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    affiliation: Optional[str] = None
    registration_number: Optional[str] = None
    proof_document_url: Optional[str] = None
    year_established: Optional[int] = Field(None, ge=1800, le=2100)
    active_member_count: Optional[int] = Field(None, ge=0)
    cause: Optional[str] = None
    description: Optional[str] = None
    event_frequency: Optional[str] = None

    @field_validator("affiliation")
    @classmethod
    def validate_affiliation(cls, v):
        if v and v not in VALID_AFFILIATIONS:
            raise ValueError(f"affiliation must be one of {sorted(VALID_AFFILIATIONS)}")
        return v

    @field_validator("event_frequency")
    @classmethod
    def validate_frequency(cls, v):
        if v and v not in VALID_FREQUENCIES:
            raise ValueError(f"event_frequency must be one of {sorted(VALID_FREQUENCIES)}")
        return v


class NGOOut(BaseModel):
    """Full NGO record returned to callers."""
    id: str
    admin_user_id: str
    name: str
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    pincode: Optional[str]
    website: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    affiliation: Optional[str]
    registration_number: Optional[str]
    proof_document_url: Optional[str]
    year_established: Optional[int]
    active_member_count: Optional[int]
    cause: Optional[str]
    description: Optional[str]
    event_frequency: Optional[str]
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
