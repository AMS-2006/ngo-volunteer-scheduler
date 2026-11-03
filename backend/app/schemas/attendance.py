"""
schemas/attendance.py
─────────────────────
Pydantic schemas for Module 7: Attendance & Volunteer History.
"""

from datetime import date, datetime, time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Attendance Marking Schemas ────────────────────────────────────────────────

class AttendanceRecordCreate(BaseModel):
    volunteer_id: str = Field(..., description="UUID of confirmed volunteer")
    status: str = Field("present", description="'present', 'absent', or 'late'")
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        s = v.lower().strip()
        if s not in {"present", "absent", "late"}:
            raise ValueError("status must be 'present', 'absent', or 'late'")
        return s


class AttendanceBatchCreate(BaseModel):
    records: List[AttendanceRecordCreate] = Field(
        ..., min_length=1, description="Batch list of attendance records to record"
    )


class AttendanceRecordUpdate(BaseModel):
    status: Optional[str] = Field(None, description="'present', 'absent', or 'late'")
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.lower().strip()
        if s not in {"present", "absent", "late"}:
            raise ValueError("status must be 'present', 'absent', or 'late'")
        return s


# ── Output Records ────────────────────────────────────────────────────────────

class AttendanceRecordOut(BaseModel):
    id: str
    event_id: str
    shift_id: str
    registration_id: str
    volunteer_id: str
    volunteer_name: Optional[str] = None
    volunteer_email: Optional[str] = None
    status: str
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    hours_awarded: float
    recorded_by: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShiftRosterVolunteerItem(BaseModel):
    registration_id: str
    volunteer_id: str
    volunteer_name: str
    volunteer_email: str
    registration_status: str
    attendance: Optional[AttendanceRecordOut] = None


class ShiftRosterAttendanceOut(BaseModel):
    shift_id: str
    shift_name: str
    event_id: str
    event_title: str
    start_time: datetime
    end_time: datetime
    volunteers: List[ShiftRosterVolunteerItem]


# ── Summaries & Analytics ─────────────────────────────────────────────────────

class ShiftAttendanceSummary(BaseModel):
    shift_id: str
    shift_name: str
    start_time: datetime
    end_time: datetime
    total_registered: int
    present_count: int
    absent_count: int
    late_count: int
    unmarked_count: int
    attendance_percentage: float
    total_hours_awarded: float


class EventAttendanceSummary(BaseModel):
    event_id: str
    event_title: str
    total_shifts: int
    total_registered: int
    total_present: int
    total_absent: int
    total_late: int
    attendance_percentage: float
    total_hours_awarded: float
    shifts: List[ShiftAttendanceSummary] = []


class NGOAttendanceAnalytics(BaseModel):
    ngo_id: str
    total_events: int
    total_shifts: int
    total_registered_volunteers: int
    total_present: int
    total_absent: int
    total_late: int
    overall_attendance_percentage: float
    total_volunteer_hours: float
    event_breakdown: List[EventAttendanceSummary] = []


# ── Volunteer History Schemas ─────────────────────────────────────────────────

class VolunteerHistoryItem(BaseModel):
    attendance_id: str
    event_id: str
    event_title: str
    cause_category: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    shift_id: str
    shift_name: str
    start_time: datetime
    end_time: datetime
    status: str
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    hours_awarded: float
    notes: Optional[str] = None
    recorded_at: datetime


class VolunteerHoursSummary(BaseModel):
    total_hours: float
    completed_shifts: int
    attended_shifts: int
    hours_by_cause: Dict[str, float]
    hours_by_month: List[Dict[str, Any]]


class VolunteerReliabilityStats(BaseModel):
    volunteer_id: str
    total_assigned_shifts: int
    attended_shifts: int
    absences: int
    cancellations: int
    attendance_percentage: float
    has_sufficient_data: bool
    notes: str
