"""
routers/shifts.py  –  Module 1 (Shift management under events)
───────────────────────────────────────────────────────────────
Endpoints:
  POST   /api/v1/events/{event_id}/shifts/         – Add shift to event (admin)
  GET    /api/v1/events/{event_id}/shifts/         – List all shifts for event
  GET    /api/v1/events/{event_id}/shifts/{id}     – Get single shift detail
  PATCH  /api/v1/events/{event_id}/shifts/{id}     – Update shift (admin)
  DELETE /api/v1/events/{event_id}/shifts/{id}     – Delete shift (admin)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.database.connection import get_db
from app.core.deps import require_admin
from app.models.event import Event
from app.models.ngo import NGO
from app.models.shift import Shift
from app.models.user import User
from app.schemas.shift import ShiftCreate, ShiftOut, ShiftUpdate

router = APIRouter(tags=["Shift Management"])


# ── Helpers ────────────────────────────────────────────────────────────────────
def _get_event_or_404(event_id: str, db: Session) -> Event:
    event = db.query(Event).options(selectinload(Event.shifts)).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
    return event


def _get_shift_or_404(shift_id: str, event_id: str, db: Session) -> Shift:
    shift = (
        db.query(Shift)
        .options(selectinload(Shift.registrations))
        .filter(Shift.id == shift_id, Shift.event_id == event_id)
        .first()
    )
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found.")
    return shift


def _assert_admin_owns_event(admin: User, event: Event, db: Session):
    ngo = db.query(NGO).filter(NGO.admin_user_id == admin.id).first()
    if not ngo or event.ngo_id != ngo.id:
        raise HTTPException(status_code=403, detail="You can only manage shifts for your own NGO's events.")


def _shift_to_out(shift: Shift) -> ShiftOut:
    return ShiftOut(
        id=shift.id,
        event_id=shift.event_id,
        name=shift.name,
        description=shift.description,
        start_time=shift.start_time,
        end_time=shift.end_time,
        required_volunteers=shift.required_volunteers,
        required_skills=shift.required_skills,
        confirmed_count=shift.confirmed_count,
        waitlist_count=shift.waitlist_count,
        slots_remaining=shift.slots_remaining,
        is_full=shift.is_full,
        created_at=shift.created_at,
        updated_at=shift.updated_at,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/events/{event_id}/shifts/",
    response_model=ShiftOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a shift to an event (admin only)",
)
def create_shift(
    event_id: str,
    payload: ShiftCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new time-slot (shift) under an event.
    - The event must belong to the authenticated admin's NGO.
    - start_time must be before end_time.
    """
    event = _get_event_or_404(event_id, db)
    _assert_admin_owns_event(admin, event, db)

    shift = Shift(event_id=event_id, **payload.model_dump())
    db.add(shift)
    db.commit()
    db.refresh(shift)

    # Reload with registrations to compute derived fields
    shift = _get_shift_or_404(shift.id, event_id, db)
    return _shift_to_out(shift)


@router.get(
    "/events/{event_id}/shifts/",
    response_model=list[ShiftOut],
    summary="List all shifts for an event",
)
def list_shifts(
    event_id: str,
    db: Session = Depends(get_db),
):
    """Returns all shifts for an event, ordered by start time. Public access."""
    _get_event_or_404(event_id, db)  # Verify event exists
    shifts = (
        db.query(Shift)
        .options(selectinload(Shift.registrations))
        .filter(Shift.event_id == event_id)
        .order_by(Shift.start_time)
        .all()
    )
    return [_shift_to_out(s) for s in shifts]


@router.get(
    "/events/{event_id}/shifts/{shift_id}",
    response_model=ShiftOut,
    summary="Get shift details with coverage data",
)
def get_shift(
    event_id: str,
    shift_id: str,
    db: Session = Depends(get_db),
):
    shift = _get_shift_or_404(shift_id, event_id, db)
    return _shift_to_out(shift)


@router.patch(
    "/events/{event_id}/shifts/{shift_id}",
    response_model=ShiftOut,
    summary="Update a shift (admin only)",
)
def update_shift(
    event_id: str,
    shift_id: str,
    payload: ShiftUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    event = _get_event_or_404(event_id, db)
    _assert_admin_owns_event(admin, event, db)
    shift = _get_shift_or_404(shift_id, event_id, db)

    update_data = payload.model_dump(exclude_unset=True)
    # Validate times if either is being updated
    start = update_data.get("start_time", shift.start_time)
    end = update_data.get("end_time", shift.end_time)
    if end <= start:
        raise HTTPException(status_code=400, detail="end_time must be after start_time.")

    for field, value in update_data.items():
        setattr(shift, field, value)

    db.commit()
    shift = _get_shift_or_404(shift_id, event_id, db)
    return _shift_to_out(shift)


@router.delete(
    "/events/{event_id}/shifts/{shift_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a shift (admin only)",
)
def delete_shift(
    event_id: str,
    shift_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    event = _get_event_or_404(event_id, db)
    _assert_admin_owns_event(admin, event, db)
    shift = _get_shift_or_404(shift_id, event_id, db)

    db.delete(shift)
    db.commit()
