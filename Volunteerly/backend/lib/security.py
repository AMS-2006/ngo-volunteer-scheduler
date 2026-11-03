"""Sessions (httpOnly cookie) + role guards. Role is always read from the DB, never from the client."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response

from lib.db import db

COOKIE = "vc_session"
SESSION_DAYS = 14


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        salt, dk = stored.split("$")
    except ValueError:
        return False
    test = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000)
    return hmac.compare_digest(test.hex(), dk)


async def create_session(request: Request, response: Response, user_id: str) -> None:
    token = secrets.token_urlsafe(32)
    await db.sessions.insert_one({"token": token, "user_id": user_id,
                                  "expires_at": datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)})
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=secure,
                        max_age=SESSION_DAYS * 86400, path="/")


async def current_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Not authenticated")
    sess = await db.sessions.find_one({"token": token})
    if not sess or sess["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(401, "Session expired")
    user = await db.users.find_one({"id": sess["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


async def require_ngo(user: dict = Depends(current_user)) -> tuple[dict, dict]:
    if user["role"] != "ngo":
        raise HTTPException(403, "NGO account required")
    ngo = await db.ngo_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not ngo:
        raise HTTPException(403, "NGO profile missing")
    return user, ngo


async def require_volunteer(user: dict = Depends(current_user)) -> tuple[dict, dict]:
    if user["role"] != "volunteer":
        raise HTTPException(403, "Volunteer account required")
    vol = await db.volunteer_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not vol:
        raise HTTPException(403, "Volunteer profile missing")
    return user, vol
