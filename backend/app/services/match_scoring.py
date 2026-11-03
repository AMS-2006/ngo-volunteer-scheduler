"""
Module 4 – pure (database-free) scoring, eligibility, ranking and explanations.

Weights (100 total): skills 40 · availability 30 · interests 20 · experience 10.

Design rules
  • Everything here is deterministic and works on plain dataclasses, so it is
    unit-testable without a database. The DB layer (recommendation_service)
    gathers facts and feeds them in.
  • Terms (skills / interests) are compared case-insensitively with whitespace
    collapsed, and de-duplicated, so repeating a skill never inflates a score.
  • A criterion the shift does not configure (e.g. no required skills) is
    vacuously satisfied by everyone (full points for all candidates, so it never
    changes the ranking) and is flagged `configured=False` in the output.
    Missing *volunteer* data is never a match: it scores 0.
  • The score is a compatibility measure, not a probability of attendance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── Weights & constants ───────────────────────────────────────────────────────
W_SKILLS = 40.0
W_AVAILABILITY = 30.0
W_INTERESTS = 20.0
W_EXPERIENCE = 10.0
MAX_SCORE = W_SKILLS + W_AVAILABILITY + W_INTERESTS + W_EXPERIENCE

REQUIRED_SKILL_SHARE = 0.75  # when a shift has both required and optional skills

# Experience (10): relevant history 5 + overall history 3 + self-reported months 2
EXP_RELEVANT_PTS, EXP_RELEVANT_CAP = 5.0, 4      # 4+ relevant completed shifts = full
EXP_TOTAL_PTS, EXP_TOTAL_CAP = 3.0, 10           # 10+ completed shifts = full
EXP_SELF_PTS, EXP_SELF_CAP_MONTHS = 2.0, 24      # 24+ self-reported months = full

# Fair distribution: scores within the same 2-point band are ordered by workload.
FAIR_BAND = 2.0

DISCLAIMER = (
    "Compatibility score based on skills, availability, interests and volunteering "
    "history. It is not a probability of attendance or performance."
)

# Exclusion codes
ACCOUNT_INACTIVE = "ACCOUNT_INACTIVE"
ALREADY_REGISTERED = "ALREADY_REGISTERED"
PROFILE_MISSING = "PROFILE_MISSING"
NOT_AVAILABLE = "NOT_AVAILABLE"
SCHEDULE_CONFLICT = "SCHEDULE_CONFLICT"
MISSING_MANDATORY_SKILLS = "MISSING_MANDATORY_SKILLS"
LOCATION_UNKNOWN = "LOCATION_UNKNOWN"
LOCATION_MISMATCH = "LOCATION_MISMATCH"


# ── Helpers ───────────────────────────────────────────────────────────────────
def term_map(values) -> dict[str, str]:
    """{normalised_key: display_text}, de-duplicated, first spelling wins."""
    out: dict[str, str] = {}
    for value in values or ():
        if not isinstance(value, str):
            continue
        display = " ".join(value.split())
        key = display.casefold()
        if key and key not in out:
            out[key] = display
    return out


def normalize_terms(values) -> list[str]:
    return list(term_map(values))


def _r(value: float) -> float:
    return round(value, 1)


# ── Input facts ───────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ShiftNeeds:
    required_skills: tuple = ()
    optional_skills: tuple = ()
    categories: tuple = ()          # event categories + shift interest tags
    skills_mandatory: bool = True
    required_city: str | None = None


@dataclass(frozen=True)
class VolunteerFacts:
    volunteer_id: str
    full_name: str
    is_active: bool = True
    has_profile: bool = True
    skills: tuple = ()
    interests: tuple = ()
    city: str | None = None
    experience_months: int = 0


@dataclass(frozen=True)
class AvailabilityResult:
    covered: bool
    code: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class ExperienceFacts:
    completed_total: int = 0        # confirmed registrations on shifts that already ended
    completed_relevant: int = 0     # subset in the same category / organisation
    self_reported_months: int = 0


# ── Criterion results ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class SkillScore:
    points: float
    configured: bool
    required_total: int
    matched_required: list
    missing_required: list
    optional_total: int
    matched_optional: list
    missing_optional: list


@dataclass(frozen=True)
class InterestScore:
    points: float
    configured: bool
    targets_total: int
    matched: list


@dataclass(frozen=True)
class Exclusion:
    code: str
    message: str


@dataclass
class MatchResult:
    volunteer_id: str
    full_name: str
    eligible: bool
    total_score: float
    skill: SkillScore
    availability_points: float
    interest: InterestScore
    experience_points: float
    availability: AvailabilityResult
    experience: ExperienceFacts
    recent_assignments: int = 0
    exclusions: list = field(default_factory=list)
    explanation: list = field(default_factory=list)
    summary: str = ""


# ── Scoring functions ─────────────────────────────────────────────────────────
def score_skills(needs: ShiftNeeds, volunteer_skills) -> SkillScore:
    """40 pts. Required skills weigh 75% when optional skills exist, else 100%."""
    req = term_map(needs.required_skills)
    opt = {k: v for k, v in term_map(needs.optional_skills).items() if k not in req}
    have = term_map(volunteer_skills)

    m_req = [v for k, v in req.items() if k in have]
    x_req = [v for k, v in req.items() if k not in have]
    m_opt = [v for k, v in opt.items() if k in have]
    x_opt = [v for k, v in opt.items() if k not in have]

    if not req and not opt:
        points, configured = W_SKILLS, False
    elif req and opt:
        points = W_SKILLS * (
            REQUIRED_SKILL_SHARE * len(m_req) / len(req)
            + (1 - REQUIRED_SKILL_SHARE) * len(m_opt) / len(opt)
        )
        configured = True
    elif req:
        points, configured = W_SKILLS * len(m_req) / len(req), True
    else:
        points, configured = W_SKILLS * len(m_opt) / len(opt), True

    return SkillScore(_r(points), configured, len(req), m_req, x_req, len(opt), m_opt, x_opt)


def score_availability(availability: AvailabilityResult) -> float:
    """30 pts, all-or-nothing: the volunteer must cover the COMPLETE shift."""
    return W_AVAILABILITY if availability.covered else 0.0


def score_interests(needs: ShiftNeeds, volunteer_interests) -> InterestScore:
    """20 pts = share of the shift's categories/tags the volunteer is interested in."""
    targets = term_map(needs.categories)
    have = term_map(volunteer_interests)
    if not targets:
        return InterestScore(W_INTERESTS, False, 0, [])
    matched = [v for k, v in targets.items() if k in have]
    return InterestScore(_r(W_INTERESTS * len(matched) / len(targets)), True, len(targets), matched)


