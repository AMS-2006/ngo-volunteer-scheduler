"""Idempotent demo seed: `cd /app/backend && python seed.py`. Drops only demo (is_demo) records and recreates them.
Dates are relative to today (IST) so the demo stays current. All people, NGOs and emails are fictional."""
import asyncio
from datetime import datetime, timedelta

from lib.db import db, ensure_indexes
from lib.logic import TZ, new_id, now_local, shift_hours
from lib.security import hash_password

PW = hash_password("Demo@1234")
TODAY = now_local().date()


def d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def ts(offset_days: float = 0) -> str:
    return (datetime.now(TZ) + timedelta(days=offset_days)).isoformat(timespec="seconds")


ALL_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
PLACES = {
    "Koramangala": (12.9352, 77.6245), "Indiranagar": (12.9719, 77.6412), "Jayanagar": (12.9250, 77.5938),
    "Whitefield": (12.9698, 77.7500), "Malleshwaram": (13.0031, 77.5643), "HSR Layout": (12.9116, 77.6474),
    "Rajajinagar": (12.9910, 77.5520), "BTM Layout": (12.9166, 77.6101), "Hebbal": (13.0358, 77.5970),
    "Electronic City": (12.8452, 77.6602), "Mysuru": (12.2958, 76.6394), "Chennai": (13.0827, 80.2707),
    "Lalbagh": (12.9507, 77.5848), "Ulsoor Lake": (12.9817, 77.6194),
}

NGOS = [
    ("annapurna@demo.vc", "Annapurna Food Trust", "Koramangala",
     "Community kitchen network rescuing surplus food and distributing meals to families across Bengaluru.",
     ["food_distribution", "disaster_relief", "community_development"], "verified"),
    ("jeevan@demo.vc", "Jeevan Health Foundation", "Jayanagar",
     "Free health camps, first-aid training and blood donation drives for under-served neighbourhoods.",
     ["healthcare", "education"], "verified"),
    ("hasiru@demo.vc", "Hasiru Bengaluru Collective", "Malleshwaram",
     "Citizen-led urban greening: tree plantations, lake clean-ups and children's nature education.",
     ["environment", "education", "animal_welfare"], "pending"),
]

# email, name, place, skills, interests, days, slots, radius, privacy overrides, lang
VOLS = [
    ("priya@demo.vc", "Priya Sharma", "Indiranagar", ["communication", "event_management", "first_aid"],
     ["community_service", "healthcare"], ALL_DAYS, ["morning", "afternoon"], 15, {}, "en"),
    ("kavya@demo.vc", "Kavya Reddy", "Koramangala", ["logistics", "event_management", "communication"],
     ["community_service", "disaster_relief"], ALL_DAYS, ["morning", "afternoon", "evening"], 12, {}, "te"),
    ("arjun@demo.vc", "Arjun Nair", "HSR Layout", ["logistics", "data_entry"],
     ["community_service"], ALL_DAYS, ["morning", "afternoon"], 15, {}, "en"),
    ("meera@demo.vc", "Meera Iyer", "BTM Layout", ["logistics", "fundraising"],
     ["education", "community_service"], ALL_DAYS, ["afternoon"], 10, {}, "ta"),
    ("rohan@demo.vc", "Rohan Gowda", "Jayanagar", ["logistics", "photography"],
     ["environment", "community_service"], ALL_DAYS, ["morning", "afternoon"], 20, {}, "kn"),
    ("ananya@demo.vc", "Ananya Krishnan", "Whitefield", ["teaching", "communication"],
     ["education"], ["sat", "sun"], ["morning"], 25, {}, "ta"),
    ("vikram@demo.vc", "Vikram Singh", "Hebbal", ["first_aid", "logistics", "technical_support"],
     ["healthcare", "disaster_relief"], ALL_DAYS, ["morning", "afternoon", "evening"], 20, {}, "hi"),
    ("sneha@demo.vc", "Sneha Patil", "Rajajinagar", ["graphic_design", "photography", "communication"],
     ["animal_welfare", "environment"], ALL_DAYS, ["afternoon", "evening"], 15, {}, "en"),
    ("farhan@demo.vc", "Farhan Sheikh", "Electronic City", ["logistics", "technical_support"],
     ["disaster_relief"], ALL_DAYS, ["morning", "afternoon"], 30, {}, "hi"),
    ("lakshmi@demo.vc", "Lakshmi Rao", "Malleshwaram", ["first_aid", "teaching", "data_entry"],
     ["healthcare", "education"], ALL_DAYS, ["morning"], 12, {}, "kn"),
    ("aditya@demo.vc", "Aditya Menon", "Koramangala", ["logistics", "event_management"],
     ["community_service"], ALL_DAYS, ["morning", "afternoon"], 10, {"replacement_opt_in": False}, "en"),
    ("divya@demo.vc", "Divya Hegde", "Indiranagar", ["logistics", "communication"],
     ["community_service", "healthcare"], ALL_DAYS, ["morning", "afternoon"], 15, {"share_location": False}, "kn"),
    ("sanjay@demo.vc", "Sanjay Kumar", "Mysuru", ["logistics", "first_aid"],
     ["disaster_relief"], ALL_DAYS, ["morning", "afternoon"], 20, {}, "kn"),
    ("nisha@demo.vc", "Nisha Verma", "Chennai", ["teaching", "fundraising"],
     ["education"], ALL_DAYS, ["morning", "afternoon"], 10, {}, "hi"),
]

