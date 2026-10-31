"""End-to-end runs against the sandbox portal with a simulated citizen."""

import httpx

from executor.models import Receipt, TaskMode, TaskStatus
from executor.receipts import verify
from harness.seed import seed_task
from harness.sim_human import SimHuman
from sandbox_portal import app as sandbox

from .conftest import SANDBOX_URL


def events(ex, task_id):
    return ex.store.events_after(task_id, 0)


async def run(ex, task, **human):
    task_id, created = ex.submit(task)
    assert created
    human_ = SimHuman(ex, SANDBOX_URL, **human)
    status = await human_.drive(task_id)
    return task_id, status, human_


async def test_scholarship_assist_end_to_end(executor):
    task = seed_task(executor, persona=0)
    task_id, status, human = await run(executor, task)
    row = executor.store.get_task(task_id)
    assert status == TaskStatus.completed, row["error"]
    receipt = Receipt(**executor.store.get_receipt(row["receipt_id"]))
    assert receipt.outcome == "submitted"
    assert receipt.reference_no and receipt.reference_no.startswith("SBX-SCH/2026/")
    assert receipt.approved_by == "citizen"
    assert verify(receipt, executor.signer.public_key_b64)
    assert {e.name for e in receipt.evidence} >= {"approval_screenshot", "final_screenshot", "manifest"}
    assert human.actions == ["otp", "captcha:ok", "approve"]
    t = receipt.timing
    assert t.human_wait_ms > 0 and t.agent_ms > 0 and t.model_calls == 0
    statuses = [e["status"] for e in events(executor, task_id) if e["kind"] == "status"]
    for s in ["validating", "preparing_docs", "running", "awaiting_human", "awaiting_approval", "submitting", "verifying"]:
        assert s in statuses


async def test_receipt_tamper_detected(executor):
    task = seed_task(executor, persona=1)
    task_id, status, _ = await run(executor, task)
    assert status == TaskStatus.completed
    data = executor.store.get_receipt(executor.store.get_task(task_id)["receipt_id"])
    forged = Receipt(**{**data, "reference_no": "SBX-SCH/2026/999999"})
    assert verify(Receipt(**data), executor.signer.public_key_b64)
    assert not verify(forged, executor.signer.public_key_b64)


async def test_grievance_assist_end_to_end(executor):
    task = seed_task(executor, persona=1, service="public_grievance", with_attachment=True, origin_ref="part2-issue-42")
    task_id, status, _ = await run(executor, task)
    row = executor.store.get_task(task_id)
    assert status == TaskStatus.completed, row["error"]
    receipt = executor.store.get_receipt(row["receipt_id"])
    assert receipt["reference_no"].startswith("SBX/MOHUA/E/2026/")
    assert receipt["origin_ref"] == "part2-issue-42"
    card = next(e for e in events(executor, task_id) if e["kind"] == "approval_needed")["data"]["card"]
    assert card["differences"] == []  # grievance category is not the citizen's social category
    assert "'Submit Grievance' once" in card["next"]
    assert not any(v["source"] == "document" for v in card["values"]) and card["documents"]


async def test_grievance_without_optional_attachment(executor):
    task = seed_task(executor, persona=2, service="public_grievance")
    task_id, status, _ = await run(executor, task)
    assert status == TaskStatus.completed, executor.store.get_task(task_id)["error"]
    assert any("Optional step 'upload_attachment' skipped" in e["message"] for e in events(executor, task_id))


async def test_dry_run_never_submits(executor):
    before = sandbox.COUNTER["sch"]
    task = seed_task(executor, persona=2, mode=TaskMode.dry_run)
    task_id, status, human = await run(executor, task)
    row = executor.store.get_task(task_id)
    assert status == TaskStatus.completed, row["error"]
    receipt = executor.store.get_receipt(row["receipt_id"])
    assert receipt["outcome"] == "dry_run_complete" and receipt["reference_no"] is None
    assert sandbox.COUNTER["sch"] == before
    assert "approve" not in human.actions
    card = next(e for e in events(executor, task_id) if e["kind"] == "approval_needed")["data"]["card"]
    # persona 2's profile says General but the application says EWS: the card must flag it
    assert any("category" in d for d in card["differences"])
    bank = next(v for v in card["values"] if v["label"] == "Bank Account Number")
    assert bank["value"].startswith("••••") and "30300011223344" not in str(card)


async def test_wrong_captcha_recovers_without_double_filing(executor):
    before = sandbox.COUNTER["sch"]
    task = seed_task(executor, persona=0)
    task_id, status, human = await run(executor, task, wrong_captcha_first=True)
    assert status == TaskStatus.completed, executor.store.get_task(task_id)["error"]
    assert human.actions == ["otp", "captcha:wrong", "approve", "captcha:ok", "approve"]
    assert sandbox.COUNTER["sch"] == before + 1


async def test_citizen_rejects(executor):
    before = sandbox.COUNTER["grv"]
    task = seed_task(executor, persona=0, service="public_grievance")
    task_id, status, _ = await run(executor, task, approve=False)
    assert status == TaskStatus.failed
    assert "rejected" in executor.store.get_task(task_id)["error"]
    assert sandbox.COUNTER["grv"] == before


async def test_session_expiry_fails_safe(executor):
    old = sandbox.SESSION_TTL_S
    sandbox.SESSION_TTL_S = 3
    try:
        task = seed_task(executor, persona=1, service="public_grievance")
        task_id, status, _ = await run(executor, task, approval_delay_s=4)
    finally:
        sandbox.SESSION_TTL_S = old
    row = executor.store.get_task(task_id)
    assert status == TaskStatus.needs_review
    assert "Do NOT resubmit" in row["error"]


async def test_idempotency_key_returns_same_task(executor):
    task = seed_task(executor, persona=0, mode=TaskMode.dry_run)
    a, created_a = executor.submit(task)
    b, created_b = executor.submit(task)
    assert a == b and created_a and not created_b
    await SimHuman(executor, SANDBOX_URL).drive(a)


async def test_sandbox_has_banner():
    r = httpx.get(SANDBOX_URL + "/")
    assert "SANDBOX REPLICA — not a government website" in r.text
