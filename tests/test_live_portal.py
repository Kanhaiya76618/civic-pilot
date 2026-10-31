"""Runs against the real myScheme portal (network). Skip with: pytest -m 'not live'."""

import pytest

from executor.models import ApplicationTask, ConsentRecord, Receipt, TaskMode, TaskStatus
from executor.receipts import verify
from harness.sim_human import SimHuman

from .conftest import SANDBOX_URL

pytestmark = pytest.mark.live


def lookup_task(executor, inputs: dict, strategy: str = "auto") -> ApplicationTask:
    import uuid
    from datetime import datetime, timedelta, timezone

    cid = "cit_live_" + uuid.uuid4().hex[:6]
    consent = ConsentRecord(consent_id="cons_" + uuid.uuid4().hex[:8], citizen_id=cid, portal_ids=["myscheme"],
                            service_ids=["find_schemes"], purpose="find schemes", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    executor.store.put_consent(consent.model_dump(mode="json"))
    return ApplicationTask(idempotency_key="idem_" + uuid.uuid4().hex, citizen_id=cid, portal_id="myscheme", service_id="find_schemes",
                           inputs=inputs, consent_id=consent.consent_id, mode=TaskMode.assist, strategy=strategy, origin="eval")


async def test_myscheme_recorded_route_returns_real_schemes(executor):
    inputs = {"gender": "Female", "age": "20", "marital_status": "Never Married", "state": "Bihar", "residence": "Rural",
              "caste": "Scheduled Caste (SC)", "disability": "No", "minority": "No", "is_student": "Yes", "bpl": "Yes",
              "economic_distress": "No"}
    task_id, _ = executor.submit(lookup_task(executor, inputs))
    status = await SimHuman(executor, SANDBOX_URL).drive(task_id, timeout_s=120)
    row = executor.store.get_task(task_id)
    assert status == TaskStatus.completed, row["error"]
    receipt = Receipt(**executor.store.get_receipt(row["receipt_id"]))
    assert receipt.outcome == "information_retrieved" and verify(receipt, executor.signer.public_key_b64)
    result = receipt.result
    # Live data: this profile may legitimately match nothing ("No Schemes Found!"); both are valid answers.
    assert result["count"] == len(result["items"]) == 0 or (result["count"] > 0 and 1 <= len(result["items"]) <= 10)
    assert all(i["url"].startswith("https://www.myscheme.gov.in/schemes/") for i in result["items"])
    assert receipt.timing.model_calls == 0


async def test_myscheme_male_non_student_branch(executor):
    inputs = {"gender": "Male", "age": "34", "state": "Tamil Nadu", "residence": "Urban", "caste": "Other Backward Class (OBC)",
              "disability": "Yes", "disability_percentage": "60", "is_student": "No", "employment_status": "Employed", "government_employee": "No", "occupation": "Construction Worker", "bpl": "No"}
    task_id, _ = executor.submit(lookup_task(executor, inputs))
    status = await SimHuman(executor, SANDBOX_URL).drive(task_id, timeout_s=120)
    row = executor.store.get_task(task_id)
    assert status == TaskStatus.completed, row["error"]
    assert executor.store.get_receipt(row["receipt_id"])["result"]["count"] > 0


async def test_myscheme_ai_explore_then_replay(executor, tmp_path):
    """Explore the real portal with a scripted model, then replay the recorded route with no model at all."""
    import shutil
    from pathlib import Path

    import yaml

    from executor.config import ROOT
    from executor.registry import Registry
    from harness.rule_llm import RuleExploreLLM

    inputs = {"gender": "Female", "age": "20", "marital_status": "Never Married", "state": "Bihar", "residence": "Rural",
              "caste": "Scheduled Caste (SC)", "disability": "No", "minority": "No", "is_student": "Yes", "bpl": "Yes",
              "economic_distress": "No"}
    nxt = ("click", r"button 'Next'", "")
    executor.llm = RuleExploreLLM([
        ([("choose", r"id=answerFemale ", ""), ("select", r'"options_count": 115', "input.age")], "continue"),
        ([("select", r"Never Married", "input.marital_status"), nxt], "continue"),
        ([("select", r"Andaman", "input.state"), ("choose", r"id=answerRural_residence ", ""), nxt], "continue"),
        ([("choose", r"id=answerScheduled Caste \(SC\)_caste ", ""), nxt], "continue"),
        ([("choose", r"id=answerNo_disability ", "")], "continue"),
        ([("choose", r"id=answerNo_minority ", ""), nxt], "continue"),
        ([("choose", r"id=answerYes_isStudent ", ""), nxt], "continue"),
        ([("choose", r"id=answerYes_isBpl ", "")], "continue"),
        ([("choose", r"id=answerNo_isEconomicDistress ", ""), ("click", r"button 'Submit'", "")], "finished"),
    ])
    task_id, _ = executor.submit(lookup_task(executor, inputs, strategy="explore"))
    status = await SimHuman(executor, SANDBOX_URL).drive(task_id, timeout_s=120)
    row = executor.store.get_task(task_id)
    if status != TaskStatus.completed:
        for r in executor.llm.requests[1:4]:
            print("=====", r[r.index("DONE SO FAR"):r.index("CURRENT PAGE")])
    assert status == TaskStatus.completed, row["error"]
    first = executor.store.get_receipt(row["receipt_id"])
    assert first["timing"]["model_calls"] == 9

    draft = yaml.safe_load(Path(executor.last_patch[task_id]).read_text().split("\n", 2)[2])
    ids = [s["target"].get("id") for s in draft["steps"] if s["do"] == "check"]
    assert "answer{{input.gender}}" in ids and "answer{{input.disability}}_disability" in ids
    assert "answer{{input.is_student}}_isStudent" in ids

    reg_dir = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", reg_dir)
    draft["status"] = "stable"
    (reg_dir / "myscheme" / "find_schemes.route.yaml").write_text(yaml.safe_dump(draft, sort_keys=False))
    old = executor.registry
    executor.registry = executor.policy.registry = Registry(reg_dir)
    executor.llm = None
    try:
        task_id2, _ = executor.submit(lookup_task(executor, inputs, strategy="route"))
        try:
            status2 = await SimHuman(executor, SANDBOX_URL).drive(task_id2, timeout_s=90)
        except TimeoutError:
            for e in executor.store.events_after(task_id2, 0):
                print(e["timing"]["agent_ms"], e["kind"], e["message"][:200])
            print(yaml.safe_dump(draft["steps"][:6]))
            raise
    finally:
        executor.registry = executor.policy.registry = old
    row2 = executor.store.get_task(task_id2)
    assert status2 == TaskStatus.completed, row2["error"]
    second = executor.store.get_receipt(row2["receipt_id"])
    assert second["timing"]["model_calls"] == 0
    assert second["result"]["count"] == first["result"]["count"]


async def test_live_public_apis():
    from executor import enrich
    pin = await enrich.pincode("823001")
    assert pin.ok and pin.data["state"] == "Bihar" and "Gaya" in pin.data["districts"]
    assert (await enrich.pincode("999999")).ok is False
    bank = await enrich.ifsc("SBIN0001234")
    assert bank.ok and bank.data["bank"] == "State Bank of India"
    assert (await enrich.ifsc("ABCD0000000")).ok is False
