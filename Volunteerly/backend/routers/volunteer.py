"""Volunteer-only routes + shared public event discovery, notifications and uploads."""
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pymongo.errors import DuplicateKeyError

from lib.db import db
from lib.logic import (CATEGORY_INTEREST, P, availability_score, build_event_cards, find_conflict, fmt_shift, new_id,
                       notify, now_iso, now_local, registration_open, shift_hours, shift_start, target_skills_for,
                       find_candidates)
from lib.security import current_user, require_volunteer
from models.schemas import (EventCard, EventDetail, Invitation, MessageOut, MyRegistration, NgoPublic, Notification,
                            RegisterShiftIn, RespondIn, UploadOut, VolAnalytics, VolDashboard, VolunteerProfile,
                            VolunteerProfileIn)

router = APIRouter(tags=["volunteer"])
UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


async def my_rows(regs: list[dict]) -> list[dict]:
    if not regs:
        return []
    shifts = {s["id"]: s for s in await db.shifts.find({"id": {"$in": [r["shift_id"] for r in regs]}}, P).to_list(10000)}
    events = {e["id"]: e for e in await db.events.find({"id": {"$in": [r["event_id"] for r in regs]}}, P).to_list(10000)}
    ngos = {n["id"]: n for n in await db.ngo_profiles.find({"id": {"$in": [e["ngo_id"] for e in events.values()]}}, P).to_list(1000)}
    att = {a["registration_id"]: a for a in await db.attendance.find({"registration_id": {"$in": [r["id"] for r in regs]}}, P).to_list(10000)}
    now = now_local()
    out = []
    for r in regs:
        s, e = shifts.get(r["shift_id"]), events.get(r["event_id"])
        if not (s and e):
            continue
        out.append({**r, "event_title": e["title"], "event_location": e["location"], "category": e["category"],
                    "ngo_id": e["ngo_id"], "ngo_name": ngos.get(e["ngo_id"], {}).get("organization_name", ""),
                    "shift_date": s["shift_date"], "start_time": s["start_time"], "end_time": s["end_time"],
                    "hours": shift_hours(s), "attendance": att.get(r["id"]),
                    "can_cancel": r["registration_status"] == "confirmed" and shift_start(s) > now})
    return sorted(out, key=lambda x: (x["shift_date"], x["start_time"]))


async def generate_reminders(user: dict):
    """In-app reminders 24h and 2h before a shift (generated on read; no push/email/SMS)."""
    vol = await db.volunteer_profiles.find_one({"user_id": user["id"]}, P)
    if not vol:
        return
    regs = await db.registrations.find({"volunteer_id": vol["id"], "registration_status": "confirmed"}, P).to_list(1000)
    now = now_local()
    for row in await my_rows(regs):
        start = datetime.fromisoformat(f"{row['shift_date']}T{row['start_time']}")
        delta = start - now
        for key, window in (("reminder_24h", timedelta(hours=24)), ("reminder_2h", timedelta(hours=2))):
            if timedelta(0) < delta <= window:
                await notify(user["id"], key, f"Reminder: {row['event_title']}",
                             f"Your shift at {row['event_location']} starts {row['shift_date']} at {row['start_time']}.",
                             {"event": row["event_title"], "location": row["event_location"],
                              "shift": f"{row['shift_date']} {row['start_time']}"},
                             row["event_id"], row["shift_id"], dedupe_key=f"{key}:{row['id']}")


# ---------- public discovery (any signed-in user) ----------
@router.get("/events", response_model=list[EventCard])
async def discover(q: str = "", category: str = "", location: str = "", date_from: str = "", date_to: str = "",
                   skill: str = "", user: dict = Depends(current_user)):
    query: dict = {"status": "published", "event_date": {"$gte": date_from or now_local().date().isoformat()}}
    if date_to:
        query["event_date"]["$lte"] = date_to
    if category:
        query["category"] = category
    if skill:
        query["required_skills"] = skill
    if location:
        query["location"] = {"$regex": location, "$options": "i"}
    events = await db.events.find(query, P).sort("event_date", 1).to_list(1000)
    vol = await db.volunteer_profiles.find_one({"user_id": user["id"]}, P)
    cards = await build_event_cards(events, vol["id"] if vol else None)
    if q:
        ql = q.lower()
        cards = [c for c in cards if ql in c["title"].lower() or ql in c["ngo_name"].lower()]
    return cards


