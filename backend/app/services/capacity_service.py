"""
Capacity management service.

Remaining slots are ALWAYS computed live from CONFIRMED registrations; there is
no denormalised counter that could drift. `Shift.status` (open/full) is kept in
sync by `sync_shift_status`, which every write path calls while it still holds
the shift's row lock.

Autoflush is disabled on this project's sessions, so counts flush first.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.registration import Registration, RegistrationStatus
from app.models.shift import Shift, ShiftStatus


def confirmed_count(db: Session, shift_id: str) -> int:
    db.flush()
    return (
        db.scalar(
            select(func.count())
            .select_from(Registration)
            .where(
                Registration.shift_id == shift_id,
                Registration.status == RegistrationStatus.CONFIRMED,
            )
        )
        or 0
    )


def remaining_slots(db: Session, shift: Shift) -> int:
    return max(shift.capacity - confirmed_count(db, shift.id), 0)


def sync_shift_status(db: Session, shift: Shift) -> str:
    """Flip the shift between 'open' and 'full' to match live confirmed count."""
    if shift.status == ShiftStatus.CANCELLED:
        return shift.status
    desired = (
        ShiftStatus.FULL
        if confirmed_count(db, shift.id) >= shift.capacity
        else ShiftStatus.OPEN
    )
    if shift.status != desired:
        shift.status = desired
        db.flush()
    return shift.status
