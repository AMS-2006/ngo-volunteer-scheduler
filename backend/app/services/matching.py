"""
services/matching.py
─────────────────────
Module 4 facade – public entry points of the Volunteer Matching engine.

Implementation lives in:
  match_scoring.py          pure scoring / eligibility / ranking / explanations
  recommendation_service.py DB layer (reuses Module 3 availability, conflict, capacity)
  invitation_service.py     shortlist + invitation workflow (accept -> Module 3 register)
"""

from app.services.invitation_service import (  # noqa: F401
    accept,
    cancel,
    decline,
    expire_due_invitations,
    invite,
    list_invitations,
    shortlist,
)
from app.services.match_scoring import (  # noqa: F401
    MAX_SCORE,
    detect_skill_gap,
    evaluate_match,
    rank_results,
)
from app.services.recommendation_service import (  # noqa: F401
    event_recommendations,
    shift_recommendations,
    volunteer_recommendations,
    volunteer_shift_match,
)

# Backwards-compatible alias for the original Module 4 stub name.
calculate_match_score = evaluate_match
