"""
models/__init__.py

Imports all ORM models so that:
  • Alembic's `env.py` can discover every table via `Base.metadata`.
  • SQLAlchemy's relationship resolution works across modules.

When you add a new model, import it here.
"""

from app.models.user import User  # noqa: F401
from app.models.volunteer import VolunteerProfile  # noqa: F401

# Module 3 – Scheduling engine (Event is a minimal shell until Module 1 extends it)
from app.models.event import Event  # noqa: F401
from app.models.shift import Shift  # noqa: F401
from app.models.registration import Registration  # noqa: F401
from app.models.availability import VolunteerAvailability  # noqa: F401

# Future modules – uncomment as you build them:
# from app.models.notification import Notification # noqa: F401 – Module 6
# from app.models.attendance import Attendance     # noqa: F401 – Module 7

__all__ = [
    "User",
    "VolunteerProfile",
    "Event",
    "Shift",
    "Registration",
    "VolunteerAvailability",
]
