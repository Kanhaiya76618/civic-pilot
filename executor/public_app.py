"""Public citizen console: the hosted front door.

A citizen picks a service, types their own details (checked live against India
Post and RBI IFSC data), gives explicit consent, and is taken to their live
task page. No API key is needed, so this is limited to portals marked
public_demo and rate-limited per IP. The recent-runs board shows timing and
outcome only, never personal data.
"""

from __future__ import annotations

import json
import secrets
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import httpx
from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from . import enrich
from .config import settings
from .models import ApplicationTask, CitizenProfile, ConsentRecord, DocumentRef
from .registry import RegistryError

STATIC = Path(__file__).parent / "static"


def make_router(ex: Callable) -> APIRouter:
    r = APIRouter()
    starts: dict[str, deque] = defaultdict(deque)

    def limit(request: Request) -> None:
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
        q = starts[ip]
        now = time.time()
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= settings.public_starts_per_hour:
            raise HTTPException(429, "Too many applications from this address in the last hour")
        q.append(now)

    @r.get("/", response_class=HTMLResponse)
    async def console():
        return (STATIC / "console.html").read_text()

    @r.get("/app/services")
    async def services():
        return [s for s in ex().registry.list() if s["public_demo"] and s["status"] in {"stable", "candidate"}]

    @r.get("/app/lookup/pincode/{pin}")
    async def lookup_pincode(pin: str):
        res = await enrich.pincode(pin)
        return {"ok": res.ok, "source": res.source, "data": res.data, "error": res.error}

    @r.get("/app/lookup/ifsc/{code}")
    async def lookup_ifsc(code: str):
        res = await enrich.ifsc(code)
        return {"ok": res.ok, "source": res.source, "data": res.data, "error": res.error}

    @r.get("/app/runs")
    async def runs():
        out = []
        for row in ex().store.recent_tasks(25):
            task = json.loads(row["task_json"])
            last = ex().store.last_event(row["task_id"]) or {}
            receipt = ex().store.get_receipt(row["receipt_id"]) if row["receipt_id"] else None
            out.append({
                "service": f"{task['portal_id']}/{task['service_id']}",
                "strategy": task.get("strategy", "auto"),
                "status": row["status"],
                "outcome": receipt and receipt["outcome"],
                "results": receipt and receipt.get("result") and receipt["result"].get("count"),
                "timing": last.get("timing", {}),
                "created_at": row["created_at"],
            })
        return out

    @r.get("/app/sandbox/sms")
    async def sandbox_sms():
        """The sandbox's 'phone'. In a deployment the sandbox is internal, so its SMS inbox is relayed here."""
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                return (await c.get(settings.sandbox_url + "/__sms")).json()
        except httpx.HTTPError:
            raise HTTPException(503, "sandbox is not running")

    @r.post("/app/start")
    async def start(request: Request, payload: str = Form(...), files: list[UploadFile] | None = None):
        limit(request)
        try:
            body = json.loads(payload)
            portal_id, service_id = body["portal_id"], body["service_id"]
        except (ValueError, KeyError):
            raise HTTPException(400, "bad payload")
        if not body.get("consent"):
            raise HTTPException(400, "consent is required")
        try:
            portal = ex().registry.portal(portal_id)
            route = ex().registry.route(portal_id, service_id)
        except RegistryError as e:
            raise HTTPException(404, str(e))
        if not portal.public_demo:
            raise HTTPException(403, "this portal is not offered in the public console")

        inputs = {k: str(v).strip() for k, v in (body.get("inputs") or {}).items() if str(v).strip()}
        private = {k: str(v).strip() for k, v in (body.get("private") or {}).items() if str(v).strip()}
        allowed_private = {i.key for i in route.inputs if i.source == "vault"}
        if set(private) - allowed_private:
            raise HTTPException(400, "unexpected private fields")

        citizen_id = "cit_" + secrets.token_hex(6)
        profile = CitizenProfile(
            citizen_id=citizen_id, state=inputs.get("state", "unknown"), district=inputs.get("district"),
            category=inputs.get("category") or inputs.get("caste"), course_level=inputs.get("course_level"),
            preferred_language=body.get("language") or "en-IN",
        )
        ex().store.put_profile(profile.model_dump(mode="json"))
        consent = ConsentRecord(
            consent_id="cons_" + uuid.uuid4().hex[:12], citizen_id=citizen_id, portal_ids=[portal_id], service_ids=[service_id],
            purpose=f"Fill {route.description or service_id} on {portal.name}; nothing is submitted without approval",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        ex().store.put_consent(consent.model_dump(mode="json"))
        vault_ref = ex().vault.put(private, ttl_s=24 * 3600) if private else None

        docs: list[DocumentRef] = []
        doc_keys = {d.key for d in route.documents}
        for f in files or []:
            key = (f.filename or "").split("::", 1)[0]
            if key not in doc_keys:
                continue
            data = await f.read()
            if len(data) > 20 * 1024 * 1024:
                raise HTTPException(413, "files are limited to 20 MB")
            doc_id = uuid.uuid4().hex[:16]
            path = settings.uploads_dir / f"{doc_id}{Path(f.filename).suffix.lower()[:6]}"
            path.write_bytes(data)
            ex().store.put_document(doc_id, str(path), f.content_type)
            docs.append(DocumentRef(key=key, uri=f"doc://{doc_id}", media_type=f.content_type))

        try:
            task = ApplicationTask(
                idempotency_key="console-" + uuid.uuid4().hex, citizen_id=citizen_id, portal_id=portal_id, service_id=service_id,
                inputs=inputs, documents=docs, vault_ref=vault_ref, consent_id=consent.consent_id,
                mode=body.get("mode") or ("assist" if route.read_only else "dry_run"),
                strategy=body.get("strategy") or "auto", origin="citizen",
            )
        except ValidationError as e:
            raise HTTPException(400, str(e.errors()[0]["msg"]))
        task_id, _ = ex().submit(task)
        token = ex().store.get_task(task_id)["citizen_token"]
        return {"task_id": task_id, "citizen_path": f"/citizen/{task_id}?t={token}"}

    return r
