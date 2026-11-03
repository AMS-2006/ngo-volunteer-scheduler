"""
routers/events.py  –  Module 1: NGO Admin & Event Management
─────────────────────────────────────────────────────────────
Endpoints:
  POST   /api/v1/events/                  – Create event (admin only)
  GET    /api/v1/events/                  – List published events (public)
  GET    /api/v1/events/admin             – List all events for admin's NGO
  GET    /api/v1/events/{event_id}        – Get single event with shifts
  PATCH  /api/v1/events/{event_id}        – Update event (admin only)
  DELETE /api/v1/events/{event_id}        – Delete event (admin only)
  POST   /api/v1/events/{event_id}/publish – Publish a draft event
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.database.connection import get_db
from app.core.deps import get_current_user, require_admin
from app.models.event import Event
from app.models.ngo import NGO
from app.models.user import User
from app.schemas.event import EventCreate, EventOut, EventSummary, EventUpdate

router = APIRouter(prefix="/events", tags=["Event Management"])


# ── Helper ─────────────────────────────────────────────────────────────────────
def _get_event_or_404(event_id: str, db: Session) -> Event:
    event = (
        db.query(Event)
        .options(selectinload(Event.shifts))
        .filter(Event.id == event_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
    return event


def _get_admin_ngo(admin: User, db: Session) -> NGO:
    """Fetch the NGO owned by this admin, or raise 404 if they haven't created one."""
    ngo = db.query(NGO).filter(NGO.admin_user_id == admin.id).first()
    if not ngo:
        raise HTTPException(
            status_code=404,
            detail="NGO profile not found. Please create your NGO profile first.",
        )
    return ngo


# ── Public: browse published events ───────────────────────────────────────────

@router.get(
    "/",
    response_model=list[EventSummary],
    summary="Browse published events (public)",
)
def list_published_events(
    city: str | None = Query(None, description="Filter by city"),
    cause: str | None = Query(None, description="Filter by cause category"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Public endpoint – no authentication required.
    Returns all PUBLISHED events for the volunteer portal and public landing page.
    """
    query = (
        db.query(Event)
        .options(selectinload(Event.shifts))
        .filter(Event.status == "published")
    )
    if city:
        query = query.filter(Event.city.ilike(f"%{city}%"))
    if cause:
        query = query.filter(Event.cause_category.ilike(f"%{cause}%"))

    events = query.order_by(Event.event_date.asc()).offset(skip).limit(limit).all()
    return [
        EventSummary(
            id=e.id,
            title=e.title,
            location_name=e.location_name,
            city=e.city,
            event_date=e.event_date,
            total_volunteers_required=e.total_volunteers_required,
            status=e.status,
            cause_category=e.cause_category,
            shift_count=len(e.shifts),
        )
        for e in events
    ]


# ── Admin: manage their NGO's events ─────────────────────────────────────────

@router.get(
    "/admin",
    response_model=list[EventSummary],
    summary="List all events for my NGO (admin only)",
)
def list_my_events(
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Returns all events (all statuses) belonging to the authenticated admin's NGO."""
    ngo = _get_admin_ngo(admin, db)
    query = (
        db.query(Event)
        .options(selectinload(Event.shifts))
        .filter(Event.ngo_id == ngo.id)
    )
    if status_filter:
        query = query.filter(Event.status == status_filter)

    events = query.order_by(Event.event_date.desc()).offset(skip).limit(limit).all()
    return [
        EventSummary(
            id=e.id,
            title=e.title,
            location_name=e.location_name,
            city=e.city,
            event_date=e.event_date,
            total_volunteers_required=e.total_volunteers_required,
            status=e.status,
            cause_category=e.cause_category,
            shift_count=len(e.shifts),
        )
        for e in events
    ]


@router.post(
    "/",
    response_model=EventOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new volunteering event (admin only)",
)
def create_event(
    payload: EventCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin creates a new event under their NGO.
    Event starts as DRAFT and must be explicitly published.
    """
    ngo = _get_admin_ngo(admin, db)

    event = Event(
        ngo_id=ngo.id,
        created_by=admin.id,
        **payload.model_dump(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    # Reload with shifts relationship
    return _get_event_or_404(event.id, db)


@router.get(
    "/{event_id}",
    response_model=EventOut,
    summary="Get event details with all shifts",
)
def get_event(event_id: str, db: Session = Depends(get_db)):
    """
    Retrieve full event details including all shift summaries.
    Accessible publicly for published events; all statuses for admins.
    """
    return _get_event_or_404(event_id, db)


@router.patch(
    "/{event_id}",
    response_model=EventOut,
    summary="Update event (admin only)",
)
def update_event(
    event_id: str,
    payload: EventUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Partial update of any event field. Admin must own the event's NGO."""
    event = _get_event_or_404(event_id, db)
    ngo = _get_admin_ngo(admin, db)

    if event.ngo_id != ngo.id:
        raise HTTPException(status_code=403, detail="You can only edit events belonging to your NGO.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)

    db.commit()
    db.refresh(event)
    return _get_event_or_404(event_id, db)


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete event (admin only)",
)
def delete_event(
    event_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete an event and all its shifts. Admin must own the event's NGO."""
    event = _get_event_or_404(event_id, db)
    ngo = _get_admin_ngo(admin, db)

    if event.ngo_id != ngo.id:
        raise HTTPException(status_code=403, detail="You can only delete events belonging to your NGO.")

    db.delete(event)
    db.commit()


@router.post(
    "/{event_id}/publish",
    response_model=EventOut,
    summary="Publish a draft event (admin only)",
)
def publish_event(
    event_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Transition event from DRAFT → PUBLISHED.
    Published events appear on the volunteer portal.
    Requires at least one shift to be created before publishing.
    """
    event = _get_event_or_404(event_id, db)
    ngo = _get_admin_ngo(admin, db)

    if event.ngo_id != ngo.id:
        raise HTTPException(status_code=403, detail="Not your event.")
    if event.status != "draft":
        raise HTTPException(status_code=400, detail=f"Event is already '{event.status}'. Cannot publish.")
    if not event.shifts:
        raise HTTPException(
            status_code=400,
            detail="Cannot publish an event with no shifts. Add at least one shift first.",
        )

    event.status = "published"
    db.commit()
    db.refresh(event)
    return _get_event_or_404(event_id, db)
