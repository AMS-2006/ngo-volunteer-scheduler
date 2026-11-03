"""
Scheduling / conflict-detection service.

Rules implemented here:
  • Time-overlap detection:  new_start < existing_end AND new_end > existing_start
    (so back-to-back shifts 09:00-11:00 and 11:00-13:00 do NOT conflict).
  • Only CONFIRMED registrations occupy a volunteer's time. WAITLISTED entries are
    tentative and CANCELLED ones are ignored. Conflicts are checked across ALL
    events, because a volunteer cannot be in two places at once.
  • A shift must be bookable: not cancelled, event not cancelled, not yet started.
  • `ensure_can_attend` bundles the volunteer-specific checks (conflicts +
    availability) so registration, waitlist-join and waitlist-promotion all apply
    exactly the same rules.
"""

from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.models.event import Event, EventStatus
from app.models.registration import Registration, RegistrationStatus
from app.models.shift import Shift, ShiftStatus
from app.services import availability_service
from app.services.common import hhmm, pretty_date
from app.services.errors import ConflictError, ScheduleConflictError


def intervals_overlap(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    """True when [a_start, a_end) and [b_start, b_end) share any time."""
    return a_start < b_end and a_end > b_start


def shift_start_at(shift: Shift) -> datetime:
    return datetime.combine(shift.shift_date, shift.start_time)


# ── Bookability ───────────────────────────────────────────────────────────────

def ensure_shift_bookable(shift: Shift) -> None:
    if shift.status == ShiftStatus.CANCELLED:
        raise ConflictError("This shift has been cancelled.", code="SHIFT_CANCELLED")
    if shift.event.status == EventStatus.CANCELLED:
        raise ConflictError("This event has been cancelled.", code="EVENT_CANCELLED")
    if shift_start_at(shift) <= clock.now():
        raise ConflictError(
            "This shift has already started or finished, so registration is closed.",
            code="SHIFT_CLOSED",
        )


def is_bookable(shift: Shift) -> bool:
    try:
        ensure_shift_bookable(shift)
        return True
    except ConflictError:
        return False


# ── Conflict detection ────────────────────────────────────────────────────────

def find_conflict(db: Session, volunteer_id: str, shift: Shift):
    """
    Return (Registration, Shift, Event) for the first CONFIRMED assignment of this
    volunteer that overlaps `shift`, or None.
    """
    stmt = (
        select(Registration, Shift, Event)
        .join(Shift, Shift.id == Registration.shift_id)
        .join(Event, Event.id == Shift.event_id)
        .where(
            Registration.volunteer_id == volunteer_id,
            Registration.status == RegistrationStatus.CONFIRMED,
            Registration.shift_id != shift.id,
            Shift.status != ShiftStatus.CANCELLED,
            Shift.shift_date == shift.shift_date,
            # existing.start < new.end  AND  existing.end > new.start
            Shift.start_time < shift.end_time,
            Shift.end_time > shift.start_time,
        )
        .order_by(Shift.start_time)
        .limit(1)
    )
    return db.execute(stmt).first()


def ensure_no_conflict(db: Session, volunteer_id: str, shift: Shift) -> None:
    found = find_conflict(db, volunteer_id, shift)
    if found is None:
        return
    registration, other_shift, other_event = found
    raise ScheduleConflictError(
        "Registration rejected: You already have an assignment from "
        f"{hhmm(other_shift.start_time)} to {hhmm(other_shift.end_time)} "
        f"on {pretty_date(other_shift.shift_date)} "
        f"({other_event.name} - {other_shift.title}).",
        context={
            "conflicting_registration_id": registration.id,
            "conflicting_shift_id": other_shift.id,
            "event_name": other_event.name,
            "shift_title": other_shift.title,
            "shift_date": other_shift.shift_date.isoformat(),
            "start_time": hhmm(other_shift.start_time),
            "end_time": hhmm(other_shift.end_time),
        },
    )


def ensure_can_attend(db: Session, volunteer_id: str, shift: Shift) -> None:
    """Volunteer-specific eligibility: no overlapping assignment + inside availability."""
    ensure_no_conflict(db, volunteer_id, shift)
    availability_service.ensure_covered(
        db, volunteer_id, shift.shift_date, shift.start_time, shift.end_time
    )
