"""
database/models.py
──────────────────
Central import registry for ALL SQLAlchemy ORM models.

This file exists so that:
  1. Alembic's env.py has a single import to discover every table.
  2. SQLAlchemy can resolve all cross-model relationships at startup.
  3. app/main.py can trigger table creation with one import.

Rule: whenever you add a new model file under app/models/,
      add its import here too.
"""

# ── Module 1 & 2 core entities ────────────────────────────────────────────────
from app.models.user import User                      # noqa: F401
from app.models.ngo import NGO                        # noqa: F401
from app.models.volunteer import VolunteerProfile     # noqa: F401

# ── Module 1 – Events & Shifts ────────────────────────────────────────────────
from app.models.event import Event                    # noqa: F401
from app.models.shift import Shift                    # noqa: F401

# ── Module 3 – Registrations & Availability (Scheduling Engine) ──────────────
from app.models.registration import Registration      # noqa: F401
from app.models.availability import VolunteerAvailability  # noqa: F401

# ── Module 4 – Matching & invitations ─────────────────────────────────────────
from app.models.matching import (                     # noqa: F401
    EventMatchingProfile,
    ShiftRequirement,
    VolunteerInvitation,
    VolunteerShortlist,
)

# ── Future modules – uncomment as you implement them ──────────────────────────
# from app.models.notification import Notification    # noqa: F401  Module 6
# from app.models.attendance import Attendance        # noqa: F401  Module 7

__all__ = [
    "User",
    "NGO",
    "VolunteerProfile",
    "Event",
    "Shift",
    "Registration",
    "VolunteerAvailability",
    "ShiftRequirement",
    "EventMatchingProfile",
    "VolunteerShortlist",
    "VolunteerInvitation",
]
