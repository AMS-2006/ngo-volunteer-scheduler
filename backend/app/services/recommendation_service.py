"""
Module 4 – recommendation engine (DB layer).

Gathers facts and feeds the pure scorers in `match_scoring`. It REUSES Module 3:
  • availability   -> availability_service.ensure_covered (full-shift coverage)
  • conflicts      -> scheduling_service.find_conflict (CONFIRMED overlaps only)
  • bookability    -> scheduling_service.ensure_shift_bookable / is_bookable
  • capacity       -> capacity_service.remaining_slots
It never creates registrations; recommendations are read-only.

Shift dates/times are naive local wall-clock values in both the shifts and the
availability tables, so availability matching compares like with like.
"""

from collections import defaultdict
from datetime import timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core import clock
from app.models.event import Event, EventStatus
from app.models.matching import (
    EventMatchingProfile,
    ShiftRequirement,
    VolunteerInvitation,
    VolunteerShortlist,
)
from app.models.ngo import NGO
from app.models.registration import Registration, RegistrationStatus
from app.models.shift import Shift, ShiftStatus
from app.models.user import User
from app.models.volunteer import VolunteerProfile
from app.services import availability_service, capacity_service, scheduling_service
from app.services import match_scoring as ms
from app.services.common import hhmm, pretty_date
from app.services.errors import ForbiddenError, NotFoundError, SchedulingError
from app.services.transactions import run_in_transaction

WORKLOAD_WINDOW_DAYS = 30
MAX_PERSONAL_SHIFTS = 200


# ── Ownership ─────────────────────────────────────────────────────────────────
def _admin_ngo_id(db: Session, admin: User) -> str | None:
    return db.scalar(select(NGO.id).where(NGO.admin_user_id == admin.id))


def owned_events_clause(db: Session, admin: User):
    """SQL condition: events that belong to this admin (created by them or owned by their NGO)."""
    cond = Event.created_by == admin.id
    ngo_id = _admin_ngo_id(db, admin)
    return or_(cond, Event.ngo_id == ngo_id) if ngo_id else cond


def admin_owns_event(db: Session, admin: User, event: Event) -> bool:
    if event.created_by == admin.id:
        return True
    ngo_id = _admin_ngo_id(db, admin)
    return bool(ngo_id and event.ngo_id == ngo_id)


def get_owned_event(db: Session, admin: User, event_id: str) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise NotFoundError("Event not found.")
    if not admin_owns_event(db, admin, event):
        raise ForbiddenError("You can only manage matching for your own NGO's events.")
    return event


def get_owned_shift(db: Session, admin: User, shift_id: str) -> Shift:
    shift = db.get(Shift, shift_id)
    if shift is None:
        raise NotFoundError("Shift not found.")
    if not admin_owns_event(db, admin, shift.event):
        raise ForbiddenError("You can only manage matching for your own NGO's events.")
    return shift


# ── Requirements (NGO configures what a shift needs) ──────────────────────────
def _clean(values) -> list[str]:
    return list(ms.term_map(values).values())


def set_requirements(db: Session, admin: User, shift_id: str, data: dict) -> ShiftRequirement:
    get_owned_shift(db, admin, shift_id)

    def operation() -> ShiftRequirement:
        row = db.get(ShiftRequirement, shift_id)
        if row is None:
            row = ShiftRequirement(shift_id=shift_id)
            db.add(row)
        row.required_skills = _clean(data.get("required_skills"))
        row.optional_skills = _clean(data.get("optional_skills"))
        row.interest_tags = _clean(data.get("interest_tags"))
        row.skills_mandatory = bool(data.get("skills_mandatory", True))
        city = (data.get("required_city") or "").strip()
        row.required_city = city or None
        db.flush()
        return row

    row = run_in_transaction(db, operation)
    db.refresh(row)
    return row


def get_requirements(db: Session, admin: User, shift_id: str) -> ShiftRequirement | None:
    get_owned_shift(db, admin, shift_id)
    return db.get(ShiftRequirement, shift_id)


def set_event_categories(db: Session, admin: User, event_id: str, categories) -> EventMatchingProfile:
    get_owned_event(db, admin, event_id)

    def operation() -> EventMatchingProfile:
        row = db.get(EventMatchingProfile, event_id)
        if row is None:
            row = EventMatchingProfile(event_id=event_id)
            db.add(row)
        row.categories = _clean(categories)
        db.flush()
        return row

    row = run_in_transaction(db, operation)
    db.refresh(row)
    return row


