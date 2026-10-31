"""HTTP API for Part 3.

Service API (/v1, X-API-Key):   tasks, events (SSE), consents, profiles, vault, documents, receipts
Citizen API (/citizen, token):  approval card, live view, human-step controls

Run: uv run uvicorn executor.api:app --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .config import settings
from .db import Store
from .console import make_console_router
from .public_app import make_router, mount_spa, spa_index
from .models import TERMINAL_STATUSES, ApplicationTask, CitizenProfile, ConsentRecord, Receipt, TaskStatus, TaskView
from .receipts import verify
from .vault import VaultError
from .worker import Executor
from server.api import router as unified_civic_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
STATIC = Path(__file__).parent / "static"


# Request bodies live at module level: FastAPI cannot resolve classes defined inside
# make_app() when annotations are postponed.
class VaultIn(BaseModel):
    fields: dict[str, str]
    ttl_s: int | None = None


class KillSwitch(BaseModel):
    on: bool


class Decision(BaseModel):
    decision: str


class SandboxVariant(BaseModel):
    variant: str = Field(pattern=r"^(default|v2_renamed|v3_relabel|v4_interstitial|inject)(,(v2_renamed|v3_relabel|v4_interstitial|inject))*$")


def make_app(executor_factory=None) -> FastAPI:
    state: dict = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.ensure_dirs()
        store = Store(settings.db_path)
        executor = executor_factory(store) if executor_factory else Executor(store)
        await executor.start()
        state["executor"] = executor
        app.state.executor = executor
        yield
        await executor.stop()

    app = FastAPI(title="Civic Pulse Part 3: Execution Agent", version="0.1.0", lifespan=lifespan)

    def ex() -> Executor:
        return state["executor"]

    app.include_router(unified_civic_router)
    app.include_router(make_router(ex))
    app.include_router(make_console_router(ex))

    def require_key(x_api_key: str | None = Header(None)) -> None:
        if settings.api_key and x_api_key != settings.api_key:
            raise HTTPException(401, "missing or wrong X-API-Key")

    def citizen(task_id: str, t: str = Query(...)):
        row = ex().store.get_task(task_id)
        if not row or row["citizen_token"] != t:
            raise HTTPException(404, "not found")
        return row

    # Endpoints are async so they run on the event loop that owns the executor,
    # the approval futures and the human-step events.
    # ------------------------------------------------------------------ service API
    @app.get("/health")
    async def health():
        key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("AIMLAPI_KEY"))
        llm = ex().llm
        return {"ok": True, "kill_switch": ex().store.get_flag("kill_switch", False), "llm": bool(llm), "llm_key_present": key,
                "llm_provider": getattr(llm, "provider", None), "llm_model": getattr(llm, "model", None)}

    @app.get("/v1/registry", dependencies=[Depends(require_key)])
    async def registry():
        return ex().registry.list()

    @app.post("/v1/profiles", dependencies=[Depends(require_key)])
    async def put_profile(p: CitizenProfile):
        ex().store.put_profile(p.model_dump(mode="json"))
        return {"ok": True}

    @app.post("/v1/consents", dependencies=[Depends(require_key)])
    async def put_consent(c: ConsentRecord):
        ex().store.put_consent(c.model_dump(mode="json"))
        return {"ok": True, "consent_id": c.consent_id}

    @app.post("/v1/consents/{consent_id}/revoke", dependencies=[Depends(require_key)])
    async def revoke_consent(consent_id: str):
        c = ex().store.get_consent(consent_id)
        if not c:
            raise HTTPException(404, "no such consent")
        c["revoked"] = True
        ex().store.put_consent(c)
        return {"ok": True}

    @app.post("/v1/vault", dependencies=[Depends(require_key)])
    async def put_vault(body: VaultIn):
        try:
            return {"vault_ref": ex().vault.put(body.fields, body.ttl_s)}
        except VaultError as e:
            raise HTTPException(400, str(e))

    @app.delete("/v1/vault/{ref}", dependencies=[Depends(require_key)])
    async def delete_vault(ref: str):
        ex().vault.delete(ref)
        return {"ok": True}

    @app.post("/v1/documents", dependencies=[Depends(require_key)])
    async def upload_document(file: UploadFile = File(...)):
        data = await file.read()
        if len(data) > 20 * 1024 * 1024:
            raise HTTPException(413, "max 20 MB")
        doc_id = uuid.uuid4().hex[:16]
        suffix = Path(file.filename or "").suffix.lower()[:6]
        path = settings.uploads_dir / f"{doc_id}{suffix}"
        path.write_bytes(data)
        ex().store.put_document(doc_id, str(path), file.content_type)
        return {"uri": f"doc://{doc_id}", "size_kb": round(len(data) / 1024, 1)}

    @app.post("/v1/tasks", status_code=201, dependencies=[Depends(require_key)])
    async def create_task(task: ApplicationTask, idempotency_key: str | None = Header(None)):
        if idempotency_key:
            task = task.model_copy(update={"idempotency_key": idempotency_key})
        task_id, created = ex().submit(task)
        body = {
            "task_id": task_id,
            "created": created,
            "status": ex().store.get_task(task_id)["status"],
            "events_url": f"/v1/tasks/{task_id}/events",
            "citizen_url": ex().citizen_url(task_id),
        }
        return JSONResponse(body, status_code=201 if created else 200)

    @app.get("/v1/tasks/{task_id}", response_model=TaskView, dependencies=[Depends(require_key)])
    async def get_task(task_id: str):
        row = ex().store.get_task(task_id)
        if not row:
            raise HTTPException(404, "no such task")
        receipt = ex().store.get_receipt(row["receipt_id"]) if row["receipt_id"] else None
        return TaskView(
            task_id=task_id, status=row["status"], task=ApplicationTask.model_validate_json(row["task_json"]),
            created_at=row["created_at"], updated_at=row["updated_at"], error=row["error"],
            receipt=Receipt(**receipt) if receipt else None, citizen_url=ex().citizen_url(task_id),
        )

    @app.get("/v1/tasks/{task_id}/events", dependencies=[Depends(require_key)])
    async def task_events(task_id: str, request: Request, last_event_id: str | None = Header(None)):
        if not ex().store.get_task(task_id):
            raise HTTPException(404, "no such task")
        return StreamingResponse(_sse(task_id, request, int(last_event_id or 0)), media_type="text/event-stream")

    async def _sse(task_id: str, request: Request, after: int):
        q = ex().bus.subscribe(task_id)
        try:
            last = after
            for ev in ex().store.events_after(task_id, after):
                last = ev["seq"]
                yield f"id: {ev['seq']}\nevent: {ev['kind']}\ndata: {json.dumps(ev)}\n\n"
            while not await request.is_disconnected():
                status = ex().store.get_task(task_id)["status"]
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=10)
                except asyncio.TimeoutError:
                    if TaskStatus(status) in TERMINAL_STATUSES:
                        break
                    yield ": keep-alive\n\n"
                    continue
                if ev["seq"] <= last:
                    continue
                last = ev["seq"]
                yield f"id: {ev['seq']}\nevent: {ev['kind']}\ndata: {json.dumps(ev)}\n\n"
        finally:
            ex().bus.unsubscribe(task_id, q)

    @app.get("/v1/receipts/public-key")
    async def public_key():
        return {"key_id": ex().signer.key_id, "ed25519_public_key_b64": ex().signer.public_key_b64, "pem": ex().signer.public_pem()}

    @app.get("/v1/receipts/{receipt_id}", dependencies=[Depends(require_key)])
    async def get_receipt(receipt_id: str):
        r = ex().store.get_receipt(receipt_id)
        if not r:
            raise HTTPException(404, "no such receipt")
        return r

    @app.post("/v1/receipts/verify")
    async def verify_receipt(receipt: Receipt):
        valid = receipt.signer_key_id == ex().signer.key_id and verify(receipt, ex().signer.public_key_b64)
        return {"valid": valid, "meaning": "The receipt is unchanged since Civic Pulse issued it. It does not prove the portal accepted the application."}

    @app.post("/v1/admin/sandbox-variant", dependencies=[Depends(require_key)])
    async def sandbox_variant(body: SandboxVariant):
        """Demo control: change the sandbox's layout (portal changed overnight) or add an injected notice."""
        import httpx

        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.post(settings.sandbox_url + "/__admin/config", json={"variant": body.variant})
        return r.json()

    @app.post("/v1/admin/kill-switch", dependencies=[Depends(require_key)])
    async def kill_switch(body: KillSwitch):
        ex().store.set_flag("kill_switch", body.on)
        return {"kill_switch": body.on}

    # ------------------------------------------------------------------ citizen API
    @app.get("/citizen/{task_id}", response_class=HTMLResponse)
    async def citizen_page(row=Depends(citizen)):
        return spa_index()

    @app.get("/citizen/{task_id}/state")
    async def citizen_state(task_id: str, row=Depends(citizen)):
        ch = ex().gateway.channels.get(task_id)
        events = ex().store.events_after(task_id, 0)
        timing = events[-1]["timing"] if events else {}
        card = None
        for ev in reversed(events):
            if ev["kind"] == "approval_needed":
                card = ev["data"].get("card")
                break
        receipt_id = ex().store.get_task(task_id)["receipt_id"]
        task = json.loads(row["task_json"])
        try:
            portal = ex().registry.portal(task["portal_id"])
            portal_info = {"id": portal.portal_id, "name": portal.name, "is_sandbox": portal.is_sandbox}
        except Exception:
            portal_info = {"id": task["portal_id"], "name": task["portal_id"], "is_sandbox": False}
        return {
            "status": row["status"],
            "error": row["error"],
            "portal": portal_info,
            "service": task["service_id"],
            "reasoning": [
                {"kind": e["kind"], "message": e["message"], "actions": e["data"].get("actions"), "turn": e["data"].get("turn")}
                for e in events if e["kind"] in {"reasoning", "heal", "security"}
            ][-40:],
            "human": {"kind": ch.human.kind, "instructions": ch.human.instructions} if ch and ch.human else None,
            "approval_pending": bool(ch and ch.approval),
            "card": card,
            "timing": timing,
            "receipt": ex().store.get_receipt(receipt_id) if receipt_id else None,
            "log": [{"kind": e["kind"], "message": e["message"], "step_id": e["step_id"]} for e in events[-30:]],
            "task_id": task_id,
            "mode": task.get("mode"),
            "strategy": task.get("strategy", "auto"),
            "created_at": row["created_at"],
            "page_url": ch.page.url if ch and ch.page and not ch.page.is_closed() else None,
            "has_final": (settings.evidence_dir / task_id / "final.png").exists(),
            "events": [
                {"seq": e["seq"], "kind": e["kind"], "status": e["status"], "message": e["message"], "step_id": e["step_id"], "at": e["at"],
                 "data": {k: v for k, v in e["data"].items() if k in {"do", "label", "value", "host", "kind", "actions", "turn", "status", "model_ms", "result"}}}
                for e in events
            ],
        }

    @app.post("/citizen/{task_id}/approve")
    async def citizen_approve(task_id: str, body: Decision, row=Depends(citizen)):
        if not ex().gateway.decide(task_id, body.decision):
            raise HTTPException(409, "no approval is pending")
        return {"ok": True}

    @app.post("/citizen/{task_id}/human/done")
    async def citizen_done(task_id: str, row=Depends(citizen)):
        if not ex().gateway.human_done(task_id):
            raise HTTPException(409, "no human step is pending")
        return {"ok": True}

    @app.post("/citizen/{task_id}/human/cancel")
    async def citizen_cancel(task_id: str, row=Depends(citizen)):
        if not ex().gateway.human_cancel(task_id):
            raise HTTPException(409, "no human step is pending")
        return {"ok": True}

    @app.get("/citizen/{task_id}/final.png")
    async def citizen_final(task_id: str, row=Depends(citizen)):
        path = settings.evidence_dir / task_id / "final.png"
        if not path.exists():
            raise HTTPException(404, "no screenshot")
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.get("/citizen/{task_id}/approval.png")
    async def citizen_screenshot(task_id: str, row=Depends(citizen)):
        path = settings.evidence_dir / task_id / "approval.png"
        if not path.exists():
            raise HTTPException(404, "no screenshot")
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.websocket("/citizen/{task_id}/live")
    async def citizen_live(ws: WebSocket, task_id: str, t: str = Query(...)):
        if not ex().gateway.check_token(task_id, t):
            await ws.close(code=4404)
            return
        await ws.accept()
        live = await ex().gateway.live(task_id)
        if not live:
            await ws.close(code=4409)
            return
        q: asyncio.Queue = asyncio.Queue(maxsize=2)
        live.subscribers.add(q)
        if live.last_frame:
            q.put_nowait(live.last_frame)

        async def pump_frames():
            while True:
                frame = await q.get()
                await ws.send_text(json.dumps({"frame": frame["data"], "w": frame["w"], "h": frame["h"], "input": ex().gateway.input_allowed(task_id)}))

        sender = asyncio.create_task(pump_frames())
        try:
            while True:
                msg = json.loads(await ws.receive_text())
                if not ex().gateway.input_allowed(task_id):
                    continue  # view only outside human steps
                current = await ex().gateway.live(task_id)
                if current is not live and current:  # page changed (new tab): follow it
                    live.subscribers.discard(q)
                    live = current
                    live.subscribers.add(q)
                await live.dispatch(msg)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            sender.cancel()
            live.subscribers.discard(q)

    mount_spa(app)  # last: the React app's catch-all routes
    return app


app = make_app()
