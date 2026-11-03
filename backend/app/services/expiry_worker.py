"""
Background sweep that expires overdue invitations without waiting for someone to
list/accept them. Runs inside the API process every
`invitation_expiry_interval_seconds` (default 60; set 0 to disable). Safe with
several workers: the sweep uses SELECT ... FOR UPDATE SKIP LOCKED.
"""

import asyncio
import logging

from app.core.config import get_settings
from app.database.connection import SessionLocal
from app.services.invitation_service import expire_due_invitations

log = logging.getLogger(__name__)
_task: asyncio.Task | None = None


def _sweep_once() -> None:
    db = SessionLocal()
    try:
        changed = expire_due_invitations(db)
        if changed:
            log.info("Invitation sweep: %s invitation(s) expired/cancelled", changed)
    except Exception:  # never let the loop die
        log.exception("Invitation expiry sweep failed")
    finally:
        db.close()


async def _loop(interval: int) -> None:
    while True:
        await asyncio.sleep(interval)
        await asyncio.to_thread(_sweep_once)


async def start() -> None:
    global _task
    interval = get_settings().invitation_expiry_interval_seconds
    if interval > 0 and _task is None:
        _task = asyncio.create_task(_loop(interval))


async def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
