"""
Volunteer profile routes.

Endpoints:
  POST   /api/v1/volunteers/profile           – Create my profile (volunteer only)
  GET    /api/v1/volunteers/profile           – Get my profile
  PATCH  /api/v1/volunteers/profile           – Update my profile (partial)
  DELETE /api/v1/volunteers/profile           – Delete my profile
  GET    /api/v1/volunteers/                  – List all volunteers (admin only)
  GET    /api/v1/volunteers/{user_id}         – Get any volunteer profile (admin only)
  GET    /api/v1/volunteers/{user_id}/summary – Lightweight summary card
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.user import User
from app.models.volunteer import VolunteerProfile
from app.schemas.volunteer import (
    VolunteerProfileCreate,
    VolunteerProfileOut,
    VolunteerProfileUpdate,
    VolunteerSummary,
)

router = APIRouter(prefix="/volunteers", tags=["Volunteer Management"])


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_profile_or_404(user_id: str, db: Session) -> VolunteerProfile:
    profile = (
        db.query(VolunteerProfile)
        .filter(VolunteerProfile.user_id == user_id)
        .first()
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volunteer profile not found.",
        )
    return profile


# ── Volunteer: own profile endpoints ─────────────────────────────────────────

@router.post(
    "/profile",
    response_model=VolunteerProfileOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create my volunteer profile",
)
def create_my_profile(
    payload: VolunteerProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    A volunteer creates their profile after registration.
    Only one profile per account is allowed.
    """
    if current_user.role != "volunteer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only volunteers can create a volunteer profile.",
        )

    existing = (
        db.query(VolunteerProfile)
        .filter(VolunteerProfile.user_id == current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a profile. Use PATCH /profile to update it.",
        )

    profile = VolunteerProfile(user_id=current_user.id, **payload.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get(
    "/profile",
    response_model=VolunteerProfileOut,
    summary="Get my volunteer profile",
)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the authenticated volunteer's own profile."""
    return _get_profile_or_404(current_user.id, db)


@router.patch(
    "/profile",
    response_model=VolunteerProfileOut,
    summary="Update my volunteer profile (partial)",
)
def update_my_profile(
    payload: VolunteerProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Partially update the authenticated volunteer's profile.
    Only the fields present in the request body are updated.
    """
    profile = _get_profile_or_404(current_user.id, db)

    # Apply only provided fields (exclude_unset skips fields not sent by client)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile


@router.delete(
    "/profile",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete my volunteer profile",
)
def delete_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete the authenticated volunteer's profile (not the account)."""
    profile = _get_profile_or_404(current_user.id, db)
    db.delete(profile)
    db.commit()


# ── Admin: volunteer management endpoints ─────────────────────────────────────

@router.get(
    "/",
    response_model=list[VolunteerSummary],
    summary="List all volunteers (admin only)",
)
def list_volunteers(
    city: str | None = Query(None, description="Filter by city"),
    skill: str | None = Query(None, description="Filter by skill (case-insensitive)"),
    interest: str | None = Query(None, description="Filter by interest"),
    min_hours: float | None = Query(None, description="Minimum weekly hours"),
    max_distance: float | None = Query(None, description="Maximum travel distance km"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Return a paginated, filterable list of all volunteer profiles.
    Accessible by NGO admins only.
    """
    query = (
        db.query(VolunteerProfile, User)
        .join(User, VolunteerProfile.user_id == User.id)
        .filter(User.is_active == True)  # noqa: E712
    )

    if city:
        query = query.filter(VolunteerProfile.city.ilike(f"%{city}%"))
    if skill:
        # PostgreSQL ARRAY contains check (case-insensitive via ANY)
        query = query.filter(
            VolunteerProfile.skills.any(skill.strip())
        )
    if interest:
        query = query.filter(
            VolunteerProfile.interests.any(interest.strip())
        )
    if min_hours is not None:
        query = query.filter(
            VolunteerProfile.volunteering_hours_per_week >= min_hours
        )
    if max_distance is not None:
        query = query.filter(
            VolunteerProfile.max_travel_distance_km <= max_distance
        )

    results = query.offset(skip).limit(limit).all()

    summaries = []
    for profile, user in results:
        summaries.append(
            VolunteerSummary(
                user_id=user.id,
                full_name=user.full_name,
                email=user.email,
                city=profile.city,
                skills=profile.skills,
                interests=profile.interests,
                experience_months=profile.experience_months,
                max_travel_distance_km=profile.max_travel_distance_km,
                availability=profile.availability,
            )
        )
    return summaries


@router.get(
    "/{user_id}",
    response_model=VolunteerProfileOut,
    summary="Get any volunteer's full profile (admin only)",
)
def get_volunteer_by_id(
    user_id: str,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Retrieve the complete profile for any volunteer by their user ID."""
    return _get_profile_or_404(user_id, db)


@router.get(
    "/{user_id}/summary",
    response_model=VolunteerSummary,
    summary="Get lightweight volunteer summary card (admin only)",
)
def get_volunteer_summary(
    user_id: str,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return a summary card for a volunteer (used in matching results)."""
    profile = _get_profile_or_404(user_id, db)
    user = db.get(User, user_id)
    return VolunteerSummary(
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        city=profile.city,
        skills=profile.skills,
        interests=profile.interests,
        experience_months=profile.experience_months,
        max_travel_distance_km=profile.max_travel_distance_km,
        availability=profile.availability,
    )
