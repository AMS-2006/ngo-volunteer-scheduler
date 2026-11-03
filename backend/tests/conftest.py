"""
Test fixtures. DB-backed tests need a dedicated PostgreSQL database (the models use
ARRAY columns, identity columns and partial unique indexes, so SQLite cannot be used):

    set TEST_DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/ngo_volunteer_test

The database name MUST contain "test": its tables are dropped and re-created.
Pure scoring tests (test_match_scoring.py) run without any database.
"""

import os
import uuid
from datetime import date, time, timedelta
from types import SimpleNamespace

import pytest

TEST_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_URL:
    os.environ["DATABASE_URL"] = TEST_URL  # must happen before the app is imported


@pytest.fixture(scope="session")
def _engine():
    if not TEST_URL:
        pytest.skip("Set TEST_DATABASE_URL (a PostgreSQL database whose name contains 'test').")
    if "test" not in TEST_URL.rsplit("/", 1)[-1].lower():
        pytest.skip("Refusing to run: TEST_DATABASE_URL database name must contain 'test'.")
    import app.database.models  # noqa: F401
    from app.database.connection import Base, engine

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db(_engine):
    from app.database.connection import Base, SessionLocal

    session = SessionLocal()
    yield session
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


@pytest.fixture
def client(_engine):
    from fastapi.testclient import TestClient

    from app.main import app

    yield TestClient(app)  # no context manager -> startup create_all is not re-run
    app.dependency_overrides.clear()


@pytest.fixture
def act_as(client):
    from app.core.deps import get_current_user
    from app.main import app

    def _act(user):
        snap = SimpleNamespace(
            id=user.id, role=user.role, full_name=user.full_name, email=user.email, is_active=True
        )
        app.dependency_overrides[get_current_user] = lambda: snap

    return _act


# ── Data builders ─────────────────────────────────────────────────────────────
SHIFT_DAY = date.today() + timedelta(days=7)


def make_user(db, role, name, active=True):
    from app.models.user import User

    u = User(email=f"{uuid.uuid4().hex[:10]}@t.test", password_hash="x", full_name=name, role=role, is_active=active)
    db.add(u)
    db.commit()
    return u


def make_volunteer(db, name, skills=("First Aid",), interests=("Health",), window=(time(8), time(18)), city="Pune"):
    from app.models.availability import VolunteerAvailability
    from app.models.volunteer import VolunteerProfile

    u = make_user(db, "volunteer", name)
    db.add(VolunteerProfile(user_id=u.id, skills=list(skills), interests=list(interests), city=city))
    if window:
        db.add(VolunteerAvailability(
            volunteer_id=u.id, day_of_week=SHIFT_DAY.weekday(), start_time=window[0], end_time=window[1]
        ))
    db.commit()
    return u


def make_event(db, admin, name="Health Camp"):
    from app.models.event import Event

    e = Event(name=name, location="Pune", start_date=SHIFT_DAY, end_date=SHIFT_DAY, created_by=admin.id)
    db.add(e)
    db.commit()
    return e


def make_shift(db, event, capacity=2, start=time(9), end=time(12), title="Morning"):
    from app.models.shift import Shift

    s = Shift(event_id=event.id, title=title, shift_date=SHIFT_DAY, start_time=start, end_time=end, capacity=capacity)
    db.add(s)
    db.commit()
    return s


def require(db, shift, skills=("First Aid",), tags=("Health",), mandatory=True, city=None):
    from app.models.matching import ShiftRequirement

    db.add(ShiftRequirement(
        shift_id=shift.id, required_skills=list(skills), optional_skills=[], interest_tags=list(tags),
        skills_mandatory=mandatory, required_city=city,
    ))
    db.commit()


def confirm(db, shift, volunteer):
    from app.models.registration import Registration
    from app.services.common import utcnow

    r = Registration(shift_id=shift.id, volunteer_id=volunteer.id, status="CONFIRMED", confirmed_at=utcnow())
    db.add(r)
    db.commit()
    return r
