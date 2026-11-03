"""
routers/matching.py  –  Module 4: Smart Volunteer Matching & Invitations
──────────────────────────────────────────────────────────────────────────
NGO (admin) endpoints
  GET  /api/v1/matching/shifts/{shift_id}/recommendations
  GET  /api/v1/matching/events/{event_id}/recommendations
  GET  /api/v1/matching/shifts/{shift_id}/requirements        PUT same path
  PUT  /api/v1/matching/events/{event_id}/profile
  POST /api/v1/matching/shifts/{shift_id}/shortlist           GET same path
  POST /api/v1/matching/shifts/{shift_id}/invite
  POST /api/v1/matching/invitations/{invitation_id}/cancel
Volunteer endpoints
  GET  /api/v1/matching/recommendations
  GET  /api/v1/matching/recommendations/{shift_id}
  POST /api/v1/matching/invitations/{invitation_id}/accept
  POST /api/v1/matching/invitations/{invitation_id}/decline
Shared (role-aware)
  GET  /api/v1/matching/invitations
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin, require_volunteer
from app.database.connection import get_db
from app.models.matching import EventMatchingProfile
from app.models.user import User
from app.schemas.invitations import (
    InvitationActionOut,
    InvitationOut,
    InviteIn,
    InviteOut,
    ShortlistEntryOut,
    ShortlistIn,
    ShortlistOut,
)
from app.schemas.matching import (
    EventProfileIn,
    EventProfileOut,
    EventRecommendationsOut,
    RequirementsIn,
    RequirementsOut,
    ShiftRecommendationsOut,
    VolunteerRecommendationsOut,
    VolunteerShiftRecOut,
)
from app.services import invitation_service as inv_svc
from app.services import recommendation_service as rec_svc

router = APIRouter(prefix="/matching", tags=["Volunteer Matching (Module 4)"])


# ── NGO: configuration ────────────────────────────────────────────────────────
@router.put("/shifts/{shift_id}/requirements", response_model=RequirementsOut,
            summary="Set a shift's skill / interest / location requirements (admin)")
def put_requirements(shift_id: str, payload: RequirementsIn,
                     admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = rec_svc.set_requirements(db, admin, shift_id, payload.model_dump())
    return RequirementsOut(
        shift_id=row.shift_id, required_skills=row.required_skills, optional_skills=row.optional_skills,
        interest_tags=row.interest_tags, skills_mandatory=row.skills_mandatory, required_city=row.required_city,
    )


@router.get("/shifts/{shift_id}/requirements", response_model=RequirementsOut,
            summary="Get a shift's matching requirements (admin)")
def get_requirements(shift_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = rec_svc.get_requirements(db, admin, shift_id)
    if row is None:
        return RequirementsOut(shift_id=shift_id)
    return RequirementsOut(
        shift_id=row.shift_id, required_skills=row.required_skills, optional_skills=row.optional_skills,
        interest_tags=row.interest_tags, skills_mandatory=row.skills_mandatory, required_city=row.required_city,
    )


@router.put("/events/{event_id}/profile", response_model=EventProfileOut,
            summary="Set an event's categories used for interest matching (admin)")
def put_event_profile(event_id: str, payload: EventProfileIn,
                      admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row: EventMatchingProfile = rec_svc.set_event_categories(db, admin, event_id, payload.categories)
    return EventProfileOut(event_id=row.event_id, categories=row.categories)


# ── NGO: recommendations ──────────────────────────────────────────────────────
@router.get("/shifts/{shift_id}/recommendations", response_model=ShiftRecommendationsOut,
            summary="Ranked eligible volunteers + skill gap for a shift (admin)")
def shift_recommendations(
    shift_id: str,
    limit: int = Query(50, ge=1, le=200),
    min_score: float = Query(0, ge=0, le=100),
    include_excluded: bool = Query(True, description="Also return ineligible volunteers with reasons."),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return rec_svc.shift_recommendations(
        db, admin, shift_id, limit=limit, min_score=min_score, include_excluded=include_excluded
    )


@router.get("/events/{event_id}/recommendations", response_model=EventRecommendationsOut,
            summary="Recommendations for every open shift of an event (admin)")
def event_recommendations(
    event_id: str,
    limit: int = Query(20, ge=1, le=200),
    min_score: float = Query(0, ge=0, le=100),
    include_excluded: bool = Query(False),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return rec_svc.event_recommendations(
        db, admin, event_id, limit=limit, min_score=min_score, include_excluded=include_excluded
    )


# ── NGO: shortlist & invitations ──────────────────────────────────────────────
@router.post("/shifts/{shift_id}/shortlist", response_model=ShortlistOut, status_code=status.HTTP_201_CREATED,
             summary="Shortlist eligible volunteers for a shift (admin)")
def shortlist(shift_id: str, payload: ShortlistIn,
              admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return inv_svc.shortlist(db, admin, shift_id, payload.volunteer_ids, payload.note)


@router.get("/shifts/{shift_id}/shortlist", response_model=list[ShortlistEntryOut],
            summary="List the shortlist of a shift (admin)")
def get_shortlist(shift_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return inv_svc.list_shortlist(db, admin, shift_id)


@router.post("/shifts/{shift_id}/invite", response_model=InviteOut, status_code=status.HTTP_201_CREATED,
             summary="Invite volunteers (explicit ids, or the whole shortlist) to a shift (admin)")
def invite(shift_id: str, payload: InviteIn,
           admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return inv_svc.invite(db, admin, shift_id, payload.volunteer_ids, payload.message, payload.expires_in_hours)


@router.post("/invitations/{invitation_id}/cancel", response_model=InvitationOut,
             summary="Cancel a pending invitation (admin)")
def cancel_invitation(invitation_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return inv_svc.cancel(db, admin, invitation_id)


# ── Shared ────────────────────────────────────────────────────────────────────
@router.get("/invitations", response_model=list[InvitationOut],
            summary="Admins: invitations for their events. Volunteers: their own invitations.")
def list_invitations(
    status_filter: str | None = Query(None, alias="status", description="PENDING|ACCEPTED|DECLINED|EXPIRED|CANCELLED"),
    shift_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return inv_svc.list_invitations(db, user, status=status_filter, shift_id=shift_id, limit=limit)


# ── Volunteer ─────────────────────────────────────────────────────────────────
@router.get("/recommendations", response_model=VolunteerRecommendationsOut,
            summary="Personalised shift recommendations (volunteer)")
def my_recommendations(
    limit: int = Query(20, ge=1, le=100),
    min_score: float = Query(0, ge=0, le=100),
    include_ineligible: bool = Query(False),
    user: User = Depends(require_volunteer),
    db: Session = Depends(get_db),
):
    return rec_svc.volunteer_recommendations(
        db, user, limit=limit, min_score=min_score, include_ineligible=include_ineligible
    )


@router.get("/recommendations/{shift_id}", response_model=VolunteerShiftRecOut,
            summary="How well I match one shift, with reasons (volunteer)")
def my_shift_match(shift_id: str, user: User = Depends(require_volunteer), db: Session = Depends(get_db)):
    return rec_svc.volunteer_shift_match(db, user, shift_id)


@router.post("/invitations/{invitation_id}/accept", response_model=InvitationActionOut,
             summary="Accept an invitation (re-validated by the Module 3 scheduling engine)")
def accept_invitation(invitation_id: str, user: User = Depends(require_volunteer), db: Session = Depends(get_db)):
    return inv_svc.accept(db, user, invitation_id)


@router.post("/invitations/{invitation_id}/decline", response_model=InvitationActionOut,
             summary="Decline an invitation (volunteer)")
def decline_invitation(invitation_id: str, user: User = Depends(require_volunteer), db: Session = Depends(get_db)):
    return inv_svc.decline(db, user, invitation_id)
