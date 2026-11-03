"""
Clock helper.

Shift dates/times are stored as *naive local wall-clock* values (an NGO event
at 09:00 means 09:00 where the event happens), so "is this shift in the future?"
must be answered against the server's local wall clock.

Always call `clock.now()` (module attribute access) so tests can patch it.
"""

from datetime import datetime


def now() -> datetime:
    """Current local wall-clock time (naive)."""
    return datetime.now()
