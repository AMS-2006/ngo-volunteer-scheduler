"""Pure unit tests for Module 4 scoring (no database required)."""

from app.services import match_scoring as ms

AVAIL = ms.AvailabilityResult(True)


def needs(**kw):
    base = dict(
        required_skills=("First Aid", "CPR"),
        optional_skills=(),
        categories=("Health",),
        skills_mandatory=True,
        required_city=None,
    )
    base.update(kw)
    return ms.ShiftNeeds(**base)


def vol(**kw):
    base = dict(
        volunteer_id="v1",
        full_name="Rahul",
        is_active=True,
        has_profile=True,
        skills=("First Aid", "CPR"),
        interests=("Health",),
        city="Pune",
        experience_months=24,
    )
    base.update(kw)
    return ms.VolunteerFacts(**base)


def run(n=None, v=None, availability=AVAIL, conflict=None, reg=None, exp=None, load=0):
    return ms.evaluate_match(n or needs(), v or vol(), availability, conflict, reg, exp, load)


# 1 ─ perfect match
def test_perfect_match_scores_100():
    r = run(exp=ms.ExperienceFacts(completed_total=10, completed_relevant=4, self_reported_months=24))
    assert r.eligible and r.total_score == 100.0
    assert (r.skill.points, r.availability_points, r.interest.points, r.experience_points) == (40.0, 30.0, 20.0, 10.0)
    assert r.summary == "Rahul — 100/100"
    assert r.explanation[0].startswith("All required skills matched")


# 2 ─ partial skills (non-mandatory) still scored proportionally
def test_partial_skill_match_is_proportional():
    n = needs(required_skills=("a", "b", "c", "d"), skills_mandatory=False)
    r = run(n, vol(skills=("a", "b")))
    assert r.skill.points == 20.0 and r.eligible
    assert r.skill.missing_required == ["c", "d"]


def test_required_and_optional_split():
    n = needs(required_skills=("a", "b"), optional_skills=("x", "y"))
    r = run(n, vol(skills=("a", "b", "x")))
    assert r.skill.points == 40 * (0.75 * 1 + 0.25 * 0.5)  # 35.0
    assert r.skill.missing_optional == ["y"] and r.skill.matched_optional == ["x"]


# 3 ─ missing mandatory skills -> ineligible
def test_missing_mandatory_skill_excludes():
    r = run(v=vol(skills=("First Aid",)))
    assert not r.eligible
    assert [e.code for e in r.exclusions] == [ms.MISSING_MANDATORY_SKILLS]
    assert "CPR" in r.exclusions[0].message


# 4 ─ unavailable (partial availability is rejected, 0 availability points)
def test_unavailable_volunteer_excluded():
    r = run(availability=ms.AvailabilityResult(False, "OUTSIDE_AVAILABILITY", "outside declared availability"))
    assert not r.eligible and r.availability_points == 0.0
    assert ms.NOT_AVAILABLE in [e.code for e in r.exclusions]


# 5 ─ existing scheduling conflict
def test_scheduling_conflict_excluded():
    r = run(conflict="Already confirmed 09:00-11:00")
    assert not r.eligible and ms.SCHEDULE_CONFLICT in [e.code for e in r.exclusions]


# 6 ─ interests
def test_interest_scoring_is_normalized():
    n = needs(categories=("Health", "Education", "Environment", "Animals"))
    r = run(n, vol(interests=("health", "EDUCATION")))
    assert r.interest.points == 10.0 and r.interest.matched == ["Health", "Education"]
    assert run(n, vol(interests=())).interest.points == 0.0


# 7 ─ experience
def test_experience_scoring():
    assert ms.score_experience(ms.ExperienceFacts(2, 2, 0)) == round(5 * 2 / 4 + 3 * 2 / 10, 1)  # 3.1
    assert ms.score_experience(ms.ExperienceFacts()) == 0.0
    assert ms.score_experience(ms.ExperienceFacts(0, 0, 12)) == 1.0


# 8 ─ normalisation / caps
def test_scores_are_capped_and_add_up():
    huge = ms.ExperienceFacts(completed_total=999, completed_relevant=999, self_reported_months=999)
    r = run(exp=huge)
    assert r.experience_points == 10.0 and r.total_score <= ms.MAX_SCORE
    parts = r.skill.points + r.availability_points + r.interest.points + r.experience_points
    assert abs(r.total_score - parts) < 0.11


