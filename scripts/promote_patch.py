"""Review and promote a healer patch.

  uv run python scripts/promote_patch.py registry/sandbox/patches/<file>.route.yaml

Shows the diff against the stable route, replays the patch 3 times as dry runs
on the sandbox portal in fresh sessions, and only then (after you type 'yes')
replaces the stable route. Live portals are never promoted from here: review the
diff by hand and commit it yourself.
"""

from __future__ import annotations

import asyncio
import difflib
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CIVIC_DATA_DIR", tempfile.mkdtemp(prefix="civic-promote-"))
os.environ.setdefault("EVAL_SANDBOX_PORT", "8188")
os.environ["SANDBOX_URL"] = f"http://127.0.0.1:{os.environ['EVAL_SANDBOX_PORT']}"
os.environ["SANDBOX_TEST_MODE"] = "1"
os.environ["CIVIC_LLM_ENABLED"] = "0"

import yaml  # noqa: E402

from executor.models import TaskMode, TaskStatus  # noqa: E402
from executor.registry import Registry, Route  # noqa: E402


async def replay(patch: Route, times: int = 3) -> list[str]:
    import shutil

    import scripts.eval as ev  # reuses the sandbox server and simulated citizen
    from executor.config import settings
    from executor.db import Store
    from executor.worker import Executor
    from harness.seed import seed_task
    from harness.sim_human import SimHuman

    reg_dir = Path(tempfile.mkdtemp(prefix="civic-reg-"))
    shutil.copytree(ROOT / "registry", reg_dir, dirs_exist_ok=True)
    (reg_dir / patch.portal_id / f"{patch.service_id}.route.yaml").write_text(
        yaml.safe_dump(patch.model_copy(update={"status": "stable"}).model_dump(mode="json", exclude_none=True), sort_keys=False)
    )
    ev.start_sandbox()
    settings.ensure_dirs()
    ex = Executor(Store(settings.db_path), registry=Registry(reg_dir))
    await ex.start()
    out = []
    try:
        for i in range(times):
            task = seed_task(ex, persona=i % 3, service=patch.service_id, mode=TaskMode.dry_run)
            task_id, _ = ex.submit(task)
            status = await SimHuman(ex, ev.SANDBOX).drive(task_id)
            out.append(status.value)
            print(f"replay {i + 1}: {status.value} {ex.store.get_task(task_id)['error'] or ''}")
    finally:
        await ex.stop()
    return out


def main(path: str) -> None:
    patch = Route(**yaml.safe_load(Path(path).read_text()))
    reg = Registry()
    portal = reg.portal(patch.portal_id)
    stable_path = reg.route_path(patch.portal_id, patch.service_id)
    # Compare both through the same serializer so only real changes show up.
    old = yaml.safe_dump(reg.route(patch.portal_id, patch.service_id).model_dump(mode="json", exclude_none=True), sort_keys=False).splitlines()
    new = yaml.safe_dump(patch.model_dump(mode="json", exclude_none=True), sort_keys=False).splitlines()
    print("\n".join(difflib.unified_diff(old, new, "stable", "patch", lineterm="")))
    if not portal.is_sandbox:
        print("\nLive portal: not promoting automatically. Review the diff, dry-run it on the live portal, and commit by hand.")
        return
    results = asyncio.run(replay(patch))
    if results != [TaskStatus.completed.value] * 3:
        print("\nPatch did not pass 3 clean replays; not promoted.")
        return
    if input("\n3/3 replays passed. Promote to stable? Type 'yes': ").strip() != "yes":
        return
    promoted = patch.model_copy(update={"status": "stable", "verified_runs": 3})
    stable_path.write_text(yaml.safe_dump(promoted.model_dump(mode="json", exclude_none=True), sort_keys=False))
    print(f"Promoted. Review and commit {stable_path.relative_to(ROOT)}.")


if __name__ == "__main__":
    main(sys.argv[1])