IMG = {
    "food": "https://images.unsplash.com/photo-1593113598332-cd288d649433?w=1200&q=70",
    "health": "https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=1200&q=70",
    "tree": "https://images.unsplash.com/photo-1551855350-c86caeaf8707?w=1200&q=70",
    "lake": "https://images.unsplash.com/photo-1618477461853-cf6ed80faba5?w=1200&q=70",
    "flood": "https://images.unsplash.com/photo-1547683905-f686c993aae5?w=1200&q=70",
    "book": "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=1200&q=70",
    "team": "https://images.unsplash.com/photo-1542323228-002ac256e7b8?w=1200&q=70",
}


def S(date_off, start, end, cap, skills=()):
    return {"shift_date": d(date_off), "start_time": start, "end_time": end, "capacity": cap,
            "required_skills": [{"skill": s, "count": c} for s, c in skills]}


# ngo index, key, title, desc, category, place, day offset, start, end, req, skills, img, status, shifts, translations
EVENTS = [
    (0, "food", "Community Food Distribution Drive",
     "Help pack and distribute 1,500 meal kits to families in Koramangala and Ejipura. Volunteers handle unloading, packing lines, queue management and record keeping.",
     "food_distribution", "Koramangala", 1, "08:00", "17:00", 18, ["logistics", "communication", "data_entry"], "food", "published",
     [S(1, "08:00", "11:00", 5, [("logistics", 2), ("communication", 1)]),
      S(1, "11:00", "14:00", 8, [("logistics", 3), ("event_management", 1)]),
      S(1, "14:00", "17:00", 5, [("data_entry", 1)])],
     {"hi": {"title": "सामुदायिक भोजन वितरण अभियान", "description": "कोरमंगला और एजिपुरा के परिवारों को 1,500 भोजन किट पैक करने और वितरित करने में मदद करें।"},
      "kn": {"title": "ಸಮುದಾಯ ಆಹಾರ ವಿತರಣಾ ಅಭಿಯಾನ", "description": "ಕೋರಮಂಗಲ ಮತ್ತು ಈಜಿಪುರದ ಕುಟುಂಬಗಳಿಗೆ 1,500 ಆಹಾರ ಕಿಟ್‌ಗಳನ್ನು ಪ್ಯಾಕ್ ಮಾಡಿ ವಿತರಿಸಲು ಸಹಾಯ ಮಾಡಿ."}}),
    (0, "flood", "Flood Relief Supply Kits",
     "Urgent assembly of hygiene and dry-ration kits for flood-affected households in Kodagu, dispatched from our Koramangala warehouse.",
     "disaster_relief", "Koramangala", 3, "09:00", "15:00", 12, ["logistics", "first_aid"], "flood", "published",
     [S(3, "09:00", "12:00", 6, [("logistics", 3), ("first_aid", 1)]), S(3, "12:00", "15:00", 6, [("logistics", 3)])], {}),
    (0, "food2", "Weekend Meal Packing Marathon",
     "Join our weekend packing marathon for the school breakfast programme.", "food_distribution", "HSR Layout",
     5, "09:00", "13:00", 10, ["logistics"], "team", "published",
     [S(5, "09:00", "11:00", 5, [("logistics", 2)]), S(5, "11:00", "13:00", 5)], {}),
    (1, "med", "Medical Awareness Camp",
     "A free screening and awareness camp in Jayanagar 4th Block. Needs first-aid volunteers, registration desk staff and logistics support.",
     "healthcare", "Jayanagar", 2, "09:00", "17:00", 16, ["first_aid", "communication", "logistics"], "health", "published",
     [S(2, "09:00", "13:00", 10, [("first_aid", 2), ("communication", 3), ("logistics", 3)]),
      S(2, "13:00", "17:00", 6, [("first_aid", 1)])],
     {"hi": {"title": "चिकित्सा जागरूकता शिविर", "description": "जयनगर में निःशुल्क स्वास्थ्य जांच और जागरूकता शिविर।"},
      "ta": {"title": "மருத்துவ விழிப்புணர்வு முகாம்", "description": "ஜெயநகரில் இலவச பரிசோதனை மற்றும் விழிப்புணர்வு முகாம்."}}),
    (1, "senior", "Senior Citizens Health Check-up",
     "Assist doctors with vitals, queue management and counselling for elderly residents.", "healthcare", "Indiranagar",
     1, "09:00", "15:00", 10, ["first_aid", "communication"], "health", "published",
     [S(1, "09:00", "12:00", 6, [("first_aid", 2)]), S(1, "12:00", "15:00", 4)], {}),
    (1, "blood", "Blood Donation Drive", "Quarterly blood donation drive with Rotary partners.", "healthcare", "Jayanagar",
     8, "10:00", "16:00", 8, ["first_aid"], "health", "draft", [S(8, "10:00", "16:00", 8, [("first_aid", 2)])], {}),
    (2, "tree", "Lalbagh Tree Plantation",
     "Plant 400 native saplings along the Lalbagh periphery and set up watering schedules.", "environment", "Lalbagh",
     4, "07:00", "12:00", 15, ["logistics", "photography"], "tree", "published",
     [S(4, "07:00", "09:30", 8, [("logistics", 2)]), S(4, "09:30", "12:00", 7, [("photography", 1)])], {}),
    (2, "lake", "Ulsoor Lake Clean-up Saturday", "Remove plastic waste and invasive weeds around Ulsoor Lake.",
     "environment", "Ulsoor Lake", 10, "07:00", "11:00", 20, ["logistics"], "lake", "published",
     [S(10, "07:00", "09:00", 10), S(10, "09:00", "11:00", 10, [("logistics", 2)])], {}),
    # past events for participation history
    (2, "read", "Children's Reading Week", "Storytelling and reading sessions in government schools.", "education",
     "Malleshwaram", -12, "09:00", "12:00", 6, ["teaching"], "book", "published", [S(-12, "09:00", "12:00", 6, [("teaching", 2)])], {}),
    (0, "pastfood", "Ramadan Iftar Meal Drive", "Evening meal distribution across Shivajinagar.", "food_distribution",
     "Koramangala", -20, "09:00", "14:00", 8, ["logistics"], "food", "published", [S(-20, "09:00", "14:00", 8, [("logistics", 3)])], {}),
]

