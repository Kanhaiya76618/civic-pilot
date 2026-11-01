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
from fastapi import APIRouter, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import enrich
from .config import settings
from .models import ApplicationTask, CitizenProfile, ConsentRecord, DocumentRef
from .registry import RegistryError

STATIC = Path(__file__).parent / "static"
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
# Client-side routes of the React app (web/). Everything else under / is the API.
SPA_ROUTES = ["/", "/schemes", "/schemes/engine", "/grievance", "/board", "/admin", "/admin/queue", "/agent", "/agent/history", "/agent/runs/{run_id}", "/history", "/home", "/signin"]


def spa_index() -> str:
    index = WEB_DIST / "index.html"
    if index.exists():
        return index.read_text()
    return (STATIC / "console.html").read_text()  # fallback when the web app has not been built


def mount_spa(app: FastAPI) -> None:
    if (WEB_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")
    if (WEB_DIST / "images").exists():  # the pages' illustrations (web/public/images)
        app.mount("/images", StaticFiles(directory=WEB_DIST / "images"), name="images")
    for name in ("logo.svg", "favicon.svg"):
        if (WEB_DIST / name).exists():
            app.add_api_route(f"/{name}", lambda name=name: Response((WEB_DIST / name).read_bytes(), media_type="image/svg+xml"),
                              methods=["GET"], include_in_schema=False)


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

    for path in SPA_ROUTES:
        r.add_api_route(path, lambda: HTMLResponse(spa_index()), methods=["GET"], include_in_schema=False)

    @r.get("/app/config")
    async def config():
        return {
            "part1_connected": bool(settings.part1_api_url) or bool(ex().llm),  # built-in explainer needs a model
            "part2_connected": True,
            "ai_available": bool(ex().llm),
            "sandbox_url_internal": bool(settings.sandbox_url),
        }

    async def _proxy(base: str, path: str, request: Request) -> Response:
        """Server-side pass-through to a teammate's API: one config value, no CORS setup on their side."""
        if not base:
            raise HTTPException(503, "this service is not connected yet")
        url = f"{base.rstrip('/')}/{path}"
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.request(request.method, url, params=dict(request.query_params), content=await request.body(),
                                    headers={k: v for k, v in request.headers.items() if k.lower() in {"content-type", "accept"}})
        except httpx.HTTPError as e:
            raise HTTPException(502, f"could not reach the service: {type(e).__name__}")
        return Response(r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))

    @r.api_route("/app/part1/{path:path}", methods=["GET", "POST"])
    async def part1(path: str, request: Request):
        return await _proxy(settings.part1_api_url, path, request)

    @r.api_route("/app/part2/{path:path}", methods=["GET", "POST"])
    async def part2(path: str, request: Request):
        return await _proxy(settings.part2_api_url, path, request)

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
            inputs = task.get("inputs", {})
            coarse = None
            if task["service_id"] == "public_grievance" and inputs.get("latitude") and inputs.get("longitude"):
                try:  # ~1 km precision: enough for a public map, not enough to find a home
                    coarse = [round(float(inputs["latitude"]), 2), round(float(inputs["longitude"]), 2)]
                except ValueError:
                    coarse = None
            out.append({
                "service": f"{task['portal_id']}/{task['service_id']}",
                "portal_id": task["portal_id"],
                "service_id": task["service_id"],
                "category": inputs.get("category") if task["service_id"] == "public_grievance" else None,
                "district": inputs.get("district") if task["service_id"] == "public_grievance" else None,
                "location": coarse,
                "reference_no": receipt and receipt.get("reference_no"),
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
