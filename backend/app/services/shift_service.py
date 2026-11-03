"""
Event & shift management service (admin commands + volunteer-facing queries).

Read side builds `ShiftOut` with LIVE numbers (registered_count, remaining_slots,
waitlist_count) computed from registrations in a single grouped query, plus the
viewing volunteer's own registration state on each shift.
"""

from datetime import date, datetime, time

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core import clock
from app.models.event import Event, EventStatus
from app.models.registration import Registration, RegistrationStatus
from app.models.shift import Shift, ShiftStatus
from app.models.user import User
from app.schemas.event import EventCreate
from app.schemas.registration import WaitlistProcessResponse
from app.schemas.shift import MyRegistrationInfo, ShiftCreate, ShiftOut, ShiftUpdate
from app.services import capacity_service, locks, waitlist_service
from app.services.common import hhmm, pretty_date, utcnow
from app.services.errors import ConflictError, NotFoundError, ValidationFailed
from app.services.transactions import run_in_transaction


# ── Events (minimal; Module 1 will extend) ────────────────────────────────────

def create_event(db: Session, admin: User, payload: EventCreate) -> Event:
    if payload.end_date < clock.now().date():
        raise ValidationFailed("Event end date is in the past.")

    def operation() -> Event:
        event = Event(created_by=admin.id, **payload.model_dump())
        db.add(event)
        db.flush()
        return event

    event = run_in_transaction(db, operation)
    db.refresh(event)
    return event


def list_events(db: Session, include_cancelled: bool = False) -> list[Event]:
    stmt = select(Event).order_by(Event.start_date, Event.name)
    if not include_cancelled:
        stmt = stmt.where(Event.status != EventStatus.CANCELLED)
    return list(db.scalars(stmt))


def get_event(db: Session, event_id: str) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise NotFoundError("Event not found.")
    return event


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_shift_timing(event: Event, on_date: date, start: time, end: time) -> None:
    if end <= start:
        raise ValidationFailed("Shift end time must be after its start time.")
    if not (event.start_date <= on_date <= event.end_date):
        raise ValidationFailed(
            f"Shift date {pretty_date(on_date)} is outside the event's dates "
            f"({pretty_date(event.start_date)} to {pretty_date(event.end_date)})."
        )
    if clock.now() >= datetime.combine(on_date, start):
        raise ValidationFailed("Shift start must be in the future.")


# ── Shift commands (admin) ────────────────────────────────────────────────────

def create_shift(db: Session, payload: ShiftCreate, viewer: User) -> ShiftOut:
    def operation() -> Shift:
        event = db.get(Event, payload.event_id)
        if event is None:
            raise NotFoundError("Event not found.")
        if event.status == EventStatus.CANCELLED:
            raise ConflictError("Cannot add shifts to a cancelled event.", code="EVENT_CANCELLED")
        _validate_shift_timing(event, payload.shift_date, payload.start_time, payload.end_time)
        shift = Shift(**payload.model_dump())
        db.add(shift)
        db.flush()
        return shift

    shift = run_in_transaction(db, operation)
    return get_shift(db, viewer, shift.id)


def update_shift(db: Session, shift_id: str, payload: ShiftUpdate, viewer: User) -> ShiftOut:
    changes = payload.model_dump(exclude_unset=True)

    def operation() -> None:
        shift = locks.lock_shift(db, shift_id)
        if shift.status == ShiftStatus.CANCELLED:
            raise ConflictError("A cancelled shift cannot be edited.", code="SHIFT_CANCELLED")

        new_date = changes.get("shift_date", shift.shift_date)
        new_start = changes.get("start_time", shift.start_time)
        new_end = changes.get("end_time", shift.end_time)
        timing_changed = (new_date, new_start, new_end) != (
            shift.shift_date,
            shift.start_time,
            shift.end_time,
        )

        if timing_changed:
            active = db.scalar(
                select(func.count())
                .select_from(Registration)
                .where(
                    Registration.shift_id == shift.id,
                    Registration.status.in_(RegistrationStatus.ACTIVE),
                )
            )
            if active:
                raise ConflictError(
                    f"The date/time cannot be changed because {active} volunteer(s) are "
                    "registered or waitlisted. Cancel this shift and create a new one instead.",
                    code="SHIFT_HAS_REGISTRATIONS",
                )
            _validate_shift_timing(shift.event, new_date, new_start, new_end)
            shift.shift_date, shift.start_time, shift.end_time = new_date, new_start, new_end

        if "title" in changes:
            shift.title = changes["title"]

        capacity_increased = False
        if "capacity" in changes:
            confirmed = capacity_service.confirmed_count(db, shift.id)
            if changes["capacity"] < confirmed:
                raise ConflictError(
                    f"Capacity cannot be lowered to {changes['capacity']} because "
                    f"{confirmed} volunteers are already confirmed.",
                    code="CAPACITY_BELOW_CONFIRMED",
                )
            capacity_increased = changes["capacity"] > shift.capacity
            shift.capacity = changes["capacity"]

        db.flush()
        if capacity_increased:
            waitlist_service.promote_eligible(db, shift)
        capacity_service.sync_shift_status(db, shift)

    run_in_transaction(db, operation)
    return get_shift(db, viewer, shift_id)


