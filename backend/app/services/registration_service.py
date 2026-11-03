"""
Registration service – register, join waitlist, cancel, and read registrations.

Every write is ONE transaction following the same recipe:

    lock shift row  ->  lock volunteer row  ->  validate  ->  write  ->  sync shift status  ->  commit

* The shift lock makes capacity decisions race-free (no overbooking).
* The volunteer lock makes the "no overlapping assignment" decision race-free
  across different shifts.
* Cancelling a confirmed registration promotes the waitlist inside the SAME
  transaction, so a vacated slot can never be grabbed out of queue order.
"""

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import clock
from app.models.event import Event
from app.models.registration import Registration, RegistrationStatus
from app.models.shift import Shift
from app.models.user import User
from app.schemas.registration import (
    CancelResponse,
    RegistrationDetailOut,
    RegistrationOut,
    RosterEntryOut,
    ShiftBrief,
)
from app.services import capacity_service, locks, scheduling_service, waitlist_service
from app.services.common import utcnow
from app.services.errors import (
    AlreadyRegisteredError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ShiftFullError,
)
from app.services.transactions import run_in_transaction


# ── Presenters ────────────────────────────────────────────────────────────────

def _registration_out(db: Session, registration: Registration) -> RegistrationOut:
    return RegistrationOut(
        id=registration.id,
        shift_id=registration.shift_id,
        volunteer_id=registration.volunteer_id,
        status=registration.status,
        waitlist_position=waitlist_service.waitlist_position(db, registration),
        created_at=registration.created_at,
        confirmed_at=registration.confirmed_at,
        cancelled_at=registration.cancelled_at,
    )


def _shift_brief(shift: Shift, event: Event) -> ShiftBrief:
    return ShiftBrief(
        shift_id=shift.id,
        event_id=event.id,
        event_name=event.name,
        event_location=event.location,
        title=shift.title,
        shift_date=shift.shift_date,
        start_time=shift.start_time,
        end_time=shift.end_time,
        shift_status=shift.status,
    )


# ── Guards ────────────────────────────────────────────────────────────────────

def _ensure_no_active_registration(db: Session, volunteer_id: str, shift_id: str) -> None:
    existing = db.scalars(
        select(Registration).where(
            Registration.shift_id == shift_id,
            Registration.volunteer_id == volunteer_id,
            Registration.status.in_(RegistrationStatus.ACTIVE),
        )
    ).first()
    if existing is None:
        return
    if existing.status == RegistrationStatus.CONFIRMED:
        raise AlreadyRegisteredError(
            "You are already registered for this shift.",
            context={"registration_id": existing.id},
        )
    raise AlreadyRegisteredError(
        "You are already on the waitlist for this shift.",
        code="ALREADY_WAITLISTED",
        context={"registration_id": existing.id},
    )


def _duplicate_race_error() -> AlreadyRegisteredError:
    return AlreadyRegisteredError("You already have an active registration for this shift.")


# ── Commands ──────────────────────────────────────────────────────────────────

def register(db: Session, volunteer_id: str, shift_id: str) -> RegistrationOut:
    """Confirm a volunteer on a shift with a free slot."""

    def operation() -> Registration:
        shift = locks.lock_shift(db, shift_id)
        locks.lock_volunteer(db, volunteer_id)

        scheduling_service.ensure_shift_bookable(shift)
        _ensure_no_active_registration(db, volunteer_id, shift.id)
        scheduling_service.ensure_can_attend(db, volunteer_id, shift)

        if capacity_service.remaining_slots(db, shift) <= 0:
            raise ShiftFullError(
                f"This shift is full ({shift.capacity}/{shift.capacity} volunteers confirmed). "
                "You can join the waitlist and will be offered the next free slot.",
                context={
                    "capacity": shift.capacity,
                    "waitlist_count": waitlist_service.waitlist_count(db, shift.id),
                    "can_join_waitlist": True,
                },
            )

        registration = Registration(
            shift_id=shift.id,
            volunteer_id=volunteer_id,
            status=RegistrationStatus.CONFIRMED,
            confirmed_at=utcnow(),
        )
        db.add(registration)
        db.flush()
        capacity_service.sync_shift_status(db, shift)
        return registration

    try:
        registration = run_in_transaction(db, operation)
    except IntegrityError:
        raise _duplicate_race_error()
    return _registration_out(db, registration)


