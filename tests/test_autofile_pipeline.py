"""
Escalation for filing (Part 2 -> Part 3 bridge):
1. Only municipal staff can escalate a report
2. Escalating marks the report ASSIGNED to the filing agent
3. Nothing is filed: no invented confirmation number and no "filed" receipt
"""

import pytest
from fastapi.testclient import TestClient
from executor.api import make_app

@pytest.fixture(scope="module")
def client():
    app = make_app()
    with TestClient(app) as c:
        yield c

def test_closed_loop_autofile_escalation(client):
    # 1. Sign in as admin
    login_res = client.post("/api/v1/auth/login", json={"email": "admin@demo.in"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get the SLA-breached P1 report from admin queue
    queue_res = client.get("/api/v1/admin/queue", headers=headers)
    assert queue_res.status_code == 200
    queue = queue_res.json()
    breached_report = next((r for r in queue if r["severity"] == "P1"), queue[0])
    report_id = breached_report["id"]

    receipts_before = len(client.get("/api/v1/receipts").json())
    # 3. Escalate: flags the report for the filing agent; nothing is filed and no confirmation number is invented
    client.cookies.clear()
    assert client.post(f"/api/v1/reports/{report_id}/autofile").status_code == 401  # municipal staff only
    autofile_res = client.post(f"/api/v1/reports/{report_id}/autofile", headers=headers)
    assert autofile_res.status_code == 200
    data = autofile_res.json()
    assert data["ok"] is True and data["filed"] is False and data["status"] == "ASSIGNED"
    assert "confirmation_number" not in data and "ticket_hash" not in data

    # 4. No receipt is issued: only a real, approved filing by the agent issues one
    assert len(client.get("/api/v1/receipts").json()) == receipts_before
