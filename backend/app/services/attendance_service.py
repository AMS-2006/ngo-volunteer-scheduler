"""
services/attendance_service.py
───────────────────────────────
Module 7: Attendance Recording & Management Service

Handles:
  • Verification of shift authorization for NGO coordinators
  • Calculating credited volunteering hours from timestamps or scheduled duration
  • Recording and updating attendance for confirmed volunteers
  • Generating shift and event attendance summaries
  • NGO-level attendance analytics
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.attendance import Attendance, AttendanceStatus
from app.models.event import Event
from app.models.ngo import NGO
from app.models.registration import Registration
from app.models.shift import Shift
from app.models.user import User
from app.schemas.attendance import (
    AttendanceRecordCreate,
    AttendanceRecordOut,
    AttendanceRecordUpdate,
    EventAttendanceSummary,
    NGOAttendanceAnalytics,
    ShiftAttendanceSummary,
    ShiftRosterAttendanceOut,
    ShiftRosterVolunteerItem,
)


# ── 1. Authorization & Shift Verification ─────────────────────────────────────

def get_admin_ngo(admin: User, db: Session) -> NGO:
    """Fetch the NGO managed by this admin, or raise 404."""
    ngo = db.query(NGO).filter(NGO.admin_user_id == admin.id).first()
    if not ngo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NGO profile not found for this administrator account.",
        )
    return ngo


def ensure_coordinator_owns_shift(coordinator: User, shift: Shift, db: Session) -> NGO:
    """Ensure the calling coordinator/admin owns the NGO organizing this shift."""
    ngo = get_admin_ngo(coordinator, db)
    if shift.event.ngo_id != ngo.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are only authorized to manage attendance for your own NGO's events.",
        )
    return ngo


def ensure_coordinator_owns_event(coordinator: User, event: Event, db: Session) -> NGO:
    ngo = get_admin_ngo(coordinator, db)
    if event.ngo_id != ngo.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are only authorized to manage attendance for your own NGO's events.",
        )
    return ngo


# ── 2. Hour Calculation Logic ─────────────────────────────────────────────────

def calculate_hours_awarded(
    status_val: str,
    shift: Shift,
    check_in: Optional[datetime],
    check_out: Optional[datetime],
) -> float:
    """
    Calculate credited volunteering hours:
      • If status is 'absent': 0.0 hours.
      • If valid check_in and check_out are provided (check_out > check_in):
        calculate exact elapsed hours from timestamps.
      • If 'present' or 'late' without complete custom timestamps:
        award scheduled shift duration (end_time - start_time).
      • Guaranteed non-negative and rounded to 2 decimal places.
    """
    if status_val == AttendanceStatus.ABSENT:
        return 0.0

    if check_in and check_out and check_out > check_in:
        elapsed_seconds = (check_out - check_in).total_seconds()
        return round(max(0.0, elapsed_seconds / 3600.0), 2)

    # Fallback to scheduled shift duration for confirmed attendees
    if status_val in (AttendanceStatus.PRESENT, AttendanceStatus.LATE):
        duration_seconds = (shift.end_time - shift.start_time).total_seconds()
        return round(max(0.0, duration_seconds / 3600.0), 2)

    return 0.0


# ── 3. Presenters ─────────────────────────────────────────────────────────────

def _attendance_to_out(att: Attendance) -> AttendanceRecordOut:
    return AttendanceRecordOut(
        id=att.id,
        event_id=att.event_id,
        shift_id=att.shift_id,
        registration_id=att.registration_id,
        volunteer_id=att.volunteer_id,
        volunteer_name=att.volunteer.full_name if att.volunteer else None,
        volunteer_email=att.volunteer.email if att.volunteer else None,
        status=att.status,
        check_in_time=att.check_in_time,
        check_out_time=att.check_out_time,
        hours_awarded=att.hours_awarded,
        recorded_by=att.recorded_by,
        notes=att.notes,
        created_at=att.created_at,
        updated_at=att.updated_at,
    )


# ── 4. Recording & Updating Attendance ────────────────────────────────────────

def get_shift_roster_with_attendance(
    shift_id: str,
    coordinator: User,
    db: Session,
) -> ShiftRosterAttendanceOut:
    """View all registered volunteers for a shift and their marked attendance."""
    shift = (
        db.query(Shift)
        .options(selectinload(Shift.event))
        .filter(Shift.id == shift_id)
        .first()
    )
    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found.")

    ensure_coordinator_owns_shift(coordinator, shift, db)

    # Query confirmed registrations
    regs = (
        db.query(Registration)
        .options(selectinload(Registration.volunteer))
        .filter(
            Registration.shift_id == shift_id,
            Registration.status == "confirmed",
        )
        .all()
    )

    # Query existing attendance records for this shift
    att_map = {
        att.volunteer_id: att
        for att in db.query(Attendance)
        .options(selectinload(Attendance.volunteer))
        .filter(Attendance.shift_id == shift_id)
        .all()
    }

    volunteers: List[ShiftRosterVolunteerItem] = []
    for reg in regs:
        vol = reg.volunteer
        att = att_map.get(reg.volunteer_id)
        volunteers.append(
            ShiftRosterVolunteerItem(
                registration_id=reg.id,
                volunteer_id=reg.volunteer_id,
                volunteer_name=vol.full_name if vol else "Volunteer",
                volunteer_email=vol.email if vol else "",
                registration_status=reg.status,
                attendance=_attendance_to_out(att) if att else None,
            )
        )

    return ShiftRosterAttendanceOut(
        shift_id=shift.id,
        shift_name=shift.name,
        event_id=shift.event_id,
        event_title=shift.event.title,
        start_time=shift.start_time,
        end_time=shift.end_time,
        volunteers=volunteers,
    )


def record_shift_attendance_batch(
    shift_id: str,
    records: List[AttendanceRecordCreate],
    coordinator: User,
    db: Session,
) -> List[AttendanceRecordOut]:
    """
    Record or update attendance for one or more confirmed volunteers on a shift.
      • Only volunteers with confirmed registrations are eligible.
      • Automatically creates or updates attendance without duplicates.
      • Calculates awarded hours.
    """
    shift = (
        db.query(Shift)
        .options(selectinload(Shift.event))
        .filter(Shift.id == shift_id)
        .first()
    )
    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found.")

    ensure_coordinator_owns_shift(coordinator, shift, db)

    # Fetch confirmed registrations mapped by volunteer_id
    confirmed_regs = {
        r.volunteer_id: r
        for r in db.query(Registration)
        .filter(
            Registration.shift_id == shift_id,
            Registration.status == "confirmed",
        )
        .all()
    }

    # Fetch existing attendance records mapped by volunteer_id
    existing_att_map = {
        a.volunteer_id: a
        for a in db.query(Attendance)
        .filter(Attendance.shift_id == shift_id)
        .all()
    }

    now = datetime.now(timezone.utc)
    results: List[Attendance] = []

    for item in records:
        reg = confirmed_regs.get(item.volunteer_id)
        if not reg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Volunteer {item.volunteer_id} does not have a confirmed registration for this shift.",
            )

        hours = calculate_hours_awarded(
            status_val=item.status,
            shift=shift,
            check_in=item.check_in_time,
            check_out=item.check_out_time,
        )

        existing = existing_att_map.get(item.volunteer_id)
        if existing:
            # Update existing record
            existing.status = item.status
            existing.check_in_time = item.check_in_time
            existing.check_out_time = item.check_out_time
            existing.hours_awarded = hours
            existing.notes = item.notes
            existing.recorded_by = coordinator.id
            existing.updated_at = now
            results.append(existing)
        else:
            # Create new record
            att = Attendance(
                event_id=shift.event_id,
                shift_id=shift.id,
                registration_id=reg.id,
                volunteer_id=item.volunteer_id,
                status=item.status,
                check_in_time=item.check_in_time,
                check_out_time=item.check_out_time,
                hours_awarded=hours,
                recorded_by=coordinator.id,
                notes=item.notes,
                created_at=now,
                updated_at=now,
            )
            db.add(att)
            results.append(att)

    db.commit()

    # Re-fetch with volunteer relationship
    saved_ids = [r.id for r in results]
    refetched = (
        db.query(Attendance)
        .options(selectinload(Attendance.volunteer))
        .filter(Attendance.id.in_(saved_ids))
        .all()
    )
    return [_attendance_to_out(a) for a in refetched]


def update_attendance_record(
    attendance_id: str,
    payload: AttendanceRecordUpdate,
    coordinator: User,
    db: Session,
) -> AttendanceRecordOut:
    """Update a specific attendance record (status, check-in/out times, notes)."""
    att = (
        db.query(Attendance)
        .options(
            selectinload(Attendance.shift).selectinload(Shift.event),
            selectinload(Attendance.volunteer),
        )
        .filter(Attendance.id == attendance_id)
        .first()
    )
    if not att:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found.",
        )

    ensure_coordinator_owns_shift(coordinator, att.shift, db)

    update_dict = payload.model_dump(exclude_unset=True)
    for field, val in update_dict.items():
        setattr(att, field, val)

    att.hours_awarded = calculate_hours_awarded(
        status_val=att.status,
        shift=att.shift,
        check_in=att.check_in_time,
        check_out=att.check_out_time,
    )
    att.recorded_by = coordinator.id
    att.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(att)
    return _attendance_to_out(att)


# ── 5. Summaries & Analytics ──────────────────────────────────────────────────

def get_shift_attendance_summary(shift_id: str, db: Session) -> ShiftAttendanceSummary:
    """Aggregate attendance counts and hours for a single shift."""
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found.")

    total_registered = (
        db.query(func.count(Registration.id))
        .filter(Registration.shift_id == shift_id, Registration.status == "confirmed")
        .scalar()
        or 0
    )

    records = db.query(Attendance).filter(Attendance.shift_id == shift_id).all()

    present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
    absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
    late_count = sum(1 for r in records if r.status == AttendanceStatus.LATE)
    marked_count = len(records)
    unmarked_count = max(0, total_registered - marked_count)

    total_hours = sum(r.hours_awarded for r in records)
    pct = round(((present_count + late_count) / total_registered * 100.0), 1) if total_registered > 0 else 0.0

    return ShiftAttendanceSummary(
        shift_id=shift.id,
        shift_name=shift.name,
        start_time=shift.start_time,
        end_time=shift.end_time,
        total_registered=total_registered,
        present_count=present_count,
        absent_count=absent_count,
        late_count=late_count,
        unmarked_count=unmarked_count,
        attendance_percentage=pct,
        total_hours_awarded=round(total_hours, 2),
    )


def get_event_attendance_summary(
    event_id: str,
    coordinator: User,
    db: Session,
) -> EventAttendanceSummary:
    """Aggregate attendance summary for all shifts under an event."""
    event = (
        db.query(Event)
        .options(selectinload(Event.shifts))
        .filter(Event.id == event_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    ensure_coordinator_owns_event(coordinator, event, db)

    shifts_summaries = [get_shift_attendance_summary(s.id, db) for s in event.shifts]

    tot_reg = sum(s.total_registered for s in shifts_summaries)
    tot_pres = sum(s.present_count for s in shifts_summaries)
    tot_abs = sum(s.absent_count for s in shifts_summaries)
    tot_late = sum(s.late_count for s in shifts_summaries)
    tot_hrs = sum(s.total_hours_awarded for s in shifts_summaries)

    pct = round(((tot_pres + tot_late) / tot_reg * 100.0), 1) if tot_reg > 0 else 0.0

    return EventAttendanceSummary(
        event_id=event.id,
        event_title=event.title,
        total_shifts=len(shifts_summaries),
        total_registered=tot_reg,
        total_present=tot_pres,
        total_absent=tot_abs,
        total_late=tot_late,
        attendance_percentage=pct,
        total_hours_awarded=round(tot_hrs, 2),
        shifts=shifts_summaries,
    )


def get_ngo_attendance_analytics(coordinator: User, db: Session) -> NGOAttendanceAnalytics:
    """Generate complete NGO-level attendance statistics across all events."""
    ngo = get_admin_ngo(coordinator, db)

    events = (
        db.query(Event)
        .options(selectinload(Event.shifts))
        .filter(Event.ngo_id == ngo.id)
        .all()
    )

    event_summaries: List[EventAttendanceSummary] = []
    tot_shifts = 0
    tot_reg = 0
    tot_pres = 0
    tot_abs = 0
    tot_late = 0
    tot_hrs = 0.0

    for ev in events:
        s_sums = [get_shift_attendance_summary(s.id, db) for s in ev.shifts]
        ev_reg = sum(s.total_registered for s in s_sums)
        ev_pres = sum(s.present_count for s in s_sums)
        ev_abs = sum(s.absent_count for s in s_sums)
        ev_late = sum(s.late_count for s in s_sums)
        ev_hrs = sum(s.total_hours_awarded for s in s_sums)
        ev_pct = round(((ev_pres + ev_late) / ev_reg * 100.0), 1) if ev_reg > 0 else 0.0

        event_summaries.append(
            EventAttendanceSummary(
                event_id=ev.id,
                event_title=ev.title,
                total_shifts=len(s_sums),
                total_registered=ev_reg,
                total_present=ev_pres,
                total_absent=ev_abs,
                total_late=ev_late,
                attendance_percentage=ev_pct,
                total_hours_awarded=round(ev_hrs, 2),
                shifts=s_sums,
            )
        )

        tot_shifts += len(s_sums)
        tot_reg += ev_reg
        tot_pres += ev_pres
        tot_abs += ev_abs
        tot_late += ev_late
        tot_hrs += ev_hrs

    overall_pct = round(((tot_pres + tot_late) / tot_reg * 100.0), 1) if tot_reg > 0 else 0.0

    return NGOAttendanceAnalytics(
        ngo_id=ngo.id,
        total_events=len(events),
        total_shifts=tot_shifts,
        total_registered_volunteers=tot_reg,
        total_present=tot_pres,
        total_absent=tot_abs,
        total_late=tot_late,
        overall_attendance_percentage=overall_pct,
        total_volunteer_hours=round(tot_hrs, 2),
        event_breakdown=event_summaries,
    )
