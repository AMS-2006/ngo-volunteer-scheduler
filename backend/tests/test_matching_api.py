"""DB-backed API tests for Module 4 (need TEST_DATABASE_URL, see conftest.py)."""

from datetime import time

from tests.conftest import confirm, make_event, make_shift, make_user, make_volunteer, require

API = "/api/v1/matching"


def _world(db, capacity=2):
    admin = make_user(db, "admin", "NGO Admin")
    event = make_event(db, admin)
    shift = make_shift(db, event, capacity=capacity)
    require(db, shift)
    return admin, event, shift


def _invite(client, act_as, admin, shift, volunteer):
    act_as(admin)
    r = client.post(f"{API}/shifts/{shift.id}/invite", json={"volunteer_ids": [volunteer.id]})
    assert r.status_code == 201, r.text
    return r.json()["invitations"][0]["id"]


# ── recommendations ───────────────────────────────────────────────────────────
def test_recommendations_rank_exclude_and_report_gap(client, act_as, db):
    admin, _, shift = _world(db, capacity=5)
    good = make_volunteer(db, "Good")
    unskilled = make_volunteer(db, "Unskilled", skills=("Driving",))
    unavailable = make_volunteer(db, "Away", window=None)
    busy = make_volunteer(db, "Busy")
    other = make_shift(db, shift.event, start=time(10), end=time(13), title="Overlap")
    confirm(db, other, busy)  # 5 – overlapping confirmed registration

    act_as(admin)
    r = client.get(f"{API}/shifts/{shift.id}/recommendations")
    assert r.status_code == 200, r.text
    body = r.json()
    assert [m["volunteer_id"] for m in body["recommendations"]] == [good.id]
    reasons = {m["volunteer_id"]: {e["code"] for e in m["exclusions"]} for m in body["excluded"]}
    assert "MISSING_MANDATORY_SKILLS" in reasons[unskilled.id]
    assert "NOT_AVAILABLE" in reasons[unavailable.id]
    assert "SCHEDULE_CONFLICT" in reasons[busy.id]
    assert body["skill_gap"]["eligible_count"] == 1 and body["skill_gap"]["gap"] == 4
    assert body["recommendations"][0]["explanation"]


def test_no_eligible_volunteers(client, act_as, db):
    admin, _, shift = _world(db, capacity=3)
    make_volunteer(db, "Unskilled", skills=("Driving",))
    act_as(admin)
    body = client.get(f"{API}/shifts/{shift.id}/recommendations").json()
    assert body["recommendations"] == [] and body["skill_gap"]["gap"] == 3


def test_volunteer_personal_recommendations(client, act_as, db):
    _, _, shift = _world(db)
    me = make_volunteer(db, "Me")
    act_as(me)
    r = client.get(f"{API}/recommendations")
    assert r.status_code == 200 and r.json()["count"] == 1
    assert client.get(f"{API}/recommendations/{shift.id}").json()["match"]["eligible"] is True


# ── 13 – authorization ────────────────────────────────────────────────────────
def test_unauthorized_ngo_access(client, act_as, db):
    _, _, shift = _world(db)
    vol = make_volunteer(db, "Vol")
    rival = make_user(db, "admin", "Other NGO")

    assert client.get(f"{API}/shifts/{shift.id}/recommendations").status_code == 401  # anonymous
    act_as(vol)
    assert client.get(f"{API}/shifts/{shift.id}/recommendations").status_code == 403  # volunteer
    act_as(rival)
    assert client.get(f"{API}/shifts/{shift.id}/recommendations").status_code == 403  # other NGO
    assert client.post(f"{API}/shifts/{shift.id}/invite", json={"volunteer_ids": [vol.id]}).status_code == 403
    act_as(make_user(db, "admin", "Admin 3"))
    assert client.get(f"{API}/invitations").json() == []


# ── 14 / 15 / 16 – invitation workflow ────────────────────────────────────────
def test_accept_invitation_creates_confirmed_registration(client, act_as, db):
    from app.models.registration import Registration

    admin, _, shift = _world(db)
    vol = make_volunteer(db, "Vol")
    inv_id = _invite(client, act_as, admin, shift, vol)

    act_as(vol)
    r = client.post(f"{API}/invitations/{inv_id}/accept")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["invitation"]["status"] == "ACCEPTED" and body["registration"]["status"] == "CONFIRMED"
    db.expire_all()
    assert db.query(Registration).filter_by(shift_id=shift.id, volunteer_id=vol.id, status="CONFIRMED").count() == 1
    assert client.post(f"{API}/invitations/{inv_id}/accept").status_code == 409  # not re-acceptable