# event key -> list of (shift index, volunteer email, status, hours or None)
REGS = {
    "food": [(0, "priya@demo.vc", "confirmed"), (0, "arjun@demo.vc", "confirmed"), (0, "lakshmi@demo.vc", "confirmed"),
             (1, "meera@demo.vc", "confirmed"), (1, "farhan@demo.vc", "confirmed"), (1, "aditya@demo.vc", "confirmed"),
             (1, "sneha@demo.vc", "confirmed"), (1, "vikram@demo.vc", "confirmed"), (1, "rohan@demo.vc", "cancelled"),
             (2, "ananya@demo.vc", "confirmed"), (2, "nisha@demo.vc", "confirmed"), (2, "sanjay@demo.vc", "confirmed"),
             (2, "divya@demo.vc", "confirmed"), (2, "kavya@demo.vc", "confirmed")],
    "flood": [(0, "vikram@demo.vc", "confirmed")],
    "food2": [(0, "arjun@demo.vc", "confirmed"), (0, "farhan@demo.vc", "confirmed"), (1, "meera@demo.vc", "confirmed")],
    "med": [(0, "lakshmi@demo.vc", "confirmed"), (0, "priya@demo.vc", "confirmed"), (0, "divya@demo.vc", "confirmed"),
            (0, "sneha@demo.vc", "confirmed"), (0, "rohan@demo.vc", "confirmed"), (1, "vikram@demo.vc", "confirmed")],
    "senior": [(1, "lakshmi@demo.vc", "cancelled")],
    "tree": [(0, "rohan@demo.vc", "confirmed"), (0, "arjun@demo.vc", "confirmed"), (1, "sneha@demo.vc", "confirmed")],
    "read": [(0, "ananya@demo.vc", "present"), (0, "lakshmi@demo.vc", "present"), (0, "nisha@demo.vc", "absent"),
             (0, "priya@demo.vc", "present")],
    "pastfood": [(0, "priya@demo.vc", "present"), (0, "kavya@demo.vc", "present"), (0, "arjun@demo.vc", "present"),
                 (0, "farhan@demo.vc", "present"), (0, "meera@demo.vc", "present"), (0, "rohan@demo.vc", "present")],
}