# 9 ─ missing profile information is not a match
def test_missing_profile_is_not_a_match():
    r = run(v=vol(has_profile=False, skills=(), interests=()))
    assert not r.eligible
    assert ms.PROFILE_MISSING in [e.code for e in r.exclusions]
    assert r.skill.points == 0.0 and r.interest.points == 0.0


def test_location_constraint():
    n = needs(required_city="Pune")
    assert run(n, vol(city="  pune ")).eligible
    assert ms.LOCATION_MISMATCH in [e.code for e in run(n, vol(city="Delhi")).exclusions]
    assert ms.LOCATION_UNKNOWN in [e.code for e in run(n, vol(city=None)).exclusions]


def test_inactive_and_already_registered_excluded():
    r = run(v=vol(is_active=False), reg="CONFIRMED")
    assert {e.code for e in r.exclusions} == {ms.ACCOUNT_INACTIVE, ms.ALREADY_REGISTERED}


# 10 ─ duplicate skills never inflate
def test_duplicate_skills_do_not_inflate():
    n = needs(required_skills=("First Aid", "first  aid", "FIRST AID"), categories=())
    r = run(n, vol(skills=("First Aid", "first aid", " FIRST AID ")))
    assert r.skill.required_total == 1 and r.skill.matched_required == ["First Aid"]
    assert r.skill.points == 40.0


def test_unconfigured_requirements_are_vacuous_not_volunteer_dependent():
    n = needs(required_skills=(), categories=())
    a, b = run(n, vol(skills=(), interests=())), run(n, vol())
    assert a.skill.points == b.skill.points == 40.0 and not a.skill.configured


# 11 & 12 ─ no eligible volunteers + skill-gap detection
def test_no_eligible_volunteers_gap_equals_remaining():
    n = needs()
    results = [run(n, vol(volunteer_id=f"v{i}", skills=())) for i in range(3)]
    gap = ms.detect_skill_gap(10, results, n)
    assert gap["eligible_count"] == 0 and gap["gap"] == 10
    assert all(s["shortage"] == 10 for s in gap["per_skill"])


def test_skill_gap_scenario_ten_first_aiders():
    n = needs(required_skills=("First Aid",), categories=())
    results = (
        [run(n, vol(volunteer_id=f"ok{i}", skills=("First Aid",))) for i in range(4)]
        + [run(n, vol(volunteer_id=f"part{i}", skills=("First Aid",)), conflict="busy") for i in range(4)]
        + [run(n, vol(volunteer_id=f"none{i}", skills=())) for i in range(2)]
    )
    gap = ms.detect_skill_gap(10, results, n)
    assert gap["eligible_count"] == 4 and gap["gap"] == 6
    assert gap["per_skill"][0] == {"skill": "First Aid", "slots_needed": 10, "eligible_with_skill": 4, "shortage": 6}
    assert gap["exclusion_counts"][ms.SCHEDULE_CONFLICT] == 4
    assert gap["exclusion_counts"][ms.MISSING_MANDATORY_SKILLS] == 2
    assert gap["partially_matching_ineligible"] == 4


def test_gap_never_negative():
    n = needs(required_skills=(), categories=())
    results = [run(n, vol(volunteer_id=f"v{i}")) for i in range(5)]
    assert ms.detect_skill_gap(2, results, n)["gap"] == 0


# ranking / fairness / determinism
def test_fair_distribution_breaks_ties_within_band():
    busy = run(v=vol(volunteer_id="busy", full_name="Busy"), load=6)
    idle = run(v=vol(volunteer_id="idle", full_name="Idle"), load=0)
    assert [r.volunteer_id for r in ms.rank_results([busy, idle])] == ["idle", "busy"]
    low = run(v=vol(volunteer_id="low", full_name="Low", skills=("First Aid",)), load=0)
    assert ms.rank_results([low, busy])[0].volunteer_id == "busy"  # clearly higher score still wins


def test_explanations_are_deterministic():
    assert run().explanation == run().explanation
    d = ms.result_to_dict(run())
    assert d["max_score"] == 100.0 and set(d["scores"]) == {"skills", "availability", "interests", "experience"}
