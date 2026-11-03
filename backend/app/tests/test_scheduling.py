"""
tests/test_scheduling.py
─────────────────────────
Comprehensive test suite for Module 3: Smart Shift Scheduling Engine.

Covers all 13 critical edge cases:
  1. Volunteer registers for a valid shift.
  2. Volunteer attempts overlapping registration (rejected 409).
  3. Volunteer registers for consecutive shifts (allowed).
  4. Shift reaches full capacity.
  5. Another volunteer attempts to register for a full shift (added to waitlist).
  6. Volunteer cancels a confirmed registration.
  7. Waitlisted volunteer is promoted after cancellation.
  8. Waitlisted volunteer has a scheduling conflict (skipped, next eligible promoted).
  9. Volunteer attempts duplicate registration (rejected).
  10. Volunteer attempts registration outside declared availability (rejected).
  11. Multiple volunteers register up to capacity (overbooking prevented).
  12. Volunteer attempts to cancel another person's registration (rejected 403).
  13. Cancelled registration does not block future registration.
"""

from datetime import date, datetime, time, timedelta, timezone
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base
import app.database.models  # Registers User, NGO, Event, Shift, Registration, VolunteerAvailability
from app.models.availability import VolunteerAvailability
from app.models.event import Event
from app.models.ngo import NGO
from app.models.registration import Registration
from app.models.shift import Shift
from app.models.user import User
from app.services.scheduling import (
    cancel_registration,
    check_time_overlap,
    detect_conflict,
    register_volunteer_for_shift,
)


