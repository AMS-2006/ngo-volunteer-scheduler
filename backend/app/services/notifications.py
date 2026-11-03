"""
services/notifications.py
──────────────────────────
Module 6: Reminder & Notification Management

Manages an in-app notification queue (simulated for hackathon).
No external email/SMS service required — reminders are stored in DB
and displayed on the volunteer's dashboard.

Notification types:
  • REGISTRATION_CONFIRMED  – shift registration successful
  • REGISTRATION_CANCELLED  – registration cancelled
  • WAITLIST_PROMOTED       – promoted from waitlist to confirmed
  • SHIFT_REMINDER          – upcoming shift reminder (T-24h, T-1h)
  • EVENT_UPDATE            – event details changed
"""


def queue_registration_confirmation(volunteer_id: str, shift_id: str, db):
    """
    Create an in-app notification confirming a shift registration.
    TODO (Member 3): Implement in Module 6.
    """
    raise NotImplementedError("Pending Module 6 implementation.")


def queue_shift_reminder(volunteer_id: str, shift_id: str, db):
    """
    Queue a reminder notification for an upcoming shift.
    Called by a background task that checks for shifts in the next 24 hours.
    TODO (Member 3): Implement in Module 6.
    """
    raise NotImplementedError("Pending Module 6 implementation.")


def queue_waitlist_promotion(volunteer_id: str, shift_id: str, db):
    """
    Notify a volunteer that they've been promoted from waitlist to confirmed.
    TODO (Member 3): Implement in Module 6.
    """
    raise NotImplementedError("Pending Module 6 implementation.")


def get_unread_notifications(volunteer_id: str, db) -> list:
    """
    Return all unread notifications for a volunteer.
    TODO (Member 3): Implement in Module 6.
    """
    raise NotImplementedError("Pending Module 6 implementation.")