def load_needs(db: Session, shift: Shift, event: Event) -> ms.ShiftNeeds:
    req = db.get(ShiftRequirement, shift.id)
    profile = db.get(EventMatchingProfile, event.id)
    categories = _clean([*(profile.categories if profile else []), *(req.interest_tags if req else [])])
    if req is None:
        return ms.ShiftNeeds(categories=tuple(categories))
    return ms.ShiftNeeds(
        required_skills=tuple(req.required_skills or ()),
        optional_skills=tuple(req.optional_skills or ()),
        categories=tuple(categories),
        skills_mandatory=bool(req.skills_mandatory),
        required_city=req.required_city,
    )


# ── Fact gathering ────────────────────────────────────────────────────────────
def _availability(db: Session, volunteer_id: str, shift: Shift) -> ms.AvailabilityResult:
    try:
        availability_service.ensure_covered(
            db, volunteer_id, shift.shift_date, shift.start_time, shift.end_time
        )
    except SchedulingError as exc:
        return ms.AvailabilityResult(False, exc.code, exc.message.replace("Registration rejected: ", ""))
    return ms.AvailabilityResult(True)


def _conflict(db: Session, volunteer_id: str, shift: Shift) -> str | None:
    found = scheduling_service.find_conflict(db, volunteer_id, shift)
    if found is None:
        return None
    _, other_shift, other_event = found
    return (
        f"Already confirmed {hhmm(other_shift.start_time)}-{hhmm(other_shift.end_time)} on "
        f"{pretty_date(other_shift.shift_date)} ({other_event.name} - {other_shift.title})."
    )


class HistoryIndex:
    """Completed participation = CONFIRMED registrations on non-cancelled shifts that already ended."""

    def __init__(self, db: Session, volunteer_ids):
        self._rows: dict[str, list] = defaultdict(list)
        self._cats: dict[str, set] = {}
        ids = list(volunteer_ids)
        if not ids:
            return
        now = clock.now()
        rows = db.execute(
            select(Registration.volunteer_id, Event.id, Event.created_by, Event.ngo_id)
            .select_from(Registration)
            .join(Shift, Shift.id == Registration.shift_id)
            .join(Event, Event.id == Shift.event_id)
            .where(
                Registration.volunteer_id.in_(ids),
                Registration.status == RegistrationStatus.CONFIRMED,
                Shift.status != ShiftStatus.CANCELLED,
                Event.status != EventStatus.CANCELLED,
                or_(
                    Shift.shift_date < now.date(),
                    and_(Shift.shift_date == now.date(), Shift.end_time <= now.time()),
                ),
            )
        ).all()
        for vid, event_id, created_by, ngo_id in rows:
            self._rows[vid].append((event_id, created_by, ngo_id))
        event_ids = {r[1] for r in rows}
        if event_ids:
            self._cats = {
                p.event_id: set(ms.normalize_terms(p.categories))
                for p in db.scalars(
                    select(EventMatchingProfile).where(EventMatchingProfile.event_id.in_(event_ids))
                )
            }

    def facts(self, volunteer_id: str, event: Event, targets, months: int) -> ms.ExperienceFacts:
        wanted = set(ms.normalize_terms(targets))
        rows = self._rows.get(volunteer_id, [])
        relevant = 0
        for event_id, created_by, ngo_id in rows:
            past = self._cats.get(event_id)
            if wanted and past:
                hit = bool(wanted & past)
            else:  # no category data on one side -> fall back to "same organisation"
                hit = bool(
                    (event.created_by and created_by == event.created_by)
                    or (event.ngo_id and ngo_id == event.ngo_id)
                )
            relevant += hit
        return ms.ExperienceFacts(len(rows), relevant, months or 0)


def _recent_load(db: Session, volunteer_ids) -> dict[str, int]:
    ids = list(volunteer_ids)
    if not ids:
        return {}
    today = clock.now().date()
    span = timedelta(days=WORKLOAD_WINDOW_DAYS)
    rows = db.execute(
        select(Registration.volunteer_id, func.count())
        .select_from(Registration)
        .join(Shift, Shift.id == Registration.shift_id)
        .where(
            Registration.volunteer_id.in_(ids),
            Registration.status == RegistrationStatus.CONFIRMED,
            Shift.status != ShiftStatus.CANCELLED,
            Shift.shift_date.between(today - span, today + span),
        )
        .group_by(Registration.volunteer_id)
    ).all()
    return {vid: n for vid, n in rows}