def cancel_shift(db: Session, shift_id: str, viewer: User) -> ShiftOut:
    """Withdraw a shift and cancel every active registration on it."""

    def operation() -> None:
        shift = locks.lock_shift(db, shift_id)
        if shift.status == ShiftStatus.CANCELLED:
            raise ConflictError("This shift is already cancelled.", code="SHIFT_CANCELLED")
        now = utcnow()
        active = db.scalars(
            select(Registration).where(
                Registration.shift_id == shift.id,
                Registration.status.in_(RegistrationStatus.ACTIVE),
            )
        )
        for registration in active:
            registration.status = RegistrationStatus.CANCELLED
            registration.cancelled_at = now
        shift.status = ShiftStatus.CANCELLED
        db.flush()

    run_in_transaction(db, operation)
    return get_shift(db, viewer, shift_id)


def process_waitlist(db: Session, shift_id: str, viewer: User) -> WaitlistProcessResponse:
    """Admin tool: re-run FIFO promotion (e.g. after a volunteer's own conflict cleared)."""

    def operation() -> int:
        shift = locks.lock_shift(db, shift_id)
        promoted = waitlist_service.promote_eligible(db, shift)
        capacity_service.sync_shift_status(db, shift)
        return len(promoted)

    count = run_in_transaction(db, operation)
    return WaitlistProcessResponse(
        promoted_count=count, shift=get_shift(db, viewer, shift_id)
    )


# ── Shift queries ─────────────────────────────────────────────────────────────

def _counts_statement():
    confirmed_sq = (
        select(Registration.shift_id.label("shift_id"), func.count().label("n"))
        .where(Registration.status == RegistrationStatus.CONFIRMED)
        .group_by(Registration.shift_id)
        .subquery()
    )
    waitlisted_sq = (
        select(Registration.shift_id.label("shift_id"), func.count().label("n"))
        .where(Registration.status == RegistrationStatus.WAITLISTED)
        .group_by(Registration.shift_id)
        .subquery()
    )
    confirmed_n = func.coalesce(confirmed_sq.c.n, 0)
    waitlisted_n = func.coalesce(waitlisted_sq.c.n, 0)
    stmt = (
        select(Shift, Event, confirmed_n, waitlisted_n)
        .join(Event, Event.id == Shift.event_id)
        .outerjoin(confirmed_sq, confirmed_sq.c.shift_id == Shift.id)
        .outerjoin(waitlisted_sq, waitlisted_sq.c.shift_id == Shift.id)
    )
    return stmt, confirmed_n


def _build_outputs(db: Session, viewer: User, rows) -> list[ShiftOut]:
    mine: dict[str, MyRegistrationInfo] = {}
    if viewer.role == "volunteer" and rows:
        shift_ids = [row[0].id for row in rows]
        registrations = db.scalars(
            select(Registration).where(
                Registration.volunteer_id == viewer.id,
                Registration.status.in_(RegistrationStatus.ACTIVE),
                Registration.shift_id.in_(shift_ids),
            )
        )
        for registration in registrations:
            mine[registration.shift_id] = MyRegistrationInfo(
                registration_id=registration.id,
                status=registration.status,
                waitlist_position=waitlist_service.waitlist_position(db, registration),
            )

    outputs: list[ShiftOut] = []
    for shift, event, confirmed, waitlisted in rows:
        remaining = max(shift.capacity - confirmed, 0)
        outputs.append(
            ShiftOut(
                id=shift.id,
                event_id=event.id,
                event_name=event.name,
                event_location=event.location,
                title=shift.title,
                shift_date=shift.shift_date,
                start_time=shift.start_time,
                end_time=shift.end_time,
                capacity=shift.capacity,
                registered_count=confirmed,
                remaining_slots=remaining,
                waitlist_count=waitlisted,
                is_full=remaining == 0,
                status=shift.status,
                my_registration=mine.get(shift.id),
            )
        )
    return outputs


def list_shifts(
    db: Session,
    viewer: User,
    *,
    event_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    available_only: bool = False,
    include_past: bool = False,
    include_cancelled: bool = False,
    skip: int = 0,
    limit: int = 50,
) -> list[ShiftOut]:
    stmt, confirmed_n = _counts_statement()

    show_cancelled = include_cancelled and viewer.role == "admin"
    if not show_cancelled:
        stmt = stmt.where(
            Shift.status != ShiftStatus.CANCELLED, Event.status != EventStatus.CANCELLED
        )
    if event_id:
        stmt = stmt.where(Shift.event_id == event_id)
    if date_from:
        stmt = stmt.where(Shift.shift_date >= date_from)
    if date_to:
        stmt = stmt.where(Shift.shift_date <= date_to)
    if available_only:
        stmt = stmt.where(Shift.capacity > confirmed_n)
    if not include_past:
        now = clock.now()
        stmt = stmt.where(
            or_(
                Shift.shift_date > now.date(),
                and_(Shift.shift_date == now.date(), Shift.start_time > now.time()),
            )
        )

    stmt = (
        stmt.order_by(Shift.shift_date, Shift.start_time, Shift.title)
        .offset(skip)
        .limit(limit)
    )
    return _build_outputs(db, viewer, db.execute(stmt).all())


def get_shift(db: Session, viewer: User, shift_id: str) -> ShiftOut:
    stmt, _ = _counts_statement()
    rows = db.execute(stmt.where(Shift.id == shift_id)).all()
    if not rows:
        raise NotFoundError("Shift not found.")
    return _build_outputs(db, viewer, rows)[0]