@router.get("/events/{event_id}", response_model=EventDetail)
async def event_detail(event_id: str, user: dict = Depends(current_user)):
    ev = await db.events.find_one({"id": event_id}, P)
    own = False
    if ev and user["role"] == "ngo":
        ngo = await db.ngo_profiles.find_one({"user_id": user["id"]}, P)
        own = bool(ngo and ngo["id"] == ev["ngo_id"])
    if not ev or (ev["status"] != "published" and not own):
        raise HTTPException(404, "Event not found")
    vol = await db.volunteer_profiles.find_one({"user_id": user["id"]}, P)
    card = (await build_event_cards([ev], vol["id"] if vol else None, with_shifts=True))[0]
    card["ngo"] = await ngo_public(ev["ngo_id"])
    return card


async def ngo_public(ngo_id: str) -> dict:
    n = await db.ngo_profiles.find_one({"id": ngo_id}, P)
    if not n:
        raise HTTPException(404, "NGO not found")
    cnt = await db.events.count_documents({"ngo_id": ngo_id, "status": "published"})
    return {**n, "published_events": cnt}


@router.get("/ngos/{ngo_id}", response_model=NgoPublic)
async def get_ngo(ngo_id: str, user: dict = Depends(current_user)):
    return await ngo_public(ngo_id)


@router.get("/ngos/{ngo_id}/events", response_model=list[EventCard])
async def ngo_events(ngo_id: str, user: dict = Depends(current_user)):
    events = await db.events.find({"ngo_id": ngo_id, "status": "published"}, P).sort("event_date", 1).to_list(500)
    return await build_event_cards(events)


# ---------- notifications (both roles) ----------
@router.get("/notifications", response_model=list[Notification])
async def notifications(user: dict = Depends(current_user)):
    if user["role"] == "volunteer":
        await generate_reminders(user)
    return await db.notifications.find({"recipient_user_id": user["id"]}, P).sort("created_at", -1).to_list(200)


@router.post("/notifications/read-all", response_model=MessageOut)
async def read_all(user: dict = Depends(current_user)):
    await db.notifications.update_many({"recipient_user_id": user["id"]}, {"$set": {"read_status": True}})
    return {"message": "ok"}


@router.post("/notifications/{nid}/read", response_model=MessageOut)
async def read_one(nid: str, user: dict = Depends(current_user)):
    res = await db.notifications.update_one({"id": nid, "recipient_user_id": user["id"]}, {"$set": {"read_status": True}})
    if not res.matched_count:
        raise HTTPException(404, "Notification not found")
    return {"message": "ok"}


