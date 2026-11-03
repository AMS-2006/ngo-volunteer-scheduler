"""Criterion: Invitation -> accept -> assignment, race-safe. Uses fresh tscheck fixtures
(own event/shift/volunteers) rather than the seeded Rohan/Kavya scenario, so the test
stays isolated and rerun-safe."""
import uuid
from datetime import datetime, timedelta

import httpx

from tests.conftest import api_url


def tomorrow(offset_days=1):
    return (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


def register_volunteer(c, tag):
    suffix = uuid.uuid4().hex[:6]
    name = f"tscheck-inv-{tag}-{suffix}"
    body = {"role": "volunteer", "full_name": name,
            "email": f"tscheck-inv-{tag}-{suffix}@example.com", "password": "Demo@1234",
            "phone": "9100000000", "location": "Bengaluru"}
    r = c.post("/auth/register", json=body)
    assert r.status_code == 200, r.text
    # give the fresh volunteer broad availability so the matching engine considers them eligible
    prof = c.put("/volunteer/profile", json={
        "name": name, "location": "Bengaluru",
        "availability": {"days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"], "slots": ["morning", "afternoon", "evening"]},
        "preferred_travel_radius": 50,
    })
    assert prof.status_code == 200, prof.text
    return r.json()["profile_id"]


def test_invite_accept_and_race_safety(client):
    event_date = tomorrow(14)

    # NGO: create + publish an event with one shift, capacity 2
    client.post("/auth/login", json={"email": "annapurna@demo.vc", "password": "Demo@1234"})
    ev = client.post("/ngo/events", json={
        "title": "tscheck-invite-flow-event", "description": "Event used for invite/accept race test.",
        "category": "education", "location": "Bengaluru", "event_date": event_date,
        "start_time": "09:00", "end_time": "17:00",
        "registration_deadline": f"{tomorrow(13)}T23:59", "required_volunteers": 2,
    }).json()
    sh = client.post(f"/ngo/events/{ev['id']}/shifts", json={
        "shift_date": event_date, "start_time": "09:00", "end_time": "12:00", "capacity": 2,
    }).json()
    pub = client.post(f"/ngo/events/{ev['id']}/status", json={"status": "published"})
    assert pub.status_code == 200, pub.text

    # Two fresh volunteers, one registers then cancels to create the vacancy
    with httpx.Client(base_url=api_url(), timeout=30.0) as v1, httpx.Client(base_url=api_url(), timeout=30.0) as v2:
        v1_profile_id = register_volunteer(v1, "a")
        v2_profile_id = register_volunteer(v2, "b")

        reg = v1.post("/volunteer/registrations", json={"shift_id": sh["id"]}).json()
        cancelled_reg_id = reg["id"]
        cancel = v1.post(f"/volunteer/registrations/{cancelled_reg_id}/cancel")
        assert cancel.status_code == 200, cancel.text

        # NGO invites both the (now-cancelled) volunteer... no — invites v2 and itself is not eligible.
        # Invite v2 twice via two "copies" by re-using the same cancelled_registration_id vacancy is only
        # meaningful with >=2 distinct invitees, so register + cancel a second time for a second candidate.
        v3_profile_id = register_volunteer(v1, "c")  # new session on same client object is fine (separate email)

        inv = client.post("/ngo/invitations", json={
            "shift_id": sh["id"], "cancelled_registration_id": cancelled_reg_id,
            "volunteer_ids": [v2_profile_id, v3_profile_id], "urgent": False,
        })
        assert inv.status_code == 200, inv.text
        assert inv.json()["invited"] == 2, inv.json()

        v2_invites = v2.get("/volunteer/invitations").json()
        v2_inv_id = [i for i in v2_invites if i["shift_id"] == sh["id"]][0]["id"]

        # v3 is logged in as v1's client since we reused v1's session for registration c; fetch own invites
        v3_invites = v1.get("/volunteer/invitations").json()
        v3_inv_id = [i for i in v3_invites if i["shift_id"] == sh["id"]][0]["id"]

        # v2 accepts -> confirmed registration, source replacement
        accept = v2.post(f"/volunteer/invitations/{v2_inv_id}/respond", json={"accept": True})
        assert accept.status_code == 200, accept.text

        my_regs = v2.get("/volunteer/registrations").json()
        new_reg = [r for r in my_regs if r["shift_id"] == sh["id"]][0]
        assert new_reg["registration_status"] == "confirmed"
        assert new_reg["source"] == "replacement"

        # v3's pending invite is now "filled" and accepting it fails with a clear error
        v3_invites_after = v1.get("/volunteer/invitations").json()
        v3_after = [i for i in v3_invites_after if i["id"] == v3_inv_id][0]
        assert v3_after["invitation_status"] == "filled", v3_after

        fail = v1.post(f"/volunteer/invitations/{v3_inv_id}/respond", json={"accept": True})
        assert fail.status_code >= 400, fail.text

        # vacancy shows filled-by name on NGO side
        overview = client.get("/ngo/cancellations").json()
        vac = [v for v in overview["vacancies"] if v["cancelled_registration_id"] == cancelled_reg_id][0]
        assert vac["replaced_by_name"], vac


def test_decline_invitation(client):
    event_date = tomorrow(15)
    client.post("/auth/login", json={"email": "annapurna@demo.vc", "password": "Demo@1234"})
    ev = client.post("/ngo/events", json={
        "title": "tscheck-decline-flow-event", "description": "Event used for decline flow test.",
        "category": "education", "location": "Bengaluru", "event_date": event_date,
        "start_time": "09:00", "end_time": "17:00",
        "registration_deadline": f"{tomorrow(14)}T23:59", "required_volunteers": 1,
    }).json()
    sh = client.post(f"/ngo/events/{ev['id']}/shifts", json={
        "shift_date": event_date, "start_time": "09:00", "end_time": "12:00", "capacity": 2,
    }).json()
    client.post(f"/ngo/events/{ev['id']}/status", json={"status": "published"})

    with httpx.Client(base_url=api_url(), timeout=30.0) as v1:
        v1_profile_id = register_volunteer(v1, "decline")
        inv = client.post("/ngo/invitations", json={"shift_id": sh["id"], "volunteer_ids": [v1_profile_id]})
        assert inv.status_code == 200, inv.text
        v1_inv_id = v1.get("/volunteer/invitations").json()[0]["id"]
        resp = v1.post(f"/volunteer/invitations/{v1_inv_id}/respond", json={"accept": False})
        assert resp.status_code == 200, resp.text
        after = v1.get("/volunteer/invitations").json()
        assert [i for i in after if i["id"] == v1_inv_id][0]["invitation_status"] == "declined"
