# Submission kit

Draft text for the hackathon submission form, a 2–3 minute video script and a
6-slide deck outline. Part 3's sections are complete; the `[Part 1: …]` and
`[Part 2: …]` placeholders are for your teammates to fill in. Every number here
comes from a measured run; re-measure before you submit.

## 1. Problem statement

**Target issue and context.** India runs its public services through many
separate portals: myScheme for discovery, the National Scholarship Portal,
CPGRAMS for grievances, RTI Online, and state portals. Each is a multi-step
wizard with OTPs, CAPTCHAs, strict upload limits, timeouts, and questions that
appear only after earlier answers. Citizens who most need welfare (first-time
internet users, people with limited English or literacy, older people) give up,
or pay middlemen and cyber-cafés who see their bank details. Grievances go
unfiled, and eligible people never apply.

**Target audience.** Citizens applying for schemes and scholarships or filing
grievances; the frontline helpers who assist them (CSC operators, NGO
volunteers, ward offices); and departments that want fewer incomplete
applications.

## 2. Solution description

**High-level overview.** Civic Pulse takes a citizen from "I have a problem" or
"I might be eligible" to "it is filed, here is the receipt", in their own
language, with a human approving every submission. [Part 1: the explainer turns
policy text into plain regional-language answers.] [Part 2: triage turns a
photo or voice note into a classified, routed grievance.] Part 3 is the agent
that does the paperwork: it operates the real government web portal in a
browser, asks the citizen only for what must be theirs (OTP, CAPTCHA, final
approval), and returns a signed receipt.

What makes Part 3 different from a chatbot or an RPA script:
- **AI plans once, then runs at zero model cost.** On a portal it has never seen, Claude explores screen by screen with visible reasoning; the run is recorded as a route. On live myScheme, the first AI-explored run took 36.7 s with 9 model calls; replaying the recorded route took a median 3.7 s with none, about 10 times faster.
- **Self-healing.** When a portal changes, the healer repairs the broken step and proposes a reviewed route patch. All 3 injected layout changes were recovered in testing (renamed ids with no model call; a relabelled field and a new instructions page with 1 and 2 Claude calls).
- **Never guesses for the citizen.** If a portal asks something the citizen's details do not answer, the agent hands the portal's exact question to the citizen. This was observed live on myScheme ("Please select your occupation!").
- **Guardrails enforced in code, not prompts.** The model picks where to act, never what to type; sensitive values stay in an encrypted vault; it cannot leave the portal's domains or press Submit or Pay. Prompt injection on a page is detected and logged, and an obedient model is still contained (tested).
- **Accountable.** SHA-256 evidence and an Ed25519-signed receipt; the timing panel separates agent time from the citizen's waiting time.

**Technical architecture.** Python 3.11, FastAPI, Playwright (Chromium) and
SQLite. Claude Opus 5.5 (low effort, through the Anthropic SDK with structured
outputs; served through AIML API or Anthropic's own API) is used only for
exploration and repair. The policy gate
checks consent and allow-lists, and validates PIN codes and IFSC codes live
against India Post and RBI IFSC data. The live view uses a Chrome DevTools
Protocol screencast over a WebSocket. Routes are versioned YAML. Integration is
through REST + SSE + HMAC webhooks, an MCP server and one-file SDKs. Data
sources: the live myScheme.gov.in portal, the live India Post and RBI IFSC APIs,
citizen input; a clearly labelled sandbox replica is used for filings. See the
diagrams in the README.

## 3. Prototype link
`https://<your-space>.hf.space` (see docs/DEPLOY.md). Open it a minute before judging.

## 4. Demo video (2–3 minutes, one continuous screen recording of the live system)

| Time | Show | Say |
|---|---|---|
| 0:00–0:15 | Console home | "Civic Pulse fills government portals for citizens; a human approves every submission." |
| 0:15–0:55 | myScheme service: type a PIN code (district and state fill from live India Post data), answer the questions, consent, Start. The citizen page shows the steps, then the real scheme list. | "This is the real myScheme.gov.in. The agent answers six screens, including questions that only appear after earlier answers, in about 4 to 6 seconds with zero AI calls, because it replays a route it learned earlier." |
| 0:55–1:30 | The same service with "Let the AI explore live" (needs the API key). The reasoning panel fills turn by turn. | "With no route, Claude plans each screen. It chooses where to click, never what to type. The run is saved as a new route." |
| 1:30–2:15 | Grievance filing (sandbox replica): OTP typed in the live view, CAPTCHA, the approval card (values, masked bank number, differences), Approve, reference number, signed receipt. | "Filing stops for the citizen: the OTP and CAPTCHA are typed by them, and nothing is submitted until they approve. We use a sandbox for filings, because test complaints to real ministries would be fake government records." |
| 2:15–2:45 | Scholarship with the `inject` layout: the security log shows the injected notice ignored. Optionally, a layout change repaired. | "A page told the AI to send the bank number elsewhere. It was flagged and ignored, and the rules are enforced in code." |
| 2:45–3:00 | Recent-runs board, receipt verify | "Measured, signed, and ready for Part 1 and Part 2 through REST, webhooks and MCP." |

Record it live from start to finish. Do not present a recording as if it were live during judging.

## 5. GitHub repository
Public repository with this README, diagrams, setup steps, and all source and configuration.

## 6. Deck (6 slides)
1. **Civic Pulse**: team, one-line pitch, the three parts.
2. **The problem**: the portal maze (screenshots of OTP, CAPTCHA, upload limits); who drops out.
3. **The solution**: citizen journey: ask → explain (Part 1) or report (Part 2) → file (Part 3) → receipt and tracking.
4. **Architecture and innovation**: the diagram; "AI plans once, replays forever"; guardrails in code; signed receipts.
5. **Evidence**: the measured numbers table (README), the live myScheme result, the injection test, the citizen hand-off.
6. **Roadmap and live demo**: real CPGRAMS dry runs with the citizen's own login; more state portals; DigiLocker via the API Setu sandbox; Part 4 fact verification. Then switch to the live app.

## Rules checklist

- [x] Live backend and real-time data: myScheme.gov.in, India Post and RBI IFSC lookups, citizen input. No hard-coded results.
- [x] Agentic workflow with error handling and self-correction (repair, explore, recover, human hand-off).
- [x] README with setup steps and architecture diagrams.
- [ ] Deployed URL working (build the Docker image once; see DEPLOY.md).
- [ ] API key with a spending cap set in the deployment.
- [ ] Every team member can explain the data flow (go through docs/PLAN_REVIEW.md and this file together).
- [ ] Ask the organisers whether a clearly labelled sandbox replica is acceptable for the filing step (suggested wording in docs/YOUR_TASKS.md).
