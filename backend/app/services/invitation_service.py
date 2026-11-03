"""
Module 4 – shortlist & invitation workflow.

An invitation is NOT a registration. Accepting one delegates to Module 3's
`registration_service.register`, which re-validates shift bookability, existing
registrations, scheduling conflicts, availability and capacity under row locks.
If that fails the invitation stays PENDING and the Module 3 error is returned
(SHIFT_FULL, SCHEDULE_CONFLICT, OUTSIDE_AVAILABILITY, ...). Accepting never
bypasses the waitlist: a full shift is rejected, not auto-waitlisted.

Lifecycle: PENDING -> ACCEPTED | DECLINED | EXPIRED | CANCELLED (all terminal).
Expiry is applied lazily (before every list/accept/decline/invite) when
`expires_at` has passed or the shift has started; invitations of a cancelled
shift become CANCELLED.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import clock
from app.models.event import Event
from app.models.matching import InvitationStatus, VolunteerInvitation, VolunteerShortlist
from app.models.shift import Shift, ShiftStatus
from app.models.user import User
from app.services import capacity_service, registration_service, scheduling_service
from app.services import recommendation_service as rec
from app.services.common import utcnow
from app.services.errors import ConflictError, NotFoundError, ShiftFullError, ValidationFailed
from app.services.transactions import run_in_transaction


# ── Presenters ────────────────────────────────────────────────────────────────
def _to_dict(inv: VolunteerInvitation, shift: Shift, event: Event, volunteer_name: str | None) -> dict:
    return {
        "id": inv.id,
        "shift_id": inv.shift_id,
        "volunteer_id": inv.volunteer_id,
        "volunteer_name": volunteer_name,
        "status": inv.status,
        "match_score": inv.match_score,
        "message": inv.message,
        "expires_at": inv.expires_at,
        "responded_at": inv.responded_at,
        "registration_id": inv.registration_id,
        "created_at": inv.created_at,
        "shift": {
            "shift_id": shift.id,
            "event_id": event.id,
            "event_name": event.name,
            "event_location": event.location,
            "title": shift.title,
            "shift_date": shift.shift_date,
            "start_time": shift.start_time,
            "end_time": shift.end_time,
        },
    }


def _out(db: Session, invitation_id: str) -> dict:
    inv = db.execute(
        select(VolunteerInvitation).where(VolunteerInvitation.id == invitation_id)
        .execution_options(populate_existing=True)
    ).scalar_one()
    shift = db.get(Shift, inv.shift_id)
    volunteer = db.get(User, inv.volunteer_id)
    return _to_dict(inv, shift, shift.event, volunteer.full_name if volunteer else None)


def _reject(volunteer_id: str, code: str, message: str) -> dict:
    return {"volunteer_id": volunteer_id, "code": code, "message": message}


def _not_eligible(result) -> dict:
    return _reject(
        result.volunteer_id,
        "NOT_ELIGIBLE",
        " ".join(e.message for e in result.exclusions),
    )


# ── Expiry ────────────────────────────────────────────────────────────────────
def expire_due_invitations(db: Session) -> int:
    """Mark overdue PENDING invitations EXPIRED (CANCELLED if their shift was cancelled)."""

    def operation() -> int:
        now_utc, local = utcnow(), clock.now()
        rows = db.execute(
            select(VolunteerInvitation, Shift)
            .join(Shift, Shift.id == VolunteerInvitation.shift_id)
            .where(VolunteerInvitation.status == InvitationStatus.PENDING)
            .with_for_update(of=VolunteerInvitation, skip_locked=True)
        ).all()
        changed = 0
        for inv, shift in rows:
            if shift.status == ShiftStatus.CANCELLED:
                inv.status = InvitationStatus.CANCELLED
            elif inv.expires_at <= now_utc or scheduling_service.shift_start_at(shift) <= local:
                inv.status = InvitationStatus.EXPIRED
            else:
                continue
            inv.responded_at = now_utc
            changed += 1
        db.flush()
        return changed

    return run_in_transaction(db, operation)


# ── Shortlist ─────────────────────────────────────────────────────────────────
def shortlist(db: Session, admin: User, shift_id: str, volunteer_ids: list[str], note: str | None) -> dict:
    admin_id = admin.id
    shift = rec.get_owned_shift(db, admin, shift_id)
    scheduling_service.ensure_shift_bookable(shift)

    ids = list(dict.fromkeys(volunteer_ids))
    _, results = rec.evaluate_shift(db, shift, volunteer_ids=ids)
    by_id = {r.volunteer_id: r for r in results}
    existing = set(
        db.scalars(
            select(VolunteerShortlist.volunteer_id).where(
                VolunteerShortlist.shift_id == shift.id, VolunteerShortlist.volunteer_id.in_(ids)
            )
        )
    )

    rejected, to_add = [], []
    for vid in ids:
        r = by_id.get(vid)
        if r is None:
            rejected.append(_reject(vid, "VOLUNTEER_NOT_FOUND", "No volunteer account with this id."))
        elif vid in existing:
            rejected.append(_reject(vid, "ALREADY_SHORTLISTED", "Volunteer is already shortlisted for this shift."))
        elif not r.eligible:
            rejected.append(_not_eligible(r))
        else:
            to_add.append(r)

    def operation() -> list[VolunteerShortlist]:
        rows = [
            VolunteerShortlist(
                shift_id=shift.id,
                volunteer_id=r.volunteer_id,
                shortlisted_by=admin_id,
                match_score=r.total_score,
                note=note,
            )
            for r in to_add
        ]
        db.add_all(rows)
        db.flush()
        return rows

    try:
        rows = run_in_transaction(db, operation)
    except IntegrityError:
        raise ConflictError("A volunteer was shortlisted concurrently. Retry.", code="ALREADY_SHORTLISTED")

    names = {r.volunteer_id: r.full_name for r in to_add}
    return {
        "added": [
            {
                "volunteer_id": row.volunteer_id,
                "volunteer_name": names.get(row.volunteer_id),
                "match_score": row.match_score,
                "note": row.note,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "rejected": rejected,
    }


def list_shortlist(db: Session, admin: User, shift_id: str) -> list[dict]:
    shift = rec.get_owned_shift(db, admin, shift_id)
    rows = db.execute(
        select(VolunteerShortlist, User)
        .join(User, User.id == VolunteerShortlist.volunteer_id)
        .where(VolunteerShortlist.shift_id == shift.id)
        .order_by(VolunteerShortlist.match_score.desc(), User.full_name)
    ).all()
    return [
        {
            "volunteer_id": s.volunteer_id,
            "volunteer_name": u.full_name,
            "match_score": s.match_score,
            "note": s.note,
            "created_at": s.created_at,
        }
        for s, u in rows
    ]


# ── Invitations (NGO) ─────────────────────────────────────────────────────────
def invite(
    db: Session,
    admin: User,
    shift_id: str,
    volunteer_ids: list[str] | None,
    message: str | None,
    expires_in_hours: int,
) -> dict:
    admin_id = admin.id
    shift = rec.get_owned_shift(db, admin, shift_id)
    scheduling_service.ensure_shift_bookable(shift)
    expire_due_invitations(db)

    if capacity_service.remaining_slots(db, shift) <= 0:
        raise ShiftFullError("This shift is full, so new invitations cannot be sent.")

    if not volunteer_ids:
        volunteer_ids = list(
            db.scalars(select(VolunteerShortlist.volunteer_id).where(VolunteerShortlist.shift_id == shift.id))
        )
    ids = list(dict.fromkeys(volunteer_ids))
    if not ids:
        raise ValidationFailed("No volunteers supplied and the shortlist for this shift is empty.")

    _, results = rec.evaluate_shift(db, shift, volunteer_ids=ids)
    by_id = {r.volunteer_id: r for r in results}
    pending = set(
        db.scalars(
            select(VolunteerInvitation.volunteer_id).where(
                VolunteerInvitation.shift_id == shift.id,
                VolunteerInvitation.status == InvitationStatus.PENDING,
                VolunteerInvitation.volunteer_id.in_(ids),
            )
        )
    )

    rejected, to_create = [], []
    for vid in ids:
        r = by_id.get(vid)
        if r is None:
            rejected.append(_reject(vid, "VOLUNTEER_NOT_FOUND", "No volunteer account with this id."))
        elif vid in pending:
            rejected.append(_reject(vid, "DUPLICATE_INVITATION", "A pending invitation already exists for this volunteer."))
        elif not r.eligible:
            rejected.append(_not_eligible(r))
        else:
            to_create.append(r)

    expires_at = utcnow() + timedelta(hours=expires_in_hours)

    def operation() -> list[VolunteerInvitation]:
        rows = [
            VolunteerInvitation(
                shift_id=shift.id,
                volunteer_id=r.volunteer_id,
                invited_by=admin_id,
                status=InvitationStatus.PENDING,
                message=message,
                match_score=r.total_score,
                expires_at=expires_at,
            )
            for r in to_create
        ]
        db.add_all(rows)
        db.flush()
        return rows

    try:
        rows = run_in_transaction(db, operation)
    except IntegrityError:
        raise ConflictError("A pending invitation was created concurrently. Retry.", code="DUPLICATE_INVITATION")

    return {"invitations": [_out(db, row.id) for row in rows], "rejected": rejected}


def cancel(db: Session, admin: User, invitation_id: str) -> dict:
    inv = db.get(VolunteerInvitation, invitation_id)
    if inv is None:
        raise NotFoundError("Invitation not found.")
    rec.get_owned_shift(db, admin, inv.shift_id)  # ownership
    expire_due_invitations(db)

    def operation() -> None:
        row = db.execute(
            select(VolunteerInvitation)
            .where(VolunteerInvitation.id == invitation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one()
        if row.status != InvitationStatus.PENDING:
            raise ConflictError(
                f"Only pending invitations can be cancelled (this one is {row.status.lower()}).",
                code=f"INVITATION_{row.status}",
            )
        row.status = InvitationStatus.CANCELLED
        row.responded_at = utcnow()
        db.flush()

    run_in_transaction(db, operation)
    return _out(db, invitation_id)


# ── Invitations (volunteer) ───────────────────────────────────────────────────
def accept(db: Session, volunteer: User, invitation_id: str) -> dict:
    vid = volunteer.id
    expire_due_invitations(db)

    inv = db.get(VolunteerInvitation, invitation_id)
    if inv is None or inv.volunteer_id != vid:
        raise NotFoundError("Invitation not found.")
    if inv.status != InvitationStatus.PENDING:
        raise ConflictError(
            f"This invitation is {inv.status.lower()} and can no longer be accepted.",
            code=f"INVITATION_{inv.status}",
        )
    shift_id = inv.shift_id
    db.rollback()  # end the read transaction; Module 3 starts its own locked one

    def claim(session: Session, new_registration) -> None:
        # Runs INSIDE Module 3's registration transaction (after its validation, before commit):
        # the invitation flips to ACCEPTED atomically with the registration. If it was cancelled /
        # expired / answered meanwhile, this raises and the registration is rolled back too.
        row = session.execute(
            select(VolunteerInvitation)
            .where(VolunteerInvitation.id == invitation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one()
        if row.status != InvitationStatus.PENDING:
            raise ConflictError(
                f"This invitation is {row.status.lower()} and can no longer be accepted.",
                code=f"INVITATION_{row.status}",
            )
        row.status = InvitationStatus.ACCEPTED
        row.responded_at = utcnow()
        row.registration_id = new_registration.id
        session.flush()

    # Module 3 revalidates availability, conflicts, capacity and existing registrations.
    # Any failure propagates and leaves the invitation PENDING.
    registration = registration_service.register(db, vid, shift_id, on_confirm=claim)
    return {"invitation": _out(db, invitation_id), "registration": registration}


def decline(db: Session, volunteer: User, invitation_id: str) -> dict:
    vid = volunteer.id
    expire_due_invitations(db)

    def operation() -> None:
        row = db.execute(
            select(VolunteerInvitation)
            .where(VolunteerInvitation.id == invitation_id, VolunteerInvitation.volunteer_id == vid)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Invitation not found.")
        if row.status != InvitationStatus.PENDING:
            raise ConflictError(
                f"This invitation is {row.status.lower()} and can no longer be declined.",
                code=f"INVITATION_{row.status}",
            )
        row.status = InvitationStatus.DECLINED
        row.responded_at = utcnow()
        db.flush()

    run_in_transaction(db, operation)
    return {"invitation": _out(db, invitation_id), "registration": None}


# ── Listing (role-aware) ──────────────────────────────────────────────────────
def list_invitations(
    db: Session, user: User, *, status: str | None = None, shift_id: str | None = None, limit: int = 100
) -> list[dict]:
    expire_due_invitations(db)
    stmt = (
        select(VolunteerInvitation, Shift, Event, User)
        .join(Shift, Shift.id == VolunteerInvitation.shift_id)
        .join(Event, Event.id == Shift.event_id)
        .join(User, User.id == VolunteerInvitation.volunteer_id)
    )
    if user.role == "admin":
        stmt = stmt.where(rec.owned_events_clause(db, user))
    else:
        stmt = stmt.where(VolunteerInvitation.volunteer_id == user.id)
    if status:
        if status.upper() not in InvitationStatus.ALL:
            raise ValidationFailed(f"status must be one of {', '.join(InvitationStatus.ALL)}.")
        stmt = stmt.where(VolunteerInvitation.status == status.upper())
    if shift_id:
        stmt = stmt.where(VolunteerInvitation.shift_id == shift_id)
    stmt = stmt.order_by(VolunteerInvitation.created_at.desc()).limit(limit)
    return [_to_dict(inv, shift, event, vol.full_name) for inv, shift, event, vol in db.execute(stmt).all()]