async def clear_demo():
    demo_users = [u["id"] for u in await db.users.find({"is_demo": True}, {"id": 1}).to_list(1000)]
    demo_ngos = [n["id"] for n in await db.ngo_profiles.find({"is_demo": True}, {"id": 1}).to_list(100)]
    # events owned by demo NGOs (including ones created during a demo walkthrough) are reset too
    demo_events = [e["id"] for e in await db.events.find(
        {"$or": [{"is_demo": True}, {"ngo_id": {"$in": demo_ngos}}]}, {"id": 1}).to_list(1000)]
    demo_vols = [v["id"] for v in await db.volunteer_profiles.find({"is_demo": True}, {"id": 1}).to_list(1000)]
    shift_ids = [s["id"] for s in await db.shifts.find({"event_id": {"$in": demo_events}}, {"id": 1}).to_list(10000)]
    reg_ids = [r["id"] for r in await db.registrations.find(
        {"$or": [{"event_id": {"$in": demo_events}}, {"volunteer_id": {"$in": demo_vols}}]}, {"id": 1}).to_list(100000)]
    await db.attendance.delete_many({"registration_id": {"$in": reg_ids}})
    await db.registrations.delete_many({"id": {"$in": reg_ids}})
    await db.replacement_invitations.delete_many({"$or": [{"shift_id": {"$in": shift_ids}}, {"invited_volunteer_id": {"$in": demo_vols}}]})
    # keep real users' shift counters consistent
    await db.shifts.delete_many({"event_id": {"$in": demo_events}})
    await db.events.delete_many({"id": {"$in": demo_events}})
    await db.notifications.delete_many({"recipient_user_id": {"$in": demo_users}})
    await db.sessions.delete_many({"user_id": {"$in": demo_users}})
    await db.ngo_profiles.delete_many({"is_demo": True})
    await db.volunteer_profiles.delete_many({"is_demo": True})
    await db.users.delete_many({"is_demo": True})


