"""
routers/events.py  –  Module 1: NGO Admin & Event Management
─────────────────────────────────────────────────────────────
Aligned with the Module 3 Event model (name / location / start_date / end_date,
status published|cancelled). Events are published as soon as they are created.

  POST   /api/v1/events/                   – Create event (admin)
  GET    /api/v1/events/                   – Browse active events (public)
  GET    /api/v1/events/admin              – Events owned by the calling admin
  GET    /api/v1/events/{event_id}         – Event details
  PATCH  /api/v1/events/{event_id}         – Update event (admin, owner)
  POST   /api/v1/events/{event_id}/cancel  – Cancel event + all its shifts (admin, owner)
  DELETE /api/v1/events/{event_id}         – Hard delete, only if nobody is registered
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.database.connection import get_db
from app.models.event import Event, EventStatus
from app.models.ngo import NGO
from app.models.registration import Registration, RegistrationStatus
from app.models.shift import Shift, ShiftStatus
from app.models.user import User
from app.schemas.event import EventCreate, EventOut, EventUpdate
from app.services import recommendation_service as ownership
from app.services import shift_service
from app.services.errors import ConflictError, NotFoundError, ValidationFailed

router = APIRouter(prefix="/events", tags=["Event Management"])


@router.get("/", response_model=list[EventOut], summary="Browse active events (public)")
def list_events(db: Session = Depends(get_db)):
    return shift_service.list_events(db)


@router.get("/admin", response_model=list[EventOut], summary="Events owned by the calling admin")
def list_my_events(
    include_cancelled: bool = False,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(Event).where(ownership.owned_events_clause(db, admin))
    if not include_cancelled:
        stmt = stmt.where(Event.status != EventStatus.CANCELLED)
    return list(db.scalars(stmt.order_by(Event.start_date.desc(), Event.name)))


@router.post("/", response_model=EventOut, status_code=status.HTTP_201_CREATED, summary="Create an event (admin)")
def create_event(payload: EventCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    event = shift_service.create_event(db, admin, payload)
    ngo_id = db.scalar(select(NGO.id).where(NGO.admin_user_id == admin.id))
    if ngo_id:
        event.ngo_id = ngo_id
        db.commit()
        db.refresh(event)
    return event


@router.get("/{event_id}", response_model=EventOut, summary="Get event details")
def get_event(event_id: str, db: Session = Depends(get_db)):
    return shift_service.get_event(db, event_id)


@router.patch("/{event_id}", response_model=EventOut, summary="Update an event (admin, owner)")
def update_event(
    event_id: str, payload: EventUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    event = ownership.get_owned_event(db, admin, event_id)
    if event.status == EventStatus.CANCELLED:
        raise ConflictError("A cancelled event cannot be edited.", code="EVENT_CANCELLED")

    changes = {
        k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None or k == "description"
    }
    start = changes.get("start_date", event.start_date)
    end = changes.get("end_date", event.end_date)
    if end < start:
        raise ValidationFailed("end_date cannot be before start_date.")

    outside = db.scalar(
        select(func.count())
        .select_from(Shift)
        .where(
            Shift.event_id == event.id,
            Shift.status != ShiftStatus.CANCELLED,
            or_(Shift.shift_date < start, Shift.shift_date > end),
        )
    )
    if outside:
        raise ConflictError(
            f"{outside} active shift(s) fall outside the new event dates. Cancel or move them first.",
            code="SHIFTS_OUTSIDE_DATES",
        )

    for field, value in changes.items():
        setattr(event, field, value)
    db.commit()
    db.refresh(event)
    return event


@router.post("/{event_id}/cancel", response_model=EventOut, summary="Cancel an event and all its shifts (admin, owner)")
def cancel_event(event_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    event = ownership.get_owned_event(db, admin, event_id)
    if event.status == EventStatus.CANCELLED:
        raise ConflictError("This event is already cancelled.", code="EVENT_CANCELLED")

    shift_ids = list(
        db.scalars(select(Shift.id).where(Shift.event_id == event_id, Shift.status != ShiftStatus.CANCELLED))
    )
    for shift_id in shift_ids:  # each cancellation also cancels that shift's registrations
        shift_service.cancel_shift(db, shift_id, admin)

    event = db.get(Event, event_id)
    event.status = EventStatus.CANCELLED
    db.commit()
    db.refresh(event)
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an event with no registrations")
def delete_event(event_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    event = ownership.get_owned_event(db, admin, event_id)
    active = db.scalar(
        select(func.count())
        .select_from(Registration)
        .join(Shift, Shift.id == Registration.shift_id)
        .where(Shift.event_id == event.id, Registration.status.in_(RegistrationStatus.ACTIVE))
    )
    if active:
        raise ConflictError(
            f"{active} volunteer(s) are registered or waitlisted. Cancel the event instead.",
            code="EVENT_HAS_REGISTRATIONS",
        )
    db.delete(event)
    db.commit()
