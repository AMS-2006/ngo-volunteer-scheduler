"""
services/matching.py
─────────────────────
Module 4: Volunteer Matching & Recommendation Engine

Weighted rule-based algorithm (100 points total):
  • Skill match:        40 pts
  • Availability match: 30 pts
  • Interest match:     20 pts
  • Experience score:   10 pts

TODO (Member 2): Implement score calculation and recommendation queries.
"""


def calculate_match_score(volunteer_profile, event_or_shift) -> dict:
    """
    Compute a 0–100 compatibility score for a volunteer against an event/shift.

    Args:
        volunteer_profile: VolunteerProfile ORM object
        event_or_shift:    Event or Shift ORM object

    Returns:
        {
          "score": int,           # 0–100
          "skill_score": int,     # 0–40
          "availability_score": int,  # 0–30
          "interest_score": int,  # 0–20
          "experience_score": int,    # 0–10
          "breakdown": str        # Human-readable explanation
        }

    TODO: Implement in Module 4.
    """
    raise NotImplementedError("Pending Module 4 implementation.")


def get_recommended_volunteers(event_id: str, db, top_n: int = 10) -> list:
    """
    Return the top N volunteers ranked by match score for an event.
    Filters out volunteers already registered for conflicting shifts.

    TODO: Implement in Module 4.
    """
    raise NotImplementedError("Pending Module 4 implementation.")
