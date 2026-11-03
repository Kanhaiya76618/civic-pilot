# Swayam-sevak — Technical Round Study Guide (Team Orion)

Read this top to bottom once, then use the **Likely questions** section to practise out loud.
Everything here is what the code actually does today, checked against the live system on 3 Nov 2026.

---

## 0. The 30-second answer ("What is your project?")

> India's government help exists, but citizens can't reach it: rules are written in legal English, portals are
> hard (OTPs, CAPTCHAs, multi-page forms), and complaints disappear. **Swayam-sevak** is one web app with three
> connected parts: (1) an **explainer** that turns any official notice into plain answers in 12 Indian languages,
> where every point quotes the document; (2) **grievance reporting** with a photo and a voice note in your own
> language, a pothole-detection model, a ticket on a municipal desk, and a public board where the citizen confirms
> the fix; (3) an **AI agent** that works official websites in a real browser while you watch, and never submits
> without your approval. Our rule: **AI does the language work; code decides what is allowed.**

---

## 1. The problem (say it with three gaps)

| Gap | What goes wrong today | Who it hurts |
|---|---|---|
| **Understanding** | Schemes, Gazette notifications, municipal orders are long, legal, English. | People who read Hindi/Tamil/Bengali etc., first-time internet users |
| **Doing** | Portals = multi-page wizards, OTPs, CAPTCHAs, upload limits. People quit or pay a middleman who then sees their bank details. | Older people, farmers, daily-wage workers |
| **Accountability** | A pothole or broken streetlight is reported, then nothing. No one knows who acted. | Everyone in a ward |

**Theme:** Theme 1 · Civic Pulse & Digital Governance.

---

## 2. Our solution in one picture

```
                 ┌─ 1 Explainer ──► reads official notice ──► answer in your language + voice (every point quoted)
Citizen (any ────┼─ 2 Report    ──► photo check + voice→text ──► desk ticket ──► proof photo ──► citizen confirms ──► public board
phone, 12 langs) └─ 3 Agent     ──► plan → search allow-listed sites → real browser loop ──► you approve ──► data + signed receipt
```
Links between parts: an explained scheme offers **"Apply with the agent"**; the desk can **escalate** a ticket;
a report can also be **filed on the grievance portal by the agent** (sandbox replica).

---

## 3. Part 1 — Rights & Policy Explainer

**Where:** `executor/explainer.py` · page "Know your schemes" (`web/src/pages/Schemes.tsx`).

**Input:** a `.gov.in` / `.nic.in` link (only those domains are fetched — `CIVIC_DOC_DOMAINS`), a PDF upload, or
pasted text, plus the citizen's question.

**Pipeline (8 named stages, shown live in the "engine room"):**
1. **Ingest** — download the page/PDF (only allowed government domains; it even fetches missing intermediate SSL
   certificates for badly configured govt sites).
2. **Parse** — HTML → text; PDF → text per page (`pypdf`).
   - If the PDF is a **scan** or an **Indian-script PDF with a garbled text layer** (legacy fonts turn "नियम" into
     "ननयम"), we detect it (`indic_share()` — share of Indian-script letters) and instead render the pages to
     images (`pypdfium2`) and let **Claude read the page images** (vision OCR), up to 12 pages.
3. **Chunk** — split into ~2000-character pieces that **keep their page number**.
4. **Retrieve** — rank chunks by keyword overlap with the question + legal "focus terms" (eligible, entitle, shall,
   deadline, penalty, fee…). Small documents are sent whole (up to 60,000 characters).
   *This is RAG (Retrieval-Augmented Generation) with keyword retrieval — no vector database/embeddings needed yet.*
