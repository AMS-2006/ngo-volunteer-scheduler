"""
Volunteer availability service.

Volunteers declare weekly recurring windows (day_of_week + start/end time).
A shift may only be assigned if ONE merged window fully covers the shift's
[start, end] on that weekday. Adjacent windows (10:00-12:00 + 12:00-14:00) are
merged, so a 11:00-13:00 shift is covered by them.
"""

from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.availability import VolunteerAvailability
from app.services import locks
from app.services.common import DAY_NAMES, hhmm, pretty_date
from app.services.errors import NotFoundError, OutsideAvailabilityError, ValidationFailed
from app.services.transactions import run_in_transaction


# ── Queries ───────────────────────────────────────────────────────────────────

def list_windows(db: Session, volunteer_id: str) -> list[VolunteerAvailability]:
    return list(
        db.scalars(
            select(VolunteerAvailability)
            .where(VolunteerAvailability.volunteer_id == volunteer_id)
            .order_by(VolunteerAvailability.day_of_week, VolunteerAvailability.start_time)
        )
    )


def _get_own_window(db: Session, volunteer_id: str, window_id: str) -> VolunteerAvailability:
    window = db.scalars(
        select(VolunteerAvailability).where(
            VolunteerAvailability.id == window_id,
            VolunteerAvailability.volunteer_id == volunteer_id,
        )
    ).first()
    if window is None:
        raise NotFoundError("Availability window not found.")
    return window


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_window(day_of_week: int, start: time, end: time) -> None:
    if not 0 <= day_of_week <= 6:
        raise ValidationFailed("day_of_week must be between 0 (Monday) and 6 (Sunday).")
    if end <= start:
        raise ValidationFailed("Availability end time must be after the start time.")


def _ensure_no_overlap(
    db: Session,
    volunteer_id: str,
    day_of_week: int,
    start: time,
    end: time,
    exclude_id: str | None = None,
) -> None:
    for w in list_windows(db, volunteer_id):
        if w.id == exclude_id or w.day_of_week != day_of_week:
            continue
        if start < w.end_time and end > w.start_time:  # same overlap rule as shifts
            raise ValidationFailed(
                f"This window overlaps your existing {DAY_NAMES[day_of_week]} availability "
                f"{hhmm(w.start_time)}-{hhmm(w.end_time)}. Edit that window instead."
            )


# ── Commands ──────────────────────────────────────────────────────────────────

def create_window(
    db: Session, volunteer_id: str, day_of_week: int, start: time, end: time
) -> VolunteerAvailability:
    _validate_window(day_of_week, start, end)

    def operation() -> VolunteerAvailability:
        locks.lock_volunteer(db, volunteer_id)
        _ensure_no_overlap(db, volunteer_id, day_of_week, start, end)
        window = VolunteerAvailability(
            volunteer_id=volunteer_id,
            day_of_week=day_of_week,
            start_time=start,
            end_time=end,
        )
        db.add(window)
        db.flush()
        return window

    window = run_in_transaction(db, operation)
    db.refresh(window)
    return window


def update_window(
    db: Session,
    volunteer_id: str,
    window_id: str,
    *,
    day_of_week: int | None = None,
    start: time | None = None,
    end: time | None = None,
) -> VolunteerAvailability:
    def operation() -> VolunteerAvailability:
        locks.lock_volunteer(db, volunteer_id)
        window = _get_own_window(db, volunteer_id, window_id)
        new_day = window.day_of_week if day_of_week is None else day_of_week
        new_start = window.start_time if start is None else start
        new_end = window.end_time if end is None else end
        _validate_window(new_day, new_start, new_end)
        _ensure_no_overlap(db, volunteer_id, new_day, new_start, new_end, exclude_id=window.id)
        window.day_of_week = new_day
        window.start_time = new_start
        window.end_time = new_end
        db.flush()
        return window

    window = run_in_transaction(db, operation)
    db.refresh(window)
    return window


def delete_window(db: Session, volunteer_id: str, window_id: str) -> None:
    def operation() -> None:
        locks.lock_volunteer(db, volunteer_id)
        window = _get_own_window(db, volunteer_id, window_id)
        db.delete(window)
        db.flush()

    run_in_transaction(db, operation)


# ── Coverage check (used by registration + waitlist promotion) ────────────────

def _merge(intervals: list[tuple[time, time]]) -> list[tuple[time, time]]:
    merged: list[tuple[time, time]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:  # overlapping or touching
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def ensure_covered(
    db: Session, volunteer_id: str, on_date: date, start: time, end: time
) -> None:
    """Raise OutsideAvailabilityError unless the volunteer's windows cover [start, end]."""
    windows = list_windows(db, volunteer_id)
    when = f"{pretty_date(on_date)}, {hhmm(start)}-{hhmm(end)}"

    if not windows:
        raise OutsideAvailabilityError(
            "Registration rejected: You have not set any availability yet. "
            "Add your available days and times before registering for shifts.",
            code="NO_AVAILABILITY_SET",
        )

    weekday = on_date.weekday()
    todays = [(w.start_time, w.end_time) for w in windows if w.day_of_week == weekday]
    if not todays:
        raise OutsideAvailabilityError(
            f"Registration rejected: You are not available on {DAY_NAMES[weekday]}s. "
            f"Add an availability window covering {hhmm(start)}-{hhmm(end)} to join this shift ({when}).",
        )

    merged = _merge(todays)
    if any(w_start <= start and w_end >= end for w_start, w_end in merged):
        return

    ranges = ", ".join(f"{hhmm(s)}-{hhmm(e)}" for s, e in merged)
    raise OutsideAvailabilityError(
        f"Registration rejected: This shift ({when}) is outside your declared availability. "
        f"Your availability on {DAY_NAMES[weekday]}: {ranges}.",
        context={"availability": [{"start_time": hhmm(s), "end_time": hhmm(e)} for s, e in merged]},
    )
