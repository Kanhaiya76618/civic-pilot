"""The whole HTTP surface, used the way Part 1, Part 2 and the citizen's phone use it.

Runs the API in its own process. The citizen's OTP and CAPTCHA are typed through
the live-view websocket; approval goes through the citizen endpoint; the
callback receiver checks every webhook's HMAC signature.
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest
import websockets

from executor.events import verify_signature
from harness.seed import PERSONAS, _sample_photo

from .conftest import SANDBOX_URL

API_PORT = 8197
API = f"http://127.0.0.1:{API_PORT}"
HOOK_PORT = 8196
KEY = {"X-API-Key": "test-key"}
received: list[dict] = []


class Hook(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        ok = verify_signature(body, self.headers["X-CivicPulse-Timestamp"], self.headers["X-CivicPulse-Signature"], secret="hook-secret")
        received.append({"valid": ok, "body": json.loads(body)})
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def api(sandbox):
    hook = HTTPServer(("127.0.0.1", HOOK_PORT), Hook)
    threading.Thread(target=hook.serve_forever, daemon=True).start()
    env = {**os.environ, "CIVIC_DATA_DIR": tempfile.mkdtemp(prefix="civic-api-"), "CIVIC_API_KEY": "test-key",
           "CIVIC_WEBHOOK_SECRET": "hook-secret", "CIVIC_PUBLIC_URL": API}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "executor.api:app", "--port", str(API_PORT), "--log-level", "warning"],
                            env=env, cwd=os.path.dirname(os.path.dirname(__file__)))
    for _ in range(150):
        try:
            if httpx.get(API + "/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    yield API
    proc.terminate()
    proc.wait(10)
    hook.shutdown()


async def wait_status(c, task_id, wanted, timeout=60):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        st = (await c.get(f"/v1/tasks/{task_id}", headers=KEY)).json()["status"]
        if st in wanted:
            return st
        await asyncio.sleep(0.25)
    raise TimeoutError(f"{task_id} never reached {wanted}")


async def live_send(citizen_url, msgs):
    ws_url = citizen_url.replace("http://", "ws://").replace("/citizen/", "/citizen/").replace("?t=", "/live?t=")
    async with websockets.connect(ws_url) as ws:
        first = json.loads(await asyncio.wait_for(ws.recv(), 10))
        assert first["frame"] and first["input"] is True  # a JPEG frame arrived and input is open
        for m in msgs:
            await ws.send(json.dumps(m))
            await asyncio.sleep(0.15)
        await asyncio.sleep(0.5)


async def test_full_http_flow(api, tmp_path):
    p = PERSONAS[1]
    async with httpx.AsyncClient(base_url=api, timeout=20) as c:
        assert (await c.get("/v1/registry")).status_code == 401  # API key enforced
        assert any(r["service_id"] == "public_grievance" for r in (await c.get("/v1/registry", headers=KEY)).json())

        await c.post("/v1/profiles", json=p["profile"], headers=KEY)
        consent = {"consent_id": "cons_api_1", "citizen_id": p["profile"]["citizen_id"], "portal_ids": ["sandbox"],
                   "service_ids": ["public_grievance"], "purpose": "test", "expires_at": "2099-01-01T00:00:00Z"}
        assert (await c.post("/v1/consents", json=consent, headers=KEY)).status_code == 200
        vault_ref = (await c.post("/v1/vault", json={"fields": p["vault"]}, headers=KEY)).json()["vault_ref"]
        photo = tmp_path / "pothole.jpg"
        _sample_photo(photo)
        doc = (await c.post("/v1/documents", files={"file": ("pothole.jpg", photo.read_bytes(), "image/jpeg")}, headers=KEY)).json()

        task = {"idempotency_key": "part2-issue-77", "citizen_id": p["profile"]["citizen_id"], "portal_id": "sandbox",
                "service_id": "public_grievance", "inputs": p["inputs"]["public_grievance"],
                "documents": [{"key": "attachment", "uri": doc["uri"]}], "vault_ref": vault_ref, "consent_id": "cons_api_1",
                "mode": "assist", "callback_url": f"http://127.0.0.1:{HOOK_PORT}/hook", "origin": "part2", "origin_ref": "issue-77"}
        r = await c.post("/v1/tasks", json=task, headers=KEY)
        assert r.status_code == 201
        created = r.json()
        again = await c.post("/v1/tasks", json=task, headers=KEY)
        assert again.status_code == 200 and again.json()["task_id"] == created["task_id"]  # idempotent
        task_id, citizen_url = created["task_id"], created["citizen_url"]
        assert (await c.get(citizen_url.replace(api, "").replace("?t=", "?t=wrong"))).status_code == 404

        # OTP: read the "phone", type it into the live view (the field has focus), press Enter
        await wait_status(c, task_id, {"awaiting_human"})
        otp = re.search(r"\d{6}", httpx.get(SANDBOX_URL + "/__sms").json()["messages"][-1]["text"]).group(0)
        await live_send(citizen_url, [{"t": "type", "text": otp}, {"t": "key", "key": "Enter"}])

        # CAPTCHA: the agent has put the cursor in the CAPTCHA box; type and tap Done
        await wait_status(c, task_id, {"awaiting_human"})
        await asyncio.sleep(0.5)
        state = (await c.get(citizen_url.replace(api, "").replace("?t=", "/state?t="))).json()
        assert state["human"]["kind"] == "captcha"
        await live_send(citizen_url, [{"t": "type", "text": "7KQ2M"}])
        assert (await c.post(citizen_url.replace(api, "").replace("?t=", "/human/done?t="))).status_code == 200

        await wait_status(c, task_id, {"awaiting_approval"})
        state = (await c.get(citizen_url.replace(api, "").replace("?t=", "/state?t="))).json()
        assert state["approval_pending"] and state["card"]["portal"]["is_sandbox"]
        assert (await c.get(citizen_url.replace(api, "").replace("?t=", "/approval.png?t="))).headers["content-type"] == "image/png"
        assert (await c.post(citizen_url.replace(api, "").replace("?t=", "/approve?t="), json={"decision": "approved"})).status_code == 200

        assert await wait_status(c, task_id, {"completed", "failed", "needs_review"}) == "completed"
        view = (await c.get(f"/v1/tasks/{task_id}", headers=KEY)).json()
        receipt = view["receipt"]
        assert receipt["reference_no"].startswith("SBX/MOHUA/E/2026/") and receipt["origin_ref"] == "issue-77"
        assert (await c.post("/v1/receipts/verify", json=receipt)).json()["valid"] is True
        assert (await c.post("/v1/receipts/verify", json={**receipt, "reference_no": "X"})).json()["valid"] is False

        # SSE replays the whole history in order
        async with c.stream("GET", f"/v1/tasks/{task_id}/events", headers=KEY) as s:
            body = ""
            async for chunk in s.aiter_text():
                body += chunk
                if "event: receipt" in body:
                    break
        seqs = [int(x) for x in re.findall(r"^id: (\d+)$", body, re.M)]
        assert seqs == sorted(seqs) and "awaiting_approval" in body

    await asyncio.sleep(1.5)
    assert received and all(h["valid"] for h in received)
    kinds = {h["body"]["type"] for h in received}
    assert kinds == {"task_event", "receipt"}


async def test_public_console_endpoints(api):
    async with httpx.AsyncClient(base_url=api, timeout=20) as c:
        home = await c.get("/")
        assert home.status_code == 200 and "<title>Civic Pulse Agent</title>" in home.text
        services = (await c.get("/app/services")).json()
        assert {s["service_id"] for s in services} >= {"find_schemes", "public_grievance"}
        assert all(s["public_demo"] for s in services)

        no_consent = await c.post("/app/start", data={"payload": json.dumps({"portal_id": "sandbox", "service_id": "eligibility_check", "inputs": {}})})
        assert no_consent.status_code == 400
        not_public = await c.post("/app/start", data={"payload": json.dumps({"portal_id": "cpgrams", "service_id": "lodge_grievance", "consent": True})})
        assert not_public.status_code in {403, 404}
        bad_private = await c.post("/app/start", data={"payload": json.dumps({"portal_id": "sandbox", "service_id": "eligibility_check", "consent": True, "private": {"aadhaar": "1"}})})
        assert bad_private.status_code == 400

        ok = await c.post("/app/start", data={"payload": json.dumps({"portal_id": "sandbox", "service_id": "eligibility_check", "consent": True,
                                                                        "inputs": {"state": "Bihar", "category": "SC", "annual_income": "100000"}})})
        assert ok.status_code == 200 and ok.json()["citizen_path"].startswith("/citizen/")
        state = (await c.get(ok.json()["citizen_path"].replace("?t=", "/state?t="))).json()
        assert state["portal"]["is_sandbox"] is True
        runs = (await c.get("/app/runs")).json()
        assert runs and "inputs" not in json.dumps(runs) and "Bihar" not in json.dumps(runs)  # no personal data on the board

        assert (await c.post("/v1/admin/sandbox-variant", json={"variant": "inject"})).status_code == 401
        assert (await c.post("/v1/admin/sandbox-variant", json={"variant": "drop tables"}, headers=KEY)).status_code == 422
        r = await c.post("/v1/admin/sandbox-variant", json={"variant": "inject"}, headers=KEY)
        assert r.json()["variant"] == "inject"
        await c.post("/v1/admin/sandbox-variant", json={"variant": "default"}, headers=KEY)
