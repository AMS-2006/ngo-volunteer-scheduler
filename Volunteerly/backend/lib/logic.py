"""Domain logic: time math, availability, coverage, matching engine, notifications, view builders."""
import math
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from lib.db import db

TZ = ZoneInfo("Asia/Kolkata")  # event times are local Indian time
INVITE_HOURS = 6  # unanswered invitations expire after this (never later than shift start)
FORWARD_COUNT = 3  # on expiry, the vacancy is offered to this many next-best candidates
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
SLOTS = {"morning": (360, 720), "afternoon": (720, 1020), "evening": (1020, 1320)}
CATEGORY_INTEREST = {
    "education": "education", "healthcare": "healthcare", "environment": "environment",
    "animal_welfare": "animal_welfare", "food_distribution": "community_service",
    "disaster_relief": "disaster_relief", "community_development": "community_service", "other": "",
}
P = {"_id": 0}


def new_id() -> str:
    return str(uuid.uuid4())


def now_local() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def to_min(t: str) -> int:
    h, m = t.split(":")[:2]
    return int(h) * 60 + int(m)


def shift_start(s: dict) -> datetime:
    return datetime.fromisoformat(f"{s['shift_date']}T{s['start_time']}")


def shift_hours(s: dict) -> float:
    return round(max(0, to_min(s["end_time"]) - to_min(s["start_time"])) / 60, 2)


def overlaps(a: dict, b: dict) -> bool:
    return (a["shift_date"] == b["shift_date"]
            and to_min(a["start_time"]) < to_min(b["end_time"])
            and to_min(b["start_time"]) < to_min(a["end_time"]))


def valid_date(d: str) -> bool:
    try:
        date.fromisoformat(d)
        return True
    except ValueError:
        return False


def valid_time(t: str) -> bool:
    try:
        h, m = t.split(":")[:2]
        return 0 <= int(h) < 24 and 0 <= int(m) < 60
    except (ValueError, AttributeError):
        return False


def availability_score(vol: dict, shift: dict) -> Optional[float]:
    """Fraction of the shift covered by the volunteer's availability; None when not specified."""
    av = vol.get("availability") or {}
    days, slots = av.get("days") or [], av.get("slots") or []
    if not days and not slots:
        return None
    wd = DAYS[date.fromisoformat(shift["shift_date"]).weekday()]
    if days and wd not in days:
        return 0.0
    if not slots:
        return 1.0
    s, e = to_min(shift["start_time"]), to_min(shift["end_time"])
    total = e - s
    if total <= 0:
        return 0.0
    covered = sum(max(0, min(e, b) - max(s, a)) for k, (a, b) in SLOTS.items() if k in slots)
    return round(min(1.0, covered / total), 3)


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def compute_coverage(shift: dict, vol_skills: list[list[str]]) -> dict:
    """Headcount + skill coverage. Reusable for any shift and list of registered volunteers' skills."""
    cap = int(shift.get("capacity") or 0)
    reg = len(vol_skills)
    pool = [set(s) for s in vol_skills]
    used = [False] * len(pool)
    gaps = []
    reqs = shift.get("required_skills") or []
    for r in sorted(reqs, key=lambda r: sum(r["skill"] in p for p in pool)):  # scarcest first
        have = 0
        for i, p in enumerate(pool):
            if have >= r["count"]:
                break
            if not used[i] and r["skill"] in p:
                used[i] = True
                have += 1
        if have < r["count"]:
            gaps.append({"skill": r["skill"], "required": r["count"], "have": have})
    pct = round(min(reg, cap) / cap * 100) if cap else 0
    if cap and reg >= cap:
        status = "fully_staffed" if not gaps else "fully_booked"
    elif pct >= 50:
        status = "partially_staffed"
    else:
        status = "critical_shortage"
    return {"required": cap, "registered": reg, "vacant": max(0, cap - reg),
            "coverage_pct": pct, "status": status, "missing_skills": gaps}