@pytest.fixture
def db():
    """Create an isolated in-memory SQLite database for each test run."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def setup_data(db):
    """Seed base admin, NGO, published event, and volunteers."""
    # Admin & NGO
    admin = User(
        id="admin-1",
        email="admin@testngo.org",
        password_hash="fakehash",
        full_name="NGO Coordinator",
        role="admin",
    )
    db.add(admin)
    db.flush()

    ngo = NGO(
        id="ngo-1",
        admin_user_id=admin.id,
        name="Action for Nature",
    )
    db.add(ngo)
    db.flush()

    # Event tomorrow
    now = datetime.now(timezone.utc)
    event_day = now + timedelta(days=2)
    event = Event(
        id="event-1",
        ngo_id=ngo.id,
        created_by=admin.id,
        title="Lake Cleanup Drive",
        event_date=event_day,
        total_volunteers_required=10,
        status="published",
    )
    db.add(event)
    db.flush()

    # Volunteers
    v1 = User(id="vol-1", email="rahul@test.com", password_hash="hash", full_name="Rahul", role="volunteer")
    v2 = User(id="vol-2", email="priya@test.com", password_hash="hash", full_name="Priya", role="volunteer")
    v3 = User(id="vol-3", email="aman@test.com", password_hash="hash", full_name="Aman", role="volunteer")
    v4 = User(id="vol-4", email="sneha@test.com", password_hash="hash", full_name="Sneha", role="volunteer")
    db.add_all([v1, v2, v3, v4])
    db.commit()

    return {
        "admin": admin,
        "ngo": ngo,
        "event": event,
        "volunteers": [v1, v2, v3, v4],
        "base_date": event_day.date(),
    }


# ── Scenario 1: Volunteer registers for a valid shift ─────────────────────────

def test_01_valid_registration(db, setup_data):
    base_date = setup_data["base_date"]
    shift = Shift(
        id="shift-1",
        event_id=setup_data["event"].id,
        name="Morning Cleanup",
        start_time=datetime.combine(base_date, time(9, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(base_date, time(12, 0), tzinfo=timezone.utc),
        required_volunteers=5,
    )
    db.add(shift)
    db.commit()

    result = register_volunteer_for_shift("vol-1", shift.id, db)
    assert result["status"] == "confirmed"
    assert result["waitlist_position"] is None
    assert result["registration"].status == "confirmed"


# ── Scenario 2: Overlapping registration is rejected ─────────────────────────

def test_02_overlapping_shift_rejected(db, setup_data):
    base_date = setup_data["base_date"]
    # Shift A: 09:00 - 12:00
    shift_a = Shift(
        id="shift-a",
        event_id=setup_data["event"].id,
        name="Shift A",
        start_time=datetime.combine(base_date, time(9, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(base_date, time(12, 0), tzinfo=timezone.utc),
        required_volunteers=5,
    )
    # Shift B: 11:00 - 14:00 (overlaps with Shift A by 1 hour)
    shift_b = Shift(
        id="shift-b",
        event_id=setup_data["event"].id,
        name="Shift B",
        start_time=datetime.combine(base_date, time(11, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(base_date, time(14, 0), tzinfo=timezone.utc),
        required_volunteers=5,
    )
    db.add_all([shift_a, shift_b])
    db.commit()

    # Register for Shift A
    res_a = register_volunteer_for_shift("vol-1", shift_a.id, db)
    assert res_a["status"] == "confirmed"

    # Attempt registration for Shift B -> Must be rejected with 409 Conflict
    with pytest.raises(HTTPException) as exc_info:
        register_volunteer_for_shift("vol-1", shift_b.id, db)
    assert exc_info.value.status_code == 409
    assert "Registration rejected: You already have an assignment" in exc_info.value.detail


# ── Scenario 3: Consecutive shifts are allowed ───────────────────────────────

def test_03_consecutive_shifts_allowed(db, setup_data):
    base_date = setup_data["base_date"]
    # Shift 1: 09:00 - 11:00
    shift_1 = Shift(
        id="shift-c1",
        event_id=setup_data["event"].id,
        name="Morning",
        start_time=datetime.combine(base_date, time(9, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(base_date, time(11, 0), tzinfo=timezone.utc),
        required_volunteers=5,
    )
    # Shift 2: 11:00 - 13:00 (starts exactly when Shift 1 ends)
    shift_2 = Shift(
        id="shift-c2",
        event_id=setup_data["event"].id,
        name="Noon",
        start_time=datetime.combine(base_date, time(11, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(base_date, time(13, 0), tzinfo=timezone.utc),
        required_volunteers=5,
    )
    db.add_all([shift_1, shift_2])
    db.commit()

    res_1 = register_volunteer_for_shift("vol-1", shift_1.id, db)
    res_2 = register_volunteer_for_shift("vol-1", shift_2.id, db)
    assert res_1["status"] == "confirmed"
    assert res_2["status"] == "confirmed"


# ── Scenario 4 & 5: Capacity limit & Waitlist placement ───────────────────────

def test_04_05_capacity_and_waitlist(db, setup_data):
    base_date = setup_data["base_date"]
    # Capacity = 2 volunteers
    shift = Shift(
        id="shift-cap",
        event_id=setup_data["event"].id,
        name="Small Team Shift",
        start_time=datetime.combine(base_date, time(10, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(base_date, time(12, 0), tzinfo=timezone.utc),
        required_volunteers=2,
    )
    db.add(shift)
    db.commit()

    # Vol-1 & Vol-2 register -> both confirmed
    r1 = register_volunteer_for_shift("vol-1", shift.id, db)
    r2 = register_volunteer_for_shift("vol-2", shift.id, db)
    assert r1["status"] == "confirmed"
    assert r2["status"] == "confirmed"

    # Vol-3 registers -> shift is full -> waitlist position #1
    r3 = register_volunteer_for_shift("vol-3", shift.id, db)
    assert r3["status"] == "waitlisted"
    assert r3["waitlist_position"] == 1

    # Vol-4 registers -> waitlist position #2
    r4 = register_volunteer_for_shift("vol-4", shift.id, db)
    assert r4["status"] == "waitlisted"
    assert r4["waitlist_position"] == 2


# ── Scenario 6 & 7: Cancellation and Waitlist FIFO Promotion ─────────────────

def test_06_07_cancellation_and_waitlist_promotion(db, setup_data):
    base_date = setup_data["base_date"]
    shift = Shift(
        id="shift-promo",
        event_id=setup_data["event"].id,
        name="Promo Shift",
        start_time=datetime.combine(base_date, time(14, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(base_date, time(16, 0), tzinfo=timezone.utc),
        required_volunteers=1,
    )
    db.add(shift)
    db.commit()

    # Vol-1 confirmed, Vol-2 waitlist #1, Vol-3 waitlist #2
    r1 = register_volunteer_for_shift("vol-1", shift.id, db)
    r2 = register_volunteer_for_shift("vol-2", shift.id, db)
    r3 = register_volunteer_for_shift("vol-3", shift.id, db)
    assert r1["status"] == "confirmed"
    assert r2["status"] == "waitlisted" and r2["waitlist_position"] == 1
    assert r3["status"] == "waitlisted" and r3["waitlist_position"] == 2

    # Vol-1 cancels
    vol1_user = db.get(User, "vol-1")
    cancel_res = cancel_registration(r1["registration"].id, vol1_user, "Can't make it", db)
    assert cancel_res["registration"].status == "cancelled"

    # Vol-2 was automatically promoted to confirmed!
    assert cancel_res["promoted_registration"] is not None
    assert cancel_res["promoted_registration"].volunteer_id == "vol-2"
    assert cancel_res["promoted_registration"].status == "confirmed"

    # Vol-3 is now moved to waitlist position #1
    reg_v3 = db.get(Registration, r3["registration"].id)
    assert reg_v3.status == "waitlisted"
    assert reg_v3.waitlist_position == 1


# ── Scenario 8: Conflicted waitlisted volunteer is skipped on promotion ───────

def test_08_conflicted_waitlist_skipped(db, setup_data):
    base_date = setup_data["base_date"]
    # Main Shift: 09:00 - 12:00 (capacity 1)
    shift_main = Shift(
        id="shift-main",
        event_id=setup_data["event"].id,
        name="Main Clean",
        start_time=datetime.combine(base_date, time(9, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(base_date, time(12, 0), tzinfo=timezone.utc),
        required_volunteers=1,
    )
    # Afternoon Shift for Vol-2: 10:00 - 13:00 (will conflict with shift_main)
    shift_other = Shift(
        id="shift-other",
        event_id=setup_data["event"].id,
        name="Conflicting Clean",
        start_time=datetime.combine(base_date, time(10, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(base_date, time(13, 0), tzinfo=timezone.utc),
        required_volunteers=5,
    )
    db.add_all([shift_main, shift_other])
    db.commit()

    # 1. Vol-1 fills shift_main
    r1 = register_volunteer_for_shift("vol-1", shift_main.id, db)
    # 2. Vol-2 joins waitlist #1
    r2 = register_volunteer_for_shift("vol-2", shift_main.id, db)
    # 3. Vol-3 joins waitlist #2
    r3 = register_volunteer_for_shift("vol-3", shift_main.id, db)

    # 4. In the meantime, Vol-2 registers for shift_other (10:00-13:00)
    register_volunteer_for_shift("vol-2", shift_other.id, db)

    # 5. Vol-1 cancels shift_main
    vol1_user = db.get(User, "vol-1")
    cancel_res = cancel_registration(r1["registration"].id, vol1_user, "Emergency", db)

    # Vol-2 had a newly developed conflict (10:00-13:00 vs 09:00-12:00),
    # so the engine MUST skip Vol-2 and promote Vol-3!
    assert cancel_res["promoted_registration"] is not None
    assert cancel_res["promoted_registration"].volunteer_id == "vol-3"
    assert cancel_res["promoted_registration"].status == "confirmed"


# ── Scenario 9: Duplicate registration is rejected ───────────────────────────

def test_09_duplicate_registration_rejected(db, setup_data):
    base_date = setup_data["base_date"]
    shift = Shift(
        id="shift-dup",
        event_id=setup_data["event"].id,
        name="Dup Shift",
        start_time=datetime.combine(base_date, time(9, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(base_date, time(11, 0), tzinfo=timezone.utc),
        required_volunteers=5,
    )
    db.add(shift)
    db.commit()

    register_volunteer_for_shift("vol-1", shift.id, db)
    # Attempting to register again
    with pytest.raises(HTTPException) as exc_info:
        register_volunteer_for_shift("vol-1", shift.id, db)
    assert exc_info.value.status_code == 400
    assert "already confirmed" in exc_info.value.detail


# ── Scenario 10: Registration outside volunteer availability is rejected ──────

def test_10_outside_availability_rejected(db, setup_data):
    base_date = setup_data["base_date"]  # e.g., Tuesday
    day_of_week = base_date.weekday()

    # Vol-1 declares availability: 14:00 to 18:00 only on this day
    avail = VolunteerAvailability(
        id="avail-1",
        volunteer_id="vol-1",
        day_of_week=day_of_week,
        start_time=time(14, 0),
        end_time=time(18, 0),
        is_recurring=True,
    )
    db.add(avail)

    # Shift is in the morning: 09:00 - 12:00
    morning_shift = Shift(
        id="shift-morn",
        event_id=setup_data["event"].id,
        name="Morning Event",
        start_time=datetime.combine(base_date, time(9, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(base_date, time(12, 0), tzinfo=timezone.utc),
        required_volunteers=5,
    )
    # Shift in the afternoon: 14:30 - 17:00 (fits availability)
    afternoon_shift = Shift(
        id="shift-afternoon",
        event_id=setup_data["event"].id,
        name="Afternoon Event",
        start_time=datetime.combine(base_date, time(14, 30), tzinfo=timezone.utc),
        end_time=datetime.combine(base_date, time(17, 0), tzinfo=timezone.utc),
        required_volunteers=5,
    )
    db.add_all([morning_shift, afternoon_shift])
    db.commit()

    # Morning registration must fail
    with pytest.raises(HTTPException) as exc_info:
        register_volunteer_for_shift("vol-1", morning_shift.id, db)
    assert exc_info.value.status_code == 400
    assert "outside your declared availability" in exc_info.value.detail

    # Afternoon registration succeeds
    res = register_volunteer_for_shift("vol-1", afternoon_shift.id, db)
    assert res["status"] == "confirmed"


# ── Scenario 11: Exact capacity limit enforced ───────────────────────────────

def test_11_multiple_volunteers_capacity_enforced(db, setup_data):
    base_date = setup_data["base_date"]
    shift = Shift(
        id="shift-exact-cap",
        event_id=setup_data["event"].id,
        name="Exact Cap Shift",
        start_time=datetime.combine(base_date, time(9, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(base_date, time(12, 0), tzinfo=timezone.utc),
        required_volunteers=3,
    )
    db.add(shift)
    db.commit()

    # Register 3 volunteers (should all be confirmed)
    for v_id in ["vol-1", "vol-2", "vol-3"]:
        r = register_volunteer_for_shift(v_id, shift.id, db)
        assert r["status"] == "confirmed"

    # 4th volunteer must be waitlisted
    r4 = register_volunteer_for_shift("vol-4", shift.id, db)
    assert r4["status"] == "waitlisted"
    assert r4["waitlist_position"] == 1


# ── Scenario 12: Cannot cancel another person's registration ─────────────────

def test_12_cancel_unauthorized_rejected(db, setup_data):
    base_date = setup_data["base_date"]
    shift = Shift(
        id="shift-auth-test",
        event_id=setup_data["event"].id,
        name="Auth Test Shift",
        start_time=datetime.combine(base_date, time(9, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(base_date, time(12, 0), tzinfo=timezone.utc),
        required_volunteers=5,
    )
    db.add(shift)
    db.commit()

    r1 = register_volunteer_for_shift("vol-1", shift.id, db)

    # Vol-2 tries to cancel Vol-1's registration
    vol2_user = db.get(User, "vol-2")
    with pytest.raises(HTTPException) as exc_info:
        cancel_registration(r1["registration"].id, vol2_user, "Malicious attempt", db)
    assert exc_info.value.status_code == 403
    assert "not authorized" in exc_info.value.detail


# ── Scenario 13: Cancelled registration allows future re-registration ─────────

def test_13_cancelled_registration_allows_re_registration(db, setup_data):
    base_date = setup_data["base_date"]
    shift = Shift(
        id="shift-re-reg",
        event_id=setup_data["event"].id,
        name="Re-reg Shift",
        start_time=datetime.combine(base_date, time(9, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(base_date, time(12, 0), tzinfo=timezone.utc),
        required_volunteers=5,
    )
    db.add(shift)
    db.commit()

    # 1. Register
    r = register_volunteer_for_shift("vol-1", shift.id, db)
    assert r["status"] == "confirmed"

    # 2. Cancel
    vol1_user = db.get(User, "vol-1")
    cancel_registration(r["registration"].id, vol1_user, "Changed mind", db)

    # 3. Re-register (MUST succeed and not fail on DB unique constraint)
    re_r = register_volunteer_for_shift("vol-1", shift.id, db)
    assert re_r["status"] == "confirmed"
    assert re_r["registration"].status == "confirmed"
