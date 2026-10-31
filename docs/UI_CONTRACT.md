# UI contract: what the unified Civic Pulse app expects from Part 1 and Part 2

One web app (`web/`) shows all three parts. Part 3's screens already run on live
data. Part 1 and Part 2 screens are built and wired; each shows an honest "not
connected yet" panel until its API is set on the server:

```bash
PART1_API_URL=https://part1.example.com   # your explainer service
PART2_API_URL=https://part2.example.com   # your grievance service
```

The browser never calls your service directly. Part 3's server forwards
`/app/part1/<path>` to `PART1_API_URL/<path>` and `/app/part2/<path>` to
`PART2_API_URL/<path>`, so you need no CORS setup and no extra deployment.
Return JSON with the shapes below. Extra fields are ignored; missing optional
fields are simply not shown.

## Part 1: rights and schemes explainer

### `POST /api/explain` (Schemes page: question box)

Request:
```json
{ "question": "Can I get a scholarship?", "language": "hi-IN" }
```
Response:
```json
{
  "answer": "Plain-language answer in the requested language.",
  "citations": [
    { "title": "Post Matric Scholarship guidelines", "reference": "F.No. 11017/2/2024", "date": "2024-04-01", "url": "https://..." }
  ],
  "eligibility": [
    { "criterion": "Family income below ₹2.5 lakh", "met": true },
    { "criterion": "Studying in Class 11 or above", "met": null, "note": "Tell us your class to check" }
  ],
  "audio_url": "https://.../answer.mp3",
  "apply": { "portal_id": "sandbox", "service_id": "scholarship_postmatric", "label": "Apply with the agent" }
}
```
- `met`: `true` (✓), `false` (✗) or `null` (unknown).
- Without `audio_url`, the page reads the answer aloud with the browser's own speech in the chosen language.
- `apply` shows an "Apply" button that opens that service in the agent room. Get the ids from `GET /v1/registry`.

### `GET /api/pipeline/latest` (Engine room canvas)

Polled every 1.2 s. Node ids are fixed: `ingest, parse, chunk, embed, retrieve, reason, translate, voice`.
```json
{
  "question": "Can I get a scholarship?",
  "nodes": [
    { "id": "ingest", "status": "done", "ms": 120 },
    { "id": "retrieve", "status": "running" },
    { "id": "voice", "status": "idle" }
  ]
}
```
`status` is one of `idle | running | done | error`; `ms` is how long the stage took.

## Part 2: grievance triage and accountability

### `POST /api/reports` (Report a problem: step 4, "AI triage")

Multipart form: `photo` (file, optional), `audio` (file, optional), `category`, `description`, `lat`, `lng`.
Response:
```json
{ "code": "CP-2026-0042", "severity": "P2", "category": "Water Supply", "reasoning": "Visible leak near a school; affects supply to several homes.", "duplicate_of": null }
```
`severity`: `P1` (critical), `P2` (high), `P3` (medium).

### `GET /api/public/reports` (Accountability board: map and kanban)
```json
[
  { "code": "CP-2026-0042", "lat": 24.79, "lng": 85.0, "severity": "P2", "status": "assigned", "category": "Water Supply", "source": "citizen", "ward": "Ward 7", "sla_breached": false }
]
```
- `status` maps to columns: `submitted`/`acknowledged` → Submitted, `assigned` → Routed, `in_progress` → In progress, `resolved` → Resolved.
- `source: "agent"` shows the "filed by agent" badge.
- Round public coordinates to about 1 km.

### `GET /api/public/stats` (Accountability board: top cards)
```json
{ "total": 128, "open": 41, "resolved_pct": 68, "avg_resolution_hours": 52, "sla_breached": 3 }
```

## Receipts from Part 3 to Part 2

Unchanged: send a task with `callback_url` and `origin_ref` (your report code). Part 3
POSTs every event and the final receipt there, HMAC-signed. See `docs/INTEGRATION.md`.