async def shifts_with_coverage(shifts: list[dict], vol_id: Optional[str] = None) -> list[dict]:
    ids = [s["id"] for s in shifts]
    regs = await db.registrations.find({"shift_id": {"$in": ids}, "active": True}, P).to_list(50000)
    vids = list({r["volunteer_id"] for r in regs})
    skills = {v["id"]: v.get("skills", []) for v in
              await db.volunteer_profiles.find({"id": {"$in": vids}}, {"_id": 0, "id": 1, "skills": 1}).to_list(50000)}
    by_shift = defaultdict(list)
    mine = set()
    for r in regs:
        by_shift[r["shift_id"]].append(skills.get(r["volunteer_id"], []))
        if r["volunteer_id"] == vol_id:
            mine.add(r["shift_id"])
    out = [{**s, "coverage": compute_coverage(s, by_shift[s["id"]]), "is_registered": s["id"] in mine} for s in shifts]
    return sorted(out, key=lambda s: (s["shift_date"], s["start_time"]))


def aggregate_status(shifts: list[dict]) -> str:
    st = [s["coverage"]["status"] for s in shifts]
    if not st or "critical_shortage" in st:
        return "critical_shortage"
    if all(x == "fully_staffed" for x in st):
        return "fully_staffed"
    if all(x in ("fully_staffed", "fully_booked") for x in st):
        return "fully_booked"
    return "partially_staffed"


def registration_open(event: dict) -> bool:
    try:
        return event["status"] == "published" and now_local() <= datetime.fromisoformat(event["registration_deadline"])
    except ValueError:
        return False


async def build_event_cards(events: list[dict], vol_id: Optional[str] = None, with_shifts=False) -> list[dict]:
    if not events:
        return []
    shifts = await db.shifts.find({"event_id": {"$in": [e["id"] for e in events]}}, P).to_list(50000)
    cov = await shifts_with_coverage(shifts, vol_id)
    ngos = {n["id"]: n for n in await db.ngo_profiles.find(
        {"id": {"$in": list({e["ngo_id"] for e in events})}}, P).to_list(1000)}
    by_event = defaultdict(list)
    for s in cov:
        by_event[s["event_id"]].append(s)
    out = []
    for e in events:
        sh = by_event[e["id"]]
        card = {**e, "ngo_name": ngos.get(e["ngo_id"], {}).get("organization_name", ""),
                "shifts_count": len(sh), "total_capacity": sum(s["capacity"] for s in sh),
                "total_filled": sum(s["coverage"]["registered"] for s in sh),
                "coverage_status": aggregate_status(sh), "registration_open": registration_open(e)}
        if with_shifts:
            card["shifts"] = sh
        out.append(card)
    return out


async def notify(user_id: str, ntype: str, title: str, message: str, params: Optional[dict] = None,
                 event_id: Optional[str] = None, shift_id: Optional[str] = None, dedupe_key: Optional[str] = None):
    doc = {"id": new_id(), "recipient_user_id": user_id, "title": title, "message": message,
           "notification_type": ntype, "params": {k: str(v) for k, v in (params or {}).items()},
           "related_event_id": event_id, "related_shift_id": shift_id, "read_status": False,
           "created_at": now_iso()}
    if dedupe_key:
        doc["dedupe_key"] = dedupe_key
        if await db.notifications.find_one({"dedupe_key": dedupe_key}):
            return
    await db.notifications.insert_one(doc)


def fmt_shift(s: dict) -> str:
    return f"{s['shift_date']} {s['start_time']}-{s['end_time']}"


async def volunteer_hours(vol_ids: list[str]) -> dict[str, float]:
    regs = await db.registrations.find({"volunteer_id": {"$in": vol_ids}}, {"_id": 0, "id": 1, "volunteer_id": 1}).to_list(100000)
    rmap = {r["id"]: r["volunteer_id"] for r in regs}
    att = await db.attendance.find({"registration_id": {"$in": list(rmap)}, "attendance_status": "present"}, P).to_list(100000)
    hours = defaultdict(float)
    for a in att:
        hours[rmap[a["registration_id"]]] += a["hours_contributed"]
    return hours