def score_experience(exp: ExperienceFacts) -> float:
    """10 pts from recorded history only (never invented): relevant 5 + overall 3 + self-reported 2."""
    relevant = min(max(exp.completed_relevant, 0), EXP_RELEVANT_CAP) / EXP_RELEVANT_CAP
    overall = min(max(exp.completed_total, 0), EXP_TOTAL_CAP) / EXP_TOTAL_CAP
    selfrep = min(max(exp.self_reported_months, 0), EXP_SELF_CAP_MONTHS) / EXP_SELF_CAP_MONTHS
    return _r(EXP_RELEVANT_PTS * relevant + EXP_TOTAL_PTS * overall + EXP_SELF_PTS * selfrep)


# ── Eligibility ───────────────────────────────────────────────────────────────
def check_eligibility(
    needs: ShiftNeeds,
    vol: VolunteerFacts,
    skill: SkillScore,
    availability: AvailabilityResult,
    conflict: str | None,
    registration_status: str | None,
) -> list[Exclusion]:
    out: list[Exclusion] = []
    if not vol.is_active:
        out.append(Exclusion(ACCOUNT_INACTIVE, "Volunteer account is not active."))
    if registration_status:
        out.append(
            Exclusion(ALREADY_REGISTERED, f"Already {registration_status.lower()} for this shift.")
        )
    if not vol.has_profile:
        out.append(Exclusion(PROFILE_MISSING, "Volunteer has not completed a profile."))
    if not availability.covered:
        out.append(
            Exclusion(NOT_AVAILABLE, availability.detail or "Not available for the complete shift.")
        )
    if conflict:
        out.append(Exclusion(SCHEDULE_CONFLICT, conflict))
    if needs.skills_mandatory and skill.missing_required:
        out.append(
            Exclusion(
                MISSING_MANDATORY_SKILLS,
                "Missing mandatory skills: " + ", ".join(skill.missing_required) + ".",
            )
        )
    if needs.required_city:
        if not (vol.city or "").strip():
            out.append(
                Exclusion(LOCATION_UNKNOWN, f"Volunteer city is unknown; shift requires {needs.required_city}.")
            )
        elif vol.city.strip().casefold() != needs.required_city.strip().casefold():
            out.append(
                Exclusion(
                    LOCATION_MISMATCH,
                    f"Volunteer is in {vol.city.strip()}; shift requires {needs.required_city}.",
                )
            )
    return out


# ── Explanations (generated only from the scoring results) ────────────────────
def build_explanation(r: MatchResult) -> list[str]:
    lines: list[str] = []
    for ex in r.exclusions:
        lines.append(f"Not eligible: {ex.message}")

    s = r.skill
    if not s.configured:
        lines.append("No specific skills are required for this shift.")
    else:
        if s.required_total:
            if not s.missing_required:
                lines.append(f"All required skills matched ({', '.join(s.matched_required)}).")
            else:
                lines.append(
                    f"Matched {len(s.matched_required)} of {s.required_total} required skills; "
                    f"missing: {', '.join(s.missing_required)}."
                )
        if s.optional_total:
            tail = f" (missing: {', '.join(s.missing_optional)})" if s.missing_optional else ""
            lines.append(f"Optional skills: {len(s.matched_optional)} of {s.optional_total} matched{tail}.")

    if r.availability.covered:
        lines.append("Fully available for the entire shift.")
    elif r.availability.detail:
        lines.append(f"Availability: {r.availability.detail}")

    i = r.interest
    if not i.configured:
        lines.append("No event category specified, so interests were not compared.")
    elif i.matched:
        ratio = len(i.matched) / i.targets_total
        label = "Strong" if ratio >= 0.75 else "Partial"
        lines.append(f"{label} interest match ({', '.join(i.matched)}).")
    else:
        lines.append("No overlap between volunteer interests and the event categories.")

    e = r.experience
    if r.experience_points >= 7:
        label = "Strong"
    elif r.experience_points >= 3:
        label = "Some"
    elif r.experience_points > 0:
        label = "Limited"
    else:
        label = None
    if label:
        lines.append(
            f"{label} experience: {e.completed_relevant} relevant and {e.completed_total} total "
            f"completed shifts, {e.self_reported_months} months self-reported."
        )
    else:
        lines.append("No relevant volunteering history on record.")
    return lines


