"""
routers/registrations.py
─────────────────────────
Module 3: Smart Shift Scheduling Engine – API Endpoints.

Endpoints:
  • GET    /api/v1/registrations/shifts/available – Browse shifts with live capacity & conflict checks
  • POST   /api/v1/registrations/                 – Register / join waitlist for a shift
  • DELETE /api/v1/registrations/{id}             – Cancel a registration (triggers FIFO auto-promotion)
  • GET    /api/v1/registrations/my               – My registrations (volunteer)
  • GET    /api/v1/registrations/shift/{id}       – Shift registrations list (admin)
  • GET    /api/v1/registrations/availability     – View volunteer availability windows
  • POST   /api/v1/registrations/availability     – Add a new availability window
  • DELETE /api/v1/registrations/availability/{id} – Delete an availability window
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_admin, require_volunteer
from app.database.connection import get_db
from app.models.availability import VolunteerAvailability
from app.models.event import Event
from app.models.registration import Registration
from app.models.shift import Shift
from app.models.user import User
from app.schemas.registration import (
    AvailabilityCreate,
    AvailabilityOut,
    RegistrationCancel,
    RegistrationCreate,
    RegistrationOut,
    ShiftBrief,
    ShiftWithAvailability,
)
from app.services.scheduling import (
    cancel_registration,
    check_volunteer_availability,
    detect_conflict,
    register_volunteer_for_shift,
)

router = APIRouter(prefix="/registrations", tags=["Shift Scheduling & Registrations"])


# ── Helper to build RegistrationOut ──────────────────────────────────────────

def _build_reg_out(reg: Registration, message: Optional[str] = None) -> RegistrationOut:
    shift_brief = None
    if reg.shift:
        shift_brief = ShiftBrief(
            id=reg.shift.id,
            event_id=reg.shift.event_id,
            name=reg.shift.name,
            start_time=reg.shift.start_time,
            end_time=reg.shift.end_time,
            required_volunteers=reg.shift.required_volunteers,
            required_skills=reg.shift.required_skills,
            event_title=reg.shift.event.title if reg.shift.event else None,
            location_name=reg.shift.event.location_name if reg.shift.event else None,
            city=reg.shift.event.city if reg.shift.event else None,
        )

    return RegistrationOut(
        id=reg.id,
        shift_id=reg.shift_id,
        volunteer_id=reg.volunteer_id,
        status=reg.status,
        waitlist_position=reg.waitlist_position,
        cancellation_reason=reg.cancellation_reason,
        registered_at=reg.registered_at,
        updated_at=reg.updated_at,
        shift=shift_brief,
        message=message,
    )


# ── 1. Shift Browsing with Compatibility Info ────────────────────────────────

@router.get(
    "/shifts/available",
    response_model=List[ShiftWithAvailability],
    summary="Browse shifts with live capacity and conflict status",
)
def list_available_shifts(
    event_id: Optional[str] = Query(None, description="Filter shifts by event ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns published shifts enriched with:
      • Current capacity, registered count, waitlist count, remaining slots.
      • Personal status for the caller (none, confirmed, waitlisted).
      • Live conflict detection against caller's other assignments.
      • Availability check against caller's declared availability.
    """
    query = (
        db.query(Shift)
        .join(Event, Shift.event_id == Event.id)
        .options(selectinload(Shift.event), selectinload(Shift.registrations))
        .filter(Event.status == "published")
    )

    if event_id:
        query = query.filter(Shift.event_id == event_id)

    shifts = query.order_by(Shift.start_time.asc()).all()

    # Pre-fetch user's active registrations for mapping
    user_regs = {
        r.shift_id: r
        for r in db.query(Registration)
        .filter(
            Registration.volunteer_id == current_user.id,
            Registration.status.in_(["confirmed", "waitlisted"]),
        )
        .all()
    }

    result = []
    for s in shifts:
        user_reg = user_regs.get(s.id)
        user_status = user_reg.status if user_reg else None

        # Conflict check if not already confirmed
        has_conflict = False
        conflict_reason = None
        if user_status != "confirmed":
            conf_check = detect_conflict(current_user.id, s, db, exclude_shift_id=s.id)
            if conf_check["has_conflict"]:
                has_conflict = True
                conflict_reason = conf_check["message"]

        # Availability check
        avail_check = check_volunteer_availability(current_user.id, s, db)

        result.append(
            ShiftWithAvailability(
                id=s.id,
                event_id=s.event_id,
                event_title=s.event.title if s.event else "Event",
                location_name=s.event.location_name if s.event else None,
                city=s.event.city if s.event else None,
                name=s.name,
                description=s.description,
                start_time=s.start_time,
                end_time=s.end_time,
                required_volunteers=s.required_volunteers,
                confirmed_count=s.confirmed_count,
                waitlist_count=s.waitlist_count,
                slots_remaining=s.slots_remaining,
                is_full=s.is_full,
                user_status=user_status,
                has_conflict=has_conflict,
                conflict_reason=conflict_reason,
                is_available=avail_check["is_available"],
            )
        )

    return result


# ── 2. Register for a Shift ──────────────────────────────────────────────────