async def main():
    await ensure_indexes()
    await clear_demo()
    ngo_ids, ngo_users = [], []
    for email, name, place, desc, causes, ver in NGOS:
        uid, nid = new_id(), new_id()
        lat, lng = PLACES[place]
        await db.users.insert_one({"id": uid, "role": "ngo", "full_name": name, "email": email, "phone": "+91 80 4000 1000",
                                   "preferred_language": "en", "created_at": ts(-60), "password_hash": PW, "is_demo": True})
        await db.ngo_profiles.insert_one({"id": nid, "user_id": uid, "organization_name": name, "description": desc,
                                          "logo_url": "", "contact_email": email, "contact_number": "+91 80 4000 1000",
                                          "location": f"{place}, Bengaluru", "latitude": lat, "longitude": lng,
                                          "causes": causes, "verification_status": ver, "is_demo": True})
        ngo_ids.append(nid)
        ngo_users.append(uid)
    vols = {}
    for i, (email, name, place, skills, interests, days, slots, radius, priv, lang) in enumerate(VOLS):
        uid, vid = new_id(), new_id()
        lat, lng = PLACES[place]
        phone = f"+91 98450 {10000 + i * 137}"
        await db.users.insert_one({"id": uid, "role": "volunteer", "full_name": name, "email": email, "phone": phone,
                                   "preferred_language": lang, "created_at": ts(-50 + i), "password_hash": PW, "is_demo": True})
        privacy = {"share_location": True, "share_contact": i % 2 == 0, "replacement_opt_in": True, **priv}
        await db.volunteer_profiles.insert_one({
            "id": vid, "user_id": uid, "name": name, "profile_image": f"https://i.pravatar.cc/150?u={email}",
            "phone": phone, "location": place if place in ("Mysuru", "Chennai") else f"{place}, Bengaluru",
            "latitude": lat, "longitude": lng, "skills": skills, "interests": interests, "preferred_activities": [],
            "availability": {"days": days, "slots": slots}, "preferred_language": lang, "languages_spoken": ["en", lang],
            "preferred_travel_radius": radius, "privacy": privacy, "is_demo": True})
        vols[email] = {"id": vid, "user_id": uid, "name": name}
    for ngo_i, key, title, desc, cat, place, off, st, et, req, skills, img, status, shifts, tr in EVENTS:
        eid = new_id()
        lat, lng = PLACES[place]
        dl = (datetime.fromisoformat(f"{d(off)}T{st}") - timedelta(hours=2)).isoformat(timespec="minutes")
        await db.events.insert_one({
            "id": eid, "ngo_id": ngo_ids[ngo_i], "title": title, "description": desc, "category": cat,
            "location": f"{place}, Bengaluru", "latitude": lat, "longitude": lng, "event_date": d(off), "start_time": st,
            "end_time": et, "registration_deadline": dl, "required_volunteers": req, "required_skills": skills,
            "image_url": IMG[img], "status": status, "emergency": key == "flood", "created_at": ts(-30),
            "translations": tr, "is_demo": True})
        sids = []
        for s in shifts:
            sid = new_id()
            sids.append({**s, "id": sid})
            await db.shifts.insert_one({**s, "id": sid, "event_id": eid, "status": "open", "filled": 0})
        for idx, email, rstatus in REGS.get(key, []):
            sh, v = sids[idx], vols[email]
            rid = new_id()
            active = rstatus != "cancelled"
            reg_status = {"present": "completed", "absent": "absent"}.get(rstatus, rstatus)
            await db.registrations.insert_one({
                "id": rid, "volunteer_id": v["id"], "event_id": eid, "shift_id": sh["id"], "registration_status": reg_status,
                "active": active, "registered_at": ts(-7 if off > 0 else off - 5),
                "cancelled_at": ts(-0.1) if not active else None, "source": "direct",
                "last_minute": not active, "replaced_by": None})
            if active:
                await db.shifts.update_one({"id": sh["id"]}, {"$inc": {"filled": 1}})
            if rstatus in ("present", "absent"):
                await db.attendance.insert_one({
                    "id": new_id(), "registration_id": rid, "attendance_status": rstatus,
                    "check_in_time": f"{sh['shift_date']}T{sh['start_time']}:00+05:30",
                    "hours_contributed": shift_hours(sh) if rstatus == "present" else 0})
            if not active:
                await db.notifications.insert_one({
                    "id": new_id(), "recipient_user_id": ngo_users[ngo_i], "notification_type": "volunteer_cancelled",
                    "title": f"LAST-MINUTE Cancellation: {title}",
                    "message": f"{v['name']} cancelled the {sh['shift_date']} {sh['start_time']}-{sh['end_time']} shift. Open the Smart Cancellation Manager to find replacements.",
                    "params": {"volunteer": v["name"], "event": title, "shift": f"{sh['shift_date']} {sh['start_time']}-{sh['end_time']}", "count": "?", "skills": ""},
                    "related_event_id": eid, "related_shift_id": sh["id"], "read_status": False, "created_at": ts(-0.1)})
    print(f"Seeded {len(NGOS)} NGOs, {len(VOLS)} volunteers, {len(EVENTS)} events. Password for all demo accounts: Demo@1234")


if __name__ == "__main__":
    asyncio.run(main())
