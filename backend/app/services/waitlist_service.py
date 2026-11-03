"""
FIFO waitlist service.

  • Queue order = `Registration.queue_seq` (identity column, strictly increasing).
  • A volunteer can be on a shift's waitlist only once (partial unique index).
  • `promote_eligible` fills vacant slots from the head of the queue. For every
    candidate it re-runs the full eligibility check (volunteer still active, no
    overlapping CONFIRMED assignment, inside availability). Ineligible
    candidates are SKIPPED and stay waitlisted (keeping their place); the scan
    continues with the next person.

All functions here assume the caller already holds the shift row lock.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.registration import Registration, RegistrationStatus
from app.models.shift import Shift
from app.models.user import User
from app.services import capacity_service, locks, scheduling_service
from app.services.common import utcnow
from app.services.errors import SchedulingError


def waitlist_count(db: Session, shift_id: str) -> int:
    db.flush()
    return (
        db.scalar(
            select(func.count())
            .select_from(Registration)
            .where(
                Registration.shift_id == shift_id,
                Registration.status == RegistrationStatus.WAITLISTED,
            )
        )
        or 0
    )


def waitlist_position(db: Session, registration: Registration) -> int | None:
    """1-based queue position, or None if the registration is not waitlisted."""
    if registration.status != RegistrationStatus.WAITLISTED:
        return None
    ahead = db.scalar(
        select(func.count())
        .select_from(Registration)
        .where(
            Registration.shift_id == registration.shift_id,
            Registration.status == RegistrationStatus.WAITLISTED,
            Registration.queue_seq < registration.queue_seq,
        )
    )
    return (ahead or 0) + 1


def add_to_waitlist(db: Session, shift: Shift, volunteer_id: str) -> Registration:
    registration = Registration(
        shift_id=shift.id,
        volunteer_id=volunteer_id,
        status=RegistrationStatus.WAITLISTED,
    )
    db.add(registration)
    db.flush()  # populates queue_seq
    return registration


def promote_eligible(db: Session, shift: Shift) -> list[Registration]:
    """Fill vacant slots from the waitlist, in FIFO order, skipping ineligible people."""
    promoted: list[Registration] = []
    if not scheduling_service.is_bookable(shift):
        return promoted

    remaining = capacity_service.remaining_slots(db, shift)
    if remaining <= 0:
        return promoted

    queue = list(
        db.scalars(
            select(Registration)
            .where(
                Registration.shift_id == shift.id,
                Registration.status == RegistrationStatus.WAITLISTED,
            )
            .order_by(Registration.queue_seq)
        )
    )

    for registration in queue:
        if remaining <= 0:
            break

        # Same lock order as direct registration: shift (held) -> volunteer.
        locks.lock_volunteer(db, registration.volunteer_id)

        volunteer = db.get(User, registration.volunteer_id)
        if volunteer is None or not volunteer.is_active:
            continue

        try:
            scheduling_service.ensure_can_attend(db, registration.volunteer_id, shift)
        except SchedulingError:
            continue  # conflict / outside availability -> keep their place, try next

        registration.status = RegistrationStatus.CONFIRMED
        registration.confirmed_at = utcnow()
        db.flush()
        promoted.append(registration)
        remaining -= 1

    return promoted
