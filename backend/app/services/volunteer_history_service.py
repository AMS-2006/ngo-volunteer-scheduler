"""
services/volunteer_history_service.py
─────────────────────────────────────
Module 7: Volunteer Participation History & Reliability Metrics

Provides:
  • Complete participation history timeline for volunteers
  • Accurate volunteering hours calculation grouped by event category and month
  • Factual reliability metrics (attendance %, cancellations, absences)
  • Clean signal integration for Module 4's recommendation engine
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.models.attendance import Attendance, AttendanceStatus
from app.models.event import Event
from app.models.registration import Registration
from app.models.shift import Shift
from app.models.user import User
from app.schemas.attendance import (
    AttendanceRecordOut,
    VolunteerHistoryItem,
    VolunteerHoursSummary,
    VolunteerReliabilityStats,
)
from app.services.attendance_service import _attendance_to_out


# ── 1. Volunteer History Timeline ─────────────────────────────────────────────

def get_volunteer_history(
    volunteer_id: str,
    db: Session,
) -> List[VolunteerHistoryItem]:
    """Retrieve full chronological history of shifts attended or recorded for a volunteer."""
    user = db.get(User, volunteer_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volunteer not found.",
        )

    records = (
        db.query(Attendance)
        .options(
            selectinload(Attendance.event),
            selectinload(Attendance.shift),
        )
        .filter(Attendance.volunteer_id == volunteer_id)
        .order_by(Attendance.created_at.desc())
        .all()
    )

    items: List[VolunteerHistoryItem] = []
    for att in records:
        ev = att.event
        sh = att.shift
        items.append(
            VolunteerHistoryItem(
                attendance_id=att.id,
                event_id=att.event_id,
                event_title=ev.title if ev else "Event",
                cause_category=ev.cause_category if ev else None,
                location=ev.location_name if ev else None,
                city=ev.city if ev else None,
                shift_id=att.shift_id,
                shift_name=sh.name if sh else "Shift",
                start_time=sh.start_time if sh else att.created_at,
                end_time=sh.end_time if sh else att.created_at,
                status=att.status,
                check_in_time=att.check_in_time,
                check_out_time=att.check_out_time,
                hours_awarded=att.hours_awarded,
                notes=att.notes,
                recorded_at=att.created_at,
            )
        )
    return items


def get_volunteer_attendance_records(
    volunteer_id: str,
    db: Session,
) -> List[AttendanceRecordOut]:
    """List raw attendance records for a volunteer."""
    records = (
        db.query(Attendance)
        .options(selectinload(Attendance.volunteer))
        .filter(Attendance.volunteer_id == volunteer_id)
        .order_by(Attendance.created_at.desc())
        .all()
    )
    return [_attendance_to_out(r) for r in records]


# ── 2. Hours Aggregation Summary ──────────────────────────────────────────────

def get_volunteer_hours_summary(
    volunteer_id: str,
    db: Session,
) -> VolunteerHoursSummary:
    """
    Calculate verified volunteer hours:
      • Excludes absent shifts.
      • Aggregates total hours by event cause category.
      • Aggregates hours across chronological monthly intervals.
    """
    user = db.get(User, volunteer_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volunteer not found.")

    records = (
        db.query(Attendance)
        .options(selectinload(Attendance.event))
        .filter(Attendance.volunteer_id == volunteer_id)
        .all()
    )

    total_hours = 0.0
    completed_shifts = 0
    attended_shifts = 0
    hours_by_cause: Dict[str, float] = defaultdict(float)
    monthly_data: Dict[str, Dict[str, Any]] = {}

    for att in records:
        completed_shifts += 1
        if att.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE):
            attended_shifts += 1
            hrs = att.hours_awarded
            total_hours += hrs

            # Cause categorization
            cause = (att.event.cause_category if att.event and att.event.cause_category else "General Volunteering")
            hours_by_cause[cause] += hrs

            # Monthly bucket
            month_key = att.created_at.strftime("%Y-%m")
            month_label = att.created_at.strftime("%B %Y")
            if month_key not in monthly_data:
                monthly_data[month_key] = {"month": month_key, "label": month_label, "hours": 0.0, "shifts": 0}
            monthly_data[month_key]["hours"] = round(monthly_data[month_key]["hours"] + hrs, 2)
            monthly_data[month_key]["shifts"] += 1

    # Format sorted monthly data
    sorted_months = [monthly_data[k] for k in sorted(monthly_data.keys())]

    return VolunteerHoursSummary(
        total_hours=round(total_hours, 2),
        completed_shifts=completed_shifts,
        attended_shifts=attended_shifts,
        hours_by_cause={k: round(v, 2) for k, v in hours_by_cause.items()},
        hours_by_month=sorted_months,
    )


# ── 3. Reliability & Participation Metrics ────────────────────────────────────

def get_volunteer_reliability_stats(
    volunteer_id: str,
    db: Session,
) -> VolunteerReliabilityStats:
    """
    Generate factual participation metrics:
      • Total assigned shifts (registrations ever confirmed)
      • Attended shifts (marked present or late)
      • Absences (marked absent)
      • Cancellations (registrations cancelled by volunteer)
      • Attendance percentage
      • Sufficient data indicator (only reliable after >= 3 assigned shifts)
    """
    user = db.get(User, volunteer_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volunteer not found.")

    # Registrations count
    total_assigned = (
        db.query(Registration)
        .filter(Registration.volunteer_id == volunteer_id, Registration.status == "confirmed")
        .count()
    )
    cancellations = (
        db.query(Registration)
        .filter(Registration.volunteer_id == volunteer_id, Registration.status == "cancelled")
        .count()
    )

    attendance_records = db.query(Attendance).filter(Attendance.volunteer_id == volunteer_id).all()

    attended_count = sum(1 for a in attendance_records if a.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE))
    absent_count = sum(1 for a in attendance_records if a.status == AttendanceStatus.ABSENT)

    # Base attendance rate on shifts with finalized attendance
    total_recorded = len(attendance_records)
    if total_recorded > 0:
        attendance_percentage = round((attended_count / total_recorded) * 100.0, 1)
    else:
        attendance_percentage = 100.0  # Clean default when no absences on record

    has_sufficient_data = (total_recorded >= 3)
    notes = (
        f"Verified attendance rate across {total_recorded} recorded assignments."
        if has_sufficient_data
        else "Preliminary data (< 3 recorded shifts). Neutral reliability signal."
    )

    return VolunteerReliabilityStats(
        volunteer_id=volunteer_id,
        total_assigned_shifts=total_assigned,
        attended_shifts=attended_count,
        absences=absent_count,
        cancellations=cancellations,
        attendance_percentage=attendance_percentage,
        has_sufficient_data=has_sufficient_data,
        notes=notes,
    )
