import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from lib.db import db
from lib.email import send_email
from lib.logic import new_id, now_iso
from lib.security import COOKIE, create_session, current_user, hash_password, verify_password
from models.schemas import ForgotIn, LanguageIn, LoginIn, MessageOut, RegisterIn, ResetIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


async def user_out(user: dict) -> dict:
    coll = db.ngo_profiles if user["role"] == "ngo" else db.volunteer_profiles
    prof = await coll.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    return {**user, "profile_id": prof["id"] if prof else None}


@router.post("/register", response_model=UserOut)
async def register(body: RegisterIn, request: Request, response: Response):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "An account with this email already exists.")
    if body.role == "ngo" and (len(body.description.strip()) < 10 or not body.causes):
        raise HTTPException(400, "NGOs must provide a description (10+ characters) and at least one area of work.")
    uid = new_id()
    user = {"id": uid, "role": body.role, "full_name": body.full_name.strip(), "email": email,
            "phone": body.phone, "preferred_language": body.preferred_language, "created_at": now_iso(),
            "password_hash": hash_password(body.password), "is_demo": False}
    await db.users.insert_one(dict(user))
    if body.role == "ngo":
        await db.ngo_profiles.insert_one({
            "id": new_id(), "user_id": uid, "organization_name": user["full_name"], "description": body.description,
            "logo_url": "", "contact_email": email, "contact_number": body.phone, "location": body.location,
            "latitude": body.latitude, "longitude": body.longitude, "causes": body.causes,
            "verification_status": "pending", "is_demo": False})
    else:
        await db.volunteer_profiles.insert_one({
            "id": new_id(), "user_id": uid, "name": user["full_name"], "profile_image": "", "phone": body.phone,
            "location": body.location, "latitude": body.latitude, "longitude": body.longitude, "skills": [],
            "interests": [], "preferred_activities": [], "availability": {"days": [], "slots": []},
            "preferred_language": body.preferred_language, "languages_spoken": [], "preferred_travel_radius": 15,
            "privacy": {"share_location": True, "share_contact": False, "replacement_opt_in": True}, "is_demo": False})
    await create_session(request, response, uid)
    user.pop("password_hash")
    return await user_out(user)


@router.post("/login", response_model=UserOut)
async def login(body: LoginIn, request: Request, response: Response):
    user = await db.users.find_one({"email": body.email.lower()}, {"_id": 0})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password.")
    await create_session(request, response, user["id"])
    user.pop("password_hash")
    return await user_out(user)


@router.post("/logout", response_model=MessageOut)
async def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        await db.sessions.delete_one({"token": token})
    response.delete_cookie(COOKIE, path="/")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(current_user)):
    user.pop("password_hash", None)
    return await user_out(user)


@router.get("/session", response_model=Optional[UserOut])
async def session(request: Request):
    """Signed-out-friendly probe: 200 with the user, or 200 null when there is no valid session."""
    try:
        user = await current_user(request)
    except HTTPException:
        return None
    user.pop("password_hash", None)
    return await user_out(user)


@router.patch("/language", response_model=UserOut)
async def set_language(body: LanguageIn, user: dict = Depends(current_user)):
    await db.users.update_one({"id": user["id"]}, {"$set": {"preferred_language": body.preferred_language}})
    await db.volunteer_profiles.update_one({"user_id": user["id"]}, {"$set": {"preferred_language": body.preferred_language}})
    user["preferred_language"] = body.preferred_language
    user.pop("password_hash", None)
    return await user_out(user)


GENERIC = "If an account exists for that email, a password reset link has been sent."


@router.post("/forgot-password", response_model=MessageOut)
async def forgot_password(body: ForgotIn):
    user = await db.users.find_one({"email": body.email.lower()}, {"_id": 0})
    if not user:
        return {"message": GENERIC}
    if user.get("is_demo"):
        # Seeded demo inboxes are fictional — no email is sent to them.
        return {"message": "This is a seeded demo account with a fictional inbox, so no email was sent. Demo password: Demo@1234"}
    recent = await db.password_resets.count_documents(
        {"user_id": user["id"], "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(minutes=10)}})
    if recent >= 3:
        return {"message": GENERIC}
    token = secrets.token_urlsafe(32)
    await db.password_resets.insert_one({"token": token, "user_id": user["id"], "used": False,
                                         "created_at": datetime.now(timezone.utc),
                                         "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)})
    app_url = os.environ.get("APP_URL", "").rstrip("/")
    link = f"{app_url}/reset-password?token={token}"
    brand = escape(os.environ.get("EMAIL_FROM_NAME", "Volunteer Connect"))
    html = (f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;color:#0f172a">'
            f'<h2 style="color:#0284c7;margin:0 0 12px">{brand}</h2>'
            f'<p>Hi {escape(user["full_name"])},</p>'
            f'<p>We received a request to reset your password. This link is valid for 1 hour and can be used once.</p>'
            f'<p><a href="{escape(link)}" style="display:inline-block;background:#0284c7;color:#ffffff;padding:10px 18px;'
            f'border-radius:8px;text-decoration:none">Reset my password</a></p>'
            f'<p style="font-size:13px;color:#475569">If you did not request this, you can ignore this email.</p>'
            f'<p style="font-size:12px;color:#888">Sent by {brand}. We never ask for your password by email.</p>'
            f'</td></tr></table>')
    await send_email(to=user["email"], subject=f"Reset your {brand} password", html=html)
    return {"message": GENERIC}


@router.post("/reset-password", response_model=MessageOut)
async def reset_password(body: ResetIn):
    rec = await db.password_resets.find_one_and_update(
        {"token": body.token, "used": False}, {"$set": {"used": True}})
    if not rec or rec["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(400, "This reset link is invalid or has expired.")
    await db.users.update_one({"id": rec["user_id"]}, {"$set": {"password_hash": hash_password(body.password)}})
    await db.sessions.delete_many({"user_id": rec["user_id"]})
    return {"message": "Password updated. Please sign in with your new password."}
