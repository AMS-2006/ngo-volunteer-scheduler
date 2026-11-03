"""
Row-level locks used to make registrations concurrency-safe.

LOCK ORDER (always the same, to avoid deadlocks):
    1. the shift row          -> serialises capacity decisions for that shift
    2. the volunteer's user row -> serialises conflict decisions for that volunteer

Why the second lock? Locking only the shift stops overbooking, but two
simultaneous requests from the SAME volunteer for two DIFFERENT overlapping
shifts would each pass the conflict check. Locking the volunteer row makes the
"check conflicts -> insert" sequence atomic per volunteer.

The volunteer lock is `FOR NO KEY UPDATE`, which does not block the
`FOR KEY SHARE` lock PostgreSQL takes for foreign-key inserts.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.shift import Shift
from app.models.user import User
from app.services.errors import NotFoundError


def lock_shift(db: Session, shift_id: str) -> Shift:
    """SELECT ... FOR UPDATE the shift row and return a freshly loaded instance."""
    shift = db.execute(
        select(Shift)
        .where(Shift.id == shift_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if shift is None:
        raise NotFoundError("Shift not found.")
    return shift


def lock_volunteer(db: Session, volunteer_id: str) -> None:
    """SELECT ... FOR NO KEY UPDATE the volunteer's user row."""
    db.execute(
        select(User.id).where(User.id == volunteer_id).with_for_update(key_share=True)
    ).first()
