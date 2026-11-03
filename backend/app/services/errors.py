"""
Domain errors for the scheduling engine.

Services raise these; a single exception handler in `main.py` converts them to
JSON responses of the form:

    {"detail": "<human readable message>", "code": "SCHEDULE_CONFLICT", "context": {...}}

`detail` matches FastAPI's own error shape so existing clients keep working;
`code` lets a frontend branch on the failure type without parsing text.
"""

from typing import Any


class SchedulingError(Exception):
    status_code: int = 400
    code: str = "SCHEDULING_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.context = context or {}

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"detail": self.message, "code": self.code}
        if self.context:
            body["context"] = self.context
        return body


class NotFoundError(SchedulingError):
    status_code = 404
    code = "NOT_FOUND"


class ForbiddenError(SchedulingError):
    status_code = 403
    code = "FORBIDDEN"


class ValidationFailed(SchedulingError):
    """Request is well-formed but violates a date/time/business validation rule."""

    status_code = 422
    code = "VALIDATION_ERROR"


class OutsideAvailabilityError(SchedulingError):
    status_code = 422
    code = "OUTSIDE_AVAILABILITY"


class ConflictError(SchedulingError):
    """Request conflicts with the current state of a resource."""

    status_code = 409
    code = "CONFLICT"


class ScheduleConflictError(ConflictError):
    code = "SCHEDULE_CONFLICT"


class ShiftFullError(ConflictError):
    code = "SHIFT_FULL"


class AlreadyRegisteredError(ConflictError):
    code = "ALREADY_REGISTERED"
