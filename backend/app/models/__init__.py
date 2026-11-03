"""
models/__init__.py
Central import registry for ALL SQLAlchemy ORM models.
"""

from app.models.user import User  # noqa: F401
from app.models.ngo import NGO  # noqa: F401
from app.models.volunteer import VolunteerProfile  # noqa: F401
from app.models.event import Event  # noqa: F401
from app.models.shift import Shift  # noqa: F401
from app.models.registration import Registration  # noqa: F401
from app.models.availability import VolunteerAvailability  # noqa: F401

__all__ = [
    "User",
    "NGO",
    "VolunteerProfile",
    "Event",
    "Shift",
    "Registration",
    "VolunteerAvailability",
]
