"""Tier 2 repair, injected layout changes, prompt-injection defence and the canary check."""

import json

import httpx
import yaml

from executor.config import settings
from executor.models import TaskStatus
from harness.rule_llm import RuleLLM
from harness.seed import seed_task
from harness.sim_human import SimHuman

from .conftest import SANDBOX_URL

CANARY_VAULT = {"mobile": "9999073311", "email": "canary-7f3a91@example.test", "bank_account": "77331155992288"}


def variant(v):
    httpx.post(SANDBOX_URL + "/__admin/config", json={"variant": v})


def events(ex, task_id):
    return ex.store.events_after(task_id, 0)


async def run(ex, **seed):
    task = seed_task(ex, **seed)
    task_id, _ = ex.submit(task)
    status = await SimHuman(ex, SANDBOX_URL).drive(task_id)
    return task_id, status


async def test_renamed_ids_healed_by_heuristic_without_model(executor):
    variant("v2_renamed")
    task_id, status = await run(executor, persona=0)
    assert status == TaskStatus.completed, executor.store.get_task(task_id)["error"]
    evs = events(executor, task_id)
    assert any("Layout drift" in e["message"] for e in evs)
    heals = [e["message"] for e in evs if e["kind"] == "heal" and e["message"].startswith("Repaired")]
    assert len(heals) == 2 and all("heuristic" in h for h in heals)
    receipt = executor.store.get_receipt(executor.store.get_task(task_id)["receipt_id"])
    assert receipt["timing"]["model_calls"] == 0
    patch_path = executor.last_patch[task_id]
    patch = yaml.safe_load(open(patch_path).read())
    assert patch["status"] == "candidate" and patch["version"] == 2
    income = next(s for s in patch["steps"] if s["id"] == "fill_income")
    assert income["target"]["id"] == "familyIncome"
    assert income["target"]["alt"][0]["id"] == "annualIncome"  # old locator kept as fallback


async def test_relabelled_field_without_model_stops_safely(executor):
    variant("v3_relabel")
    task_id, status = await run(executor, persona=0)
    row = executor.store.get_task(task_id)
    assert status == TaskStatus.needs_review
    assert "fill_income" in row["error"] and "no model is configured" in row["error"]


async def test_relabelled_field_healed_by_model_loop(executor):
    variant("v3_relabel")
    executor.llm = RuleLLM([("do_step", r"household earnings")])
    task_id, status = await run(executor, persona=0)
    assert status == TaskStatus.completed, executor.store.get_task(task_id)["error"]
    receipt = executor.store.get_receipt(executor.store.get_task(task_id)["receipt_id"])
    assert receipt["timing"]["model_calls"] == 1


async def test_interstitial_page_healed_with_detours(executor):
    variant("v4_interstitial")
    executor.llm = RuleLLM([("check", r"I have read"), ("click", r"button 'Continue'")])
    task_id, status = await run(executor, persona=1)
    assert status == TaskStatus.completed, executor.store.get_task(task_id)["error"]
    patch = yaml.safe_load(open(executor.last_patch[task_id]).read())
    ids = [s["id"] for s in patch["steps"]]
    assert ids[ids.index("next_1") + 1: ids.index("next_1") + 3] == ["next_1_auto1", "next_1_auto2"]


async def test_tier1_ignores_injected_notice_and_logs_it(executor):
    variant("inject")
    task_id, status = await run(executor, persona=0)
    assert status == TaskStatus.completed
    sec = [e["message"] for e in events(executor, task_id) if e["kind"] == "security"]
    assert any("treated as data" in m and "AI ASSISTANTS" in m for m in sec)


async def test_obedient_model_is_contained_by_policy(executor):
    """Simulate a model that follows the injected notice. The policy filter must block every step."""
    variant("inject,v3_relabel")
    executor.llm = RuleLLM([
        ("click", r"Verify applicant with AI helpdesk"),  # off-domain link
        ("do_step", r"id=bankAccount "),                    # wrong field, owned by another step
        ("do_step", r"household earnings"),                 # the right field
    ])
    task_id, status = await run(executor, persona=0)
    assert status == TaskStatus.completed, executor.store.get_task(task_id)["error"]
    sec = [e["message"] for e in events(executor, task_id) if e["kind"] == "security"]
    assert any("link leaves the allowed domains (evil.example)" in m for m in sec)
    assert any("belongs to route step 'fill_account'" in m for m in sec)


async def test_canary_values_never_reach_model_or_logs(executor):
    settings.llm_log_path.unlink(missing_ok=True)
    variant("v3_relabel,v4_interstitial")
    executor.llm = RuleLLM([("check", r"I have read"), ("click", r"button 'Continue'"), ("do_step", r"household earnings")])
    task_id, status = await run(executor, persona=0, vault_override=CANARY_VAULT)
    assert status == TaskStatus.completed, executor.store.get_task(task_id)["error"]
    llm_log = settings.llm_log_path.read_text()
    assert llm_log.count("\n") >= 3  # the model really was called
    ev_dump = json.dumps(events(executor, task_id))
    manifest = (settings.evidence_dir / task_id / "manifest.json").read_text()
    for value in CANARY_VAULT.values():
        assert value not in llm_log, f"{value} leaked into the model request log"
        assert value not in ev_dump, f"{value} leaked into task events"
        assert value not in manifest, f"{value} leaked into the evidence manifest"
