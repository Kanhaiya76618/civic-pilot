"""The executor: claims queued tasks and drives each one through its lifecycle.

queued -> validating -> preparing_docs -> running -> awaiting_human (repeats)
-> awaiting_approval -> submitting -> verifying -> completed
Side exits: failed, needs_review.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import shutil
import traceback
import uuid
from pathlib import Path

import httpx
from playwright.async_api import Browser, Playwright, async_playwright

from .config import settings
from .db import Store
from .docprep import DocError, PreparedDoc, prepare
from .events import EventBus
from .handoff import Gateway
from .engines import repair_engine
from .llm import LLM, default_llm
from .models import ApplicationTask, EvidenceItem, Receipt, TaskEvent, TaskMode, TaskStatus, utcnow
from .policy import PolicyError, PolicyGate
from .receipts import Signer, sha256_file
from .registry import DocDef, Registry
from .runner import RouteRunner, Stop
from .vault import EmptyVault, Vault, VaultError

log = logging.getLogger("civic.worker")


class Executor:
    def __init__(self, store: Store, llm: LLM | None = None, registry: Registry | None = None):
        settings.ensure_dirs()
        self.store = store
        self.registry = registry or Registry()
        self.vault = Vault(store)
        self.bus = EventBus(store)
        self.gateway = Gateway()
        self.signer = Signer()
        self.policy = PolicyGate(store, self.registry, self.vault)
        self.llm = llm if llm is not None else default_llm()
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._running: set[asyncio.Task] = set()
        self._loop_task: asyncio.Task | None = None
        self._stopping = False
        self.last_patch: dict[str, str] = {}

    # lifecycle ---------------------------------------------------------------
    async def start(self) -> None:
        for tid in self.store.requeue_interrupted():
            log.warning("task %s was interrupted by a restart; marked needs_review", tid)
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=settings.headless)
        self._loop_task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopping = True
        if self._loop_task:
            self._loop_task.cancel()
        for t in list(self._running):
            t.cancel()
        await asyncio.gather(*self._running, return_exceptions=True)
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def _loop(self) -> None:
        while not self._stopping:
            self.store.purge_expired_vault()
            row = self.store.claim_next_queued()
            if not row:
                await asyncio.sleep(0.3)
                continue
            t = asyncio.create_task(self._run_task(row["task_id"]))
            self._running.add(t)
            t.add_done_callback(self._running.discard)

    # submission ----------------------------------------------------------------
    def submit(self, task: ApplicationTask) -> tuple[str, bool]:
        """Queue a task. Returns (task_id, created). Same idempotency key -> same task."""
        existing = self.store.task_by_idem(task.idempotency_key)
        if existing:
            return existing["task_id"], False
        task_id = "task_" + uuid.uuid4().hex[:16]
        if not self.store.insert_task(task_id, task.idempotency_key, task.model_dump(mode="json"), secrets.token_urlsafe(24)):
            return self.store.task_by_idem(task.idempotency_key)["task_id"], False
        self.bus.set_callback(task_id, task.callback_url)
        self.publish(TaskEvent(task_id=task_id, status=TaskStatus.queued, message="queued"))
        return task_id, True

    def publish(self, event: TaskEvent) -> TaskEvent:
        return self.bus.publish(event)

    def citizen_url(self, task_id: str) -> str:
        row = self.store.get_task(task_id)
        return f"{settings.public_url}/citizen/{task_id}?t={row['citizen_token']}"

    def _status(self, task_id: str, status: TaskStatus, message: str, error: str | None = None, data: dict | None = None) -> None:
        self.store.set_status(task_id, status.value, error)
        self.publish(TaskEvent(task_id=task_id, status=status, kind="error" if error else "status", message=message, data=data or {}))

    # documents -----------------------------------------------------------------
    async def _fetch_doc(self, uri: str, dest: Path) -> Path:
        if uri.startswith("doc://"):
            row = self.store.get_document(uri[len("doc://"):])
            if not row:
                raise DocError(f"unknown document {uri}")
            path = Path(row["path"]).resolve()
            if settings.uploads_dir.resolve() not in path.parents:
                raise DocError("document path is outside the uploads folder")
            return path
        if uri.startswith("https://") or uri.startswith("http://127.0.0.1") or uri.startswith("http://localhost"):
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                r = await client.get(uri)
                r.raise_for_status()
                if len(r.content) > 20 * 1024 * 1024:
                    raise DocError("document larger than 20 MB")
                dest.write_bytes(r.content)
            return dest
        raise DocError("document uri must be doc://<id> or https://")

    async def _prepare_docs(self, task_id: str, task: ApplicationTask, rules: list[DocDef], work: Path) -> dict[str, PreparedDoc]:
        by_key = {d.key: d for d in rules}
        out: dict[str, PreparedDoc] = {}
        for ref in task.documents:
            src = await self._fetch_doc(ref.uri, work / f"src_{ref.key}")
            prepared = prepare(src, by_key[ref.key], work / "prepared")
            out[ref.key] = prepared
            self.publish(TaskEvent(task_id=task_id, status=TaskStatus.preparing_docs, kind="info", message=f"{ref.key}: {prepared.note} ({prepared.size_kb:.0f} KB, limit {by_key[ref.key].max_kb} KB)"))
        return out

    # run -----------------------------------------------------------------------
    async def _run_task(self, task_id: str) -> None:
        row = self.store.get_task(task_id)
        task = ApplicationTask.model_validate_json(row["task_json"])
        self.bus.set_callback(task_id, task.callback_url)
        evidence = settings.evidence_dir / task_id
        evidence.mkdir(parents=True, exist_ok=True)
        work = settings.data_dir / "work" / task_id
        work.mkdir(parents=True, exist_ok=True)
        self.gateway.open(task_id, row["citizen_token"])
        sem = None
        context = None
        runner: RouteRunner | None = None
        try:
            self._status(task_id, TaskStatus.validating, "Checking consent, registry and inputs")
            try:
                portal, route, task = self.policy.check(task)
            except PolicyError as e:
                self._status(task_id, TaskStatus.failed, f"Policy gate refused: {e}", error=str(e))
                return
            try:
                for note in await self.policy.verify_live(task, route):
                    self.publish(TaskEvent(task_id=task_id, status=TaskStatus.validating, kind="info", message=note))
            except PolicyError as e:
                self._status(task_id, TaskStatus.failed, f"Input check failed: {e}", error=str(e))
                return

            self._status(task_id, TaskStatus.preparing_docs, "Preparing documents")
            try:
                docs = await self._prepare_docs(task_id, task, route.documents, work)
            except (DocError, httpx.HTTPError) as e:
                self._status(task_id, TaskStatus.failed, f"Document problem: {e}", error=str(e))
                return
            try:
                vault = self.vault.open(task.vault_ref) if task.vault_ref else EmptyVault()
            except VaultError as e:
                self._status(task_id, TaskStatus.failed, str(e), error=str(e))
                return

            sem = await self.policy.acquire(portal)
            context = await self._browser.new_context(
                viewport={"width": 1280, "height": 900}, locale="en-IN", accept_downloads=False
            )
            tracing = portal.is_sandbox or settings.trace_live_portals
            if tracing:
                await context.tracing.start(screenshots=True, snapshots=True)
            page = await context.new_page()
            runner = RouteRunner(
                task_id=task_id, task=task, portal=portal, route=route, context=context, page=page,
                vault=vault, docs=docs, gateway=self.gateway, publish=self.publish, store=self.store,
                healer=repair_engine(self.llm), evidence_dir=evidence, citizen_url=self.citizen_url(task_id),
                profile=self.store.get_profile(task.citizen_id),
            )
            try:
                await runner.run()
                receipt = self._issue_receipt(task_id, task, runner)
                self._save_patch(runner)
                status = TaskStatus.completed
                msg = {
                    "submitted": f"Submitted. Reference number: {receipt.reference_no or 'not captured'}",
                    "information_retrieved": f"Done. Read {len((receipt.result or {}).get('items', []))} results from {portal.name}",
                }.get(receipt.outcome, "Dry run complete: reached the final review page without submitting")
                self.store.set_status(task_id, status.value)
                self.publish(TaskEvent(task_id=task_id, status=status, kind="receipt", message=msg, data={"receipt": receipt.model_dump(mode="json")}, timing=runner.clock.timing()))
            except Stop as s:
                self._save_patch(runner)
                self.store.set_status(task_id, s.status.value, s.reason)
                self.publish(TaskEvent(task_id=task_id, status=s.status, kind="error", message=vault.redact(s.reason), timing=runner.clock.timing()))
            finally:
                if tracing:
                    await context.tracing.stop(path=str(settings.traces_dir / f"{task_id}.zip"))
        except asyncio.CancelledError:
            self.store.set_status(task_id, TaskStatus.needs_review.value, "executor stopped mid-run")
            raise
        except Exception as e:  # never leave a task hanging
            log.error("task %s crashed: %s", task_id, traceback.format_exc())
            self._status(task_id, TaskStatus.needs_review, f"Unexpected executor error: {type(e).__name__}: {e}"[:300], error=str(e)[:300])
        finally:
            if context:
                await context.close()
            if sem:
                sem.release()
            await self.gateway.close(task_id)
            shutil.rmtree(work, ignore_errors=True)

    def _save_draft(self, runner: RouteRunner) -> None:
        """An AI-explored run becomes a draft route: replay it, review it, then promote it."""
        if not runner.state.patch_ok:
            runner.emit("heal", "The AI run worked, but some elements had no stable locator; no draft route saved.")
            return
        draft = runner.route.model_copy(update={"steps": runner.steps, "status": "draft", "version": runner.route.version + 1,
                                                "patched_from": runner.route.version, "verified_runs": 0})
        path = self.registry.save_patch(draft, f"Recorded from AI exploration in task {runner.task_id}", folder="drafts", tag=".explored")
        self.last_patch[runner.task_id] = str(path)
        runner.emit("heal", f"Saved the AI's run as a draft route ({len(runner.steps)} steps): {path.name}. "
                            "After review, the next run replays it with zero model calls.", data={"draft": str(path)})

    def _save_patch(self, runner: RouteRunner | None) -> None:
        if runner and runner.state.explored and runner.state.outcome:
            self._save_draft(runner)
            return
        if not runner or not runner.state.patched:
            return
        if not runner.state.patch_ok:
            runner.emit("heal", "Repair worked for this run, but no stable locator was found for every action; no patch saved.")
            return
        path = self.registry.save_patch(runner.patched_route(), f"Patch from task {runner.task_id}: {[h['step_id'] for h in runner.state.heals if h['ok']]}")
        self.last_patch[runner.task_id] = str(path)
        runner.emit("heal", f"Route patch saved as candidate: {path.name}. Replay it 3 times, review the diff, then promote.", data={"patch": str(path)})

    def _issue_receipt(self, task_id: str, task: ApplicationTask, runner: RouteRunner) -> Receipt:
        evidence = [EvidenceItem(name=name, sha256=sha256_file(path)) for name, path in sorted(runner.state.evidence.items())]
        receipt = Receipt(
            receipt_id="rcpt_" + uuid.uuid4().hex[:16],
            task_id=task_id,
            portal_id=task.portal_id,
            service_id=task.service_id,
            mode=task.mode,
            outcome=runner.state.outcome or "dry_run_complete",
            reference_no=runner.state.captured.get("reference_no"),
            submitted_at=utcnow(),
            approved_by="citizen" if runner.state.approved else None,
            evidence=evidence,
            tracking=dict(runner.route.tracking),
            origin_ref=task.origin_ref,
            timing=runner.clock.timing(),
            result=runner.state.result,
        )
        if runner.route.read_only and not runner.state.result:
            raise Stop(TaskStatus.needs_review, "the lookup finished but no results could be read from the portal")
        if task.mode == TaskMode.assist and not runner.route.read_only and runner.state.outcome != "submitted":
            raise Stop(TaskStatus.needs_review, "route finished without a confirmed submission")
        self.signer.sign(receipt)
        data = receipt.model_dump(mode="json")
        self.store.put_receipt(data)
        self.store.set_receipt(task_id, receipt.receipt_id)
        self.bus.post_receipt(task_id, data)
        return receipt