def test_decline_invitation(client, act_as, db):
    from app.models.registration import Registration

    admin, _, shift = _world(db)
    vol = make_volunteer(db, "Vol")
    inv_id = _invite(client, act_as, admin, shift, vol)

    act_as(vol)
    r = client.post(f"{API}/invitations/{inv_id}/decline")
    assert r.status_code == 200 and r.json()["invitation"]["status"] == "DECLINED"
    db.expire_all()
    assert db.query(Registration).filter_by(volunteer_id=vol.id).count() == 0
    assert client.post(f"{API}/invitations/{inv_id}/accept").status_code == 409


def test_volunteer_cannot_touch_someone_elses_invitation(client, act_as, db):
    admin, _, shift = _world(db)
    vol, intruder = make_volunteer(db, "Vol"), make_volunteer(db, "Intruder")
    inv_id = _invite(client, act_as, admin, shift, vol)
    act_as(intruder)
    assert client.post(f"{API}/invitations/{inv_id}/accept").status_code == 404
    assert client.post(f"{API}/invitations/{inv_id}/decline").status_code == 404


def test_duplicate_invitations_rejected(client, act_as, db):
    admin, _, shift = _world(db)
    vol = make_volunteer(db, "Vol")
    _invite(client, act_as, admin, shift, vol)
    act_as(admin)
    r = client.post(f"{API}/shifts/{shift.id}/invite", json={"volunteer_ids": [vol.id]})
    assert r.status_code == 201
    assert r.json()["invitations"] == []
    assert r.json()["rejected"][0]["code"] == "DUPLICATE_INVITATION"


def test_shortlist_then_invite_whole_shortlist(client, act_as, db):
    admin, _, shift = _world(db)
    ok, bad = make_volunteer(db, "Ok"), make_volunteer(db, "Bad", skills=("Driving",))
    act_as(admin)
    r = client.post(f"{API}/shifts/{shift.id}/shortlist", json={"volunteer_ids": [ok.id, bad.id]})
    assert r.status_code == 201
    assert [a["volunteer_id"] for a in r.json()["added"]] == [ok.id]
    assert r.json()["rejected"][0]["code"] == "NOT_ELIGIBLE"
    r = client.post(f"{API}/shifts/{shift.id}/invite", json={})
    assert r.status_code == 201 and len(r.json()["invitations"]) == 1


def test_cancelled_and_expired_invitations_cannot_be_accepted(client, act_as, db):
    from datetime import datetime, timedelta, timezone

    from app.models.matching import VolunteerInvitation

    admin, _, shift = _world(db)
    v1, v2 = make_volunteer(db, "One"), make_volunteer(db, "Two")
    cancelled = _invite(client, act_as, admin, shift, v1)
    expiring = _invite(client, act_as, admin, shift, v2)
    act_as(admin)
    assert client.post(f"{API}/invitations/{cancelled}/cancel").json()["status"] == "CANCELLED"
    row = db.get(VolunteerInvitation, expiring)
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    act_as(v1)
    assert client.post(f"{API}/invitations/{cancelled}/accept").status_code == 409
    act_as(v2)
    r = client.post(f"{API}/invitations/{expiring}/accept")
    assert r.status_code == 409 and r.json()["code"] == "INVITATION_EXPIRED"


# ── 17 / 18 – acceptance must respect Module 3 ────────────────────────────────
def test_accept_when_shift_is_full(client, act_as, db):
    from app.models.registration import Registration

    admin, _, shift = _world(db, capacity=1)
    vol, other = make_volunteer(db, "Vol"), make_volunteer(db, "Other")
    inv_id = _invite(client, act_as, admin, shift, vol)
    confirm(db, shift, other)  # the last slot is taken after the invitation was sent

    act_as(vol)
    r = client.post(f"{API}/invitations/{inv_id}/accept")
    assert r.status_code == 409 and r.json()["code"] == "SHIFT_FULL"
    db.expire_all()
    assert db.query(Registration).filter_by(volunteer_id=vol.id).count() == 0
    assert client.get(f"{API}/invitations").json()[0]["status"] == "PENDING"


def test_accept_with_scheduling_conflict(client, act_as, db):
    from app.models.registration import Registration

    admin, event, shift = _world(db)
    vol = make_volunteer(db, "Vol")
    inv_id = _invite(client, act_as, admin, shift, vol)
    overlapping = make_shift(db, event, start=time(11), end=time(14), title="Overlap")
    confirm(db, overlapping, vol)  # becomes busy after being invited

    act_as(vol)
    r = client.post(f"{API}/invitations/{inv_id}/accept")
    assert r.status_code == 409 and r.json()["code"] == "SCHEDULE_CONFLICT"
    db.expire_all()
    assert db.query(Registration).filter_by(shift_id=shift.id, volunteer_id=vol.id).count() == 0