5. **Reason** — Claude Opus 5.5 returns **structured JSON** (a JSON schema): title, summary, answer, rights,
   eligibility (yes / no / unknown against the citizen's own facts), impact on citizens, impact on small businesses,
   deadlines, how to act — **each item with an exact quote and page**.
6. **Verify (the key innovation)** — **code, not the AI,** checks every quote: the quote is normalised and searched
   in the document. **Any point whose quote is not in the document is deleted** and counted
   (`dropped_unverified`). So the AI cannot invent a right, a rupee amount, or a deadline.
7. **Translate** — into the chosen language (12: Hindi, English, Bengali, Tamil, Telugu, Marathi, Gujarati,
   Kannada, Malayalam, Punjabi, Odia, Urdu); headings (UI labels) are translated in the same call.
   *Auto language:* if the citizen asks in Tamil, the answer comes back in Tamil.
8. **Voice** — OpenAI **tts-1** reads the answer aloud. Citizens can also **ask by voice** (Whisper large via AIML
   API, 30 s max, audio not stored).

**Extras:** stable document IDs + answers cached on disk (repeat questions are instant); a cost limiter per hour;
"Apply with the agent" when the document matches a service our agent can run.

**Measured:** PMSBY rules PDF → Marathi + voice (Rs. 20/yr, Rs. 2 lakh cover, ages 18–70) · same rules as an
image-only scan → Gujarati, same figures · PMJJBY **Hindi** PDF → English/Bengali (ages 18–50, Rs. 436/yr, 30-day
rule) · POSH Act handbook, 58 pages → Hindi, citing pages 20–53. Every figure matched the document.

**Civic Guide (chatbot on the home page)** — `server/civic_guide.py`: searches official govt/regulator sites
(DuckDuckGo restricted to official domains), reads the top 3 pages, and **GPT-OSS 120B on Groq** answers only from
that material with [1][2][3] citations; if no official source is found it says so. Never asks for Aadhaar/OTP.

---

## 4. Part 2 — Grievance reporting & public accountability

**Where:** `server/api.py`, `server/triage.py`, `server/language.py`, `server/privacy.py`, `server/groq.py` ·
pages "Report a problem" (`Grievance.tsx`), Municipal desk (`Admin.tsx`), Accountability board (`Board.tsx`).

### The 8-step flow
1. **Speak or type** in any of 12 languages. The voice note goes to **Whisper large-v3-turbo on Groq**, which
   detects the language and writes it **in its own script** (Devanagari for Hindi, etc.). The citizen can correct it.
2. **Photo check** (the moment a photo is chosen; nothing is saved):
   - **YOLOv8 pothole model** (`pothole_best.pt`, trained by the team, Ultralytics) → bounding boxes + confidence.
     We draw the boxes on the photo ("Pothole 1: 57%").
   - **Black-hat morphology** (OpenCV) → % of rough/cracked surface.
   - **Laplacian variance** → is the photo blurry (score < 80)?
   - Findings are plain sentences with only measured numbers (count, confidence, share of the photo — no square
     metres, because a photo has no scale), translated into the citizen's language by Groq.
3. **Review — nothing saved yet:**
   - **Ward** by **point-in-polygon** (Shapely) on real ward-boundary GeoJSON (Bengaluru BBMP, Pune PMC; Delhi
     boundary). Outside our maps → "Ward not mapped yet" + the real district from the PIN code (never a made-up ward).
   - **Department** routing table (Roads & Engineering, Water Supply, Solid Waste Management, Electrical (Street
     Lighting), Environment, Ward Office).
   - **Severity P1/P2/P3 + the reason**: P1 if the text says danger/emergency/burst/hospital; P2 if the pothole
     model is >60% confident, or >5% cracked surface, or overflowing water/drainage; else P3.
   - **Near schools/hospitals:** distance (Haversine) to critical points of interest; within 150 m → priority
     multiplier 1.2–1.6×, which can raise severity one level.
   - **SLA deadline:** P1 24 h, P2 48 h, P3 72 h.
   - **Duplicate check:** an open report of the same category **within 50 m** → linked, and the original's priority
     (upvotes) goes up.
4. **Submit** → ticket number `CIV-XXXXXXXX` (first 8 characters of the report's UUID), visible on the desk at once.
   Optional: **file it on the grievance portal with the agent** (sandbox replica of CPGRAMS).
5. **Municipal desk** (officers only): urgency queue (P1 first, then nearest deadline); each ticket shows the
   citizen's photo with potholes outlined, the voice note, the original words, and an **English machine translation**
   (Groq GPT-OSS; done in the background after submit; a "Translate" button retries). Officers can acknowledge, assign,
   override severity (audit trail), escalate.
6. **Resolve with proof** — a proof-of-repair photo is **mandatory**. Before storing, **faces are blurred**
   (YuNet face detector, OpenCV, MIT licence; pixelate + blur) and the image is re-encoded, which **drops EXIF/GPS**.
7. **Citizen checks** — only the person who reported it can press "Yes, it is fixed" (→ "confirmed by the
   citizen") or "No, still a problem" (→ reopened **one priority higher, 24-hour deadline**).
8. **Public board** (no login): statuses, map (rounded locations), proof photos, citizen-confirmed repairs,
   **most-reported wards (hotspots)**. Citizens' own photos and voice notes are **never public**.

### Storage & privacy
- Supabase **Postgres** for reports and events; Supabase **Storage** private bucket `evidence`. The database stores
  `evidence://report/file` references; files are **served only through our server** (proof photos public, citizen
  evidence admin-only).
- Every change is a `ReportEvent` row (CREATED, TRIAGED, TRANSLATED, ASSIGNED, RESOLVED, CITIZEN_CONFIRMED,
  DISPUTED…) — an audit trail.

---

## 5. Part 3 — Autonomous Execution Agent (core innovation)

**Where:** `executor/console.py` (free-form agent), `executor/runner.py` (route runner), `executor/healer.py`,
`executor/vault.py`, `executor/receipts.py`, `registry/` (YAML portals & routes), `sandbox_portal/` · pages "Agent
room" (`AgentRoom.tsx`, `AgentRun.tsx`).

### How a request runs
1. **Plan** (Claude, JSON schema): intent = `discovery` (find out), `execution` (file something), `hybrid`, or
   `out_of_scope`. Off-limits requests (train booking, shopping, payments, banking) are **refused before any page
   opens** (measured: 3.5 s, nothing opened).
2. **Known service? → recorded route.** If the request matches a registered route (e.g. myScheme "find schemes"),
   it **replays the recorded steps with no AI in the loop** → myScheme eligibility, 92 schemes, ≈10 s, 1 AI call.
3. **Otherwise: search + browser loop.** Search allow-listed sites (DuckDuckGo; if DuckDuckGo shows a bot check we
   **never bypass it**, we use the site's own search). Then a **real Chromium browser (Playwright)**, one action per
   step: **perceive** (compact page snapshot with element refs) → **think** (Claude picks one action: goto / click /
   type / select / extract / give_up) → **act** → **evaluate**. Max 14 steps / 240 s. Every step is saved with a
   screenshot and the agent's reasoning, streamed live (Server-Sent Events), replayable at 1×/2×/5× (labelled replay).
   Measured: a brand-new question answered from official pages in 34 s, 7 steps, 6 AI calls.
4. **Filing** (e.g. public grievance on the sandbox replica): the form is filled from the citizen's words; private
   details (mobile number) come from the **vault**; **OTP/CAPTCHA are handed to the citizen**; the final **Submit
   waits for the citizen's approval**; **Pay is never pressed**.
5. **Receipt:** evidence files are hashed (**SHA-256**) and the receipt is **signed with Ed25519** (verifiable with
   the public key; `/api/v1/receipts/verify`). A receipt is issued only for a real, approved filing.
6. **Learn once:** a successful run is saved as a **route**; next time it replays fast.
7. **Self-healing:** if a portal's layout changes and a step fails, the **healer** first tries a heuristic match
   (the step's label/intent against the page's fields — no AI), then a model loop that may only choose **where** to
   act, never **what** to type (values hidden behind placeholders), cannot navigate and cannot press submit/pay; it
   proposes a reviewed route patch.

### Guardrails — enforced in code, not prompts
| Guardrail | How |
|---|---|
| Allow-list | The browser cannot open a host outside the registry's portals; every redirect is checked (`host_allowed`). |
| Typed-words rule | The model may only type words from the citizen's own request. |
| Vault | Private fields are **Fernet-encrypted**; the model and logs only see placeholders like `{{vault.mobile}}`; the real value is swapped in right before Playwright types it, and `redact()` scrubs leaks. |
| Human steps | OTP, CAPTCHA, choices only the citizen can make → handed to the citizen. |
| Approval gate | Final Submit waits for "yes"; payment buttons are never pressed. |
| Cost guard | Per-visitor run limits (30 starts/hour per IP). |
| Prompt-injection safety | Page text is treated as data; every candidate action passes an `_allowed()` check before it runs. |

**Honest point:** real CPGRAMS and RTI Online are **registered but locked**; filings run end to end on our
**sandbox replica** (clearly marked) — we never test on real ministry portals.

---

## 6. Accounts, roles & security

- **Supabase Auth** for sign-in (email + password). Our server then issues its own short-lived **JWT** (+ httpOnly
  cookie) with the user's role.
- **Roles:** `citizen` and `admin` (municipal officer). The officer role is stored in Supabase **app_metadata**
  (`civic_role: admin`), which **only the server key can set** — a user can never give it to themselves.
- **Municipal sign-up** needs the authority's access code (`CIVIC_OFFICER_SIGNUP_CODE`).
- **Judges' demo** tab: one click into demo officer/citizen accounts, only while `CIVIC_JUDGE_DEMO=1`.
- Per-account private **history** (explanations, agent runs, reports, saved news).
- Secrets live only in server environment variables (`.env` locally, Hugging Face Secrets live); never in browser code.

---

## 7. Tech stack (know every line)

| Layer | Technology | Why |
|---|---|---|
| Frontend | **React 19**, **Vite**, **Tailwind CSS**, **Motion** (animations), Leaflet (maps), lucide icons | fast, mobile-first, accessible (text-size controls, Hindi/English pages) |
| Backend | **FastAPI** (Python 3.11), Uvicorn, Pydantic | async, typed, auto docs |
| Agent browser | **Playwright** + Chromium (headless), live stream to the citizen | real websites, not APIs |
| Database | **Supabase Postgres** via **SQLAlchemy** (SQLite fallback for offline/tests) | |
| Storage | **Supabase Storage** private bucket | evidence never public |
| Auth | **Supabase Auth** + our JWT; Fernet vault; Ed25519 receipts (`cryptography`) | |
| Computer vision | **YOLOv8** (Ultralytics) pothole model; **OpenCV** (black-hat crack morphology, Laplacian blur, **YuNet** face detection) | |
| GIS | **Shapely** point-in-polygon, GeoJSON ward maps, Haversine distances | |
| PDFs | `pypdf` (text), `pypdfium2` (render pages for vision OCR) | |
| Live data | myScheme.gov.in, .gov.in/.nic.in documents, **India Post PIN API**, **RBI IFSC (Razorpay API)**, **OpenStreetMap Nominatim** (PIN ↔ location), **Google News RSS** + **PIB RSS** (news) | |
| Deploy | **One Docker image** on **Hugging Face Spaces** (port 7860); GitHub for code | website + API on one address (no CORS; WebSockets for the live browser) |
| Tests | **pytest** — 112 offline tests, plus 4 live tests on the real myScheme portal | |

### AI models & APIs (and exactly what each one does)
| Model / API | Provider | Used for |
|---|---|---|
| **Claude Opus 5.5** | AIML API (Anthropic-compatible) | explaining documents, translation, reading scanned pages (vision), agent planning and every browser step, the healer |
| **OpenAI tts-1** | AIML API | spoken answers |
| **Whisper large** | AIML API | voice questions in the explainer |
| **GPT-OSS 120B** | **Groq** | Civic Guide chatbot; English translation of reports for officers; translating photo findings for citizens |
| **Whisper large-v3-turbo** | **Groq** | report voice notes → text in the speaker's own script |
| **YOLOv8 (our trained pothole model)** | runs on our server | pothole detection + boxes |
| **YuNet** | OpenCV model zoo, on our server | face blurring in public proof photos |

**No model was fine-tuned.** Accuracy comes from **grounding** (RAG + quote check), **structured JSON outputs**, and
**checks in code**. (Groq's Llama 3.3 was retired on 16 Aug 2026; we migrated to GPT-OSS 120B.)

---

## 8. Architecture (how the pieces talk)

```
Browser (React app: citizen app · municipal desk · public board)
        │  HTTPS (same origin)
        ▼
FastAPI server — one Docker image
  executor/  explainer · agent console · route runner · healer · vault · receipts · news · history
  server/    auth · grievance triage (YOLOv8, wards) · desk · board · evidence · face blur · report languages · Civic Guide
        │
        ├── AI: Claude Opus 5.5, tts-1, Whisper (AIML API) · GPT-OSS 120B, Whisper (Groq) · YOLOv8 · YuNet (local)
        ├── Live sources: .gov.in pages, myScheme, India Post, RBI IFSC, PIB, Google News, OpenStreetMap
        ├── Supabase: Auth, Postgres (reports, events, users), private Storage (evidence)
        └── Playwright Chromium (allow-list) → official portals / sandbox replica (runs inside the same container)
```

Key data objects: **Report** (category, description, severity, lat/lng, ward, SLA, evidence refs, status) ·
**ReportEvent** (the audit trail) · **Receipt** (signature, public key, SHA-256 hashes, previous-hash chain) ·
**Route** (YAML steps for a portal service) · **Run** (agent steps + screenshots).

---

## 9. Honesty & limits (judges respect this — say it before they find it)

- **No dummy data:** the public board shows only real reports (plus one sample clearly labelled as added by the team).
- **Sandbox replica** for filings; CPGRAMS/RTI locked until a real partnership.
- The pothole model can miss or mis-mark; the texture heuristic can raise urgency on very rough roads; the officer
  always sees the photo.
- Face blurring catches most clear faces, not all; **number plates are not blurred**.
- Ward maps cover Bengaluru and Pune; elsewhere "ward not mapped" + district.
- Translations are **machine translations, labelled**; the citizen's own words are always kept.
- Voice quality in some languages not yet reviewed by native speakers.
- Retrieval is keyword-based (no embeddings yet); scans read up to 12 pages.
- Free hosting: the Space can sleep; the explainer's cached answers live on the container's disk.

---

## 10. Likely questions — with answers

**Q: Is this RAG? Did you train any model?**
Yes, RAG: we retrieve the relevant chunks (with page numbers) and the model must quote them; code verifies each
quote. We did not fine-tune any LLM. The only model we trained is the **YOLOv8 pothole detector**.

**Q: How do you stop hallucinations?**
Three layers: (1) only official documents as input; (2) JSON-schema outputs where every point must carry an exact
quote + page; (3) code deletes any point whose quote isn't in the document. The Civic Guide answers only from
retrieved official pages, else declines.

**Q: Why Claude for the agent and Groq for other things?**
Claude Opus 5.5 is strongest at long documents, vision (scanned PDFs) and multi-step tool decisions. Groq is very
fast and cheap for short tasks — transcription, translation for officers, the chatbot.

**Q: What if the AI is tricked by text on a webpage (prompt injection)?**
The safety rules are in code, not in the prompt: allow-listed hosts only, every action checked by `_allowed()`,
the model may only type the citizen's own words, private values never reach it, and Submit/Pay need the human.

**Q: How is private data protected?**
Vault fields are encrypted (Fernet) and appear to the AI only as `{{vault.mobile}}`; evidence is in a private
bucket served only through our server; public proof photos have faces blurred and GPS removed; officer role can't be
self-assigned.

**Q: What does the signed receipt prove?**
That this exact filing (its evidence files, by SHA-256 hash) happened at that time, signed by our Ed25519 key;
anyone with the public key can verify it hasn't been altered.

**Q: How do you find the ward?**
Point-in-polygon on official ward-boundary GeoJSON using Shapely. Outside our maps we say "ward not mapped" — we
never invent one.

**Q: How do you detect duplicates?**
Same category, still open, within 50 m (Haversine distance) → linked; the original's priority goes up.

**Q: How is severity decided?**
Rules, so it's explainable: danger words → P1; pothole model > 60% or > 5% cracked surface or overflowing water → P2;
else P3; near a school/hospital (within 150 m) raises it one level. Deadline 24/48/72 h. The reason is shown.

**Q: What happens if the government website changes?**
The route fails at one step → the healer re-finds the field (first by label, without AI; then a restricted model
loop) and proposes a patch for review.

**Q: Why a "recorded route"?**
Learn once, replay fast: no AI per step → ≈10 s and 1 AI call instead of 30+ s and many calls; cheaper and more
predictable.

**Q: How does it scale / cost?**
Recorded routes and cached explanations avoid repeated AI calls; per-visitor limits; one Docker image that can run
on any container platform; Supabase is managed Postgres.

**Q: What's next?**
Open real CPGRAMS/RTI with departments; Bhashini voices for all 22 scheduled languages with native review; a helper
mode for CSC operators and NGO volunteers; alerts when a new notification affects a citizen.

**Q: How did you test it?**
112 automated tests (pytest, all passing on 3 Nov) covering the explainer's quote check, guardrails, receipts, triage, desk, translations,
face blur, accounts; 4 live tests against myScheme; and end-to-end runs on the live site (see section 11).

---

## 11. Verified on the live site (3 Nov 2026)

| Check | Result |
|---|---|
| All pages (home, report, board, desk, schemes, sign-in, agent) | load (HTTP 200) |
| Public board + stats + hotspots | working (real reports) |
| Live news | 104 headlines, trending terms |
| Judges' demo login | works |
| Photo check (YOLOv8 + OpenCV) | runs; findings also in Hindi |
| Review / routing | urgency, department, ward ("not mapped" + district), deadline |
| Voice note → text (Groq Whisper) | Hindi in Devanagari, language detected |
| Civic Guide chatbot | answers from official sources (Sanchar Saathi, RBI) |
| Agent: "book a train ticket" | refused as out of scope, no site opened |

**Demo-day checklist:** open the Space 5 minutes early (it can sleep) · use the Judges' demo tab to switch between
citizen and officer · say "sandbox replica" when the agent files · keep `CIVIC_JUDGE_DEMO=1` until judging ends,
then remove it.
