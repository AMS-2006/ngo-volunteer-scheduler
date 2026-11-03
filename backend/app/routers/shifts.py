"""
routers/shifts.py  –  Module 1 shift management, backed by the Module 3 shift service
───────────────────────────────────────────────────────────────────────────────────────
  POST /api/v1/events/{event_id}/shifts/                    – Add a shift (admin, owner)
  GET  /api/v1/events/{event_id}/shifts/                    – List shifts with live capacity
  GET  /api/v1/events/{event_id}/shifts/{shift_id}          – One shift
  PATCH /api/v1/events/{event_id}/shifts/{shift_id}         – Update (admin, owner)
  POST /api/v1/events/{event_id}/shifts/{shift_id}/cancel   – Cancel shift + its registrations (admin, owner)

The request body of POST must carry `event_id` equal to the path's event_id.
Capacity, waitlist and conflict rules live in services/shift_service.py (Module 3).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.database.connection import get_db
from app.models.shift import Shift
from app.models.user import User
from app.schemas.shift import ShiftCreate, ShiftOut, ShiftUpdate
from app.services import recommendation_service as ownership
from app.services import shift_service
from app.services.errors import NotFoundError, ValidationFailed

router = APIRouter(tags=["Shift Management"])


def _shift_of_event(db: Session, event_id: str, shift_id: str) -> Shift:
    shift = db.get(Shift, shift_id)
    if shift is None or shift.event_id != event_id:
        raise NotFoundError("Shift not found.")
    return shift


@router.post(
    "/events/{event_id}/shifts/",
    response_model=ShiftOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a shift to an event (admin, owner)",
)
def create_shift(
    event_id: str, payload: ShiftCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    ownership.get_owned_event(db, admin, event_id)
    if payload.event_id != event_id:
        raise ValidationFailed("event_id in the body must match the event_id in the URL.")
    return shift_service.create_shift(db, payload, admin)


@router.get("/events/{event_id}/shifts/", response_model=list[ShiftOut], summary="List shifts of an event")
def list_shifts(
    event_id: str,
    include_past: bool = True,
    include_cancelled: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shift_service.get_event(db, event_id)  # 404 if missing
    return shift_service.list_shifts(
        db, user, event_id=event_id, include_past=include_past, include_cancelled=include_cancelled, limit=500
    )


@router.get("/events/{event_id}/shifts/{shift_id}", response_model=ShiftOut, summary="Get one shift")
def get_shift(event_id: str, shift_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _shift_of_event(db, event_id, shift_id)
    return shift_service.get_shift(db, user, shift_id)


@router.patch("/events/{event_id}/shifts/{shift_id}", response_model=ShiftOut, summary="Update a shift (admin, owner)")
def update_shift(
    event_id: str,
    shift_id: str,
    payload: ShiftUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ownership.get_owned_event(db, admin, event_id)
    _shift_of_event(db, event_id, shift_id)
    return shift_service.update_shift(db, shift_id, payload, admin)


@router.post(
    "/events/{event_id}/shifts/{shift_id}/cancel",
    response_model=ShiftOut,
    summary="Cancel a shift and all its registrations (admin, owner)",
)
def cancel_shift(
    event_id: str, shift_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    ownership.get_owned_event(db, admin, event_id)
    _shift_of_event(db, event_id, shift_id)
    return shift_service.cancel_shift(db, shift_id, admin)
