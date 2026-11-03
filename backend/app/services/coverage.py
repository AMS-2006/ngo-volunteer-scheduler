"""
services/coverage.py
─────────────────────
Module 5: Coverage & Analytics Dashboard

Calculates staffing gaps and coverage status for events and shifts.

Coverage Ratio  = Registered / Required
Status:
  GREEN  (Full)     : ratio >= 1.0
  YELLOW (Partial)  : 0.5 <= ratio < 1.0
  RED    (Critical) : ratio < 0.5
"""

from enum import Enum


class CoverageStatus(str, Enum):
    FULL = "full"           # Green
    PARTIAL = "partial"     # Yellow
    CRITICAL = "critical"   # Red


def get_coverage_status(required: int, registered: int) -> CoverageStatus:
    """
    Classify a shift's staffing status.

    >>> get_coverage_status(10, 10)  # Full
    CoverageStatus.FULL
    >>> get_coverage_status(10, 7)   # Partial
    CoverageStatus.PARTIAL
    >>> get_coverage_status(10, 3)   # Critical
    CoverageStatus.CRITICAL
    """
    if required == 0:
        return CoverageStatus.FULL
    ratio = registered / required
    if ratio >= 1.0:
        return CoverageStatus.FULL
    elif ratio >= 0.5:
        return CoverageStatus.PARTIAL
    else:
        return CoverageStatus.CRITICAL


def calculate_coverage_gap(required: int, registered: int) -> int:
    """Returns how many more volunteers are needed. 0 if fully staffed."""
    return max(0, required - registered)


def get_event_coverage_report(event_id: str, db) -> dict:
    """
    Build a full coverage report for all shifts of an event.

    Returns:
        {
          "event_id": str,
          "total_required": int,
          "total_registered": int,
          "coverage_gap": int,
          "overall_status": CoverageStatus,
          "shifts": [
            { "shift_id", "name", "required", "registered", "gap", "status" }, ...
          ]
        }

    TODO (Member 3): Implement with DB queries in Module 5.
    """
    raise NotImplementedError("Pending Module 5 implementation.")
