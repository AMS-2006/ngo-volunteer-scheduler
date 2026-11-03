"""Criterion: Volunteer cancel triggers engine (+ emergency mode urgent invites)."""
import uuid
from datetime import datetime, timedelta

import httpx

from tests.conftest import api_url


def tomorrow(offset_days=1):
    return (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


def register_volunteer(c, tag):
    suffix = uuid.uuid4().hex[:6]
    name = f"tscheck-cancel-{tag}-{suffix}"
    r = c.post("/auth/register", json={"role": "volunteer", "full_name": name,
               "email": f"tscheck-cancel-{tag}-{suffix}@example.com", "password": "Demo@1234",
               "phone": "9200000000", "location": "Bengaluru"})
    assert r.status_code == 200, r.text
    c.put("/volunteer/profile", json={"name": name, "location": "Bengaluru",
          "availability": {"days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                            "slots": ["morning", "afternoon", "evening"]}, "preferred_travel_radius": 50})
    return r.json()["profile_id"]


def test_volunteer_cancel_notifies_ngo_and_creates_vacancy(client):
    event_date = tomorrow(16)
    client.post("/auth/login", json={"email": "annapurna@demo.vc", "password": "Demo@1234"})
    ev = client.post("/ngo/events", json={
        "title": "tscheck-cancel-engine-event", "description": "Event used for volunteer-cancel-engine test.",
        "category": "education", "location": "Bengaluru", "event_date": event_date,
        "start_time": "09:00", "end_time": "17:00",
        "registration_deadline": f"{tomorrow(15)}T23:59", "required_volunteers": 1,
    }).json()
    sh = client.post(f"/ngo/events/{ev['id']}/shifts", json={
        "shift_date": event_date, "start_time": "09:00", "end_time": "12:00", "capacity": 1,
    }).json()
    client.post(f"/ngo/events/{ev['id']}/status", json={"status": "published"})

    with httpx.Client(base_url=api_url(), timeout=30.0) as v1:
        register_volunteer(v1, "a")
        reg = v1.post("/volunteer/registrations", json={"shift_id": sh["id"]}).json()
        cancel = v1.post(f"/volunteer/registrations/{reg['id']}/cancel")
        assert cancel.status_code == 200, cancel.text
        assert cancel.json()["registration_status"] == "cancelled"

    # NGO sees the vacancy in Smart Cancellation Manager
    overview = client.get("/ngo/cancellations").json()
    vac = [v for v in overview["vacancies"] if v["cancelled_registration_id"] == reg["id"]]
    assert vac, "cancelled registration did not surface as a vacancy"


def test_emergency_mode_sends_urgent_invites(client):
    event_date = tomorrow(1)  # soon, to encourage a critical-shortage shift
    client.post("/auth/login", json={"email": "annapurna@demo.vc", "password": "Demo@1234"})
    ev = client.post("/ngo/events", json={
        "title": "tscheck-emergency-event", "description": "Event used for the emergency-mode test.",
        "category": "education", "location": "Bengaluru", "event_date": event_date,
        "start_time": "18:00", "end_time": "21:00",
        "registration_deadline": f"{event_date}T17:00", "required_volunteers": 5,
    }).json()
    sh = client.post(f"/ngo/events/{ev['id']}/shifts", json={
        "shift_date": event_date, "start_time": "18:00", "end_time": "21:00", "capacity": 5,
    }).json()
    client.post(f"/ngo/events/{ev['id']}/status", json={"status": "published"})

    with httpx.Client(base_url=api_url(), timeout=30.0) as v1:
        register_volunteer(v1, "urgent")

    emer = client.post("/ngo/emergency", json={"shift_id": sh["id"], "needed": 1})
    assert emer.status_code == 200, emer.text
    body = emer.json()
    assert "message" in body
    # should find at least our freshly-eligible volunteer
    assert body["invited"] >= 1, body
