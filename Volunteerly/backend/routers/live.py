"""Live refresh counter + scheduled invitation expiry."""
import asyncio
import hmac
import logging
import os
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo.errors import DuplicateKeyError

from lib.db import db
from lib.logic import process_expired_invitations
from lib.security import current_user
from models.schemas import LiveOut, MessageOut

router = APIRouter(tags=["live"])
logger = logging.getLogger(__name__)
_last_sweep = 0.0
SWEEP_EVERY_S = 60  # while anyone is online, expiries are processed within ~1 minute


async def _sweep():
    try:
        res = await process_expired_invitations()
        if res["expired"]:
            logger.info("Invitation sweep: %s", res)
    except Exception:  # noqa: BLE001
        logger.exception("Invitation sweep failed")


@router.get("/live", response_model=LiveOut)
async def live(user: dict = Depends(current_user)):
    """Polled by signed-in clients every few seconds; when `version` changes they refetch their views."""
    global _last_sweep
    if time.monotonic() - _last_sweep > SWEEP_EVERY_S:
        _last_sweep = time.monotonic()
        asyncio.create_task(_sweep())
    doc = await db.meta.find_one({"_id": "live"})
    return {"version": int(doc["v"]) if doc else 0}


@router.post("/cron/expire-invites", response_model=MessageOut, status_code=202)
async def cron_expire_invites(request: Request):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not secret or not token or not hmac.compare_digest(token, secret):
        raise HTTPException(401, "Unauthorized")
    try:
        body = await request.json()
    except ValueError:
        body = None
    if body is not None and not isinstance(body, dict):
        raise HTTPException(400, "Invalid body")
    run_id = request.headers.get("x-webhook-id") or (body or {}).get("run_id")
    if run_id:
        try:
            await db.cron_runs.insert_one({"_id": run_id, "job": "expire-invites", "at": time.time()})
        except DuplicateKeyError:
            return {"message": "duplicate"}
    asyncio.create_task(_sweep())
    return {"message": "accepted"}
