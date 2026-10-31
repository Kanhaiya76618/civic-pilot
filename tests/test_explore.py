"""AI explore mode: plan live, record the run, replay it with zero model calls."""

import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import yaml

from executor.config import ROOT
from executor.models import ApplicationTask, ConsentRecord, TaskMode, TaskStatus
from executor.registry import Registry
from harness.rule_llm import RuleExploreLLM
from harness.sim_human import SimHuman

from .conftest import SANDBOX_URL

FILL_FORM = [
    ("select", r"id=eligState ", "input.state"),
    ("choose", r"id=catSC ", ""),
    ("fill", r"id=eligIncome ", "input.annual_income"),
    ("click", r"button 'Check eligibility'", ""),
]


def task(executor, inputs: dict, strategy: str = "auto") -> ApplicationTask:
    cid = "cit_" + uuid.uuid4().hex[:6]
    consent = ConsentRecord(consent_id="cons_" + uuid.uuid4().hex[:8], citizen_id=cid, portal_ids=["sandbox"],
                            service_ids=["eligibility_check"], purpose="check eligibility",
                            expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    executor.store.put_consent(consent.model_dump(mode="json"))
    return ApplicationTask(idempotency_key="idem_" + uuid.uuid4().hex, citizen_id=cid, portal_id="sandbox",
                           service_id="eligibility_check", inputs=inputs, consent_id=consent.consent_id,
                           mode=TaskMode.assist, strategy=strategy, origin="eval")


async def run(executor, t):
    task_id, _ = executor.submit(t)
    status = await SimHuman(executor, SANDBOX_URL).drive(task_id, timeout_s=60)
    row = executor.store.get_task(task_id)
    return task_id, status, row


def events(executor, task_id):
    return executor.store.events_after(task_id, 0)


async def test_explore_records_a_route_then_replays_it_without_the_model(executor, tmp_path):
    executor.llm = RuleExploreLLM([(FILL_FORM, "continue")])
    task_id, status, row = await run(executor, task(executor, {"state": "Bihar", "category": "SC", "annual_income": "180000"}))
    assert status == TaskStatus.completed, row["error"]
    receipt = executor.store.get_receipt(row["receipt_id"])
    assert receipt["outcome"] == "information_retrieved"
    assert receipt["result"]["count"] == 3 and len(receipt["result"]["items"]) == 3
    assert receipt["timing"]["model_calls"] == 1
    assert any(e["kind"] == "reasoning" for e in events(executor, task_id))

    draft = yaml.safe_load(Path(executor.last_patch[task_id]).read_text().split("\n", 2)[2])
    assert draft["status"] == "draft"
    choose = next(s for s in draft["steps"] if s["do"] == "check")
    assert choose["target"]["id"] == "cat{{input.category}}"  # generalised for the next citizen
    assert [s["do"] for s in draft["steps"]] == ["goto", "select", "check", "fill", "click", "extract"]

    # Promote the draft into a copy of the registry and replay it for a different citizen.
    reg_dir = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", reg_dir)
    draft["status"] = "stable"
    (reg_dir / "sandbox" / "eligibility_check.route.yaml").write_text(yaml.safe_dump(draft, sort_keys=False))
    old_registry = executor.registry
    executor.registry = executor.policy.registry = Registry(reg_dir)
    executor.llm = None
    try:
        task_id2, status2, row2 = await run(executor, task(executor, {"state": "Delhi", "category": "OBC", "annual_income": "200000"}))
    finally:
        executor.registry = executor.policy.registry = old_registry
    assert status2 == TaskStatus.completed, row2["error"]
    receipt2 = executor.store.get_receipt(row2["receipt_id"])
    assert receipt2["timing"]["model_calls"] == 0
    assert receipt2["result"]["count"] == 3


async def test_explore_blocks_injected_link(executor):
    httpx.post(SANDBOX_URL + "/__admin/config", json={"variant": "inject"})
    executor.llm = RuleExploreLLM([([("click", r"Claim benefits instantly", "")], "continue"), (FILL_FORM, "continue")])
    task_id, status, row = await run(executor, task(executor, {"state": "Bihar", "category": "SC", "annual_income": "180000"}))
    assert status == TaskStatus.completed, row["error"]
    sec = [e["message"] for e in events(executor, task_id) if e["kind"] == "security"]
    assert any("treated as data" in m for m in sec)
    assert any("link leaves the allowed domains (evil.example)" in m for m in sec)


async def test_explore_refuses_values_that_are_not_the_citizens(executor):
    executor.llm = RuleExploreLLM([
        ([("fill", r"id=eligIncome ", "input.aadhaar")], "continue"),
        (FILL_FORM, "continue"),
    ])
    task_id, status, row = await run(executor, task(executor, {"state": "Bihar", "category": "SC", "annual_income": "180000"}))
    assert status == TaskStatus.completed, row["error"]
    second_prompt = executor.llm.requests[1]
    assert "BLOCKED: 'input.aadhaar' is not one of the citizen's details" in second_prompt


async def test_explore_without_a_model_stops_safely(executor):
    executor.llm = None
    task_id, status, row = await run(executor, task(executor, {"state": "Bihar", "category": "SC", "annual_income": "180000"}))
    assert status == TaskStatus.needs_review and "needs a model" in row["error"]