def _active_map(db: Session, *, shift_id: str | None = None, volunteer_id: str | None = None) -> dict:
    stmt = select(Registration.shift_id, Registration.volunteer_id, Registration.status).where(
        Registration.status.in_(RegistrationStatus.ACTIVE)
    )
    if shift_id:
        stmt = stmt.where(Registration.shift_id == shift_id)
    if volunteer_id:
        stmt = stmt.where(Registration.volunteer_id == volunteer_id)
    return {(s, v): st for s, v, st in db.execute(stmt).all()}


def _evaluate_rows(db, shift, event, needs, rows, active, history, load) -> list[ms.MatchResult]:
    results = []
    for user, profile in rows:
        vol = ms.VolunteerFacts(
            volunteer_id=user.id,
            full_name=user.full_name,
            is_active=bool(user.is_active),
            has_profile=profile is not None,
            skills=tuple(profile.skills or ()) if profile else (),
            interests=tuple(profile.interests or ()) if profile else (),
            city=profile.city if profile else None,
            experience_months=(profile.experience_months or 0) if profile else 0,
        )
        results.append(
            ms.evaluate_match(
                needs,
                vol,
                _availability(db, user.id, shift),
                _conflict(db, user.id, shift),
                active.get((shift.id, user.id)),
                history.facts(user.id, event, needs.categories, vol.experience_months),
                load.get(user.id, 0),
            )
        )
    return results


def evaluate_shift(db: Session, shift: Shift, volunteer_ids=None) -> tuple[ms.ShiftNeeds, list[ms.MatchResult]]:
    """Score every volunteer (or just `volunteer_ids`) against one shift."""
    event = shift.event
    needs = load_needs(db, shift, event)
    stmt = (
        select(User, VolunteerProfile)
        .outerjoin(VolunteerProfile, VolunteerProfile.user_id == User.id)
        .where(User.role == "volunteer")
    )
    if volunteer_ids is not None:
        stmt = stmt.where(User.id.in_(list(volunteer_ids)))
    rows = db.execute(stmt.order_by(User.full_name, User.id)).all()
    ids = [u.id for u, _ in rows]
    results = _evaluate_rows(
        db, shift, event, needs, rows,
        _active_map(db, shift_id=shift.id), HistoryIndex(db, ids), _recent_load(db, ids),
    )
    return needs, results


# ── Presenters ────────────────────────────────────────────────────────────────
def _shift_brief(shift: Shift, event: Event, remaining: int) -> dict:
    return {
        "shift_id": shift.id,
        "event_id": event.id,
        "event_name": event.name,
        "event_location": event.location,
        "title": shift.title,
        "shift_date": shift.shift_date,
        "start_time": shift.start_time,
        "end_time": shift.end_time,
        "capacity": shift.capacity,
        "remaining_slots": remaining,
        "status": shift.status,
    }


def _needs_dict(needs: ms.ShiftNeeds) -> dict:
    return {
        "required_skills": _clean(needs.required_skills),
        "optional_skills": _clean(needs.optional_skills),
        "categories": _clean(needs.categories),
        "skills_mandatory": needs.skills_mandatory,
        "required_city": needs.required_city,
    }


def _invite_state(db: Session, shift_id: str) -> tuple[dict, set]:
    latest = {}
    for vid, status in db.execute(
        select(VolunteerInvitation.volunteer_id, VolunteerInvitation.status)
        .where(VolunteerInvitation.shift_id == shift_id)
        .order_by(VolunteerInvitation.created_at)
    ).all():
        latest[vid] = status
    short = set(db.scalars(select(VolunteerShortlist.volunteer_id).where(VolunteerShortlist.shift_id == shift_id)))
    return latest, short


def _shift_payload(db: Session, shift: Shift, *, limit: int, min_score: float, include_excluded: bool) -> dict:
    event = shift.event
    needs, results = evaluate_shift(db, shift)
    remaining = capacity_service.remaining_slots(db, shift)
    invites, shortlisted = _invite_state(db, shift.id)

    def out(r: ms.MatchResult) -> dict:
        d = ms.result_to_dict(r)
        d["invitation_status"] = invites.get(r.volunteer_id)
        d["shortlisted"] = r.volunteer_id in shortlisted
        return d

    eligible = ms.rank_results([r for r in results if r.eligible and r.total_score >= min_score])
    excluded = sorted(
        (r for r in results if not r.eligible), key=lambda r: (-r.total_score, r.full_name.casefold())
    )
    return {
        "shift": _shift_brief(shift, event, remaining),
        "needs": _needs_dict(needs),
        "skill_gap": ms.detect_skill_gap(remaining, results, needs),
        "recommendations": [out(r) for r in eligible[:limit]],
        "excluded": [out(r) for r in excluded[:limit]] if include_excluded else [],
        "disclaimer": ms.DISCLAIMER,
    }


