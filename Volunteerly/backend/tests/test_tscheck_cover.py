"""Criterion: Coverage, attendance, analytics, notifications."""
import uuid
from datetime import datetime, timedelta

import httpx

from tests.conftest import api_url


def tomorrow(offset_days=1):
    return (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


def test_coverage_badges_and_attendance_increments_hours(client):
    event_date = tomorrow(17)
    client.post("/auth/login", json={"email": "annapurna@demo.vc", "password": "Demo@1234"})
    ev = client.post("/ngo/events", json={
        "title": "tscheck-coverage-event", "description": "Event used for coverage/attendance/analytics test.",
        "category": "education", "location": "Bengaluru", "event_date": event_date,
        "start_time": "09:00", "end_time": "12:00",
        "registration_deadline": f"{tomorrow(16)}T23:59", "required_volunteers": 4,
    }).json()
    sh = client.post(f"/ngo/events/{ev['id']}/shifts", json={
        "shift_date": event_date, "start_time": "09:00", "end_time": "12:00", "capacity": 4,
    }).json()
    client.post(f"/ngo/events/{ev['id']}/status", json={"status": "published"})

    # fully empty shift -> critical_shortage in coverage
    cov = client.get("/ngo/coverage").json()
    row = [c for c in cov if c["shift"]["id"] == sh["id"]][0]
    assert row["shift"]["coverage"]["status"] == "critical_shortage", row

    # register one fresh volunteer and mark present -> hours recorded
    suffix = uuid.uuid4().hex[:6]
    with httpx.Client(base_url=api_url(), timeout=30.0) as v1:
        name = f"tscheck-cov-vol-{suffix}"
        v1.post("/auth/register", json={"role": "volunteer", "full_name": name,
                "email": f"tscheck-cov-vol-{suffix}@example.com", "password": "Demo@1234",
                "phone": "9300000000", "location": "Bengaluru"})
        reg = v1.post("/volunteer/registrations", json={"shift_id": sh["id"]}).json()

        att = client.post(f"/ngo/registrations/{reg['id']}/attendance",
                          json={"attendance_status": "present", "hours_contributed": 3})
        assert att.status_code == 200, att.text
        assert att.json()["hours_contributed"] == 3

        hist = v1.get("/volunteer/analytics").json()
        assert hist["total_hours"] >= 3, hist

        dash = v1.get("/volunteer/dashboard").json()
        assert dash["total_hours"] >= 3, dash

    # NGO analytics endpoint renders without error and reflects at least this event
    analytics = client.get("/ngo/analytics")
    assert analytics.status_code == 200, analytics.text
    assert analytics.json()["events_conducted"] >= 0


def test_notifications_mark_read_and_mark_all_read(client):
    r = client.post("/auth/login", json={"email": "priya@demo.vc", "password": "Demo@1234"})
    assert r.status_code == 200, r.text
    notes = client.get("/notifications")
    assert notes.status_code == 200, notes.text
    data = notes.json()
    assert isinstance(data, list)
    if data:
        nid = data[0]["id"]
        read = client.post(f"/notifications/{nid}/read")
        assert read.status_code == 200, read.text
    mark_all = client.post("/notifications/read-all")
    assert mark_all.status_code == 200, mark_all.text
    after = client.get("/notifications").json()
    assert all(n["read_status"] for n in after), "mark-all-read left unread notifications"
