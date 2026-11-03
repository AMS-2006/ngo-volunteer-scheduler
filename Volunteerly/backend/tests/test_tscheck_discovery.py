"""Criterion: Volunteer discovery & registration rules."""
import uuid
from datetime import datetime, timedelta

import httpx

from tests.conftest import api_url


def tomorrow(offset_days=1):
    return (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


def test_register_creates_confirmed_registration_and_increments_filled(client):
    # fresh volunteer
    suffix = uuid.uuid4().hex[:8]
    r = client.post("/auth/register", json={
        "role": "volunteer", "full_name": f"tscheck-reg-vol-{suffix}", "email": f"tscheck-reg-vol-{suffix}@example.com",
        "password": "Demo@1234", "phone": "9000000001", "location": "Bengaluru",
    })
    assert r.status_code == 200, r.text

    with httpx.Client(base_url=api_url(), timeout=30.0) as ngoc:
        ngoc.post("/auth/login", json={"email": "annapurna@demo.vc", "password": "Demo@1234"})
        event_date = tomorrow(12)
        ev = ngoc.post("/ngo/events", json={
            "title": "tscheck-discover-event", "description": "An event used for discovery/registration checks.",
            "category": "education", "location": "Bengaluru", "event_date": event_date,
            "start_time": "09:00", "end_time": "17:00",
            "registration_deadline": f"{tomorrow(11)}T23:59", "required_volunteers": 1,
        }).json()
        sh = ngoc.post(f"/ngo/events/{ev['id']}/shifts", json={
            "shift_date": event_date, "start_time": "10:00", "end_time": "12:00", "capacity": 1,
        }).json()
        pub = ngoc.post(f"/ngo/events/{ev['id']}/status", json={"status": "published"})
        assert pub.status_code == 200, pub.text

    # discover shows the published event
    disc = client.get("/events", params={"q": "tscheck-discover-event"})
    assert disc.status_code == 200
    assert any(e["id"] == ev["id"] for e in disc.json())

    # register -> confirmed, filled increments
    reg = client.post("/volunteer/registrations", json={"shift_id": sh["id"]})
    assert reg.status_code == 200, reg.text
    assert reg.json()["registration_status"] == "confirmed"

    detail = client.get(f"/events/{ev['id']}")
    matched = [s for s in detail.json()["shifts"] if s["id"] == sh["id"]][0]
    assert matched["filled"] == 1

    # duplicate registration rejected
    dup = client.post("/volunteer/registrations", json={"shift_id": sh["id"]})
    assert dup.status_code == 409, dup.text

    # full shift (capacity 1, already filled) rejected for a second volunteer
    suffix2 = uuid.uuid4().hex[:8]
    with httpx.Client(base_url=api_url(), timeout=30.0) as c2:
        c2.post("/auth/register", json={
            "role": "volunteer", "full_name": f"tscheck-reg-vol2-{suffix2}", "email": f"tscheck-reg-vol2-{suffix2}@example.com",
            "password": "Demo@1234", "phone": "9000000002", "location": "Bengaluru",
        })
        full = c2.post("/volunteer/registrations", json={"shift_id": sh["id"]})
        assert full.status_code == 409, full.text


def test_schedule_conflict_rejected_for_priya():
    """Priya is registered on Community Food Drive 08:00-11:00 tomorrow; the overlapping
    Senior Citizens Health Check-up 09:00-12:00 shift must be rejected with a conflict error."""
    with httpx.Client(base_url=api_url(), timeout=30.0) as c:
        r = c.post("/auth/login", json={"email": "priya@demo.vc", "password": "Demo@1234"})
        assert r.status_code == 200, r.text
        events = c.get("/events", params={"q": "Senior Citizens Health Check-up"}).json()
        assert events, "seeded conflicting event not found"
        detail = c.get(f"/events/{events[0]['id']}").json()
        conflicting_shift = [s for s in detail["shifts"] if s["start_time"] == "09:00"][0]
        resp = c.post("/volunteer/registrations", json={"shift_id": conflicting_shift["id"]})
        assert resp.status_code == 409, resp.text
        assert "conflict" in resp.json()["detail"].lower()
