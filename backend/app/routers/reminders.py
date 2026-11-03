"""
routers/reminders.py
─────────────────────
Module 6: Reminder & Notification Management

TODO (Member 3): Implement using services/notifications.py

Planned endpoints:
  GET  /api/v1/reminders/my           – Volunteer's upcoming reminders
  POST /api/v1/reminders/trigger      – Admin triggers a reminder batch
  GET  /api/v1/reminders/queue        – Admin views notification queue
"""

from fastapi import APIRouter

router = APIRouter(prefix="/reminders", tags=["Reminders & Notifications"])


@router.get("/", summary="[Module 6 – Reminders] Coming soon")
def reminders_placeholder():
    return {
        "status": "not_implemented",
        "module": "Module 6 – Reminder & Notification Management",
        "description": (
            "In-app reminder queue, shift reminders, registration confirmations, "
            "and waitlist promotion notifications will be implemented here."
        ),
    }