# ---------- uploads ----------
@router.post("/uploads", response_model=UploadOut)
async def upload(file: UploadFile = File(...), user: dict = Depends(current_user)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ("png", "jpg", "jpeg", "webp", "gif"):
        raise HTTPException(400, "Only PNG, JPG, WEBP or GIF images are allowed.")
    data = await file.read()
    if len(data) > 3 * 1024 * 1024:
        raise HTTPException(400, "Image must be under 3 MB.")
    name = f"{uuid.uuid4().hex}.{ext}"
    (UPLOAD_DIR / name).write_bytes(data)
    return {"url": f"/api/uploads/{name}"}


@router.get("/uploads/{name}")
async def get_upload(name: str):
    path = (UPLOAD_DIR / name).resolve()
    if path.parent != UPLOAD_DIR.resolve() or not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(path)


# ---------- volunteer ----------
@router.get("/volunteer/profile", response_model=VolunteerProfile)
async def get_vprofile(ctx=Depends(require_volunteer)):
    return ctx[1]


@router.put("/volunteer/profile", response_model=VolunteerProfile)
async def put_vprofile(body: VolunteerProfileIn, ctx=Depends(require_volunteer)):
    user, vol = ctx
    data = body.model_dump()
    await db.volunteer_profiles.update_one({"id": vol["id"]}, {"$set": data})
    await db.users.update_one({"id": user["id"]}, {"$set": {"full_name": body.name, "phone": body.phone,
                                                            "preferred_language": body.preferred_language}})
    return {**vol, **data}


@router.post("/volunteer/registrations", response_model=MyRegistration)
async def register_shift(body: RegisterShiftIn, ctx=Depends(require_volunteer)):
    user, vol = ctx
    sh = await db.shifts.find_one({"id": body.shift_id}, P)
    ev = await db.events.find_one({"id": sh["event_id"]}, P) if sh else None
    if not sh or not ev or ev["status"] != "published":
        raise HTTPException(400, "This event is not published, so registration is not possible.")
    if not registration_open(ev):
        raise HTTPException(400, "Registration for this event has closed (deadline passed).")
    if shift_start(sh) <= now_local():
        raise HTTPException(400, "This shift has already started.")
    if await db.registrations.find_one({"volunteer_id": vol["id"], "shift_id": sh["id"], "active": True}):
        raise HTTPException(409, "You are already registered for this shift.")
    if availability_score(vol, sh) == 0:
        raise HTTPException(400, "This shift falls outside your availability preferences. Update your availability in your profile to register.")
    conflict = await find_conflict(vol["id"], sh)
    if conflict:
        c = conflict["shift"]
        raise HTTPException(409, f"Schedule conflict: this overlaps your shift for '{conflict['event_title']}' "
                                 f"({c['shift_date']} {c['start_time']}-{c['end_time']}).")
    claimed = await db.shifts.find_one_and_update({"id": sh["id"], "$expr": {"$lt": ["$filled", "$capacity"]}},
                                                  {"$inc": {"filled": 1}})
    if not claimed:
        raise HTTPException(409, "This shift is full. Please choose another shift.")
    reg = {"id": new_id(), "volunteer_id": vol["id"], "event_id": ev["id"], "shift_id": sh["id"],
           "registration_status": "confirmed", "active": True, "registered_at": now_iso(), "cancelled_at": None,
           "source": "direct", "last_minute": False, "replaced_by": None}
    try:
        await db.registrations.insert_one(dict(reg))
    except DuplicateKeyError:
        await db.shifts.update_one({"id": sh["id"]}, {"$inc": {"filled": -1}})
        raise HTTPException(409, "You are already registered for this shift.")
    p = {"event": ev["title"], "shift": fmt_shift(sh), "volunteer": vol["name"]}
    await notify(user["id"], "registration_confirmed", f"Registration confirmed: {ev['title']}",
                 f"You are confirmed for {ev['title']} ({fmt_shift(sh)}).", p, ev["id"], sh["id"])
    ngo = await db.ngo_profiles.find_one({"id": ev["ngo_id"]}, P)
    await notify(ngo["user_id"], "new_registration", f"New registration: {ev['title']}",
                 f"{vol['name']} registered for the {fmt_shift(sh)} shift.", p, ev["id"], sh["id"])
    return (await my_rows([reg]))[0]


@router.get("/volunteer/registrations", response_model=list[MyRegistration])
async def my_registrations(ctx=Depends(require_volunteer)):
    return await my_rows(await db.registrations.find({"volunteer_id": ctx[1]["id"]}, P).to_list(1000))


@router.post("/volunteer/registrations/{reg_id}/cancel", response_model=MyRegistration)
async def cancel(reg_id: str, ctx=Depends(require_volunteer)):
    user, vol = ctx
    reg = await db.registrations.find_one({"id": reg_id, "volunteer_id": vol["id"]}, P)
    if not reg:
        raise HTTPException(404, "Registration not found")
    sh = await db.shifts.find_one({"id": reg["shift_id"]}, P)
    if reg["registration_status"] != "confirmed":
        raise HTTPException(400, "Only confirmed registrations can be cancelled.")
    if shift_start(sh) <= now_local():
        raise HTTPException(400, "Cancellation is not allowed after the shift has started.")
    last_minute = shift_start(sh) - now_local() <= timedelta(hours=48)
    res = await db.registrations.update_one({"id": reg_id, "registration_status": "confirmed"}, {"$set": {
        "registration_status": "cancelled", "active": False, "cancelled_at": now_iso(), "last_minute": last_minute}})
    if res.modified_count:
        await db.shifts.update_one({"id": sh["id"], "filled": {"$gt": 0}}, {"$inc": {"filled": -1}})
    ev = await db.events.find_one({"id": reg["event_id"]}, P)
    # trigger the replacement engine so the NGO alert carries the number of eligible candidates
    target = await target_skills_for(sh, ev, vol)
    cands, _ = await find_candidates(sh, ev, target, {vol["id"]})
    ngo = await db.ngo_profiles.find_one({"id": ev["ngo_id"]}, P)
    p = {"volunteer": vol["name"], "event": ev["title"], "shift": fmt_shift(sh), "count": len(cands),
         "skills": ", ".join(target)}
    await notify(ngo["user_id"], "volunteer_cancelled",
                 ("LAST-MINUTE " if last_minute else "") + f"Cancellation: {ev['title']}",
                 f"{vol['name']} cancelled the {fmt_shift(sh)} shift. {len(cands)} eligible replacement(s) found"
                 + (f" for {', '.join(target)}." if target else "."), p, ev["id"], sh["id"])
    await notify(user["id"], "registration_cancelled", f"Registration cancelled: {ev['title']}",
                 f"Your registration for {fmt_shift(sh)} was cancelled.", p, ev["id"], sh["id"])
    return (await my_rows([await db.registrations.find_one({"id": reg_id}, P)]))[0]


@router.get("/volunteer/invitations", response_model=list[Invitation])
async def my_invitations(ctx=Depends(require_volunteer)):
    inv = await db.replacement_invitations.find({"invited_volunteer_id": ctx[1]["id"]}, P).sort("created_at", -1).to_list(500)
    now = now_local().isoformat(timespec="minutes")
    shifts = {s["id"]: s for s in await db.shifts.find({"id": {"$in": [i["shift_id"] for i in inv]}}, P).to_list(1000)}
    events = {e["id"]: e for e in await db.events.find({"id": {"$in": [s["event_id"] for s in shifts.values()]}}, P).to_list(1000)}
    ngos = {n["id"]: n for n in await db.ngo_profiles.find({"id": {"$in": [e["ngo_id"] for e in events.values()]}}, P).to_list(100)}
    out = []
    for i in inv:
        s = shifts.get(i["shift_id"])
        e = events.get(s["event_id"]) if s else None
        if not e:
            continue
        status = "expired" if i["invitation_status"] == "pending" and i["expires_at"] < now else i["invitation_status"]
        out.append({**i, "invitation_status": status, "event_id": e["id"], "event_title": e["title"],
                    "ngo_name": ngos.get(e["ngo_id"], {}).get("organization_name", ""), "location": e["location"],
                    "shift_date": s["shift_date"], "start_time": s["start_time"], "end_time": s["end_time"]})
    return out


@router.post("/volunteer/invitations/{inv_id}/respond", response_model=MessageOut)
async def respond(inv_id: str, body: RespondIn, ctx=Depends(require_volunteer)):
    user, vol = ctx
    inv = await db.replacement_invitations.find_one({"id": inv_id, "invited_volunteer_id": vol["id"]}, P)
    if not inv:
        raise HTTPException(404, "Invitation not found")
    if inv["invitation_status"] != "pending":
        raise HTTPException(400, "This invitation is no longer active.")
    if inv["expires_at"] < now_local().isoformat(timespec="minutes"):
        await db.replacement_invitations.update_one({"id": inv_id}, {"$set": {"invitation_status": "expired"}})
        raise HTTPException(400, "This invitation has expired.")
    sh = await db.shifts.find_one({"id": inv["shift_id"]}, P)
    ev = await db.events.find_one({"id": sh["event_id"]}, P)
    ngo = await db.ngo_profiles.find_one({"id": ev["ngo_id"]}, P)
    p = {"volunteer": vol["name"], "event": ev["title"], "shift": fmt_shift(sh)}
    if not body.accept:
        await db.replacement_invitations.update_one({"id": inv_id}, {"$set": {"invitation_status": "declined"}})
        await notify(ngo["user_id"], "replacement_declined", f"Invitation declined: {ev['title']}",
                     f"{vol['name']} declined the replacement invitation for {fmt_shift(sh)}.", p, ev["id"], sh["id"])
        return {"message": "Invitation declined."}
    # mandatory re-checks at acceptance time
    if await db.registrations.find_one({"volunteer_id": vol["id"], "shift_id": sh["id"], "active": True}):
        raise HTTPException(409, "You are already registered for this shift.")
    conflict = await find_conflict(vol["id"], sh)
    if conflict:
        raise HTTPException(409, f"Schedule conflict with your shift for '{conflict['event_title']}'.")
    cr = inv.get("cancelled_registration_id")
    if cr:  # atomically claim the specific vacancy — only one volunteer can win
        claim = await db.registrations.find_one_and_update({"id": cr, "replaced_by": None}, {"$set": {"replaced_by": vol["id"]}})
        if not claim:
            await db.replacement_invitations.update_one({"id": inv_id}, {"$set": {"invitation_status": "filled"}})
            raise HTTPException(409, "Sorry — this vacancy has already been filled by another volunteer.")
    seat = await db.shifts.find_one_and_update({"id": sh["id"], "$expr": {"$lt": ["$filled", "$capacity"]}}, {"$inc": {"filled": 1}})
    if not seat:
        if cr:
            await db.registrations.update_one({"id": cr}, {"$set": {"replaced_by": None}})
        await db.replacement_invitations.update_one({"id": inv_id}, {"$set": {"invitation_status": "filled"}})
        raise HTTPException(409, "Sorry — this shift is already fully staffed.")
    reg = {"id": new_id(), "volunteer_id": vol["id"], "event_id": ev["id"], "shift_id": sh["id"],
           "registration_status": "confirmed", "active": True, "registered_at": now_iso(), "cancelled_at": None,
           "source": "emergency" if inv.get("urgent") else "replacement", "last_minute": False, "replaced_by": None,
           "invitation_id": inv_id}
    try:
        await db.registrations.insert_one(dict(reg))
    except DuplicateKeyError:
        await db.shifts.update_one({"id": sh["id"]}, {"$inc": {"filled": -1}})
        if cr:
            await db.registrations.update_one({"id": cr}, {"$set": {"replaced_by": None}})
        raise HTTPException(409, "You are already registered for this shift.")
    await db.replacement_invitations.update_one({"id": inv_id}, {"$set": {"invitation_status": "accepted"}})
    close_q = {"invitation_status": "pending", "id": {"$ne": inv_id}}
    if cr:
        await db.replacement_invitations.update_many({**close_q, "cancelled_registration_id": cr}, {"$set": {"invitation_status": "filled"}})
    fresh = await db.shifts.find_one({"id": sh["id"]}, P)
    if fresh["filled"] >= fresh["capacity"]:
        await db.replacement_invitations.update_many({**close_q, "shift_id": sh["id"]}, {"$set": {"invitation_status": "filled"}})
    await notify(ngo["user_id"], "replacement_accepted", f"Replacement confirmed: {ev['title']}",
                 f"{vol['name']} accepted and is now assigned to the {fmt_shift(sh)} shift.", p, ev["id"], sh["id"])
    await notify(user["id"], "registration_confirmed", f"Registration confirmed: {ev['title']}",
                 f"You are confirmed for {ev['title']} ({fmt_shift(sh)}).", p, ev["id"], sh["id"])
    return {"message": "You're confirmed for this shift. Thank you for stepping in!"}


@router.get("/volunteer/dashboard", response_model=VolDashboard)
async def vdashboard(ctx=Depends(require_volunteer)):
    user, vol = ctx
    await generate_reminders(user)
    rows = await my_rows(await db.registrations.find({"volunteer_id": vol["id"]}, P).to_list(1000))
    today = now_local().date().isoformat()
    upcoming = [r for r in rows if r["registration_status"] == "confirmed" and r["shift_date"] >= today]
    done = [r for r in rows if r["attendance"] and r["attendance"]["attendance_status"] == "present"]
    events = await db.events.find({"status": "published", "event_date": {"$gte": today}}, P).sort("event_date", 1).to_list(500)
    cards = [c for c in await build_event_cards(events, vol["id"]) if c["registration_open"]]
    interests = set(vol.get("interests") or [])
    skills = set(vol.get("skills") or [])

    def rel(c):
        return (CATEGORY_INTEREST.get(c["category"]) in interests) * 2 + len(skills & set(c.get("required_skills") or []))
    rec = sorted([c for c in cards if rel(c) > 0], key=lambda c: -rel(c))[:4]
    pending = await db.replacement_invitations.count_documents({"invited_volunteer_id": vol["id"], "invitation_status": "pending",
                                                                 "expires_at": {"$gte": now_local().isoformat(timespec="minutes")}})
    notes = await db.notifications.find({"recipient_user_id": user["id"]}, P).sort("created_at", -1).to_list(5)
    return {"upcoming": upcoming[:5], "recommended": rec, "available_count": len(cards),
            "total_hours": round(sum(r["attendance"]["hours_contributed"] for r in done), 1),
            "events_attended": len({r["event_id"] for r in done}), "pending_invitations": pending,
            "recent_notifications": notes,
            "profile_complete": bool(vol.get("skills") and (vol.get("availability") or {}).get("days"))}


@router.get("/volunteer/analytics", response_model=VolAnalytics)
async def vanalytics(ctx=Depends(require_volunteer)):
    vol = ctx[1]
    rows = await my_rows(await db.registrations.find({"volunteer_id": vol["id"]}, P).to_list(1000))
    today = now_local().date().isoformat()
    done = [r for r in rows if r["attendance"] and r["attendance"]["attendance_status"] == "present"]
    history = [r for r in rows if r["shift_date"] < today or r["attendance"] or r["registration_status"] in ("completed", "absent", "cancelled")]
    sh = {s["id"]: s for s in await db.shifts.find({"id": {"$in": [r["shift_id"] for r in done]}}, P).to_list(1000)}
    used = Counter()
    for r in done:
        for req in sh.get(r["shift_id"], {}).get("required_skills") or []:
            if req["skill"] in (vol.get("skills") or []):
                used[req["skill"]] += 1
    monthly = defaultdict(float)
    for r in done:
        monthly[r["shift_date"][:7]] += r["attendance"]["hours_contributed"]
    return {"total_hours": round(sum(r["attendance"]["hours_contributed"] for r in done), 1),
            "events_attended": len({r["event_id"] for r in done}),
            "upcoming_commitments": sum(1 for r in rows if r["registration_status"] == "confirmed" and r["shift_date"] >= today),
            "history": sorted(history, key=lambda r: r["shift_date"], reverse=True),
            "skills_used": [{"name": k, "value": v} for k, v in used.most_common()],
            "causes_supported": [{"name": k, "value": v} for k, v in Counter(r["category"] for r in done).most_common()],
            "monthly_hours": [{"name": k, "value": round(v, 1)} for k, v in sorted(monthly.items())]}