def volunteer_public(v: dict, show_contact=False, hours=0.0, engagements=0) -> dict:
    share = (v.get("privacy") or {}).get("share_contact", False)
    return {"id": v["id"], "name": v["name"], "profile_image": v.get("profile_image", ""),
            "location": v.get("location", ""), "skills": v.get("skills", []), "interests": v.get("interests", []),
            "phone": v.get("phone") if (show_contact and share) else None, "is_demo": v.get("is_demo", False),
            "total_hours": round(hours, 1), "engagements": engagements}


async def find_conflict(vol_id: str, shift: dict) -> Optional[dict]:
    same_day = await db.shifts.find({"shift_date": shift["shift_date"], "id": {"$ne": shift["id"]}}, P).to_list(1000)
    by_id = {s["id"]: s for s in same_day}
    regs = await db.registrations.find({"volunteer_id": vol_id, "active": True, "shift_id": {"$in": list(by_id)}}, P).to_list(100)
    for r in regs:
        other = by_id[r["shift_id"]]
        if overlaps(other, shift):
            ev = await db.events.find_one({"id": other["event_id"]}, P) or {}
            return {"shift": other, "event_title": ev.get("title", "another event")}
    return None


async def target_skills_for(shift: dict, event: dict, cancelled_vol: Optional[dict] = None) -> list[str]:
    cov = (await shifts_with_coverage([shift]))[0]["coverage"]
    gaps = [g["skill"] for g in cov["missing_skills"]]
    if gaps:
        return gaps
    req = [r["skill"] for r in shift.get("required_skills") or []]
    if cancelled_vol and req:
        mine = [s for s in req if s in (cancelled_vol.get("skills") or [])]
        if mine:
            return mine
    return req or list(event.get("required_skills") or [])


async def find_candidates(shift: dict, event: dict, target: list[str], exclude: set[str]) -> tuple[list[dict], dict]:
    """Eligibility filters (mandatory) + weighted score: skills 40, availability 30, distance 20, interests 10,
    then a small fairness adjustment (<=5 pts) favouring less-utilised volunteers. Cancellations never penalise."""
    vols = await db.volunteer_profiles.find({}, P).to_list(10000)
    same_day = {s["id"]: s for s in await db.shifts.find({"shift_date": shift["shift_date"]}, P).to_list(2000)}
    day_regs = await db.registrations.find({"active": True, "shift_id": {"$in": list(same_day)}}, P).to_list(50000)
    busy = defaultdict(list)
    for r in day_regs:
        busy[r["volunteer_id"]].append(same_day[r["shift_id"]])
    today = now_local().date().isoformat()
    upcoming_ids = [s["id"] for s in await db.shifts.find({"shift_date": {"$gte": today}}, {"_id": 0, "id": 1}).to_list(50000)]
    upcoming = defaultdict(int)
    for r in await db.registrations.find({"active": True, "registration_status": "confirmed", "shift_id": {"$in": upcoming_ids}},
                                         {"_id": 0, "volunteer_id": 1}).to_list(50000):
        upcoming[r["volunteer_id"]] += 1
    since = (datetime.now(TZ) - timedelta(days=30)).isoformat()
    all_regs = {r["id"]: r["volunteer_id"] for r in await db.registrations.find({}, {"_id": 0, "id": 1, "volunteer_id": 1}).to_list(100000)}
    recent = defaultdict(float)
    for a in await db.attendance.find({"attendance_status": "present", "check_in_time": {"$gte": since}}, P).to_list(100000):
        if a["registration_id"] in all_regs:
            recent[all_regs[a["registration_id"]]] += a["hours_contributed"]
    invites = {i["invited_volunteer_id"]: i["invitation_status"] for i in
               await db.replacement_invitations.find({"shift_id": shift["id"]}, P).sort("created_at", 1).to_list(1000)}
    interest = CATEGORY_INTEREST.get(event.get("category", ""), "")
    excluded: dict[str, int] = defaultdict(int)
    out = []
    for v in vols:
        vid = v["id"]
        if vid in exclude:
            continue
        if any(s["id"] == shift["id"] for s in busy[vid]):
            excluded["already_registered"] += 1
            continue
        if not (v.get("privacy") or {}).get("replacement_opt_in", True):
            excluded["opted_out"] += 1
            continue
        av = availability_score(v, shift)
        if not av:
            excluded["unavailable"] += 1
            continue
        if any(overlaps(s, shift) for s in busy[vid]):
            excluded["schedule_conflict"] += 1
            continue
        matched = [s for s in target if s in (v.get("skills") or [])]
        if target and not matched:
            excluded["no_relevant_skills"] += 1
            continue
        dist = None
        if (v.get("privacy") or {}).get("share_location", True) and v.get("latitude") is not None \
                and event.get("latitude") is not None:
            dist = round(haversine_km(v["latitude"], v["longitude"], event["latitude"], event["longitude"]), 1)
            if dist > float(v.get("preferred_travel_radius") or 15):
                excluded["outside_travel_radius"] += 1
                continue
        radius = float(v.get("preferred_travel_radius") or 15)
        s_skill = 40 * (len(matched) / len(target) if target else 1)
        s_av = 30 * av
        s_dist = 20 * (max(0.0, 1 - dist / radius) if dist is not None else 0.5)  # neutral when unknown
        prefs = set(v.get("interests") or []) | set(v.get("preferred_activities") or [])
        s_int = 10 * (1.0 if interest and interest in prefs else (0.5 if event.get("category") in prefs else 0.0))
        load = min(1.0, (recent[vid] / 20 + upcoming[vid] / 4) / 2)
        fair = -round(5 * load, 1)
        score = round(max(0, s_skill + s_av + s_dist + s_int + fair), 1)
        out.append({"volunteer": volunteer_public(v), "score": score,
                    "breakdown": {"skills": round(s_skill, 1), "availability": round(s_av, 1),
                                  "distance": round(s_dist, 1), "interests": round(s_int, 1), "fairness_adjustment": fair},
                    "matched_skills": matched, "distance_km": dist, "availability_pct": round(av * 100),
                    "recent_hours": round(recent[vid], 1), "upcoming_commitments": upcoming[vid],
                    "invitation_status": invites.get(vid)})
    out.sort(key=lambda c: (-c["score"], c["recent_hours"], c["upcoming_commitments"]))
    return out, dict(excluded)


