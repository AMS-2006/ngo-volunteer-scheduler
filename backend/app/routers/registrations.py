"""
routers/registrations.py
─────────────────────────
Module 3: Smart Shift Scheduling Engine – registration endpoints.

TODO (Member 2): Implement these endpoints using services/scheduling.py

Planned endpoints:
  POST   /api/v1/registrations/             – Register for a shift (conflict check + capacity)
  DELETE /api/v1/registrations/{id}         – Cancel a registration
  GET    /api/v1/registrations/my           – My current registrations (volunteer)
  GET    /api/v1/registrations/shift/{id}   – All registrations for a shift (admin)
"""

from fastapi import APIRouter

router = APIRouter(prefix="/registrations", tags=["Shift Registrations"])


@router.get("/", summary="[Module 3 – Scheduling Engine] Coming soon")
def registrations_placeholder():
    return {
        "status": "not_implemented",
        "module": "Module 3 – Scheduling Engine",
        "description": (
            "Registration endpoints with conflict detection, capacity management, "
            "and waitlist promotion will be implemented here."
        ),
    }
