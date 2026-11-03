"""Shared schema helpers."""

from datetime import time


def normalise_time(value: time) -> time:
    """Wall-clock times only: no timezone offsets, minute precision."""
    if value.tzinfo is not None:
        raise ValueError("Use local wall-clock times without a timezone offset, e.g. 09:00.")
    return value.replace(second=0, microsecond=0)
