"""Criterion: Role-based auth & protected routes."""
import uuid

import httpx

from tests.conftest import api_url


def test_login_role_and_me(client):
    r = client.post("/auth/login", json={"email": "annapurna@demo.vc", "password": "Demo@1234"})
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "ngo"

    r2 = client.post("/auth/login", json={"email": "priya@demo.vc", "password": "Demo@1234"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["role"] == "volunteer"


def test_volunteer_gets_403_on_ngo_dashboard(client):
    r = client.post("/auth/login", json={"email": "priya@demo.vc", "password": "Demo@1234"})
    assert r.status_code == 200
    r2 = client.get("/ngo/dashboard")
    assert r2.status_code == 403, r2.text


def test_signed_out_cannot_reach_ngo_dashboard(client):
    with httpx.Client(base_url=api_url(), timeout=30.0) as anon:
        r = anon.get("/ngo/dashboard")
        assert r.status_code in (401, 403), r.text


def test_register_new_ngo_and_volunteer():
    suffix = uuid.uuid4().hex[:8]
    with httpx.Client(base_url=api_url(), timeout=30.0) as c:
        ngo_body = {
            "role": "ngo", "full_name": f"tscheck-ngo-{suffix}", "email": f"tscheck-ngo-{suffix}@example.com",
            "password": "Demo@1234", "phone": "9999999999", "location": "Bengaluru",
            "description": "A test NGO description long enough.", "causes": ["education"],
        }
        r = c.post("/auth/register", json=ngo_body)
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "ngo"

        vol_body = {
            "role": "volunteer", "full_name": f"tscheck-vol-{suffix}", "email": f"tscheck-vol-{suffix}@example.com",
            "password": "Demo@1234", "phone": "8888888888", "location": "Bengaluru",
        }
        r2 = c.post("/auth/register", json=vol_body)
        assert r2.status_code == 200, r2.text
        assert r2.json()["role"] == "volunteer"


def test_register_ngo_without_causes_rejected():
    """Server-side mirrors the frontend rule: NGO registration needs description + >=1 cause.

    The schema itself allows empty causes/description (frontend enforces it), so this
    test documents actual behavior rather than assume a 4xx — see note below.
    """
    suffix = uuid.uuid4().hex[:8]
    with httpx.Client(base_url=api_url(), timeout=30.0) as c:
        body = {
            "role": "ngo", "full_name": f"tscheck-ngo2-{suffix}", "email": f"tscheck-ngo2-{suffix}@example.com",
            "password": "Demo@1234", "phone": "9999999999", "location": "Bengaluru",
        }
        r = c.post("/auth/register", json=body)
        # Backend enforces the same rule as the frontend: NGOs need description + >=1 cause.
        assert r.status_code == 400, r.text