def join_waitlist(db: Session, volunteer_id: str, shift_id: str) -> RegistrationOut:
    """Join the FIFO waitlist of a shift that is currently full."""

    def operation() -> Registration:
        shift = locks.lock_shift(db, shift_id)
        locks.lock_volunteer(db, volunteer_id)

        scheduling_service.ensure_shift_bookable(shift)
        _ensure_no_active_registration(db, volunteer_id, shift.id)
        scheduling_service.ensure_can_attend(db, volunteer_id, shift)

        if capacity_service.remaining_slots(db, shift) > 0:
            raise ConflictError(
                "This shift still has open slots, so there is no waitlist. Register directly instead.",
                code="SHIFT_NOT_FULL",
            )
        return waitlist_service.add_to_waitlist(db, shift, volunteer_id)

    try:
        registration = run_in_transaction(db, operation)
    except IntegrityError:
        raise _duplicate_race_error()
    return _registration_out(db, registration)


def cancel(db: Session, actor: User, registration_id: str) -> CancelResponse:
    """
    Cancel a registration (volunteers: their own only; admins: any).
    If it was CONFIRMED, the vacated slot is offered to the waitlist immediately.
    """
    is_admin = actor.role == "admin"
    first_look = db.get(Registration, registration_id)
    if first_look is None:
        raise NotFoundError("Registration not found.")
    if first_look.volunteer_id != actor.id and not is_admin:
        raise ForbiddenError("You can only cancel your own registrations.")
    shift_id = first_look.shift_id
    db.rollback()  # end the read-only transaction; the real one starts with the lock

    def operation() -> tuple[Registration, bool]:
        shift = locks.lock_shift(db, shift_id)
        registration = db.execute(
            select(Registration)
            .where(Registration.id == registration_id)
            .execution_options(populate_existing=True)
        ).scalar_one()

        if registration.status == RegistrationStatus.CANCELLED:
            raise ConflictError("This registration is already cancelled.", code="ALREADY_CANCELLED")
        if not is_admin and scheduling_service.shift_start_at(shift) <= clock.now():
            raise ConflictError(
                "This shift has already started, so it can no longer be cancelled online. "
                "Please contact the organiser.",
                code="SHIFT_STARTED",
            )

        was_confirmed = registration.status == RegistrationStatus.CONFIRMED
        registration.status = RegistrationStatus.CANCELLED
        registration.cancelled_at = utcnow()
        db.flush()

        promoted = []
        if was_confirmed:
            promoted = waitlist_service.promote_eligible(db, shift)
        capacity_service.sync_shift_status(db, shift)
        return registration, bool(promoted)

    registration, promoted = run_in_transaction(db, operation)
    return CancelResponse(
        message="Registration cancelled.",
        registration=_registration_out(db, registration),
        waitlist_promoted=promoted,
    )


# ── Queries ───────────────────────────────────────────────────────────────────

def list_my_registrations(
    db: Session,
    volunteer_id: str,
    *,
    include_past: bool = False,
    include_cancelled: bool = False,
) -> list[RegistrationDetailOut]:
    statuses = list(RegistrationStatus.ACTIVE)
    if include_cancelled:
        statuses.append(RegistrationStatus.CANCELLED)

    stmt = (
        select(Registration, Shift, Event)
        .join(Shift, Shift.id == Registration.shift_id)
        .join(Event, Event.id == Shift.event_id)
        .where(
            Registration.volunteer_id == volunteer_id,
            Registration.status.in_(statuses),
        )
    )
    if not include_past:
        now = clock.now()
        stmt = stmt.where(
            or_(
                Shift.shift_date > now.date(),
                and_(Shift.shift_date == now.date(), Shift.end_time > now.time()),
            )
        )
    stmt = stmt.order_by(Shift.shift_date, Shift.start_time, Registration.queue_seq)

    results: list[RegistrationDetailOut] = []
    for registration, shift, event in db.execute(stmt).all():
        base = _registration_out(db, registration)
        results.append(RegistrationDetailOut(**base.model_dump(), shift=_shift_brief(shift, event)))
    return results


def list_shift_roster(
    db: Session, shift_id: str, status: str | None = None
) -> list[RosterEntryOut]:
    """Admin view: who is confirmed / waitlisted on a shift."""
    if db.get(Shift, shift_id) is None:
        raise NotFoundError("Shift not found.")

    stmt = (
        select(Registration, User)
        .join(User, User.id == Registration.volunteer_id)
        .where(Registration.shift_id == shift_id)
    )
    if status:
        stmt = stmt.where(Registration.status == status)
    else:
        stmt = stmt.where(Registration.status.in_(RegistrationStatus.ACTIVE))
    stmt = stmt.order_by(Registration.status, Registration.queue_seq)

    return [
        RosterEntryOut(
            registration_id=registration.id,
            volunteer_id=user.id,
            full_name=user.full_name,
            email=user.email,
            status=registration.status,
            waitlist_position=waitlist_service.waitlist_position(db, registration),
            created_at=registration.created_at,
            confirmed_at=registration.confirmed_at,
        )
        for registration, user in db.execute(stmt).all()
    ]
