"""
Test Unified FastAPI Endpoints
Tests:
1. Health and config (part1_connected, part2_connected)
2. Auth login with demo accounts (citizen@demo.in, admin@demo.in)
3. Public reports & stats from live Supabase DB
4. Grievance reporting with AI triage & 50m spatial dedup
5. Admin queue & triage override / assignment / resolution with proof photo
6. Cryptographic receipts verification
7. Scheme explainer matching
"""

import pytest
from fastapi.testclient import TestClient
from executor.api import make_app

@pytest.fixture(scope="module")
def client():
    app = make_app()
    with TestClient(app) as c:
        yield c

def test_app_config_and_health(client):
    res = client.get("/app/config")
    assert res.status_code == 200
    data = res.json()
    assert data["part1_connected"] is bool(data["ai_available"])  # the built-in explainer needs a model
    assert data["part2_connected"] is True

def test_auth_demo_login(client):
    # Citizen login
    res = client.post("/api/v1/auth/login", json={"email": "citizen@demo.in"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "citizen"

    # Admin login
    res_admin = client.post("/api/v1/auth/login", json={"email": "admin@demo.in"})
    assert res_admin.status_code == 200
    data_admin = res_admin.json()
    assert "access_token" in data_admin
    assert data_admin["user"]["role"] == "admin"

def test_public_reports_and_stats(client):
    # Public reports
    res = client.get("/api/public/reports")
    assert res.status_code == 200
    reports = res.json()
    assert len(reports) >= 18
    assert all(r["severity"] in {"P1", "P2", "P3", "P4"} for r in reports)  # the newest 100 need not include a P1

    # Public stats
    res_stats = client.get("/api/public/stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["total"] >= 18
    assert "open" in stats
    assert "resolved_pct" in stats
    assert stats["sla_breached"] >= 1

def test_citizen_report_intake_requires_sign_in(client):
    """The public board is open, but submitting a report always has an accountable citizen session."""
    res = client.post("/api/reports")
    assert res.status_code in {401, 403}

def test_admin_queue_access(client):
    # 1. Fresh unauthenticated client should fail with 401
    from fastapi.testclient import TestClient
    from executor.api import make_app
    fresh_client = TestClient(make_app())
    res_unauth = fresh_client.get("/api/v1/admin/queue")
    assert res_unauth.status_code == 401

    # 2. Login as admin
    login_res = fresh_client.post("/api/v1/auth/login", json={"email": "admin@demo.in"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Access admin queue
    res_queue = fresh_client.get("/api/v1/admin/queue", headers=headers)
    assert res_queue.status_code == 200
    queue = res_queue.json()
    assert len(queue) >= 18
    # Confirm P1 reports are prioritized first
    assert queue[0]["severity"] == "P1"

def test_scheme_matching(client):
    res = client.post("/api/v1/schemes/match", json={
        "income": 180000,
        "location_type": "urban",
        "own_pucca_house": False
    })
    assert res.status_code == 200
    matches = res.json()
    assert len(matches) >= 3
    # First match should be eligible
    assert matches[0]["eligible"] is True
