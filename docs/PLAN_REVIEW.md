# Review of "Civic Pulse — Build Plan (Part 3 in depth)"

The plan is mostly sound: assisted filing with a human approving every submit,
a deterministic route runner first, a model only for repair, and sensitive values
kept out of the model. These are the right calls. Below is what I changed or
added while building Part 3, and why.

## 1. The PDF is incomplete

It stops at section 3.9 (page 11 holds one line). These parts are referenced but missing:

- 3.10 receipt engine, 3.11 document prep, 3.12 canary test, 3.13–3.16 (including the 3-day squeeze in 3.16)
- Section 4 (speech coverage and demo languages). Part 1 needs this.
- Appendix A (contract examples)

Part 3 now covers 3.10, 3.11, 3.12 and the eval runner (3.14) in code. Ask
whoever produced the plan for section 4 and Appendix A, or have Part 1 write
section 4. The contracts are now in `/contracts`, generated from code.

## 2. Corrections (the plan says something that is not true or not safe)

| Plan says | Problem | What we do instead |
|---|---|---|
| With the live view, "the OTP or CAPTCHA answer never passes through our code or the model" | A CDP live view relays the citizen's keystrokes through our server into the browser. They do pass through our code. | Say: "never stored, never logged, never shown to the model." That is what the code does (`executor/handoff.py`). |
| "Save a Playwright trace for every run" | Traces contain DOM snapshots with the typed values (bank number, phone). That breaks rule 2. | Traces are on for the mock portal only. Live portals need `CIVIC_TRACE_LIVE=1`. |
| "Never retry a submit automatically" with no other path | A mistyped CAPTCHA makes the portal reject the submit. Every typo would end in needs_review. | Routes declare `recover:` only for errors that prove nothing was filed (e.g. "Invalid CAPTCHA"). The agent goes back, the citizen retypes and approves again. Anything else after a submit goes to needs_review with "Do NOT resubmit". |
| S1 shows a live CPGRAMS filing in the demo | Each filing is a real grievance sent to a real ministry, and needs a real phone OTP. A demo filing is a fake complaint to the government. | Demo Loop A on the mock portal (CPGRAMS-style flow). CPGRAMS is in the registry as `draft`, with `submission_enabled: false`. |
| S2 RTI Online as a service | Real legal request with a ₹10 payment. Cannot be tested at all. | Registry entry with submission disabled. Drop it from the demo or mention it as roadmap. |

## 3. Changes that improve accuracy or reduce risk

**Tier 2: our own small healer instead of browser-use.** The plan wraps
browser-use. I did not, for four reasons:

1. browser-use acts on element indexes. The plan's healing loop needs the repair
   as a route patch with stable locators. Converting browser-use history into
   stable locators is the hard part, and the plan skips it.
2. Its API changes often between releases (custom actions, controller). That is
   a demo-day risk.
3. The safety rules are easiest to guarantee in a loop we own: the model picks
   where to act, never what to type; it cannot navigate; it cannot press a
   final-submit or payment button; it cannot use a field that belongs to another
   step. These are enforced in code (`Healer._allowed`), so they hold even when
   the model follows an injected instruction. A test proves it
   (`test_obedient_model_is_contained_by_policy`).
4. The planner/actor/validator split: the route already is the plan, and the
   validator is the step's deterministic postcondition. That is more accurate
   than a model validator, and free.

Healing runs in two stages: a heuristic label match first (no model call;
fixes renamed ids), then the model. Every action is checked against the step's
postcondition before it counts.

**SQLite instead of Postgres for Part 3.** One process, zero setup, same
behaviour. Postgres is only worth it if several executor processes share one
queue.

**Contracts:** Pydantic models are the source of truth and are exported to JSON
Schema (`scripts/export_contracts.py`). Part 2 can generate TypeScript from those
files. This is one tool fewer than "JSON Schema generates Python and TS".

**Drift check:** instead of skipping Tier 1 entirely when more than 30% of a
page's fields are missing, Tier 1 probes each locator for 1.5 s, then hands over
to Tier 2. Fields that still match keep working, and nothing waits 20 s.

