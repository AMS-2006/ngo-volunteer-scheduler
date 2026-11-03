"""
routers/attendance.py
─────────────────────
Module 7: Attendance Management & NGO Analytics Endpoints.

Endpoints:
  • GET   /api/v1/attendance/shifts/{shift_id}             – View registered volunteers & attendance roster
  • POST  /api/v1/attendance/shifts/{shift_id}/records     – Mark / update attendance (single or batch)
  • PATCH /api/v1/attendance/{attendance_id}               – Update an attendance record
  • GET   /api/v1/attendance/events/{event_id}/summary     – Summary metrics for an event
  • GET   /api/v1/attendance/shifts/{shift_id}/summary     – Summary metrics for a shift
  • GET   /api/v1/attendance/analytics                     – NGO-wide attendance analytics across all events
  • GET   /api/v1/attendance/volunteers/{id}/history       – Authorized NGO coordinator view of volunteer history
"""

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.database.connection import get_db
from app.models.user import User
from app.schemas.attendance import (
    AttendanceBatchCreate,
    AttendanceRecordCreate,
    AttendanceRecordOut,
    AttendanceRecordUpdate,
    EventAttendanceSummary,
    NGOAttendanceAnalytics,
    ShiftAttendanceSummary,
    ShiftRosterAttendanceOut,
    VolunteerHistoryItem,
    VolunteerReliabilityStats,
)
from app.services.attendance_service import (
    get_event_attendance_summary,
    get_ngo_attendance_analytics,
    get_shift_attendance_summary,
    get_shift_roster_with_attendance,
    record_shift_attendance_batch,
    update_attendance_record,
)
from app.services.volunteer_history_service import (
    get_volunteer_history,
    get_volunteer_reliability_stats,
)

router = APIRouter(prefix="/attendance", tags=["Attendance Management & Analytics"])


# ── 1. Shift Roster & Attendance ──────────────────────────────────────────────

@router.get(
    "/shifts/{shift_id}",
    response_model=ShiftRosterAttendanceOut,
    summary="View volunteers registered for a shift and their attendance",
)
def view_shift_roster_attendance(
    shift_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Returns the list of confirmed volunteers for a shift along with
    their current attendance status (present, absent, late, or unmarked).
    """
    return get_shift_roster_with_attendance(shift_id, admin, db)


@router.post(
    "/shifts/{shift_id}/records",
    response_model=List[AttendanceRecordOut],
    status_code=status.HTTP_200_OK,
    summary="Mark or update attendance for volunteers on a shift",
)
def mark_shift_attendance(
    shift_id: str,
    payload: AttendanceBatchCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Mark attendance as PRESENT, ABSENT, or LATE for confirmed volunteers.
    Calculates volunteering hours automatically and records coordinator audit trail.
    """
    return record_shift_attendance_batch(shift_id, payload.records, admin, db)


# ── 2. Update Single Attendance Record ───────────────────────────────────────

@router.patch(
    "/{attendance_id}",
    response_model=AttendanceRecordOut,
    summary="Update a specific attendance record",
)
def modify_attendance_record(
    attendance_id: str,
    payload: AttendanceRecordUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Update status, check-in, check-out, or notes for an attendance record.
    Recalculates credited hours immediately.
    """
    return update_attendance_record(attendance_id, payload, admin, db)


# ── 3. Summaries & Analytics ──────────────────────────────────────────────────

@router.get(
    "/shifts/{shift_id}/summary",
    response_model=ShiftAttendanceSummary,
    summary="View attendance summary for a shift",
)
def view_shift_summary(
    shift_id: str,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return attendance counts, attendance percentage, and total hours for a shift."""
    return get_shift_attendance_summary(shift_id, db)


@router.get(
    "/events/{event_id}/summary",
    response_model=EventAttendanceSummary,
    summary="View attendance summary for an event",
)
def view_event_summary(
    event_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return event-level attendance aggregates across all associated shifts."""
    return get_event_attendance_summary(event_id, admin, db)


@router.get(
    "/analytics",
    response_model=NGOAttendanceAnalytics,
    summary="View complete attendance analytics for the NGO",
)
def view_ngo_analytics(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    NGO-wide attendance report:
      • Total registered, present, absent, and late volunteers
      • Overall attendance percentage
      • Total verified volunteer hours credited
      • Event-by-event breakdown
    """
    return get_ngo_attendance_analytics(admin, db)


# ── 4. Coordinator Volunteer History Inspection ───────────────────────────────

@router.get(
    "/volunteers/{volunteer_id}/history",
    response_model=List[VolunteerHistoryItem],
    summary="View a volunteer's complete participation history (admin only)",
)
def view_volunteer_history_admin(
    volunteer_id: str,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Authorized NGO coordinators can inspect a volunteer's historical attendance records."""
    return get_volunteer_history(volunteer_id, db)


@router.get(
    "/volunteers/{volunteer_id}/reliability",
    response_model=VolunteerReliabilityStats,
    summary="View a volunteer's reliability stats (admin only)",
)
def view_volunteer_reliability_admin(
    volunteer_id: str,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Authorized NGO coordinators can view factual attendance reliability metrics."""
    return get_volunteer_reliability_stats(volunteer_id, db)
