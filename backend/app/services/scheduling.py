"""
services/scheduling.py
───────────────────────
Module 3: Smart Shift Scheduling Engine

Core scheduling algorithms and business logic:
  • Conflict detection: Time-overlap detection across all active confirmed shifts
  • Capacity management: Concurrency-safe slot calculations with row locking
  • FIFO Waitlist engine: Automatic promotion on cancellation with conflict re-checks
  • Availability validation: Verifying shifts fall within volunteer declared windows
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.availability import VolunteerAvailability
from app.models.event import Event
from app.models.registration import Registration
from app.models.shift import Shift
from app.models.user import User


# ── 1. Time Overlap Logic ──────────────────────────────────────────────────────

def check_time_overlap(
    start_a: datetime,
    end_a: datetime,
    start_b: datetime,
    end_b: datetime,
) -> bool:
    """
    Returns True if two time intervals overlap.
    Standard interval overlap condition:
        (StartA < EndB) AND (EndA > StartB)

    Consecutive shifts (e.g., 09:00-11:00 and 11:00-13:00) return False.
    """
    return start_a < end_b and end_a > start_b


# ── 2. Scheduling Conflict Detection ──────────────────────────────────────────

def detect_conflict(
    volunteer_id: str,
    target_shift: Shift,
    db: Session,
    exclude_shift_id: Optional[str] = None,
) -> dict:
    """
    Check if target_shift overlaps with any of the volunteer's active CONFIRMED shifts.

    Requirements:
      • Check against active (confirmed) registrations across ALL events.
      • Ignore cancelled registrations and other waitlist spots.
      • Allow consecutive shifts (09:00-11:00 and 11:00-13:00).
      • Return clear, actionable error messages.
    """
    query = (
        db.query(Shift)
        .join(Registration, Registration.shift_id == Shift.id)
        .filter(
            Registration.volunteer_id == volunteer_id,
            Registration.status == "confirmed",
        )
    )

    if exclude_shift_id:
        query = query.filter(Shift.id != exclude_shift_id)

    confirmed_shifts = query.all()

    for existing in confirmed_shifts:
        if check_time_overlap(
            target_shift.start_time,
            target_shift.end_time,
            existing.start_time,
            existing.end_time,
        ):
            # Fetch event name if available
            event_title = existing.event.title if existing.event else "Another Event"
            start_str = existing.start_time.strftime("%H:%M")
            end_str = existing.end_time.strftime("%H:%M")
            date_str = existing.start_time.strftime("%b %d, %Y")

            message = (
                f"Registration rejected: You already have an assignment from "
                f"{start_str} to {end_str} on {date_str} ('{existing.name}' for {event_title})."
            )
            return {
                "has_conflict": True,
                "conflicting_shift": existing,
                "message": message,
            }

    return {
        "has_conflict": False,
        "conflicting_shift": None,
        "message": "No scheduling conflict detected.",
    }


# ── 3. Volunteer Availability Verification ───────────────────────────────────

def check_volunteer_availability(
    volunteer_id: str,
    target_shift: Shift,
    db: Session,
) -> dict:
    """
    Verify that the requested shift falls within the volunteer's declared availability.

    If the volunteer has explicitly configured availability windows:
      • Shift must fit inside at least one window for that day of week or specific date.
    If no specific availability windows are configured:
      • Allowed by default.
    """
    availabilities = (
        db.query(VolunteerAvailability)
        .filter(VolunteerAvailability.volunteer_id == volunteer_id)
        .all()
    )

    if not availabilities:
        # No strict availability windows defined: open availability
        return {"is_available": True, "message": "Volunteer has open availability."}

    shift_date = target_shift.start_time.date()
    shift_day_of_week = target_shift.start_time.weekday()  # 0=Monday ... 6=Sunday
    shift_start_time = target_shift.start_time.time()
    shift_end_time = target_shift.end_time.time()

    is_covered = False
    for avail in availabilities:
        # Check specific date override first
        if avail.specific_date is not None:
            if avail.specific_date == shift_date:
                if avail.start_time <= shift_start_time and avail.end_time >= shift_end_time:
                    is_covered = True
                    break
        # Check recurring day of week
        elif avail.day_of_week is not None and avail.day_of_week == shift_day_of_week:
            if avail.start_time <= shift_start_time and avail.end_time >= shift_end_time:
                is_covered = True
                break

    if not is_covered:
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_name = day_names[shift_day_of_week]
        start_str = shift_start_time.strftime("%H:%M")
        end_str = shift_end_time.strftime("%H:%M")
        return {
            "is_available": False,
            "message": (
                f"Registration rejected: Shift timing ({day_name} {start_str} - {end_str}) "
                f"is outside your declared availability."
            ),
        }

    return {"is_available": True, "message": "Shift fits volunteer availability."}


# ── 4. Concurrency-Safe Shift Registration Pipeline ──────────────────────────

def register_volunteer_for_shift(
    volunteer_id: str,
    shift_id: str,
    db: Session,
) -> dict:
    """
    Complete registration pipeline:
      1. Fetch shift with row lock (prevents race condition overbooking).
      2. Check for duplicate active registration or waitlist.
      3. Verify volunteer availability.
      4. Detect scheduling conflicts with overlapping shifts.
      5. Check capacity:
           - If slots remain: assign status = 'confirmed'.
           - If full: assign status = 'waitlisted' at next FIFO position.
      6. Commit transaction and return registration info.
    """
    # 1. Fetch shift (use row locking with_for_update on PostgreSQL)
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        shift = db.query(Shift).filter(Shift.id == shift_id).with_for_update().first()
    else:
        shift = db.query(Shift).filter(Shift.id == shift_id).first()

    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found.")

    # 2. Check existing registration
    existing_reg = (
        db.query(Registration)
        .filter(
            Registration.shift_id == shift_id,
            Registration.volunteer_id == volunteer_id,
        )
        .first()
    )

    if existing_reg:
        if existing_reg.status == "confirmed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are already confirmed for this shift.",
            )
        elif existing_reg.status == "waitlisted":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You are already on the waitlist for this shift (Position #{existing_reg.waitlist_position}).",
            )

    # 3. Check volunteer availability
    avail_check = check_volunteer_availability(volunteer_id, shift, db)
    if not avail_check["is_available"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=avail_check["message"],
        )

    # 4. Check scheduling conflicts
    conflict_check = detect_conflict(volunteer_id, shift, db, exclude_shift_id=shift_id)
    if conflict_check["has_conflict"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=conflict_check["message"],
        )

    # 5. Check capacity
    confirmed_count = (
        db.query(func.count(Registration.id))
        .filter(
            Registration.shift_id == shift_id,
            Registration.status == "confirmed",
        )
        .scalar()
        or 0
    )

    if confirmed_count < shift.required_volunteers:
        reg_status = "confirmed"
        waitlist_position = None
        message = f"Registration confirmed! You have reserved slot #{confirmed_count + 1} of {shift.required_volunteers}."
    else:
        reg_status = "waitlisted"
        max_pos = (
            db.query(func.max(Registration.waitlist_position))
            .filter(
                Registration.shift_id == shift_id,
                Registration.status == "waitlisted",
            )
            .scalar()
            or 0
        )
        waitlist_position = max_pos + 1
        message = (
            f"Shift is at full capacity ({shift.required_volunteers}/{shift.required_volunteers}). "
            f"You have been added to the waitlist at position #{waitlist_position}."
        )

    # 6. Save or update registration record
    now = datetime.now(timezone.utc)
    if existing_reg:
        # Re-activating a previously cancelled registration
        existing_reg.status = reg_status
        existing_reg.waitlist_position = waitlist_position
        existing_reg.cancellation_reason = None
        existing_reg.registered_at = now
        existing_reg.updated_at = now
        reg = existing_reg
    else:
        reg = Registration(
            shift_id=shift_id,
            volunteer_id=volunteer_id,
            status=reg_status,
            waitlist_position=waitlist_position,
            registered_at=now,
            updated_at=now,
        )
        db.add(reg)

    db.commit()
    db.refresh(reg)

    return {
        "registration": reg,
        "status": reg_status,
        "waitlist_position": waitlist_position,
        "message": message,
    }


# ── 5. Cancellation & Waitlist Promotion ─────────────────────────────────────

def cancel_registration(
    registration_id: str,
    user: User,
    cancellation_reason: Optional[str],
    db: Session,
) -> dict:
    """
    Cancel an existing registration.
      • Only the registered volunteer or an admin can cancel.
      • Marks status as 'cancelled'.
      • If cancelled registration was confirmed, automatically promotes the next
        eligible waitlisted volunteer in FIFO order.
      • Re-checks availability & conflicts before promotion; skips ineligible candidates.
      • Re-sequences remaining waitlist positions.
    """
    reg = db.query(Registration).filter(Registration.id == registration_id).first()
    if not reg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registration not found.",
        )

    # Verify authorization
    if user.role != "admin" and reg.volunteer_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to cancel this registration.",
        )

    if reg.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This registration is already cancelled.",
        )

    was_confirmed = (reg.status == "confirmed")
    shift_id = reg.shift_id
    old_position = reg.waitlist_position

    reg.status = "cancelled"
    reg.waitlist_position = None
    reg.cancellation_reason = cancellation_reason or "Cancelled by user"
    reg.updated_at = datetime.now(timezone.utc)
    db.commit()

    promoted_volunteer = None

    if was_confirmed:
        # A confirmed spot opened up -> promote next eligible waitlisted candidate
        promoted_volunteer = promote_from_waitlist(shift_id, db)
    elif old_position is not None:
        # A waitlisted volunteer cancelled -> re-sequence remaining waitlist
        _resequence_waitlist(shift_id, db)

    db.refresh(reg)
    return {
        "registration": reg,
        "promoted_registration": promoted_volunteer,
        "message": "Registration cancelled successfully.",
    }


def promote_from_waitlist(shift_id: str, db: Session) -> Optional[Registration]:
    """
    Finds the next eligible waitlisted volunteer in FIFO order:
      1. Checks current capacity (ensure slot is genuinely open).
      2. Validates availability & conflicts at promotion time.
      3. If a waitlisted volunteer now has a conflict, skips them and tries the next.
      4. Promotes first eligible candidate to 'confirmed' and re-indexes remaining waitlist.
    """
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        return None

    confirmed_count = (
        db.query(func.count(Registration.id))
        .filter(
            Registration.shift_id == shift_id,
            Registration.status == "confirmed",
        )
        .scalar()
        or 0
    )

    if confirmed_count >= shift.required_volunteers:
        return None

    waitlist_candidates = (
        db.query(Registration)
        .filter(
            Registration.shift_id == shift_id,
            Registration.status == "waitlisted",
        )
        .order_by(
            Registration.waitlist_position.asc(),
            Registration.registered_at.asc(),
        )
        .all()
    )

    promoted: Optional[Registration] = None

    for candidate in waitlist_candidates:
        # Verify availability
        avail = check_volunteer_availability(candidate.volunteer_id, shift, db)
        if not avail["is_available"]:
            continue

        # Verify no scheduling conflicts have developed
        conflict = detect_conflict(
            candidate.volunteer_id, shift, db, exclude_shift_id=shift_id
        )
        if conflict["has_conflict"]:
            continue

        # Eligible candidate found: promote to confirmed
        candidate.status = "confirmed"
        candidate.waitlist_position = None
        candidate.updated_at = datetime.now(timezone.utc)
        promoted = candidate
        break

    if promoted:
        db.flush()

    # Re-sequence remaining waitlist
    _resequence_waitlist(shift_id, db)
    db.commit()

    if promoted:
        db.refresh(promoted)
    return promoted


def _resequence_waitlist(shift_id: str, db: Session) -> None:
    """Ensure waitlist positions are contiguous (1, 2, 3...) after promotions/cancellations."""
    remaining = (
        db.query(Registration)
        .filter(
            Registration.shift_id == shift_id,
            Registration.status == "waitlisted",
        )
        .order_by(
            Registration.waitlist_position.asc(),
            Registration.registered_at.asc(),
        )
        .all()
    )

    for idx, item in enumerate(remaining, start=1):
        item.waitlist_position = idx

    db.commit()
    db.expire_all()
