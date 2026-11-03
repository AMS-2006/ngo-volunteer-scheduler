"""Shared Mongo handle — import `client`/`db` from here (server.py, routers, seed.py)."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel

load_dotenv(Path(__file__).parent.parent / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

logger = logging.getLogger(__name__)

# One entry per collection: every field a route filters, sorts, or dedupes on. Applied by ensure_indexes() at startup.
INDEXES: dict[str, list[IndexModel]] = {
    "users": [IndexModel([("id", ASCENDING)], name="id", unique=True),
              IndexModel([("email", ASCENDING)], name="email", unique=True)],
    "sessions": [IndexModel([("token", ASCENDING)], name="token", unique=True),
                 IndexModel([("expires_at", ASCENDING)], name="ttl", expireAfterSeconds=0)],
    "password_resets": [IndexModel([("token", ASCENDING)], name="token", unique=True)],
    "ngo_profiles": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                     IndexModel([("user_id", ASCENDING)], name="user_id", unique=True)],
    "volunteer_profiles": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                           IndexModel([("user_id", ASCENDING)], name="user_id", unique=True)],
    "events": [IndexModel([("id", ASCENDING)], name="id", unique=True),
               IndexModel([("ngo_id", ASCENDING), ("event_date", ASCENDING)], name="ngo_date"),
               IndexModel([("status", ASCENDING), ("event_date", ASCENDING)], name="status_date")],
    "shifts": [IndexModel([("id", ASCENDING)], name="id", unique=True),
               IndexModel([("event_id", ASCENDING)], name="event_id"),
               IndexModel([("shift_date", ASCENDING)], name="shift_date")],
    "registrations": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                      # one active registration per volunteer per shift — DB-level duplicate guard
                      IndexModel([("volunteer_id", ASCENDING), ("shift_id", ASCENDING)], name="active_unique",
                                 unique=True, partialFilterExpression={"active": True}),
                      IndexModel([("shift_id", ASCENDING), ("active", ASCENDING)], name="shift_active"),
                      IndexModel([("event_id", ASCENDING)], name="event_id")],
    "replacement_invitations": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                                IndexModel([("shift_id", ASCENDING)], name="shift_id"),
                                IndexModel([("invited_volunteer_id", ASCENDING)], name="invited")],
    "notifications": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                      IndexModel([("recipient_user_id", ASCENDING), ("created_at", DESCENDING)], name="recipient"),
                      IndexModel([("dedupe_key", ASCENDING)], name="dedupe", unique=True, sparse=True)],
    "attendance": [IndexModel([("registration_id", ASCENDING)], name="registration_id", unique=True)],
}


async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:  # one at a time so a bad spec skips only itself
            try:
                await db[collection].create_indexes([model])
            except Exception as exc:  # never block boot on an index; the log line names what to fix
                logger.error("ensure_indexes(%s.%s): %s", collection, model.document["name"], exc)
