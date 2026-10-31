"""
Test Milestone 4: Closed-Loop AutoFile Pipeline (P2 -> P3 Bridge)
Tests:
1. High-severity / SLA-breached report escalation via AutoFile
2. Generation of Ed25519 tamper-evident receipt linked in SHA-256 hash chain
3. Cryptographic receipt verification via /api/v1/receipts/verify
4. Verification that ticket status transitions to ASSIGNED with confirmation reference
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

    # 3. Trigger Closed-Loop AutoFile
    autofile_res = client.post(f"/api/v1/reports/{report_id}/autofile", headers=headers)
    assert autofile_res.status_code == 200
    data = autofile_res.json()
    assert data["ok"] is True
    assert "CPGRAMS" in data["confirmation_number"]
    assert "ticket_hash" in data
    assert data["status"] == "ASSIGNED"

    # 4. Fetch receipts and verify cryptographic integrity
    rcpts_res = client.get("/api/v1/receipts")
    assert rcpts_res.status_code == 200
    receipts = rcpts_res.json()
    assert len(receipts) >= 1
    latest_receipt = receipts[0]

    # Verify receipt cryptographically via endpoint
    verify_res = client.post("/api/v1/receipts/verify", json={
        "receipt_data": {
            "payload": latest_receipt["payload"],
            "prev_hash": latest_receipt["prev_hash"],
            "ticket_hash": latest_receipt["ticket_hash"],
            "signature": latest_receipt["signature"],
            "public_key": latest_receipt["public_key"]
        },
        "expected_prev_hash": latest_receipt["prev_hash"]
    })
    assert verify_res.status_code == 200
    assert verify_res.json()["valid"] is True
