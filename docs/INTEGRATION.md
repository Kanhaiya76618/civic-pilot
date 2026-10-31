# Integrating with Part 3 (for Part 1 and Part 2)

Part 3 is one HTTP service (`http://<host>:8000`, or the deployed URL). Pick
whichever way fits your stack:

| You are building | Easiest way in |
|---|---|
| A Python backend | `clients/python/civic_part3.py` (one file, needs only httpx) |
| A Node or Next.js app | `clients/js/civic-part3.mjs` (one file, uses fetch) |
| An LLM agent or chatbot | the MCP server: `uv run python -m executor.mcp_server` |
| Anything else | the REST API below; OpenAPI at `/docs` |

Every `/v1` call sends `X-API-Key: <CIVIC_API_KEY>`. The schemas are in `/contracts`.

To show your part inside the shared web app, also follow
[UI_CONTRACT.md](UI_CONTRACT.md): it lists the endpoints and JSON the pages expect.

## Part 1 (rights and schemes explainer)

**Live scheme lookup.** Send the citizen's answers; get back the official
portal's own matches, read live from myScheme.gov.in. Then explain them in the
citizen's language.

```python
from civic_part3 import Part3
p3 = Part3("http://<host>:8000", api_key="...")
done = p3.find_schemes({
    "gender": "Female", "age": "20", "marital_status": "Never Married", "state": "Bihar", "residence": "Rural",
    "caste": "Scheduled Caste (SC)", "disability": "No", "minority": "No", "is_student": "Yes", "bpl": "Yes",
    "economic_distress": "No",
})
done["receipt"]["result"]   # {"count": <n>, "items": [{"title": ..., "url": ...}], "source_url": ..., "retrieved_at": ...}
```

The exact keys and allowed values are in `GET /v1/registry` (service `myscheme/find_schemes`).
If the portal asks a question the answers do not cover, the task waits at
`awaiting_human`; show `citizen_url` to the citizen so they can answer it.
The agent never guesses an answer.

**Scholarship application.** When the citizen is eligible, create a
`sandbox/scholarship_postmatric` task (`mode: "dry_run"` shows what would be filed).
Inputs: `full_name, dob (YYYY-MM-DD), gender, state, district, category, course_level, institution, annual_income, ifsc`.
Private (vault): `mobile, email, bank_account`. Documents: `income_certificate`, `photo`.

## Part 2 (grievance triage and tracker)

Map your triage result to `sandbox/public_grievance` inputs:

| Your triage category | ministry | department | category |
|---|---|---|---|
| road / bridge damage | Ministry of Road Transport and Highways | Road Safety | Road and Bridges |
| water leak / no water | Ministry of Housing and Urban Affairs | Municipal Services | Water Supply |
| garbage / drains | Ministry of Housing and Urban Affairs | Swachh Bharat Mission (Urban) | Sanitation and Garbage |
| street lights | Ministry of Housing and Urban Affairs | Municipal Services | Street Lights |
| air / smoke / noise | Ministry of Environment, Forest and Climate Change | Pollution Control | Pollution |

Send `pincode` too, if you have it: it is checked live against India Post, and a
mismatch with the state is flagged. `subject` is at most 150 characters and
`description` at most 4000. Upload the citizen's photo as the `attachment` document;
it is resized to the portal's limit.

```js
import { Part3 } from "./civic-part3.mjs";
const p3 = new Part3(process.env.PART3_URL, process.env.CIVIC_API_KEY);
const task = await p3.start({
  portalId: "sandbox", serviceId: "public_grievance", citizenId: issue.citizenId, originRef: issue.id,
  inputs: { ministry, department, category, state, district, pincode, subject, description },
  private: { mobile: citizen.mobile }, mode: "assist", callbackUrl: "https://<part2>/civic/webhook",
});
// show task.citizen_url to the citizen: OTP, CAPTCHA, approval
```

When the receipt webhook arrives, start your follow-up clock from
`receipt.submitted_at` and show `receipt.reference_no`. `receipt.origin_ref` is your issue id.

## REST flow

```
POST /v1/profiles        CitizenProfile (non-sensitive only)
POST /v1/consents        ConsentRecord (what the citizen agreed to, until when)
POST /v1/vault           {"fields": {"mobile": "...", ...}} -> {"vault_ref"}   (never send Aadhaar: refused)
POST /v1/documents       multipart file -> {"uri": "doc://..."}
POST /v1/tasks           ApplicationTask -> {"task_id", "citizen_url", "events_url"}
GET  /v1/tasks/{id}      status, error, receipt
GET  /v1/tasks/{id}/events   Server-Sent Events (resume with Last-Event-ID)
POST /v1/receipts/verify     check a receipt's signature
```

ApplicationTask fields that matter:
- `idempotency_key`: the same key returns the same task (HTTP 200 instead of 201). Use your own id so a retry never files twice.
- `inputs`: only keys the route declares; structured values must match its pattern or enum.
- `mode`: `dry_run` stops at the final review page; `assist` submits after the citizen approves. Lookups use `assist`.
- `strategy`: `auto` (replay the recorded route if there is one), `route`, or `explore` (Claude plans the run live; never submits).
- `callback_url`: we POST every event and the final receipt there.

## Webhooks

Each POST carries `X-CivicPulse-Timestamp` and `X-CivicPulse-Signature: sha256=<hex>`:
an HMAC-SHA256 over `timestamp + "." + raw_body` with `CIVIC_WEBHOOK_SECRET`.
Body: `{"type": "task_event", "event": TaskEvent}` or `{"type": "receipt", "receipt": Receipt}`.
Both SDKs include `verifyWebhook` / `verify_webhook`.

## Events

Kinds: `status, step, human_needed, approval_needed, heal, security, reasoning, receipt, info, error`.
`reasoning` events carry the model's explanation and chosen actions (explore mode).
Every event carries `timing`, with agent time and the citizen's waiting time kept separate.

## What a receipt proves

The Ed25519 signature proves the receipt has not changed since Part 3 issued it.
It does not prove the portal accepted anything: call it a "tamper-evident record".
Public key: `GET /v1/receipts/public-key`.
