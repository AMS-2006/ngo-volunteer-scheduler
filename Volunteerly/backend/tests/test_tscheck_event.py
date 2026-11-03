"""Criterion: NGO event + multi-shift management & publishing."""
from datetime import datetime, timedelta


def tomorrow(offset_days=1):
    return (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


def login_ngo(client):
    r = client.post("/auth/login", json={"email": "annapurna@demo.vc", "password": "Demo@1234"})
    assert r.status_code == 200, r.text


def test_create_event_add_shifts_publish_and_edit(client):
    login_ngo(client)
    event_date = tomorrow(10)
    body = {
        "title": "tscheck-event-multi-shift", "description": "A test event description long enough.",
        "category": "education", "location": "Bengaluru", "event_date": event_date,
        "start_time": "09:00", "end_time": "17:00",
        "registration_deadline": f"{tomorrow(9)}T23:59", "required_volunteers": 10,
    }
    r = client.post("/ngo/events", json=body)
    assert r.status_code == 200, r.text
    event = r.json()
    assert event["status"] == "draft"
    event_id = event["id"]

    # publish blocked with no shifts
    r = client.post(f"/ngo/events/{event_id}/status", json={"status": "published"})
    assert r.status_code >= 400, "expected publish to be blocked with no shifts"

    # add 3 shifts with different capacities / skill reqs
    shift_ids = []
    for i, (cap, skill) in enumerate([(5, "logistics"), (3, "first_aid"), (8, "cooking")]):
        sr = client.post(f"/ngo/events/{event_id}/shifts", json={
            "shift_date": event_date, "start_time": "09:00", "end_time": "12:00",
            "capacity": cap, "required_skills": [{"skill": skill, "count": 1}],
        })
        assert sr.status_code == 200, sr.text
        shift_ids.append(sr.json()["id"])
    assert len(shift_ids) == 3

    # shift end <= start rejected
    bad = client.post(f"/ngo/events/{event_id}/shifts", json={
        "shift_date": event_date, "start_time": "12:00", "end_time": "09:00", "capacity": 2,
    })
    assert bad.status_code >= 400, bad.text

    # now publish succeeds
    pub = client.post(f"/ngo/events/{event_id}/status", json={"status": "published"})
    assert pub.status_code == 200, pub.text
    assert pub.json()["status"] == "published"

    # edit a shift
    edit = client.put(f"/ngo/shifts/{shift_ids[0]}", json={
        "shift_date": event_date, "start_time": "09:00", "end_time": "13:00", "capacity": 6, "required_skills": [],
    })
    assert edit.status_code == 200, edit.text
    assert edit.json()["capacity"] == 6

    # delete a shift
    delr = client.delete(f"/ngo/shifts/{shift_ids[1]}")
    assert delr.status_code == 200, delr.text

    # delete the event (cleanup, and verifies delete works)
    deev = client.delete(f"/ngo/events/{event_id}")
    assert deev.status_code == 200, deev.text


def test_draft_event_not_visible_to_volunteer_discover(client):
    login_ngo(client)
    event_date = tomorrow(11)
    body = {
        "title": "tscheck-draft-event-hidden", "description": "Draft event should not show up for volunteers.",
        "category": "education", "location": "Bengaluru", "event_date": event_date,
        "start_time": "09:00", "end_time": "17:00",
        "registration_deadline": f"{tomorrow(10)}T23:59", "required_volunteers": 5,
    }
    r = client.post("/ngo/events", json=body)
    assert r.status_code == 200, r.text
    event_id = r.json()["id"]

    r2 = client.post("/auth/login", json={"email": "priya@demo.vc", "password": "Demo@1234"})
    assert r2.status_code == 200
    disc = client.get("/events", params={"q": "tscheck-draft-event-hidden"})
    assert disc.status_code == 200, disc.text
    assert all(e["id"] != event_id for e in disc.json()), "draft event leaked into volunteer discover"