# ── Public API ────────────────────────────────────────────────────────────────
def shift_recommendations(
    db: Session, admin: User, shift_id: str, *, limit: int = 50, min_score: float = 0, include_excluded: bool = True
) -> dict:
    shift = get_owned_shift(db, admin, shift_id)
    scheduling_service.ensure_shift_bookable(shift)
    return _shift_payload(db, shift, limit=limit, min_score=min_score, include_excluded=include_excluded)


def event_recommendations(
    db: Session, admin: User, event_id: str, *, limit: int = 50, min_score: float = 0, include_excluded: bool = False
) -> dict:
    event = get_owned_event(db, admin, event_id)
    shifts = [
        s
        for s in db.scalars(
            select(Shift)
            .where(Shift.event_id == event.id, Shift.status != ShiftStatus.CANCELLED)
            .order_by(Shift.shift_date, Shift.start_time)
        )
        if scheduling_service.is_bookable(s)
    ]
    payloads = [
        _shift_payload(db, s, limit=limit, min_score=min_score, include_excluded=include_excluded)
        for s in shifts
    ]
    distinct = {m["volunteer_id"] for p in payloads for m in p["recommendations"]}
    return {
        "event_id": event.id,
        "event_name": event.name,
        "shifts": payloads,
        "distinct_eligible_volunteers": len(distinct),
        "total_slots_remaining": sum(p["skill_gap"]["slots_remaining"] for p in payloads),
        "total_gap": sum(p["skill_gap"]["gap"] for p in payloads),
        "disclaimer": ms.DISCLAIMER,
    }


def _volunteer_rows(db: Session, user: User):
    profile = db.scalar(select(VolunteerProfile).where(VolunteerProfile.user_id == user.id))
    return [(user, profile)]


def volunteer_recommendations(
    db: Session, user: User, *, limit: int = 20, min_score: float = 0, include_ineligible: bool = False
) -> dict:
    """Upcoming OPEN shifts ranked by compatibility for this volunteer (shifts they already joined are skipped)."""
    now = clock.now()
    shifts = db.execute(
        select(Shift, Event)
        .join(Event, Event.id == Shift.event_id)
        .where(
            Shift.status == ShiftStatus.OPEN,
            Event.status != EventStatus.CANCELLED,
            or_(
                Shift.shift_date > now.date(),
                and_(Shift.shift_date == now.date(), Shift.start_time > now.time()),
            ),
        )
        .order_by(Shift.shift_date, Shift.start_time)
        .limit(MAX_PERSONAL_SHIFTS)
    ).all()

    rows = _volunteer_rows(db, user)
    active = _active_map(db, volunteer_id=user.id)
    history = HistoryIndex(db, [user.id])
    load = _recent_load(db, [user.id])

    items = []
    for shift, event in shifts:
        if (shift.id, user.id) in active:
            continue
        needs = load_needs(db, shift, event)
        result = _evaluate_rows(db, shift, event, needs, rows, active, history, load)[0]
        if (not result.eligible and not include_ineligible) or result.total_score < min_score:
            continue
        remaining = capacity_service.remaining_slots(db, shift)
        items.append((result, _shift_brief(shift, event, remaining)))

    items.sort(key=lambda t: (-t[0].total_score, t[1]["shift_date"], t[1]["start_time"]))
    items = items[:limit]
    return {
        "recommendations": [{"shift": brief, "match": ms.result_to_dict(r)} for r, brief in items],
        "count": len(items),
        "disclaimer": ms.DISCLAIMER,
    }


def volunteer_shift_match(db: Session, user: User, shift_id: str) -> dict:
    """How well this volunteer fits ONE shift (ineligibility reasons included)."""
    shift = db.get(Shift, shift_id)
    if shift is None:
        raise NotFoundError("Shift not found.")
    scheduling_service.ensure_shift_bookable(shift)
    event = shift.event
    needs = load_needs(db, shift, event)
    result = _evaluate_rows(
        db, shift, event, needs, _volunteer_rows(db, user),
        _active_map(db, volunteer_id=user.id), HistoryIndex(db, [user.id]), _recent_load(db, [user.id]),
    )[0]
    remaining = capacity_service.remaining_slots(db, shift)
    return {"shift": _shift_brief(shift, event, remaining), "match": ms.result_to_dict(result)}