@router.post(
    "/",
    response_model=RegistrationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register for a shift (or join waitlist)",
)
def register_for_shift(
    payload: RegistrationCreate,
    current_user: User = Depends(require_volunteer),
    db: Session = Depends(get_db),
):
    """
    Register the authenticated volunteer for a shift.
      • Checks availability windows.
      • Detects scheduling conflicts (rejects overlapping shifts).
      • Concurrency-safe: confirms slot if capacity remains, or queues on FIFO waitlist.
    """
    outcome = register_volunteer_for_shift(
        volunteer_id=current_user.id,
        shift_id=payload.shift_id,
        db=db,
    )
    reg = (
        db.query(Registration)
        .options(selectinload(Registration.shift).selectinload(Shift.event))
        .filter(Registration.id == outcome["registration"].id)
        .first()
    )
    return _build_reg_out(reg, message=outcome["message"])


# ── 3. Cancel a Registration ─────────────────────────────────────────────────

@router.delete(
    "/{registration_id}",
    response_model=RegistrationOut,
    summary="Cancel a registration (triggers FIFO auto-promotion)",
)
def cancel_shift_registration(
    registration_id: str,
    payload: Optional[RegistrationCancel] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancel an existing registration.
      • Volunteer can cancel their own registration; Admins can cancel any registration.
      • Re-opens the slot and automatically promotes the next eligible waitlisted volunteer.
    """
    reason = payload.cancellation_reason if payload else None
    outcome = cancel_registration(
        registration_id=registration_id,
        user=current_user,
        cancellation_reason=reason,
        db=db,
    )
    reg = (
        db.query(Registration)
        .options(selectinload(Registration.shift).selectinload(Shift.event))
        .filter(Registration.id == outcome["registration"].id)
        .first()
    )
    promo_msg = ""
    if outcome["promoted_registration"]:
        promo_msg = " Next eligible waitlisted volunteer was automatically promoted to confirmed."
    return _build_reg_out(reg, message=f"{outcome['message']}{promo_msg}")


# ── 4. My Registrations (Volunteer) ──────────────────────────────────────────

@router.get(
    "/my",
    response_model=List[RegistrationOut],
    summary="List all my registrations (confirmed, waitlisted, cancelled)",
)
def get_my_registrations(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    current_user: User = Depends(require_volunteer),
    db: Session = Depends(get_db),
):
    """Returns registrations for the authenticated volunteer."""
    query = (
        db.query(Registration)
        .options(selectinload(Registration.shift).selectinload(Shift.event))
        .filter(Registration.volunteer_id == current_user.id)
    )

    if status_filter:
        query = query.filter(Registration.status == status_filter)

    registrations = query.order_by(Registration.registered_at.desc()).all()
    return [_build_reg_out(r) for r in registrations]


# ── 5. Shift Registrations (Admin View) ───────────────────────────────────────

@router.get(
    "/shift/{shift_id}",
    response_model=List[RegistrationOut],
    summary="List all registrations for a shift (admin only)",
)
def get_shift_registrations(
    shift_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Returns all registrations (confirmed, waitlisted, cancelled) for a given shift."""
    query = (
        db.query(Registration)
        .options(selectinload(Registration.shift).selectinload(Shift.event))
        .filter(Registration.shift_id == shift_id)
    )

    if status_filter:
        query = query.filter(Registration.status == status_filter)

    registrations = query.order_by(
        Registration.status.asc(),
        Registration.waitlist_position.asc(),
        Registration.registered_at.asc(),
    ).all()
    return [_build_reg_out(r) for r in registrations]


# ── 6. Volunteer Availability Endpoints ──────────────────────────────────────

@router.get(
    "/availability",
    response_model=List[AvailabilityOut],
    summary="View declared availability windows",
)
def get_my_availability(
    current_user: User = Depends(require_volunteer),
    db: Session = Depends(get_db),
):
    """Return all recurring and date-specific availability windows for the volunteer."""
    return (
        db.query(VolunteerAvailability)
        .filter(VolunteerAvailability.volunteer_id == current_user.id)
        .order_by(
            VolunteerAvailability.day_of_week.asc(),
            VolunteerAvailability.start_time.asc(),
        )
        .all()
    )


@router.post(
    "/availability",
    response_model=AvailabilityOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add an availability window",
)
def add_availability(
    payload: AvailabilityCreate,
    current_user: User = Depends(require_volunteer),
    db: Session = Depends(get_db),
):
    """Define a new weekly or specific-date availability time window."""
    avail = VolunteerAvailability(
        volunteer_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(avail)
    db.commit()
    db.refresh(avail)
    return avail


@router.delete(
    "/availability/{availability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an availability window",
)
def remove_availability(
    availability_id: str,
    current_user: User = Depends(require_volunteer),
    db: Session = Depends(get_db),
):
    """Remove a previously saved availability window."""
    avail = (
        db.query(VolunteerAvailability)
        .filter(
            VolunteerAvailability.id == availability_id,
            VolunteerAvailability.volunteer_id == current_user.id,
        )
        .first()
    )
    if not avail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability window not found.",
        )
    db.delete(avail)
    db.commit()
