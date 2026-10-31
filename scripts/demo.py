"""Start a demo task through the HTTP API, exactly as Part 1 or Part 2 would.

  # terminal 1: sandbox portal       uv run uvicorn sandbox_portal.app:app --port 8100
  # terminal 2: executor (visible)   CIVIC_HEADLESS=0 uv run uvicorn executor.api:app --port 8000
  # terminal 3:
  uv run python scripts/demo.py --service public_grievance --persona 1
  uv run python scripts/demo.py --service scholarship_postmatric --variant inject

Open the printed citizen link on your phone (same Wi-Fi: set CIVIC_PUBLIC_URL to
http://<laptop-ip>:8000 and run the executor with --host 0.0.0.0). The OTP shows
up on the sandbox "phone" page: http://127.0.0.1:8100/__sms
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.seed import PERSONAS, _sample_certificate, _sample_photo  # noqa: E402  (rehearsal fixtures; the live demo uses the console)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--sandbox", default="http://127.0.0.1:8100")
    ap.add_argument("--key", default="", help="X-API-Key, if CIVIC_API_KEY is set on the executor")
    ap.add_argument("--service", default="public_grievance", choices=["public_grievance", "scholarship_postmatric"])
    ap.add_argument("--persona", type=int, default=0)
    ap.add_argument("--mode", default="assist", choices=["assist", "dry_run"])
    ap.add_argument("--variant", default="default", help="sandbox layout: default, v2_renamed, v3_relabel, v4_interstitial, inject")
    ap.add_argument("--test-mode", action="store_true", help="fixed OTP 123456 and CAPTCHA 7KQ2M (rehearsals only)")
    args = ap.parse_args()

    h = {"X-API-Key": args.key} if args.key else {}
    httpx.post(f"{args.sandbox}/__admin/config", json={"variant": args.variant, "test_mode": args.test_mode}).raise_for_status()
    p = PERSONAS[args.persona]
    c = httpx.Client(base_url=args.api, headers=h, timeout=30)
    c.post("/v1/profiles", json=p["profile"]).raise_for_status()
    consent_id = "cons_" + uuid.uuid4().hex[:10]
    c.post("/v1/consents", json={
        "consent_id": consent_id, "citizen_id": p["profile"]["citizen_id"], "portal_ids": ["sandbox"],
        "service_ids": [args.service], "purpose": f"Demo: file {args.service} with approval",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
    }).raise_for_status()
    vault_ref = c.post("/v1/vault", json={"fields": p["vault"], "ttl_s": 7200}).json()["vault_ref"]

    tmp = ROOT / ".data" / "demo"
    tmp.mkdir(parents=True, exist_ok=True)
    docs = []
    if args.service == "scholarship_postmatric":
        cert, photo = tmp / "income_certificate.jpg", tmp / "photo.jpg"
        _sample_certificate(cert, p["inputs"][args.service]["full_name"])
        _sample_photo(photo)
        for key, f in [("income_certificate", cert), ("photo", photo)]:
            uri = c.post("/v1/documents", files={"file": (f.name, f.read_bytes(), "image/jpeg")}).json()["uri"]
            docs.append({"key": key, "uri": uri})
    else:
        photo = tmp / "issue_photo.jpg"
        _sample_photo(photo)
        uri = c.post("/v1/documents", files={"file": (photo.name, photo.read_bytes(), "image/jpeg")}).json()["uri"]
        docs.append({"key": "attachment", "uri": uri})

    task = {
        "idempotency_key": "demo-" + uuid.uuid4().hex, "citizen_id": p["profile"]["citizen_id"], "portal_id": "sandbox",
        "service_id": args.service, "inputs": p["inputs"][args.service], "documents": docs, "vault_ref": vault_ref,
        "consent_id": consent_id, "mode": args.mode, "origin": "citizen", "origin_ref": "demo",
    }
    r = c.post("/v1/tasks", json=task)
    r.raise_for_status()
    out = r.json()
    print(json.dumps(out, indent=2))
    print(f"\nCitizen page:   {out['citizen_url']}\nSandbox SMS inbox: {args.sandbox}/__sms\nEvents (SSE):   {args.api}{out['events_url']}")


if __name__ == "__main__":
    main()
