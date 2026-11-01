# UI contract: what the unified Civic Pulse app expects from each part

One web app (`web/`) shows all three parts, served by one server.

- **Part 1 (explainer) is built in:** `executor/explainer.py`, endpoints under `/app/part1/api/`. It is live whenever the
  server has a model key (`AIMLAPI_KEY` or `ANTHROPIC_API_KEY`); `GET /app/config` reports `part1_connected`.
  `PART1_API_URL` is only a fallback pass-through for routes the built-in explainer does not handle.
- **Part 2:** described below. A teammate's own service can still be plugged in with `PART2_API_URL`
  (the server forwards `/app/part2/<path>` to it, so no CORS setup is needed).
- **Part 3 (agent):** built in; see `docs/INTEGRATION.md`.

Responses are JSON. Errors are `{"detail": "<message a citizen can read>"}` with an HTTP status.

## Part 1: rights and policy explainer (built in)

Flow: add a document once, then ask about it in any language. Every point in an answer carries an exact quote from the
document, checked in code (points whose quote is not in the text are dropped and counted).

### `POST /app/part1/api/documents` (multipart form)

One of:
- `url`: an official `.gov.in` / `.nic.in` link (web page or PDF). Every redirect must stay on such hosts.
- `file`: a PDF, at most 15 MB. Typed PDFs are read directly; scanned PDFs, and PDFs mostly in an Indian script
  (garbled text layers), are read by the model from page images (first 12 pages).
- `text`: the pasted text (at least about a paragraph). Optional `title`.

Response `201`:
```json
{ "doc_id": "doc_2cb55d2cf387", "title": "Rules.pdf", "source": "pdf_link_scan", "url": "https://…gov.in/…/Rules.pdf",
  "chars": 7245, "page_count": 4, "created_at": "2026-11-01T11:15:09Z",
  "ocr": { "pages_read": 4, "pages_total": 4, "reason": "indian_script" } }
```
`ocr` is `null` for text documents; `reason` is `scanned` or `indian_script`.
Errors: `400` link not on an official host; `413` too large; `415` not a PDF; `422` too little readable text;
`502` site unreachable or certificate unverifiable; `503` a scan needs a model; `429` hourly limit.

### `POST /app/part1/api/explain`

```json
{ "doc_id": "doc_2cb55d2cf387", "question": "I am 45 with a savings account. Can I join?", "language": "hi-IN", "auto_language": false }
```
- `language`: one of `GET /app/part1/api/languages` (en, hi, bn, ta, te, mr, gu, kn, ml, pa, or, ur, each `-IN`).
- `question`: optional; empty means "What does this mean for me, and what are my rights?".
- `auto_language`: `true` when the citizen did not pick a language: the answer follows the question's language
  (Hindi typed in English letters counts as Hindi).

Response `200` (lists may be empty):
```json
{
  "language": "hi-IN", "language_from_question": false, "question": "…", "cached": false,
  "title": "…", "summary": "…", "answer": "…",
  "doc": { "doc_id": "…", "title": "…", "url": "…", "issuer": "…", "date": "…", "doc_type": "scheme_guideline", "page_count": 4,
           "ocr": null },
  "rights":     [{ "text": "…", "quote": "exact words from the document", "page": 2 }],
  "eligibility":[{ "criterion": "…", "met": true, "note": "…", "quote": "…", "page": 2 }],
  "impacts":    { "citizens": [{ "text": "…", "quote": "…", "page": 1 }], "business": [] },
  "deadlines":  [{ "text": "…", "quote": "…", "page": 1 }],
  "how_to_act": [{ "text": "…", "quote": "…", "page": 1 }],
  "labels": { "rights": "आपके अधिकार", "what_to_do": "…" },
  "voice_script": "…", "audio_url": "/app/part1/api/audio/4984b62831534f28.mp3", "voice_provider": "openai/tts-1 via AIML API",
  "apply": { "portal_id": "myscheme", "service_id": "find_schemes", "label": "Find every scheme you qualify for on myScheme" },
  "citations": [{ "title": "…", "reference": "…", "date": "…", "url": "…" }],
  "dropped_unverified": 0, "untranslated": 0, "timing": { "ms": 40968, "ai_calls": 2 }
}
```
- `met`: `true` / `false` / `null` (the question does not say).
- `quote` stays in the document's own language; everything else is in `language`; `labels` are the page headings.
- `audio_url` is `null` when text-to-speech is unavailable: the page then uses the device's voice and says so.
- `apply` is `null` unless the document matches a service the agent runs.
Errors: `400` no document or unknown language; `404` unknown `doc_id`; `502` model error; `503` no model; `429` hourly limit.

### `POST /app/part1/api/transcribe` (multipart form)

`audio`: a recording (webm, mp4/m4a, mp3, ogg; at most 3 MB; the page records up to 30 s). Optional `language`; without
it the language is detected. Response: `{ "text": "मेरी उम्र पैंतालीस साल है…", "language": "hi-IN" }`.
The audio is not stored. Errors: `413` too long; `415` not audio; `502`/`504` recognition failed or too slow; `503` no key.

### Other Part 1 endpoints
- `GET /app/part1/api/languages` → `[{ "code": "hi-IN", "name": "Hindi" }, …]`
- `GET /app/part1/api/audio/<id>.mp3` → the spoken explainer.
- `GET /app/part1/api/pipeline/latest` (engine room, polled about every second):
  `{ "question": "…", "nodes": [{ "id": "reason", "status": "running", "ms": 25833, "note": "…" }] }` with ids
  `ingest, parse, chunk, embed, retrieve, reason, translate, voice` and `status` `idle | running | done | error`.

### Limits
Model-backed calls (explain, reading a scan, transcribe) are capped per visitor and overall per hour:
`CIVIC_EXPLAINS_PER_HOUR` (default 20) and `CIVIC_EXPLAINS_GLOBAL_PER_HOUR` (default 300). Repeating a cached answer is free.

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
