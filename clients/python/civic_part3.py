"""Tiny client for Civic Pulse Part 3 (copy this one file into Part 1 or Part 2).

    from civic_part3 import Part3
    p3 = Part3("http://<host>:8000", api_key="...")
    schemes = p3.find_schemes({"gender": "Female", "age": "20", ...})          # live myScheme results
    task = p3.start(portal_id="sandbox", service_id="public_grievance", citizen_id="cit_1",
                    inputs={...}, private={"mobile": "..."}, mode="assist", origin_ref="issue-42")
    print(task["citizen_url"])  # send to the citizen: OTP, CAPTCHA, approval
    Part3.verify_webhook(raw_body, headers, secret)  # in your webhook handler

Only needs httpx.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx


class Part3:
    def __init__(self, base_url: str, api_key: str = "", timeout: float = 30):
        self.c = httpx.Client(base_url=base_url, headers={"X-API-Key": api_key} if api_key else {}, timeout=timeout)

    def services(self) -> list[dict]:
        return self.c.get("/v1/registry").raise_for_status().json()

    def start(self, portal_id: str, service_id: str, citizen_id: str, inputs: dict, private: dict | None = None,
              documents: dict[str, bytes] | None = None, mode: str = "dry_run", origin: str = "part2",
              origin_ref: str | None = None, callback_url: str | None = None, idempotency_key: str | None = None) -> dict:
        consent_id = "cons_" + uuid.uuid4().hex[:12]
        self.c.post("/v1/consents", json={
            "consent_id": consent_id, "citizen_id": citizen_id, "portal_ids": [portal_id], "service_ids": [service_id],
            "purpose": f"{service_id} with approval before submit",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
        }).raise_for_status()
        vault_ref = self.c.post("/v1/vault", json={"fields": private}).raise_for_status().json()["vault_ref"] if private else None
        docs = [{"key": k, "uri": self.c.post("/v1/documents", files={"file": (f"{k}.jpg", data)}).raise_for_status().json()["uri"]}
                for k, data in (documents or {}).items()]
        return self.c.post("/v1/tasks", json={
            "idempotency_key": idempotency_key or f"{origin}-{origin_ref or uuid.uuid4().hex}", "citizen_id": citizen_id,
            "portal_id": portal_id, "service_id": service_id, "inputs": inputs, "documents": docs, "vault_ref": vault_ref,
            "consent_id": consent_id, "mode": mode, "origin": origin, "origin_ref": origin_ref, "callback_url": callback_url,
        }).raise_for_status().json()

    def task(self, task_id: str) -> dict:
        return self.c.get(f"/v1/tasks/{task_id}").raise_for_status().json()

    def wait(self, task_id: str, timeout_s: float = 120) -> dict:
        end = time.time() + timeout_s
        while True:
            t = self.task(task_id)
            if t["status"] in {"completed", "failed", "needs_review"} or time.time() > end:
                return t
            time.sleep(1)

    def find_schemes(self, answers: dict, citizen_id: str | None = None, timeout_s: float = 120) -> dict:
        t = self.start("myscheme", "find_schemes", citizen_id or "cit_" + uuid.uuid4().hex[:8], answers, mode="assist", origin="part1")
        return self.wait(t["task_id"], timeout_s)

    @staticmethod
    def verify_webhook(raw_body: bytes, headers: dict, secret: str, max_age_s: int = 300) -> bool:
        ts, sig = headers.get("X-CivicPulse-Timestamp", "0"), headers.get("X-CivicPulse-Signature", "")
        if abs(time.time() - int(ts)) > max_age_s:
            return False
        mac = hmac.new(secret.encode(), ts.encode() + b"." + raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest("sha256=" + mac, sig)