async def bump_live() -> None:
    """Global change counter polled by clients (/api/live) to refresh views. Carries no data."""
    await db.meta.update_one({"_id": "live"}, {"$inc": {"v": 1}}, upsert=True)


async def send_invites(ngo: dict, sh: dict, ev: dict, vol_ids: list[str], cancelled_reg_id: Optional[str],
                       urgent: bool, auto: bool = False) -> tuple[int, int, list[str]]:
    """Invite volunteers who pass the mandatory checks right now. Returns (invited, skipped, invited names)."""
    cancelled_vol = None
    exclude: set[str] = set()
    if cancelled_reg_id:
        reg = await db.registrations.find_one({"id": cancelled_reg_id, "shift_id": sh["id"], "registration_status": "cancelled"}, P)
        if not reg:
            raise HTTPException(404, "Cancelled registration not found")
        if reg.get("replaced_by"):
            raise HTTPException(409, "This vacancy has already been filled.")
        cancelled_vol = await db.volunteer_profiles.find_one({"id": reg["volunteer_id"]}, P)
        exclude.add(reg["volunteer_id"])
    target = await target_skills_for(sh, ev, cancelled_vol)
    cands, _ = await find_candidates(sh, ev, target, exclude)
    by_id = {c["volunteer"]["id"]: c for c in cands}
    vols = {v["id"]: v for v in await db.volunteer_profiles.find({"id": {"$in": vol_ids}}, P).to_list(100)}
    expires = min(shift_start(sh), now_local() + timedelta(hours=INVITE_HOURS)).isoformat(timespec="minutes")
    invited, skipped, names = 0, 0, []
    for vid in vol_ids:
        c = by_id.get(vid)
        if not c or vid not in vols or await db.replacement_invitations.find_one(
                {"shift_id": sh["id"], "invited_volunteer_id": vid, "invitation_status": "pending"}):
            skipped += 1  # ineligible (failed mandatory checks) or already invited
            continue
        await db.replacement_invitations.insert_one({
            "id": new_id(), "shift_id": sh["id"], "cancelled_registration_id": cancelled_reg_id,
            "invited_volunteer_id": vid, "match_score": c["score"], "invitation_status": "pending",
            "urgent": urgent, "auto_forwarded": auto, "created_at": now_iso(), "expires_at": expires})
        ntype = "urgent_request" if urgent else "replacement_invitation"
        await notify(vols[vid]["user_id"], ntype,
                     ("URGENT: " if urgent else "") + f"Replacement request: {ev['title']}",
                     f"{ngo['organization_name']} invites you ({c['score']}% match) to the {fmt_shift(sh)} shift of {ev['title']}.",
                     {"event": ev["title"], "ngo": ngo["organization_name"], "shift": fmt_shift(sh), "score": c["score"]},
                     ev["id"], sh["id"])
        invited += 1
        names.append(vols[vid]["name"])
    return invited, skipped, names


