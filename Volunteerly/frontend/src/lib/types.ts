// Hand-written mirrors of backend/models/schemas.py — keep in sync.
export type Role = "ngo" | "volunteer";
export type Lang = "en" | "kn" | "hi" | "ta" | "te";
export type CoverageStatus = "fully_staffed" | "partially_staffed" | "critical_shortage" | "fully_booked";

export interface MessageOut { message: string }
export interface NameValue { name: string; value: number }

export interface User {
  id: string; role: Role; full_name: string; email: string; phone: string;
  preferred_language: string; created_at: string; is_demo: boolean; profile_id: string | null;
}
export interface RegisterIn {
  role: Role; full_name: string; email: string; password: string; phone: string; location: string;
  latitude: number | null; longitude: number | null; preferred_language: Lang; description: string; causes: string[];
}

export interface Availability { days: string[]; slots: string[] }
export interface Privacy { share_location: boolean; share_contact: boolean; replacement_opt_in: boolean }

export interface NgoProfileIn {
  organization_name: string; description: string; logo_url: string; contact_email: string; contact_number: string;
  location: string; latitude: number | null; longitude: number | null; causes: string[];
}
export interface NgoProfile extends NgoProfileIn { id: string; user_id: string; verification_status: string; is_demo: boolean }
export interface NgoPublic {
  id: string; organization_name: string; description: string; logo_url: string; location: string; causes: string[];
  contact_email: string; verification_status: string; is_demo: boolean; published_events: number;
}

export interface VolunteerProfileIn {
  name: string; profile_image: string; phone: string; location: string; latitude: number | null; longitude: number | null;
  skills: string[]; interests: string[]; preferred_activities: string[]; availability: Availability;
  preferred_language: Lang; languages_spoken: string[]; preferred_travel_radius: number; privacy: Privacy;
}
export interface VolunteerProfile extends VolunteerProfileIn { id: string; user_id: string; is_demo: boolean }
export interface VolunteerPublic {
  id: string; name: string; profile_image: string; location: string; skills: string[]; interests: string[];
  phone: string | null; is_demo: boolean; total_hours: number; engagements: number;
}

export interface SkillReq { skill: string; count: number }
export interface ShiftIn { shift_date: string; start_time: string; end_time: string; capacity: number; required_skills: SkillReq[] }
export interface Shift extends ShiftIn { id: string; event_id: string; status: string; filled: number }
export interface SkillGap { skill: string; required: number; have: number }
export interface Coverage {
  required: number; registered: number; vacant: number; coverage_pct: number; status: CoverageStatus; missing_skills: SkillGap[];
}
export interface ShiftWithCoverage extends Shift { coverage: Coverage; is_registered: boolean }

export interface EventTranslation { title: string; description: string }
export interface EventIn {
  title: string; description: string; category: string; location: string; latitude: number | null; longitude: number | null;
  event_date: string; start_time: string; end_time: string; registration_deadline: string; required_volunteers: number;
  required_skills: string[]; image_url: string; translations: Record<string, EventTranslation>;
}
export interface VEvent extends EventIn {
  id: string; ngo_id: string; status: "draft" | "published" | "unpublished"; emergency: boolean; created_at: string; is_demo: boolean;
}
export interface EventCard extends VEvent {
  ngo_name: string; shifts_count: number; total_capacity: number; total_filled: number; coverage_status: CoverageStatus;
  registration_open: boolean;
}
export interface EventDetail extends EventCard { shifts: ShiftWithCoverage[]; ngo: NgoPublic | null }

export interface Attendance {
  id: string; registration_id: string; attendance_status: "present" | "absent"; check_in_time: string; hours_contributed: number;
}
export interface RegistrationRow {
  id: string; event_id: string; event_title: string; shift_id: string; shift_date: string; start_time: string; end_time: string;
  registration_status: string; registered_at: string; cancelled_at: string | null; source: string; last_minute: boolean;
  replaced_by_name: string | null; volunteer: VolunteerPublic; attendance: Attendance | null;
}
export interface MyRegistration {
  id: string; event_id: string; event_title: string; event_location: string; category: string; ngo_id: string; ngo_name: string;
  shift_id: string; shift_date: string; start_time: string; end_time: string; hours: number; registration_status: string;
  registered_at: string; cancelled_at: string | null; source: string; can_cancel: boolean; attendance: Attendance | null;
}

export interface ScoreBreakdown { skills: number; availability: number; distance: number; interests: number; fairness_adjustment: number }
export interface Candidate {
  volunteer: VolunteerPublic; score: number; breakdown: ScoreBreakdown; matched_skills: string[]; distance_km: number | null;
  availability_pct: number; recent_hours: number; upcoming_commitments: number; invitation_status: string | null;
}
export interface CandidatesOut {
  shift: ShiftWithCoverage; event_id: string; event_title: string; target_skills: string[]; candidates: Candidate[];
  excluded: Record<string, number>;
}
export interface ShiftAlert { event_id: string; event_title: string; emergency: boolean; shift: ShiftWithCoverage }
export interface Vacancy {
  cancelled_registration_id: string; event_id: string; event_title: string; shift: ShiftWithCoverage;
  cancelled_volunteer_name: string; cancelled_at: string; last_minute: boolean; invitations_sent: number; replaced_by_name: string | null;
}
export interface CancellationOverview { vacancies: Vacancy[]; understaffed: ShiftAlert[] }
export interface InviteOut { invited: number; skipped: number; message: string }
export interface InvitationRow {
  id: string; volunteer_name: string; match_score: number; invitation_status: string; urgent: boolean; created_at: string;
  expires_at: string; auto_forwarded: boolean; cancelled_registration_id: string | null;
}
export interface Invitation {
  id: string; shift_id: string; event_id: string; event_title: string; ngo_name: string; location: string; shift_date: string;
  start_time: string; end_time: string; match_score: number; invitation_status: string; urgent: boolean; created_at: string; expires_at: string;
}

export interface Notification {
  id: string; recipient_user_id: string; title: string; message: string; notification_type: string;
  params: Record<string, string>; related_event_id: string | null; related_shift_id: string | null; read_status: boolean; created_at: string;
}

export interface NgoStats {
  total_events: number; published_events: number; total_volunteers: number; upcoming_events: number;
  total_positions: number; filled_positions: number; vacant_positions: number;
}
export interface NgoDashboard { stats: NgoStats; attention: ShiftAlert[]; recent_registrations: RegistrationRow[]; upcoming: EventCard[] }
export interface NgoAnalytics {
  events_conducted: number; total_registrations: number; total_hours: number; avg_coverage: number; attendance_rate: number;
  cancellation_rate: number; top_events: NameValue[]; skill_shortages: NameValue[]; category_split: NameValue[]; status_split: NameValue[];
}
export interface VolDashboard {
  upcoming: MyRegistration[]; recommended: EventCard[]; available_count: number; total_hours: number; events_attended: number;
  pending_invitations: number; recent_notifications: Notification[]; profile_complete: boolean;
}
export interface VolAnalytics {
  total_hours: number; events_attended: number; upcoming_commitments: number; history: MyRegistration[];
  skills_used: NameValue[]; causes_supported: NameValue[]; monthly_hours: NameValue[];
}
export interface UploadOut { url: string }
export interface LiveOut { version: number }
