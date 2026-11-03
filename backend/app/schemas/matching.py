"""Schemas for Module 4 – recommendations and matching requirements."""

from datetime import date, time

from pydantic import BaseModel, Field, field_validator


def _clean_list(values: list[str]) -> list[str]:
    out, seen = [], set()
    for v in values:
        t = " ".join(v.split())
        if t and t.casefold() not in seen:
            seen.add(t.casefold())
            out.append(t[:100])
    return out


# ── Requirements (NGO input) ──────────────────────────────────────────────────
class RequirementsIn(BaseModel):
    required_skills: list[str] = Field(default_factory=list, max_length=30)
    optional_skills: list[str] = Field(default_factory=list, max_length=30)
    interest_tags: list[str] = Field(default_factory=list, max_length=30)
    skills_mandatory: bool = True
    required_city: str | None = Field(default=None, max_length=100)

    @field_validator("required_skills", "optional_skills", "interest_tags")
    @classmethod
    def _tidy(cls, v: list[str]) -> list[str]:
        return _clean_list(v)


class RequirementsOut(RequirementsIn):
    shift_id: str


class EventProfileIn(BaseModel):
    categories: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("categories")
    @classmethod
    def _tidy(cls, v: list[str]) -> list[str]:
        return _clean_list(v)


class EventProfileOut(EventProfileIn):
    event_id: str


# ── Recommendation output ─────────────────────────────────────────────────────
class CriterionScores(BaseModel):
    skills: float = Field(description="0-40")
    availability: float = Field(description="0-30")
    interests: float = Field(description="0-20")
    experience: float = Field(description="0-10")


class AvailabilityOut(BaseModel):
    covered: bool
    code: str | None = None
    detail: str | None = None


class ExperienceOut(BaseModel):
    completed_total: int
    completed_relevant: int
    self_reported_months: int


class ExclusionOut(BaseModel):
    code: str
    message: str


class MatchOut(BaseModel):
    volunteer_id: str
    volunteer_name: str
    eligible: bool
    total_score: float
    max_score: float
    scores: CriterionScores
    matched_skills: list[str]
    missing_required_skills: list[str]
    matched_optional_skills: list[str]
    missing_optional_skills: list[str]
    matching_interests: list[str]
    availability: AvailabilityOut
    relevant_experience: ExperienceOut
    recent_assignments: int
    exclusions: list[ExclusionOut]
    explanation: list[str]
    summary: str
    invitation_status: str | None = None
    shortlisted: bool = False


class ShiftBriefOut(BaseModel):
    shift_id: str
    event_id: str
    event_name: str
    event_location: str
    title: str
    shift_date: date
    start_time: time
    end_time: time
    capacity: int
    remaining_slots: int
    status: str


class NeedsOut(BaseModel):
    required_skills: list[str]
    optional_skills: list[str]
    categories: list[str]
    skills_mandatory: bool
    required_city: str | None = None


class SkillShortageOut(BaseModel):
    skill: str
    slots_needed: int
    eligible_with_skill: int
    shortage: int


class SkillGapOut(BaseModel):
    slots_remaining: int
    eligible_count: int
    gap: int
    per_skill: list[SkillShortageOut]
    exclusion_counts: dict[str, int]
    partially_matching_ineligible: int


class ShiftRecommendationsOut(BaseModel):
    shift: ShiftBriefOut
    needs: NeedsOut
    skill_gap: SkillGapOut
    recommendations: list[MatchOut]
    excluded: list[MatchOut]
    disclaimer: str


class EventRecommendationsOut(BaseModel):
    event_id: str
    event_name: str
    shifts: list[ShiftRecommendationsOut]
    distinct_eligible_volunteers: int
    total_slots_remaining: int
    total_gap: int
    disclaimer: str


class VolunteerShiftRecOut(BaseModel):
    shift: ShiftBriefOut
    match: MatchOut


class VolunteerRecommendationsOut(BaseModel):
    recommendations: list[VolunteerShiftRecOut]
    count: int
    disclaimer: str
