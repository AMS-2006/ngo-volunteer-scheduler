"""
routers/volunteers.py  (moved from app/api/routes/volunteers.py)
────────────────────────────────────────────────────────────────
Volunteer profile routes – Module 2.

Endpoints:
  POST   /api/v1/volunteers/profile           – Create my profile (volunteer only)
  GET    /api/v1/volunteers/profile           – Get my profile
  PATCH  /api/v1/volunteers/profile           – Update my profile (partial)
  DELETE /api/v1/volunteers/profile           – Delete my profile
  GET    /api/v1/volunteers/                  – List all volunteers (admin only)
  GET    /api/v1/volunteers/{user_id}         – Get any volunteer profile (admin only)
  GET    /api/v1/volunteers/{user_id}/summary – Lightweight summary card (admin only)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
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


# ── Helper ─────────────────────────────────────────────────────────────────────
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


# ── Volunteer: own profile ────────────────────────────────────────────────────

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
    if current_user.role != "volunteer":
        raise HTTPException(status_code=403, detail="Only volunteers can create a volunteer profile.")

    existing = db.query(VolunteerProfile).filter(VolunteerProfile.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Profile already exists. Use PATCH /profile to update.")

    profile = VolunteerProfile(user_id=current_user.id, **payload.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/profile", response_model=VolunteerProfileOut, summary="Get my volunteer profile")
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_profile_or_404(current_user.id, db)


@router.patch("/profile", response_model=VolunteerProfileOut, summary="Update my profile (partial)")
def update_my_profile(
    payload: VolunteerProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile_or_404(current_user.id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/profile", status_code=status.HTTP_204_NO_CONTENT, summary="Delete my volunteer profile")
def delete_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile_or_404(current_user.id, db)
    db.delete(profile)
    db.commit()


# ── Admin: volunteer management ───────────────────────────────────────────────

@router.get(
    "/",
    response_model=list[VolunteerSummary],
    summary="List all volunteers with filters (admin only)",
)
def list_volunteers(
    city: str | None = Query(None),
    skill: str | None = Query(None),
    interest: str | None = Query(None),
    min_hours: float | None = Query(None),
    max_distance: float | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = (
        db.query(VolunteerProfile, User)
        .join(User, VolunteerProfile.user_id == User.id)
        .filter(User.is_active == True)  # noqa: E712
    )
    if city:
        query = query.filter(VolunteerProfile.city.ilike(f"%{city}%"))
    if skill:
        query = query.filter(VolunteerProfile.skills.any(skill.strip()))
    if interest:
        query = query.filter(VolunteerProfile.interests.any(interest.strip()))
    if min_hours is not None:
        query = query.filter(VolunteerProfile.volunteering_hours_per_week >= min_hours)
    if max_distance is not None:
        query = query.filter(VolunteerProfile.max_travel_distance_km <= max_distance)

    results = query.offset(skip).limit(limit).all()
    return [
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
        for profile, user in results
    ]


@router.get("/{user_id}", response_model=VolunteerProfileOut, summary="Get any volunteer's full profile (admin only)")
def get_volunteer_by_id(
    user_id: str,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _get_profile_or_404(user_id, db)


@router.get("/{user_id}/summary", response_model=VolunteerSummary, summary="Volunteer summary card (admin only)")
def get_volunteer_summary(
    user_id: str,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
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
