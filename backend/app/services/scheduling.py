"""
services/scheduling.py
───────────────────────
Module 3: Smart Shift Scheduling Engine

Core logic: conflict detection, capacity management, waitlist.

TODO (Member 2): Implement these functions and wire them into routers/registrations.py
"""

from datetime import datetime


def check_time_overlap(start_a: datetime, end_a: datetime,
                       start_b: datetime, end_b: datetime) -> bool:
    """
    Returns True if two time intervals overlap.
    Uses the standard interval overlap formula:
        (StartA < EndB) AND (EndA > StartB)

    Example:
        Shift A: 09:00 – 12:00
        Shift B: 11:00 – 14:00
        → Overlap: True  (reject Shift B registration)

        Shift A: 09:00 – 12:00
        Shift B: 12:00 – 15:00
        → Overlap: False (adjacent shifts are allowed)
    """
    return start_a < end_b and end_a > start_b


def detect_conflict(volunteer_id: str, target_shift, db) -> dict:
    """
    Check whether registering volunteer_id for target_shift creates a time conflict.

    Args:
        volunteer_id: UUID string of the volunteer
        target_shift: Shift ORM object
        db:           SQLAlchemy session

    Returns:
        {
          "has_conflict": bool,
          "conflicting_shift": Shift | None,
          "message": str
        }

    TODO: Import Registration and Shift models and implement the query.
    """
    raise NotImplementedError(
        "detect_conflict() is pending implementation in Module 3 (Scheduling Engine). "
        "See routers/registrations.py for the planned API surface."
    )


def register_volunteer_for_shift(volunteer_id: str, shift_id: str, db) -> dict:
    """
    Full registration pipeline:
      1. Check for time conflicts  → reject if found
      2. Check shift capacity      → confirm or waitlist
      3. Create Registration row
      4. Trigger reminder generation (calls notifications.py)

    Returns:
        { "status": "confirmed" | "waitlisted" | "rejected", "message": str }

    TODO: Implement in Module 3.
    """
    raise NotImplementedError("Pending Module 3 implementation.")


def promote_from_waitlist(shift_id: str, db) -> list:
    """
    Called when a registration is cancelled.
    Finds the next volunteer on the waitlist and promotes them to CONFIRMED.

    Returns list of promoted Registration IDs.
    TODO: Implement in Module 3.
    """
    raise NotImplementedError("Pending Module 3 implementation.")