**Snapshot masking:** the plan masks vault-owned values. We mask all values
(the model only sees "filled" or empty). The model never needs a value.

**Stale error banners:** after clicking Submit, the old page's error banner can
still be on screen for a moment and be read as the new result. The runner marks
the document before each click and ignores an identical banner on the same
document.

**Crash safety:** if the executor restarts mid-task, the task goes to
needs_review. It is never resumed automatically, because it might be past the
submit click.

## 4. Things the plan claims that you must measure, not quote

- "Tier 2 recovers from at least two of three injected layout changes." Measured:
  3 of 3 with Claude Opus 5.5 through AIML API (the label match alone recovers 1 of 3).
- All speed numbers: use `reports/eval-*.md`, which separates agent time from
  the citizen's waiting time.
- Vendor numbers (Skyvern, Stagehand) stay labelled as vendor claims.

## 5. Facts I did not re-check in this session

The plan's [Verified] items (NSP Aadhaar face authentication, CPGRAMS flow, RTI
fee and gateway, DPDP Rules dates, API Setu sandbox terms) match my background
knowledge, but I did not open the sources again. Before any of them goes on a
slide, have one person open the source and paste the link into the deck notes.

## 6. Changes after reading the hackathon rules

The rules disqualify "fake, static, or hardcoded mock data instead of a live
backend". The plan's demo leaned on a portal we built and labelled "MOCK", plus
synthetic personas. That is a real risk, so:

- **A real portal runs live.** The myScheme.gov.in eligibility questionnaire (public, no login, files nothing) is now a stable route. The agent returns the portal's own results. Mapping it surfaced real-portal behaviour the mock never had: radio buttons hidden behind labels, dropdowns that fill after load, questions that appear only after earlier answers, a button whose accessible name differs from its text, a framework announcer using `role="alert"`, and empty results. All are handled and covered by live tests.
- **Live public data replaces static lists in the citizen path.** PIN codes are checked against India Post data and IFSC codes against RBI data, both in real time, with a graceful fallback when a service is down.
- **Citizens type their own details** in the console. Personas only exist in `tests/fixtures/` for automated tests.
- **The filing portal is a sandbox replica**, named and bannered as such. Filing test applications on real portals would create fake government records. Ask the organisers to confirm this is acceptable (wording in YOUR_TASKS.md).
- **AI reasoning is now visible.** Explore mode lets Claude plan a portal it has never seen, shows its reasoning per turn, and records the run as a route that later replays without the model. This answers the "AI reasoning and agentic execution" criterion without giving up the plan's deterministic-first design.
- **Integration surface for teammates:** an MCP server, Python and JS SDKs, and a public console that doubles as the hosted prototype.

## 7. Ideas taken (not code) from the reference repos

| Repo | Idea | Where |
|---|---|---|
| browser-use | Several actions per model call, stopping the batch when the page changes; data-grounding rule; MCP server | `explorer.py` batch + page-change break; results read from the page, not the model; `mcp_server.py` |
| LaVague | Retrieve only the page elements relevant to the goal; swappable engines | `Snapshot.focus()`; `engines.py` |
| WebVoyager | Text-only page tree; short history; stuck detection | snapshot format; last-12 history; "page has not changed" nudges |
| playwright-ai-integration | Turn an AI run into a reusable script | explorer records a YAML route with generalised locators |
| awesome-web-agents (Steel, Stagehand, Skyvern) | Live view for human steps; cached replay as the speed lever | `handoff.py` live view; Tier 1 replay |

## 8. Not built yet (deliberately)

- Recon on the real CPGRAMS portal (needs a human with their own account).
- Exploration mode (the model drafting a route for a brand-new portal). Record
  new routes with `playwright codegen` instead, as the plan itself suggests.
- DigiLocker / API Setu sandbox (optional S0).
- The model paths (repair and explore) were measured once with the real model
  (see `reports/`); CI still uses scripted stand-ins so it needs no key.
