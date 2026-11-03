"""Pydantic v2 models — mirrored by hand in frontend/src/lib/types.ts. Keep both in sync."""
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field

Role = Literal["ngo", "volunteer"]
Lang = Literal["en", "kn", "hi", "ta", "te"]


class MessageOut(BaseModel):
    message: str


class NameValue(BaseModel):
    name: str
    value: float


# ---------- auth ----------
class RegisterIn(BaseModel):
    role: Role
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: str = Field(min_length=6, max_length=20)
    location: str = Field(min_length=2, max_length=120)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    preferred_language: Lang = "en"
    description: str = ""
    causes: list[str] = []


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class LanguageIn(BaseModel):
    preferred_language: Lang


class UserOut(BaseModel):
    id: str
    role: Role
    full_name: str
    email: str
    phone: str
    preferred_language: str
    created_at: str
    is_demo: bool = False
    profile_id: Optional[str] = None


# ---------- profiles ----------
class Availability(BaseModel):
    days: list[str] = []  # mon..sun
    slots: list[str] = []  # morning | afternoon | evening


class Privacy(BaseModel):
    share_location: bool = True
    share_contact: bool = False
    replacement_opt_in: bool = True


class NgoProfileIn(BaseModel):
    organization_name: str = Field(min_length=2)
    description: str = ""
    logo_url: str = ""
    contact_email: EmailStr
    contact_number: str
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    causes: list[str] = []


class NgoProfile(NgoProfileIn):
    id: str
    user_id: str
    verification_status: str = "pending"
    is_demo: bool = False


class NgoPublic(BaseModel):
    id: str
    organization_name: str
    description: str
    logo_url: str
    location: str
    causes: list[str]
    contact_email: str
    verification_status: str
    is_demo: bool = False
    published_events: int = 0


class VolunteerProfileIn(BaseModel):
    name: str = Field(min_length=2)
    profile_image: str = ""
    phone: str = ""
    location: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    skills: list[str] = []
    interests: list[str] = []
    preferred_activities: list[str] = []
    availability: Availability = Availability()
    preferred_language: Lang = "en"
    languages_spoken: list[str] = []
    preferred_travel_radius: float = Field(default=15, ge=1, le=500)
    privacy: Privacy = Privacy()


class VolunteerProfile(VolunteerProfileIn):
    id: str
    user_id: str
    is_demo: bool = False


class VolunteerPublic(BaseModel):
    """What NGOs may see — never exact coordinates or address."""
    id: str
    name: str
    profile_image: str = ""
    location: str = ""
    skills: list[str] = []
    interests: list[str] = []
    phone: Optional[str] = None
    is_demo: bool = False
    total_hours: float = 0
    engagements: int = 0


# ---------- events / shifts ----------
class SkillReq(BaseModel):
    skill: str
    count: int = Field(ge=1, le=500)


class ShiftIn(BaseModel):
    shift_date: str
    start_time: str
    end_time: str
    capacity: int = Field(ge=1, le=1000)
    required_skills: list[SkillReq] = []


class Shift(ShiftIn):
    id: str
    event_id: str
    status: str = "open"
    filled: int = 0


class SkillGap(BaseModel):
    skill: str
    required: int
    have: int


class Coverage(BaseModel):
    required: int
    registered: int
    vacant: int
    coverage_pct: int
    status: Literal["fully_staffed", "partially_staffed", "critical_shortage", "fully_booked"]
    missing_skills: list[SkillGap] = []


class ShiftWithCoverage(Shift):
    coverage: Coverage
    is_registered: bool = False


class EventTranslation(BaseModel):
    title: str = ""
    description: str = ""


class EventIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10)
    category: str
    location: str = Field(min_length=2)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    event_date: str
    start_time: str
    end_time: str
    registration_deadline: str  # YYYY-MM-DDTHH:MM (local, IST)
    required_volunteers: int = Field(ge=1, le=5000)
    required_skills: list[str] = []
    image_url: str = ""
    translations: dict[str, EventTranslation] = {}


class Event(EventIn):
    id: str
    ngo_id: str
    status: Literal["draft", "published", "unpublished"]
    emergency: bool = False
    created_at: str
    is_demo: bool = False


class EventCard(Event):
    ngo_name: str = ""
    shifts_count: int = 0
    total_capacity: int = 0
    total_filled: int = 0
    coverage_status: str = "critical_shortage"
    registration_open: bool = False


class EventDetail(EventCard):
    shifts: list[ShiftWithCoverage] = []
    ngo: Optional[NgoPublic] = None


class EventStatusIn(BaseModel):
    status: Literal["draft", "published", "unpublished"]


# ---------- registrations / attendance ----------
class Attendance(BaseModel):
    id: str
    registration_id: str
    attendance_status: Literal["present", "absent"]
    check_in_time: str
    hours_contributed: float


class AttendanceIn(BaseModel):
    attendance_status: Literal["present", "absent"]
    hours_contributed: Optional[float] = Field(default=None, ge=0, le=24)


