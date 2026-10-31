# Your tasks (Part 3 owner and integrator)

Part 3 is built and tested: offline tests, plus live tests against the real
myScheme portal and the India Post and IFSC APIs. What is left needs you:
keys, a deployment, team decisions, rehearsal.

## Today

1. **Push to a branch** with the Antigravity prompt, never to `main`.
2. **AI key: done.** Your AIML API key is in `.env` (git-ignored) and the real-model eval passed. Before the final
   submission, re-run `uv run python scripts/eval.py --llm` and put only those numbers in the deck. Set
   `AIMLAPI_KEY` as a secret in the deployment; never commit `.env`.
3. **Deploy** following `docs/DEPLOY.md` (Hugging Face Space, Docker). Build the image once; it has not been built yet.
4. **Phone test** of the deployed URL: one myScheme lookup, then one grievance with OTP, CAPTCHA and approval done on the phone.

## Ask the organisers (one message)

> We automate Indian government portals. For read-only services we run on the real portal (myScheme.gov.in) with live data.
> For filings we use a clearly labelled sandbox replica, because test applications on real portals would create fake government records.
> Is the sandbox acceptable for the filing step, as long as the data flow is live?

## Team decisions (10 minutes, all three of you)

- Part 1 uses `find_schemes` (SDK or MCP) for live eligibility, then explains the results in the citizen's language.
- Part 2 sends grievances to `sandbox/public_grievance` with its issue id as `origin_ref`, and listens for the receipt webhook.
- Agree `CIVIC_API_KEY` and `CIVIC_WEBHOOK_SECRET` (long random strings, shared privately).
- Each person can explain the data flow on their own: go through the README diagram and `docs/SUBMISSION.md` together.
- Ask whoever wrote the plan for section 4 (languages) and Appendix A; the PDF stops at 3.9.

## Integration (your job)

- Run both loops end to end once a day. `scripts/demo.py` is a reference client; the console is the citizen view.
- The Part 2 dashboard can show our `/app/runs` board, or subscribe to SSE events.

## Optional, if time allows

- CPGRAMS dry run with **your own** login: record it with `uv run playwright codegen https://pgportal.gov.in`, stop before submit, fill `registry/cpgrams/lodge_grievance.route.yaml`, keep `submission_enabled: false`.
- Add a state portal for Part 1's schemes through explore mode, then review the draft route it records.

## Demo rules (they decide the 30 robustness points)

- The demo must be live. A recording may only be shown as a labelled backup, never as the live run (that is a disqualification ground).
- Open the deployed URL a minute before, because free hosts sleep.
- Say "assisted filing: a human approves every submission". Never say "fully autonomous", "works on NSP", "DigiLocker integration", "DPDP compliant" or "government-verified receipt".
- For the "portal changed" and "injection" moments, switch the sandbox layout (needs the API key):
  ```bash
  curl -X POST $URL/v1/admin/sandbox-variant -H "X-API-Key: $KEY" -H "Content-Type: application/json" -d '{"variant":"inject"}'
  ```
  Set it back to `{"variant":"default"}` afterwards.
