"""NGO-only routes. Every event/shift/registration reached by id is checked against the caller's NGO (404 otherwise)."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from lib.db import db
from lib.logic import (P, build_event_cards, send_invites, find_candidates, fmt_shift, new_id, notify, now_iso, now_local,
                       shift_hours, shift_start, shifts_with_coverage, target_skills_for, valid_date, valid_time,
                       volunteer_hours, volunteer_public)
from lib.security import require_ngo
from models.schemas import (Attendance, AttendanceIn, CancellationOverview, CandidatesOut, EmergencyIn, Event,
                            EventDetail, EventCard, EventIn, EventStatusIn, InvitationRow, InviteIn, InviteOut,
                            MessageOut, NgoAnalytics, NgoDashboard, NgoProfile, NgoProfileIn, RegistrationRow,
                            Shift, ShiftAlert, ShiftIn, VolunteerPublic)

router = APIRouter(prefix="/ngo", tags=["ngo"])


async def own_event(ngo: dict, event_id: str) -> dict:
    ev = await db.events.find_one({"id": event_id, "ngo_id": ngo["id"]}, P)
    if not ev:
        raise HTTPException(404, "Event not found")
    return ev


async def own_shift(ngo: dict, shift_id: str) -> tuple[dict, dict]:
    sh = await db.shifts.find_one({"id": shift_id}, P)
    if not sh:
        raise HTTPException(404, "Shift not found")
    return sh, await own_event(ngo, sh["event_id"])


def validate_event(b: EventIn):
    if not valid_date(b.event_date) or not valid_time(b.start_time) or not valid_time(b.end_time):
        raise HTTPException(400, "Invalid event date or time.")
    if b.end_time <= b.start_time:
        raise HTTPException(400, "Event end time must be after the start time.")
    try:
        dl = datetime.fromisoformat(b.registration_deadline)
    except ValueError:
        raise HTTPException(400, "Invalid registration deadline.")
    if dl > datetime.fromisoformat(f"{b.event_date}T{b.start_time}"):
        raise HTTPException(400, "Registration deadline must be on or before the event start.")


def validate_shift(b: ShiftIn):
    if not valid_date(b.shift_date) or not valid_time(b.start_time) or not valid_time(b.end_time):
        raise HTTPException(400, "Invalid shift date or time.")
    if b.end_time <= b.start_time:
        raise HTTPException(400, "Shift end time must be after the start time.")
    if sum(r.count for r in b.required_skills) > b.capacity:
        raise HTTPException(400, "Skill requirements exceed the shift capacity.")


async def registration_rows(regs: list[dict], show_contact=True) -> list[dict]:
    if not regs:
        return []
    shifts = {s["id"]: s for s in await db.shifts.find({"id": {"$in": list({r["shift_id"] for r in regs})}}, P).to_list(10000)}
    events = {e["id"]: e for e in await db.events.find({"id": {"$in": list({r["event_id"] for r in regs})}}, P).to_list(10000)}
    vids = list({r["volunteer_id"] for r in regs} | {r["replaced_by"] for r in regs if r.get("replaced_by")})
    vols = {v["id"]: v for v in await db.volunteer_profiles.find({"id": {"$in": vids}}, P).to_list(10000)}
    hours = await volunteer_hours(vids)
    att = {a["registration_id"]: a for a in await db.attendance.find({"registration_id": {"$in": [r["id"] for r in regs]}}, P).to_list(10000)}
    out = []
    for r in regs:
        s, e, v = shifts.get(r["shift_id"]), events.get(r["event_id"]), vols.get(r["volunteer_id"])
        if not (s and e and v):
            continue
        out.append({**r, "event_title": e["title"], "shift_date": s["shift_date"], "start_time": s["start_time"],
                    "end_time": s["end_time"], "volunteer": volunteer_public(v, show_contact, hours.get(v["id"], 0)),
                    "replaced_by_name": vols[r["replaced_by"]]["name"] if r.get("replaced_by") in vols else None,
                    "attendance": att.get(r["id"])})
    return out


# ---------- profile ----------
@router.get("/profile", response_model=NgoProfile)
async def get_profile(ctx=Depends(require_ngo)):
    return ctx[1]


@router.put("/profile", response_model=NgoProfile)
async def update_profile(body: NgoProfileIn, ctx=Depends(require_ngo)):
    user, ngo = ctx
    await db.ngo_profiles.update_one({"id": ngo["id"]}, {"$set": body.model_dump()})
    await db.users.update_one({"id": user["id"]}, {"$set": {"full_name": body.organization_name, "phone": body.contact_number}})
    return {**ngo, **body.model_dump()}


# ---------- events ----------
@router.get("/events", response_model=list[EventCard])
async def list_events(ctx=Depends(require_ngo)):
    events = await db.events.find({"ngo_id": ctx[1]["id"]}, P).sort("event_date", 1).to_list(1000)
    return await build_event_cards(events)


@router.post("/events", response_model=Event)
async def create_event(body: EventIn, ctx=Depends(require_ngo)):
    validate_event(body)
    doc = {**body.model_dump(), "id": new_id(), "ngo_id": ctx[1]["id"], "status": "draft", "emergency": False,
           "created_at": now_iso(), "is_demo": False}
    await db.events.insert_one(dict(doc))
    return doc


@router.get("/events/{event_id}", response_model=EventDetail)
async def get_event(event_id: str, ctx=Depends(require_ngo)):
    ev = await own_event(ctx[1], event_id)
    return (await build_event_cards([ev], with_shifts=True))[0]


async def notify_registered(event_id: str, ntype: str, title: str, message: str, params: dict, shift_ids=None):
    q = {"event_id": event_id, "active": True, "registration_status": "confirmed"}
    if shift_ids:
        q["shift_id"] = {"$in": shift_ids}
    regs = await db.registrations.find(q, P).to_list(10000)
    vols = {v["id"]: v["user_id"] for v in await db.volunteer_profiles.find(
        {"id": {"$in": [r["volunteer_id"] for r in regs]}}, P).to_list(10000)}
    for r in regs:
        if r["volunteer_id"] in vols:
            await notify(vols[r["volunteer_id"]], ntype, title, message, params, event_id, r["shift_id"])


@router.put("/events/{event_id}", response_model=Event)
async def update_event(event_id: str, body: EventIn, ctx=Depends(require_ngo)):
    ev = await own_event(ctx[1], event_id)
    validate_event(body)
    data = body.model_dump()
    await db.events.update_one({"id": event_id}, {"$set": data})
    changed = [k for k in ("location", "event_date", "start_time", "end_time") if ev.get(k) != data[k]]
    if ev["status"] == "published":
        ntype = "venue_time_changed" if changed else "event_updated"
        await notify_registered(event_id, ntype, f"Event updated: {body.title}",
                                f"{body.title} was updated" + (f" ({', '.join(changed)} changed)." if changed else "."),
                                {"event": body.title, "changes": ", ".join(changed)})
    return {**ev, **data}


@router.delete("/events/{event_id}", response_model=MessageOut)
async def delete_event(event_id: str, ctx=Depends(require_ngo)):
    ev = await own_event(ctx[1], event_id)
    await notify_registered(event_id, "shift_cancelled", f"Event cancelled: {ev['title']}",
                            f"{ev['title']} has been cancelled by the organiser.", {"event": ev["title"]})
    reg_ids = [r["id"] for r in await db.registrations.find({"event_id": event_id}, {"_id": 0, "id": 1}).to_list(100000)]
    shift_ids = [s["id"] for s in await db.shifts.find({"event_id": event_id}, {"_id": 0, "id": 1}).to_list(1000)]
    await db.attendance.delete_many({"registration_id": {"$in": reg_ids}})
    await db.replacement_invitations.delete_many({"shift_id": {"$in": shift_ids}})
    await db.registrations.delete_many({"event_id": event_id})
    await db.shifts.delete_many({"event_id": event_id})
    await db.events.delete_one({"id": event_id})
    return {"message": "Event deleted"}


@router.post("/events/{event_id}/status", response_model=Event)
async def set_status(event_id: str, body: EventStatusIn, ctx=Depends(require_ngo)):
    ev = await own_event(ctx[1], event_id)
    if body.status == "published":
        if not await db.shifts.count_documents({"event_id": event_id}):
            raise HTTPException(400, "Add at least one shift before publishing.")
    await db.events.update_one({"id": event_id}, {"$set": {"status": body.status}})
    if body.status == "published" and ev["status"] != "published":
        # new-opportunity notifications for volunteers whose interests / skills match
        from lib.logic import CATEGORY_INTEREST
        interest = CATEGORY_INTEREST.get(ev["category"], "")
        q = {"$or": [{"interests": interest}, {"skills": {"$in": ev.get("required_skills") or []}}]}
        for v in await db.volunteer_profiles.find(q, {"_id": 0, "user_id": 1}).to_list(5000):
            await notify(v["user_id"], "new_opportunity", f"New opportunity: {ev['title']}",
                         f"{ctx[1]['organization_name']} published {ev['title']} on {ev['event_date']}, matching your profile.",
                         {"event": ev["title"], "ngo": ctx[1]["organization_name"], "date": ev["event_date"]},
                         event_id, dedupe_key=f"newopp:{event_id}:{v['user_id']}")
    return {**ev, "status": body.status}


# ---------- shifts ----------
@router.post("/events/{event_id}/shifts", response_model=Shift)
async def create_shift(event_id: str, body: ShiftIn, ctx=Depends(require_ngo)):
    await own_event(ctx[1], event_id)
    validate_shift(body)
    doc = {**body.model_dump(), "id": new_id(), "event_id": event_id, "status": "open", "filled": 0}
    await db.shifts.insert_one(dict(doc))
    return doc


@router.put("/shifts/{shift_id}", response_model=Shift)
async def update_shift(shift_id: str, body: ShiftIn, ctx=Depends(require_ngo)):
    sh, ev = await own_shift(ctx[1], shift_id)
    validate_shift(body)
    if body.capacity < sh["filled"]:
        raise HTTPException(400, f"Capacity cannot be lower than the {sh['filled']} volunteers already registered.")
    data = body.model_dump()
    await db.shifts.update_one({"id": shift_id}, {"$set": data})
    if any(sh[k] != data[k] for k in ("shift_date", "start_time", "end_time")):
        await notify_registered(ev["id"], "venue_time_changed", f"Shift timing changed: {ev['title']}",
                                f"Your shift for {ev['title']} is now {fmt_shift(data)}.",
                                {"event": ev["title"], "shift": fmt_shift(data)}, [shift_id])
    return {**sh, **data}


@router.delete("/shifts/{shift_id}", response_model=MessageOut)
async def delete_shift(shift_id: str, ctx=Depends(require_ngo)):
    sh, ev = await own_shift(ctx[1], shift_id)
    await notify_registered(ev["id"], "shift_cancelled", f"Shift cancelled: {ev['title']}",
                            f"The {fmt_shift(sh)} shift of {ev['title']} was cancelled by the organiser.",
                            {"event": ev["title"], "shift": fmt_shift(sh)}, [shift_id])
    reg_ids = [r["id"] for r in await db.registrations.find({"shift_id": shift_id}, {"_id": 0, "id": 1}).to_list(10000)]
    await db.attendance.delete_many({"registration_id": {"$in": reg_ids}})
    await db.registrations.delete_many({"shift_id": shift_id})
    await db.replacement_invitations.delete_many({"shift_id": shift_id})
    await db.shifts.delete_one({"id": shift_id})
    return {"message": "Shift deleted"}


# ---------- registrations / attendance ----------
@router.get("/registrations", response_model=list[RegistrationRow])
async def list_registrations(event_id: str | None = None, ctx=Depends(require_ngo)):
    ev_ids = [e["id"] for e in await db.events.find({"ngo_id": ctx[1]["id"]}, {"_id": 0, "id": 1}).to_list(1000)]
    if event_id:
        if event_id not in ev_ids:
            raise HTTPException(404, "Event not found")
        ev_ids = [event_id]
    regs = await db.registrations.find({"event_id": {"$in": ev_ids}}, P).sort("registered_at", -1).to_list(10000)
    return await registration_rows(regs)


@router.post("/registrations/{reg_id}/attendance", response_model=Attendance)
async def record_attendance(reg_id: str, body: AttendanceIn, ctx=Depends(require_ngo)):
    reg = await db.registrations.find_one({"id": reg_id}, P)
    if not reg:
        raise HTTPException(404, "Registration not found")
    await own_event(ctx[1], reg["event_id"])
    if not reg["active"]:
        raise HTTPException(400, "Attendance can only be recorded for active registrations.")
    sh = await db.shifts.find_one({"id": reg["shift_id"]}, P)
    hours = body.hours_contributed if body.hours_contributed is not None else shift_hours(sh)
    if body.attendance_status == "absent":
        hours = 0
    existing = await db.attendance.find_one({"registration_id": reg_id}, P)
    doc = {"id": existing["id"] if existing else new_id(), "registration_id": reg_id,
           "attendance_status": body.attendance_status, "check_in_time": now_iso(), "hours_contributed": hours}
    await db.attendance.replace_one({"registration_id": reg_id}, doc, upsert=True)
    await db.registrations.update_one({"id": reg_id}, {"$set": {
        "registration_status": "completed" if body.attendance_status == "present" else "absent"}})
    vol = await db.volunteer_profiles.find_one({"id": reg["volunteer_id"]}, P)
    ev = await db.events.find_one({"id": reg["event_id"]}, P)
    if vol and body.attendance_status == "present":
        await notify(vol["user_id"], "attendance_recorded", f"Attendance recorded: {ev['title']}",
                     f"Thank you! {hours} volunteering hours were added for {ev['title']}.",
                     {"event": ev["title"], "hours": hours}, ev["id"], sh["id"])
    return doc


# ---------- coverage / dashboard ----------
async def ngo_shift_alerts(ngo: dict, only_upcoming=True, only_problem=True) -> list[dict]:
    events = {e["id"]: e for e in await db.events.find({"ngo_id": ngo["id"], "status": "published"}, P).to_list(1000)}
    q = {"event_id": {"$in": list(events)}}
    if only_upcoming:
        q["shift_date"] = {"$gte": now_local().date().isoformat()}
    cov = await shifts_with_coverage(await db.shifts.find(q, P).to_list(10000))
    out = []
    for s in cov:
        if only_problem and s["coverage"]["status"] == "fully_staffed":
            continue
        e = events[s["event_id"]]
        out.append({"event_id": e["id"], "event_title": e["title"], "emergency": e.get("emergency", False), "shift": s})
    order = {"critical_shortage": 0, "fully_booked": 1, "partially_staffed": 2, "fully_staffed": 3}
    return sorted(out, key=lambda a: (order[a["shift"]["coverage"]["status"]], a["shift"]["shift_date"]))


@router.get("/coverage", response_model=list[ShiftAlert])
async def coverage(ctx=Depends(require_ngo)):
    return await ngo_shift_alerts(ctx[1], only_upcoming=True, only_problem=False)


@router.get("/dashboard", response_model=NgoDashboard)
async def dashboard(ctx=Depends(require_ngo)):
    ngo = ctx[1]
    events = await db.events.find({"ngo_id": ngo["id"]}, P).sort("event_date", 1).to_list(1000)
    cards = await build_event_cards(events)
    today = now_local().date().isoformat()
    ev_ids = [e["id"] for e in events]
    regs = await db.registrations.find({"event_id": {"$in": ev_ids}}, P).sort("registered_at", -1).to_list(10000)
    upcoming = [c for c in cards if c["event_date"] >= today and c["status"] == "published"]
    up_total = sum(c["total_capacity"] for c in upcoming)
    up_filled = sum(c["total_filled"] for c in upcoming)
    stats = {"total_events": len(events), "published_events": sum(e["status"] == "published" for e in events),
             "total_volunteers": len({r["volunteer_id"] for r in regs if r["active"]}),
             "upcoming_events": len(upcoming), "total_positions": up_total, "filled_positions": up_filled,
             "vacant_positions": max(0, up_total - up_filled)}
    return {"stats": stats, "attention": (await ngo_shift_alerts(ngo))[:6],
            "recent_registrations": await registration_rows(regs[:6]), "upcoming": upcoming[:5]}


@router.get("/volunteers", response_model=list[VolunteerPublic])
async def directory(ctx=Depends(require_ngo)):
    """Shared volunteer database — public profile fields only; contact only for volunteers engaged with this NGO."""
    ev_ids = [e["id"] for e in await db.events.find({"ngo_id": ctx[1]["id"]}, {"_id": 0, "id": 1}).to_list(1000)]
    eng = Counter(r["volunteer_id"] for r in await db.registrations.find({"event_id": {"$in": ev_ids}}, P).to_list(100000))
    vols = await db.volunteer_profiles.find({}, P).to_list(10000)
    hours = await volunteer_hours([v["id"] for v in vols])
    out = [volunteer_public(v, eng[v["id"]] > 0, hours.get(v["id"], 0), eng[v["id"]]) for v in vols]
    return sorted(out, key=lambda v: (-v["engagements"], v["name"]))


# ---------- smart cancellation manager ----------
@router.get("/cancellations", response_model=CancellationOverview)
async def cancellations(ctx=Depends(require_ngo)):
    ngo = ctx[1]
    today = now_local().date().isoformat()
    events = {e["id"]: e for e in await db.events.find({"ngo_id": ngo["id"]}, P).to_list(1000)}
    regs = await db.registrations.find({"event_id": {"$in": list(events)}, "registration_status": "cancelled"}, P) \
        .sort("cancelled_at", -1).to_list(1000)
    shifts = {s["id"]: s for s in await shifts_with_coverage(
        await db.shifts.find({"id": {"$in": [r["shift_id"] for r in regs]}, "shift_date": {"$gte": today}}, P).to_list(1000))}
    vids = list({r["volunteer_id"] for r in regs} | {r.get("replaced_by") for r in regs if r.get("replaced_by")})
    vols = {v["id"]: v["name"] for v in await db.volunteer_profiles.find({"id": {"$in": vids}}, P).to_list(1000)}
    inv_counts = Counter(i["cancelled_registration_id"] for i in await db.replacement_invitations.find(
        {"cancelled_registration_id": {"$in": [r["id"] for r in regs]}}, P).to_list(10000))
    vac = []
    for r in regs:
        if r["shift_id"] not in shifts:
            continue
        vac.append({"cancelled_registration_id": r["id"], "event_id": r["event_id"],
                    "event_title": events[r["event_id"]]["title"], "shift": shifts[r["shift_id"]],
                    "cancelled_volunteer_name": vols.get(r["volunteer_id"], "Volunteer"),
                    "cancelled_at": r.get("cancelled_at") or "", "last_minute": r.get("last_minute", False),
                    "invitations_sent": inv_counts[r["id"]], "replaced_by_name": vols.get(r.get("replaced_by"))})
    return {"vacancies": vac, "understaffed": await ngo_shift_alerts(ngo)}


@router.get("/shifts/{shift_id}/candidates", response_model=CandidatesOut)
async def candidates(shift_id: str, registration_id: str | None = None, ctx=Depends(require_ngo)):
    sh, ev = await own_shift(ctx[1], shift_id)
    cancelled_vol = None
    exclude: set[str] = set()
    if registration_id:
        reg = await db.registrations.find_one({"id": registration_id, "shift_id": shift_id}, P)
        if not reg:
            raise HTTPException(404, "Registration not found")
        cancelled_vol = await db.volunteer_profiles.find_one({"id": reg["volunteer_id"]}, P)
        exclude.add(reg["volunteer_id"])
    target = await target_skills_for(sh, ev, cancelled_vol)
    cands, excluded = await find_candidates(sh, ev, target, exclude)
    shift_cov = (await shifts_with_coverage([sh]))[0]
    return {"shift": shift_cov, "event_id": ev["id"], "event_title": ev["title"], "target_skills": target,
            "candidates": cands[:25], "excluded": excluded}


@router.post("/invitations", response_model=InviteOut)
async def invite(body: InviteIn, ctx=Depends(require_ngo)):
    sh, ev = await own_shift(ctx[1], body.shift_id)
    if shift_start(sh) <= now_local():
        raise HTTPException(400, "This shift has already started.")
    invited, skipped, _ = await send_invites(ctx[1], sh, ev, body.volunteer_ids, body.cancelled_registration_id, body.urgent)
    return {"invited": invited, "skipped": skipped,
            "message": f"{invited} invitation(s) sent" + (f", {skipped} skipped (ineligible or already invited)" if skipped else "")}


@router.get("/shifts/{shift_id}/invitations", response_model=list[InvitationRow])
async def shift_invitations(shift_id: str, ctx=Depends(require_ngo)):
    await own_shift(ctx[1], shift_id)
    inv = await db.replacement_invitations.find({"shift_id": shift_id}, P).sort("created_at", -1).to_list(1000)
    vols = {v["id"]: v["name"] for v in await db.volunteer_profiles.find(
        {"id": {"$in": [i["invited_volunteer_id"] for i in inv]}}, P).to_list(1000)}
    return [{**i, "volunteer_name": vols.get(i["invited_volunteer_id"], "Volunteer")} for i in inv]


@router.post("/emergency", response_model=InviteOut)
async def emergency(body: EmergencyIn, ctx=Depends(require_ngo)):
    sh, ev = await own_shift(ctx[1], body.shift_id)
    if shift_start(sh) <= now_local():
        raise HTTPException(400, "This shift has already started.")
    await db.events.update_one({"id": ev["id"]}, {"$set": {"emergency": True}})
    target = await target_skills_for(sh, ev)
    cands, _ = await find_candidates(sh, ev, target, set())
    pick = [c["volunteer"]["id"] for c in cands if c["invitation_status"] != "pending"][: min(50, body.needed * 2)]
    if not pick:
        return {"invited": 0, "skipped": 0, "message": "No eligible volunteers found for this shift right now."}
    invited, skipped, _ = await send_invites(ctx[1], sh, ev, pick, None, True)
    return {"invited": invited, "skipped": skipped,
            "message": f"Emergency mode on: {invited} urgent request(s) sent to the best-matched available volunteers."}


# ---------- analytics ----------
@router.get("/analytics", response_model=NgoAnalytics)
async def analytics(ctx=Depends(require_ngo)):
    ngo = ctx[1]
    today = now_local().date().isoformat()
    events = await db.events.find({"ngo_id": ngo["id"]}, P).to_list(1000)
    ev_map = {e["id"]: e for e in events}
    regs = await db.registrations.find({"event_id": {"$in": list(ev_map)}}, P).to_list(100000)
    att = await db.attendance.find({"registration_id": {"$in": [r["id"] for r in regs]}}, P).to_list(100000)
    shifts = await shifts_with_coverage(await db.shifts.find({"event_id": {"$in": list(ev_map)}}, P).to_list(10000))
    present = sum(a["attendance_status"] == "present" for a in att)
    cancelled = sum(r["registration_status"] == "cancelled" for r in regs)
    per_event = Counter(r["event_id"] for r in regs if r["active"])
    gaps = defaultdict(int)
    for s in shifts:
        if s["shift_date"] >= today:
            for g in s["coverage"]["missing_skills"]:
                gaps[g["skill"]] += g["required"] - g["have"]
    status_split = Counter(s["coverage"]["status"] for s in shifts if s["shift_date"] >= today)
    return {
        "events_conducted": sum(1 for e in events if e["event_date"] < today and e["status"] != "draft"),
        "total_registrations": len(regs),
        "total_hours": round(sum(a["hours_contributed"] for a in att), 1),
        "avg_coverage": round(sum(s["coverage"]["coverage_pct"] for s in shifts) / len(shifts), 1) if shifts else 0,
        "attendance_rate": round(present / len(att) * 100, 1) if att else 0,
        "cancellation_rate": round(cancelled / len(regs) * 100, 1) if regs else 0,
        "top_events": [{"name": ev_map[k]["title"], "value": v} for k, v in per_event.most_common(6)],
        "skill_shortages": [{"name": k, "value": v} for k, v in sorted(gaps.items(), key=lambda x: -x[1])],
        "category_split": [{"name": k, "value": v} for k, v in Counter(e["category"] for e in events).items()],
        "status_split": [{"name": k, "value": v} for k, v in status_split.items()],
    }