class RegisterShiftIn(BaseModel):
    shift_id: str


class RegistrationRow(BaseModel):
    """NGO view of a registration."""
    id: str
    event_id: str
    event_title: str
    shift_id: str
    shift_date: str
    start_time: str
    end_time: str
    registration_status: str
    registered_at: str
    cancelled_at: Optional[str] = None
    source: str = "direct"
    last_minute: bool = False
    replaced_by_name: Optional[str] = None
    volunteer: VolunteerPublic
    attendance: Optional[Attendance] = None


class MyRegistration(BaseModel):
    """Volunteer view of their own registration."""
    id: str
    event_id: str
    event_title: str
    event_location: str
    category: str
    ngo_id: str
    ngo_name: str
    shift_id: str
    shift_date: str
    start_time: str
    end_time: str
    hours: float
    registration_status: str
    registered_at: str
    cancelled_at: Optional[str] = None
    source: str = "direct"
    can_cancel: bool = False
    attendance: Optional[Attendance] = None


# ---------- smart cancellation ----------
class ScoreBreakdown(BaseModel):
    skills: float
    availability: float
    distance: float
    interests: float
    fairness_adjustment: float


class Candidate(BaseModel):
    volunteer: VolunteerPublic
    score: float
    breakdown: ScoreBreakdown
    matched_skills: list[str]
    distance_km: Optional[float] = None
    availability_pct: int
    recent_hours: float
    upcoming_commitments: int
    invitation_status: Optional[str] = None


class CandidatesOut(BaseModel):
    shift: ShiftWithCoverage
    event_id: str
    event_title: str
    target_skills: list[str]
    candidates: list[Candidate]
    excluded: dict[str, int]


class ShiftAlert(BaseModel):
    event_id: str
    event_title: str
    emergency: bool = False
    shift: ShiftWithCoverage


class Vacancy(BaseModel):
    cancelled_registration_id: str
    event_id: str
    event_title: str
    shift: ShiftWithCoverage
    cancelled_volunteer_name: str
    cancelled_at: str
    last_minute: bool
    invitations_sent: int
    replaced_by_name: Optional[str] = None


class CancellationOverview(BaseModel):
    vacancies: list[Vacancy]
    understaffed: list[ShiftAlert]


class InviteIn(BaseModel):
    shift_id: str
    cancelled_registration_id: Optional[str] = None
    volunteer_ids: list[str] = Field(min_length=1, max_length=50)
    urgent: bool = False


class InviteOut(BaseModel):
    invited: int
    skipped: int
    message: str


class EmergencyIn(BaseModel):
    shift_id: str
    needed: int = Field(ge=1, le=100)


class InvitationRow(BaseModel):
    id: str
    volunteer_name: str
    match_score: float
    invitation_status: str
    urgent: bool
    created_at: str
    expires_at: str = ""
    auto_forwarded: bool = False
    cancelled_registration_id: Optional[str] = None


class Invitation(BaseModel):
    """Volunteer view of an invitation."""
    id: str
    shift_id: str
    event_id: str
    event_title: str
    ngo_name: str
    location: str
    shift_date: str
    start_time: str
    end_time: str
    match_score: float
    invitation_status: str
    urgent: bool
    created_at: str
    expires_at: str


class RespondIn(BaseModel):
    accept: bool


# ---------- notifications ----------
class Notification(BaseModel):
    id: str
    recipient_user_id: str
    title: str
    message: str
    notification_type: str
    params: dict[str, str] = {}
    related_event_id: Optional[str] = None
    related_shift_id: Optional[str] = None
    read_status: bool = False
    created_at: str


# ---------- dashboards / analytics ----------
class NgoStats(BaseModel):
    total_events: int
    published_events: int
    total_volunteers: int
    upcoming_events: int
    total_positions: int
    filled_positions: int
    vacant_positions: int


class NgoDashboard(BaseModel):
    stats: NgoStats
    attention: list[ShiftAlert]
    recent_registrations: list[RegistrationRow]
    upcoming: list[EventCard]


class NgoAnalytics(BaseModel):
    events_conducted: int
    total_registrations: int
    total_hours: float
    avg_coverage: float
    attendance_rate: float
    cancellation_rate: float
    top_events: list[NameValue]
    skill_shortages: list[NameValue]
    category_split: list[NameValue]
    status_split: list[NameValue]


class VolDashboard(BaseModel):
    upcoming: list[MyRegistration]
    recommended: list[EventCard]
    available_count: int
    total_hours: float
    events_attended: int
    pending_invitations: int
    recent_notifications: list[Notification]
    profile_complete: bool


class VolAnalytics(BaseModel):
    total_hours: float
    events_attended: int
    upcoming_commitments: int
    history: list[MyRegistration]
    skills_used: list[NameValue]
    causes_supported: list[NameValue]
    monthly_hours: list[NameValue]


class UploadOut(BaseModel):
    url: str


class LiveOut(BaseModel):
    version: int
