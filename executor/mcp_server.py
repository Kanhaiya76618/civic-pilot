"""Part 3 as MCP tools, so any AI agent can use it: Part 1's scheme explainer,
Part 2's triage agent, or Claude Desktop.

It talks to the running executor over its HTTP API, so it needs nothing but
the API URL and key:

  CIVIC_API_URL=http://127.0.0.1:8000 CIVIC_API_KEY=... uv run python -m executor.mcp_server

Claude Desktop / any MCP client config:
  {"mcpServers": {"swayam-sevak": {"command": "uv", "args": ["run", "--directory", "<repo>", "python", "-m", "executor.mcp_server"],
                                  "env": {"CIVIC_API_URL": "http://127.0.0.1:8000", "CIVIC_API_KEY": "..."}}}}

Filing still needs the citizen: start_application returns a citizen_url where
they do the OTP/CAPTCHA and approve. No tool can approve on their behalf.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

API = os.environ.get("CIVIC_API_URL", "http://127.0.0.1:8000")
KEY = os.environ.get("CIVIC_API_KEY", "")
TERMINAL = {"completed", "failed", "needs_review"}
logging.getLogger("httpx").setLevel(logging.WARNING)  # stdio MCP: keep stderr for real problems

server = MCPServer(
    name="swayam-sevak-executor",
    instructions=(
        "Swayam-sevak Part 3 operates Indian government portals in a real browser. "
        "Use find_schemes for live scheme eligibility from myScheme.gov.in (read-only, fast). "
        "Use list_services, then start_application to fill a form; give the returned citizen_url to the citizen, "
        "who completes OTP/CAPTCHA and approves before anything is filed. Never invent citizen details."
    ),
)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=API, headers={"X-API-Key": KEY} if KEY else {}, timeout=30)


async def _consent(c: httpx.AsyncClient, citizen_id: str, portal_id: str, service_id: str, purpose: str) -> str:
    consent_id = "cons_" + uuid.uuid4().hex[:12]
    r = await c.post("/v1/consents", json={
        "consent_id": consent_id, "citizen_id": citizen_id, "portal_ids": [portal_id], "service_ids": [service_id],
        "purpose": purpose, "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
    })
    r.raise_for_status()
    return consent_id


async def _wait(c: httpx.AsyncClient, task_id: str, timeout_s: float) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while True:
        view = (await c.get(f"/v1/tasks/{task_id}")).json()
        if view["status"] in TERMINAL or asyncio.get_running_loop().time() > deadline:
            return view
        await asyncio.sleep(1)


@server.tool()
async def list_services() -> list[dict[str, Any]]:
    """List the portals and services the agent can operate, with the exact input keys each needs."""
    async with _client() as c:
        r = await c.get("/v1/registry")
        r.raise_for_status()
        return [
            {k: s[k] for k in ("portal_id", "service_id", "description", "status", "read_only", "is_sandbox", "inputs", "documents")}
            for s in r.json() if s["status"] in {"stable", "candidate"}
        ]


@server.tool()
async def find_schemes(
    gender: str, age: int, state: str, residence: str, caste: str, disability: str, is_student: str, bpl: str,
    marital_status: str | None = None, minority: str | None = None, employment_status: str | None = None,
    government_employee: str | None = None, occupation: str | None = None, economic_distress: str | None = None,
    disability_percentage: int | None = None,
) -> dict[str, Any]:
    """Find government schemes a citizen may be eligible for, live from myScheme.gov.in.

    gender: Male | Female | Transgender. residence: Urban | Rural.
    caste: General | Other Backward Class (OBC) | Particularly Vulnerable Tribal Group (PVTG) | Scheduled Caste (SC) |
           Scheduled Tribe (ST) | De-Notified, Nomadic, and Semi-Nomadic (DNT) communities.
    Yes/No answers: disability, is_student, bpl, minority, government_employee, economic_distress.
    employment_status (non-students): Employed | Unemployed | Self-Employed/ Entrepreneur.
    Returns the portal's own result count and up to 10 scheme names with links, plus a signed receipt id.
    """
    inputs = {k: str(v) for k, v in locals().items() if v is not None}
    citizen_id = "cit_mcp_" + uuid.uuid4().hex[:8]
    async with _client() as c:
        consent_id = await _consent(c, citizen_id, "myscheme", "find_schemes", "Find schemes on myScheme.gov.in")
        r = await c.post("/v1/tasks", json={
            "idempotency_key": "mcp-" + uuid.uuid4().hex, "citizen_id": citizen_id, "portal_id": "myscheme",
            "service_id": "find_schemes", "inputs": inputs, "consent_id": consent_id, "mode": "assist", "origin": "part1",
        })
        if r.status_code >= 400:
            return {"error": r.json().get("detail", r.text)}
        view = await _wait(c, r.json()["task_id"], 120)
    if view["status"] != "completed":
        return {"status": view["status"], "error": view.get("error"), "citizen_url": view.get("citizen_url"),
                "note": "If the status is awaiting_human, the portal asked a question these details do not answer; the citizen can answer it at citizen_url."}
    receipt = view["receipt"]
    return {"source": "myScheme.gov.in (live)", "receipt_id": receipt["receipt_id"], **(receipt.get("result") or {})}


@server.tool()
async def start_application(
    portal_id: str, service_id: str, citizen_id: str, inputs: dict[str, str],
    private: dict[str, str] | None = None, mode: str = "dry_run", origin_ref: str | None = None,
) -> dict[str, Any]:
    """Start filling a service for a citizen. Use list_services for the input keys.

    private: sensitive fields (mobile, email, bank_account); they go to an encrypted vault and are never shown to any model.
    mode: dry_run (stop at the review page) or assist (submit after the citizen approves).
    Returns task_id and citizen_url. Send citizen_url to the citizen: they complete OTP/CAPTCHA and approve there.
    """
    async with _client() as c:
        consent_id = await _consent(c, citizen_id, portal_id, service_id, f"Fill {service_id} with approval before submit")
        vault_ref = None
        if private:
            v = await c.post("/v1/vault", json={"fields": private})
            if v.status_code >= 400:
                return {"error": v.json().get("detail", v.text)}
            vault_ref = v.json()["vault_ref"]
        r = await c.post("/v1/tasks", json={
            "idempotency_key": "mcp-" + uuid.uuid4().hex, "citizen_id": citizen_id, "portal_id": portal_id, "service_id": service_id,
            "inputs": inputs, "vault_ref": vault_ref, "consent_id": consent_id, "mode": mode, "origin": "part2", "origin_ref": origin_ref,
        })
        if r.status_code >= 400:
            return {"error": r.json().get("detail", r.text)}
        body = r.json()
        return {"task_id": body["task_id"], "status": body["status"], "citizen_url": body["citizen_url"]}


@server.tool()
async def get_task(task_id: str) -> dict[str, Any]:
    """Current status of a task, the last error if any, and its receipt when finished."""
    async with _client() as c:
        r = await c.get(f"/v1/tasks/{task_id}")
        if r.status_code == 404:
            return {"error": "no such task"}
        v = r.json()
        return {"status": v["status"], "error": v.get("error"), "receipt": v.get("receipt"), "citizen_url": v.get("citizen_url")}


@server.tool()
async def verify_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Check a receipt's Ed25519 signature. Valid means unchanged since issued, not that the portal accepted it."""
    async with _client() as c:
        return (await c.post("/v1/receipts/verify", json=receipt)).json()


if __name__ == "__main__":
    server.run("stdio")
