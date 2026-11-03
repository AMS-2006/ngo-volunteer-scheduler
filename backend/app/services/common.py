"""Small shared helpers for the scheduling services."""

from datetime import date, datetime, time, timezone

DAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def hhmm(value: time) -> str:
    return value.strftime("%H:%M")


def pretty_date(value: date) -> str:
    return f"{value:%a %d %b %Y}"


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp for audit columns (created_at, cancelled_at, …)."""
    return datetime.now(timezone.utc)