# ── Evaluation ────────────────────────────────────────────────────────────────
def evaluate_match(
    needs: ShiftNeeds,
    vol: VolunteerFacts,
    availability: AvailabilityResult,
    conflict: str | None = None,
    registration_status: str | None = None,
    experience: ExperienceFacts | None = None,
    recent_assignments: int = 0,
) -> MatchResult:
    experience = experience or ExperienceFacts(self_reported_months=vol.experience_months)
    skill = score_skills(needs, vol.skills)
    avail_pts = score_availability(availability)
    interest = score_interests(needs, vol.interests)
    exp_pts = score_experience(experience)
    exclusions = check_eligibility(needs, vol, skill, availability, conflict, registration_status)

    total = min(MAX_SCORE, _r(skill.points + avail_pts + interest.points + exp_pts))
    result = MatchResult(
        volunteer_id=vol.volunteer_id,
        full_name=vol.full_name,
        eligible=not exclusions,
        total_score=total,
        skill=skill,
        availability_points=avail_pts,
        interest=interest,
        experience_points=exp_pts,
        availability=availability,
        experience=experience,
        recent_assignments=recent_assignments,
        exclusions=exclusions,
    )
    result.explanation = build_explanation(result)
    result.summary = f"{vol.full_name} — {round(total)}/100"
    return result


def rank_results(results: list[MatchResult]) -> list[MatchResult]:
    """Best score first; inside a 2-point band the less-loaded volunteer comes first (fair distribution)."""
    return sorted(
        results,
        key=lambda r: (
            -(r.total_score // FAIR_BAND),
            r.recent_assignments,
            -r.total_score,
            r.full_name.casefold(),
            r.volunteer_id,
        ),
    )


def detect_skill_gap(slots_remaining: int, results: list[MatchResult], needs: ShiftNeeds) -> dict[str, Any]:
    eligible = [r for r in results if r.eligible]
    per_skill = []
    for skill in term_map(needs.required_skills).values():
        holders = sum(1 for r in eligible if skill in r.skill.matched_required)
        per_skill.append(
            {
                "skill": skill,
                "slots_needed": slots_remaining,
                "eligible_with_skill": holders,
                "shortage": max(0, slots_remaining - holders),
            }
        )
    counts: dict[str, int] = {}
    for r in results:
        if r.eligible:
            continue
        for code in {e.code for e in r.exclusions}:
            counts[code] = counts.get(code, 0) + 1
    partial = sum(
        1
        for r in results
        if not r.eligible
        and r.skill.matched_required
        and not any(e.code == ALREADY_REGISTERED for e in r.exclusions)
    )
    return {
        "slots_remaining": slots_remaining,
        "eligible_count": len(eligible),
        "gap": max(0, slots_remaining - len(eligible)),
        "per_skill": per_skill,
        "exclusion_counts": counts,
        "partially_matching_ineligible": partial,
    }


def result_to_dict(r: MatchResult) -> dict[str, Any]:
    return {
        "volunteer_id": r.volunteer_id,
        "volunteer_name": r.full_name,
        "eligible": r.eligible,
        "total_score": r.total_score,
        "max_score": MAX_SCORE,
        "scores": {
            "skills": r.skill.points,
            "availability": r.availability_points,
            "interests": r.interest.points,
            "experience": r.experience_points,
        },
        "matched_skills": r.skill.matched_required,
        "missing_required_skills": r.skill.missing_required,
        "matched_optional_skills": r.skill.matched_optional,
        "missing_optional_skills": r.skill.missing_optional,
        "matching_interests": r.interest.matched,
        "availability": {
            "covered": r.availability.covered,
            "code": r.availability.code,
            "detail": r.availability.detail,
        },
        "relevant_experience": {
            "completed_total": r.experience.completed_total,
            "completed_relevant": r.experience.completed_relevant,
            "self_reported_months": r.experience.self_reported_months,
        },
        "recent_assignments": r.recent_assignments,
        "exclusions": [{"code": e.code, "message": e.message} for e in r.exclusions],
        "explanation": r.explanation,
        "summary": r.summary,
        "invitation_status": None,
        "shortlisted": False,
    }
