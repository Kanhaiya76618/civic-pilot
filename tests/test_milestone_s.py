"""
Milestone S Verification Suite
Tests:
1. Supabase PostgreSQL live connectivity and seeded dataset integrity
2. Storage upload validation (MIME whitelisting, extension enforcement, 10MB limit)
3. Cryptographic Ed25519 signing and tamper-evident SHA-256 hash chaining
"""

import os
import pytest
from datetime import datetime, timezone
from server.db import SessionLocal, User, Report, ReceiptModel, Scheme, PortalRegistry
from server.storage import validate_file, StorageValidationError, upload_evidence
from server.receipts import sign_receipt, verify_receipt, compute_ticket_hash

def test_supabase_dataset_integrity():
    """Verify live Supabase database contains all seeded entities and relationships."""
    db = SessionLocal()
    try:
        # Check Users
        users = db.query(User).all()
        assert len(users) >= 2, f"Expected at least 2 users, found {len(users)}"
        roles = {u.role for u in users}
        assert "citizen" in roles and "admin" in roles

        # Check Reports count & wards
        reports = db.query(Report).all()
        assert len(reports) >= 18, f"Expected at least 18 reports, found {len(reports)}"
        ward_ids = {r.ward_id for r in reports}
        assert {"BBMP-111", "BBMP-151", "PMC-12", "MCD-54"}.issubset(ward_ids)

        # Check SLA-breached P1
        now = datetime.now(timezone.utc)
        breached = [r for r in reports if r.severity == "P1" and r.sla_deadline and r.sla_deadline < now and r.status != "RESOLVED"]
        assert len(breached) >= 1, "Expected at least 1 SLA-breached P1 report"

        # Check Duplicate Pair
        duplicates = [r for r in reports if r.duplicate_of is not None]
        assert len(duplicates) >= 1, "Expected at least 1 deduplicated report"

        # Check Resolved Report with Proof
        resolved = [r for r in reports if r.status == "RESOLVED" and r.resolution_proof_url]
        assert len(resolved) >= 1, "Expected at least 1 resolved report with proof photo"

        # Check Verifiable Receipt
        receipts = db.query(ReceiptModel).all()
        assert len(receipts) >= 1, "Expected at least 1 receipt in ledger"
        rcpt = receipts[0]
        assert rcpt.signature and rcpt.ticket_hash and rcpt.public_key

        # Cryptographically verify the seeded receipt
        rcpt_dict = {
            "payload": rcpt.payload,
            "prev_hash": rcpt.prev_hash,
            "ticket_hash": rcpt.ticket_hash,
            "signature": rcpt.signature,
            "public_key": rcpt.public_key
        }
        valid, msg = verify_receipt(rcpt_dict, expected_prev_hash=rcpt.prev_hash)
        assert valid, f"Seeded receipt cryptographic verification failed: {msg}"

    finally:
        db.close()


def test_storage_validation_rules():
    """Verify MIME whitelisting, extension enforcement, and 10MB limits."""
    # 1. Valid PNG
    valid_png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"0" * 100
    ext = validate_file(valid_png_bytes, "damage.png", "image/png")
    assert ext == ".png"

    # 2. Valid JPEG
    valid_jpg_bytes = b"\xff\xd8\xff" + b"0" * 100
    ext = validate_file(valid_jpg_bytes, "pothole.jpg", "image/jpeg")
    assert ext in [".jpg", ".jpeg"]

    # 3. Disallowed MIME (.gif) -> status 415
    with pytest.raises(StorageValidationError) as exc_info:
        validate_file(b"GIF89a" + b"0" * 50, "exploit.gif", "image/gif")
    assert exc_info.value.status_code == 415

    # 4. Mismatched extension (.exe disguised as image/jpeg) -> status 415
    with pytest.raises(StorageValidationError) as exc_info:
        validate_file(valid_jpg_bytes, "malware.exe", "image/jpeg")
    assert exc_info.value.status_code == 415

    # 5. Oversized payload (> 10MB) -> status 413
    oversized = b"A" * (10 * 1024 * 1024 + 1024)  # 10MB + 1KB
    with pytest.raises(StorageValidationError) as exc_info:
        validate_file(oversized, "big_video.png", "image/png")
    assert exc_info.value.status_code == 413


def test_cryptographic_receipt_tamper_detection():
    """Verify that tampering with payload or prev_hash fails verification."""
    payload = {
        "task_id": "test-task-1",
        "confirmation_number": "MOCK-123",
        "applicant": "Test User",
        "ward": "BBMP-111"
    }
    prev_hash = "0" * 64
    receipt = sign_receipt(payload, prev_hash=prev_hash)

    # 1. Verify valid receipt
    is_valid, msg = verify_receipt(receipt, expected_prev_hash=prev_hash)
    assert is_valid, f"Expected valid receipt, got: {msg}"

    # 2. Tampered payload
    tampered_receipt = dict(receipt)
    tampered_receipt["payload"] = dict(payload)
    tampered_receipt["payload"]["applicant"] = "Attacker"
    is_valid, msg = verify_receipt(tampered_receipt, expected_prev_hash=prev_hash)
    assert not is_valid
    assert "Hash mismatch" in msg

    # 3. Broken hash chain
    is_valid, msg = verify_receipt(receipt, expected_prev_hash="f" * 64)
    assert not is_valid
    assert "Broken hash chain" in msg
