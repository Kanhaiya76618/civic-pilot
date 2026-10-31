"""Policy gate, document prep and vault, without a browser."""

import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PIL import Image

from executor.docprep import DocError, prepare
from executor.models import TaskMode, TaskStatus
from executor.policy import PolicyError
from executor.registry import DocDef, Registry
from executor.vault import VaultError
from harness.seed import seed_task


def gate(ex):
    return ex.policy


async def test_policy_accepts_seeded_task(executor):
    portal, route, task = gate(executor).check(seed_task(executor))
    assert portal.portal_id == "sandbox" and route.status == "stable"


@pytest.mark.parametrize("change,needle", [
    (lambda t: t.model_copy(update={"consent_id": "nope"}), "no consent"),
    (lambda t: t.model_copy(update={"inputs": {**t.inputs, "aadhaar": "1234"}}), "not declared"),
    (lambda t: t.model_copy(update={"inputs": {**t.inputs, "dob": "14/03/2006"}}), "expected format"),
    (lambda t: t.model_copy(update={"inputs": {**t.inputs, "gender": "X"}}), "must be one of"),
    (lambda t: t.model_copy(update={"inputs": {k: v for k, v in t.inputs.items() if k != "full_name"}}), "missing input"),
    (lambda t: t.model_copy(update={"documents": []}), "missing documents"),
    (lambda t: t.model_copy(update={"vault_ref": None}), "no vault_ref"),
    (lambda t: t.model_copy(update={"service_id": "public_grievance"}), "does not cover"),
])
async def test_policy_refusals(executor, change, needle):
    with pytest.raises(PolicyError, match=needle):
        gate(executor).check(change(seed_task(executor)))


async def test_policy_expired_consent(executor):
    task = seed_task(executor)
    c = executor.store.get_consent(task.consent_id)
    c["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    executor.store.put_consent(c)
    with pytest.raises(PolicyError, match="expired"):
        gate(executor).check(task)


async def test_policy_refuses_draft_and_disabled_portals(executor):
    task = seed_task(executor)
    c = executor.store.get_consent(task.consent_id)
    c["portal_ids"] += ["cpgrams"]
    c["service_ids"] += ["lodge_grievance"]
    executor.store.put_consent(c)
    with pytest.raises(PolicyError, match="draft"):
        gate(executor).check(task.model_copy(update={"portal_id": "cpgrams", "service_id": "lodge_grievance", "inputs": {}}))


async def test_free_text_is_cleaned(executor):
    task = seed_task(executor, service="public_grievance")
    task = task.model_copy(update={"inputs": {**task.inputs, "subject": "Pothole​ near\x07 school"}})
    _, _, clean = gate(executor).check(task)
    assert clean.inputs["subject"] == "Pothole near school"


async def test_kill_switch_blocks_tasks(executor):
    from harness.sim_human import SimHuman
    from .conftest import SANDBOX_URL
    executor.store.set_flag("kill_switch", True)
    task_id, _ = executor.submit(seed_task(executor, mode=TaskMode.dry_run))
    status = await SimHuman(executor, SANDBOX_URL).drive(task_id, timeout_s=20)
    assert status == TaskStatus.failed and "kill switch" in executor.store.get_task(task_id)["error"]


def test_vault_refuses_aadhaar(executor):
    with pytest.raises(VaultError):
        executor.vault.put({"aadhaar_number": "123412341234"})


def test_registry_lists_routes():
    services = {(r["portal_id"], r["service_id"]): r for r in Registry().list()}
    assert services[("sandbox", "scholarship_postmatric")]["status"] == "stable"
    assert services[("cpgrams", "lodge_grievance")]["status"] == "draft"
    assert Registry().route("cpgrams", "lodge_grievance").unresolved_recon()


def _jpeg(path: Path, size=(3000, 2000)) -> Path:
    img = Image.effect_noise(size, 60).convert("RGB")
    img.save(path, "JPEG", quality=95)
    return path


def test_docprep_shrinks_image_to_limit(tmp_path):
    src = _jpeg(tmp_path / "big.jpg")
    out = prepare(src, DocDef(key="photo", max_kb=50, formats=["jpg"], max_px=600), tmp_path / "out")
    assert out.path.stat().st_size <= 50 * 1024
    assert max(Image.open(out.path).size) <= 600


def test_docprep_converts_png(tmp_path):
    p = tmp_path / "a.png"
    Image.new("RGB", (800, 800), (10, 120, 200)).save(p)
    out = prepare(p, DocDef(key="photo", max_kb=50, formats=["jpg"]), tmp_path / "out")
    assert out.path.suffix == ".jpg"


def test_docprep_rejects_big_pdf(tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF-1.4\n" + b"0" * 300 * 1024)
    with pytest.raises(DocError, match="smaller scan"):
        prepare(p, DocDef(key="income_certificate", max_kb=200, formats=["pdf", "jpg"]), tmp_path / "out")


async def test_live_check_refuses_unknown_ifsc(executor):
    from harness.sim_human import SimHuman
    from .conftest import SANDBOX_URL
    task = seed_task(executor, mode=TaskMode.dry_run)
    task = task.model_copy(update={"inputs": {**task.inputs, "ifsc": "ABCD0000000"}})
    task_id, _ = executor.submit(task)
    status = await SimHuman(executor, SANDBOX_URL).drive(task_id, timeout_s=20)
    row = executor.store.get_task(task_id)
    assert status == TaskStatus.failed and "IFSC ABCD0000000 does not exist" in row["error"]


async def test_live_check_flags_pincode_state_mismatch(executor):
    task = seed_task(executor, persona=1, service="public_grievance")  # Tamil Nadu
    task = task.model_copy(update={"inputs": {**task.inputs, "pincode": "823001"}})  # fake API says Bihar
    portal, route, clean = executor.policy.check(task)
    notes = await executor.policy.verify_live(clean, route)
    assert any("PIN code verified live" in n for n in notes)
    assert any("is in Bihar, but the application says Tamil Nadu" in n for n in notes)


async def test_live_check_degrades_when_api_is_down(executor):
    import httpx
    from executor import enrich

    def down(request):
        raise httpx.ConnectError("no route to host")
    enrich.transport = httpx.MockTransport(down)
    task = seed_task(executor)
    _, route, clean = executor.policy.check(task)
    notes = await executor.policy.verify_live(clean, route)
    assert any("Could not verify IFSC right now" in n for n in notes)