async def process_expired_invitations() -> dict:
    """Expire unanswered invitations and pass each still-open vacancy to the next-best candidates
    (never re-inviting anyone already asked for that shift). Idempotent: expiry is an atomic status flip."""
    now = now_local()
    stamp = now.isoformat(timespec="minutes")
    expired = []
    while True:
        inv = await db.replacement_invitations.find_one_and_update(
            {"invitation_status": "pending", "expires_at": {"$lt": stamp}},
            {"$set": {"invitation_status": "expired"}}, projection=P)
        if not inv:
            break
        expired.append(inv)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for i in expired:
        groups[(i["shift_id"], i.get("cancelled_registration_id"))].append(i)
    forwarded = 0
    for (sid, crid), invs in groups.items():
        sh = await db.shifts.find_one({"id": sid}, P)
        if not sh or shift_start(sh) <= now or sh["filled"] >= sh["capacity"]:
            continue
        ev = await db.events.find_one({"id": sh["event_id"]}, P)
        ngo = await db.ngo_profiles.find_one({"id": ev["ngo_id"]}, P) if ev else None
        if not ngo or ev["status"] != "published":
            continue
        exclude: set[str] = set()
        cancelled_vol = None
        if crid:
            reg = await db.registrations.find_one({"id": crid}, P)
            if not reg or reg.get("replaced_by"):
                continue
            exclude.add(reg["volunteer_id"])
            cancelled_vol = await db.volunteer_profiles.find_one({"id": reg["volunteer_id"]}, P)
        # someone is still considering this vacancy — only top up, don't flood
        still_pending = await db.replacement_invitations.count_documents(
            {"shift_id": sid, "cancelled_registration_id": crid, "invitation_status": "pending"})
        need = FORWARD_COUNT - still_pending
        if need <= 0:
            continue
        target = await target_skills_for(sh, ev, cancelled_vol)
        cands, _ = await find_candidates(sh, ev, target, exclude)
        pick = [c["volunteer"]["id"] for c in cands if c["invitation_status"] is None][:need]
        expired_names = ", ".join(v["name"] for v in await db.volunteer_profiles.find(
            {"id": {"$in": [i["invited_volunteer_id"] for i in invs]}}, P).to_list(100))
        p = {"event": ev["title"], "shift": fmt_shift(sh), "expired": expired_names}
        if not pick:
            await notify(ngo["user_id"], "invite_expired_none", f"No more candidates: {ev['title']}",
                         f"Invitations for {fmt_shift(sh)} expired and no further eligible volunteers were found.",
                         p, ev["id"], sid)
            continue
        n, _, names = await send_invites(ngo, sh, ev, pick, crid, any(i.get("urgent") for i in invs), auto=True)
        forwarded += n
        await notify(ngo["user_id"], "invite_forwarded", f"Invitation passed on: {ev['title']}",
                     f"{expired_names} did not respond in time for {fmt_shift(sh)}. Invited next: {', '.join(names)}.",
                     {**p, "names": ", ".join(names)}, ev["id"], sid)
    if expired:
        await bump_live()
    return {"expired": len(expired), "forwarded": forwarded}
