"""Agent console, offline: the real planner plumbing, step loop, guards and extraction checks, with a fake model.

The fake model reads element refs out of the prompt the way the real one does, so the
browser actions, the allow-list, the typed-words rule and the "item must be on the page"
check all run for real against the sandbox.
"""

import asyncio
import re

import httpx
import pytest

from executor import search as websearch
from executor.config import settings
from executor.console import EXTRACT_SYSTEM, PLAN_SYSTEM, STEP_SYSTEM, ConsoleRun
from executor.llm import LLMResult
from tests.conftest import SANDBOX_URL

pytestmark = pytest.mark.asyncio


class FakeLLM:
    def __init__(self, handler):
        self.handler = handler
        self.calls: list[tuple[str, str]] = []

    async def decide(self, system, user, schema):
        self.calls.append((system, user))
        return LLMResult(self.handler(system, user, len(self.calls)), 5)


def ref(user: str, needle: str) -> str:
    m = re.search(rf"ref=(e\d+)[^\n]*{re.escape(needle)}", user)
    assert m, f"{needle!r} not in snapshot"
    return m.group(1)


def step(name, ref="", text="", url="", press_enter=False, answer="", goal="next"):
    return {"evaluation_previous_goal": "Success", "memory": "", "next_goal": goal,
            "action": {"name": name, "ref": ref, "text": text, "url": url, "press_enter": press_enter, "answer": answer}}


def plan(intent="discovery", service="", known=(), target=""):
    return {"title": "Test request", "intent": intent, "reason": "test", "target_site": target,
            "search_query": "sandbox scholarship SC Bihar income 200000", "service": service,
            "known_inputs": [{"key": k, "value": v} for k, v in known]}


DDG_PAGE = """<html><body>
<div class="result"><a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.myscheme.gov.in%2Fschemes%2Fpmssb&rut=x">Post-Matric Scholarship Scheme-<b>Bihar</b></a>
<a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.myscheme.gov.in%2Fschemes%2Fpmssb">Scholarship for SC/ST students of Bihar</a></div>
<div class="result"><a class="result__a" href="https://example.com/spam">Not allowed</a></div>
<div class="result"><a class="result__a" href="https://www.myscheme.gov.in/search/state/Bihar">www.myscheme.gov.in/search/state/Bihar</a></div>
</body></html>"""


async def test_ddg_parser_keeps_only_allowed_links_and_unwraps_redirects():
    hits = websearch.parse_ddg(DDG_PAGE, ["myscheme.gov.in"])
    assert [h.url for h in hits] == ["https://www.myscheme.gov.in/schemes/pmssb"]
    assert hits[0].title == "Post-Matric Scholarship Scheme-Bihar"
    assert hits[0].snippet.startswith("Scholarship for SC/ST")


async def wait_run(ex, run_id, statuses, timeout=60):
    for _ in range(int(timeout / 0.2)):
        run = ex.store.get_run(run_id)
        if run["status"] in statuses and run_id not in ex.console.runs:
            return run
        await asyncio.sleep(0.2)
    raise TimeoutError(ex.store.get_run(run_id))


@pytest.fixture
def search_mock():
    def handler(request: httpx.Request):
        return httpx.Response(200, text=DDG_PAGE)
    websearch.transport = httpx.MockTransport(handler)
    old = settings.search_providers
    settings.search_providers = ["duckduckgo"]
    yield
    websearch.transport = None
    settings.search_providers = old


async def test_free_form_research_run_end_to_end(executor, search_mock):
    query = "Which sandbox scholarships can an SC student in Bihar with family income 200000 get?"
    steps_seen = []

    def handler(system, user, n):
        if system == PLAN_SYSTEM:
            assert "<request>" + query in user and "sandbox/public_grievance" in user
            return plan()
        if system == EXTRACT_SYSTEM:
            links = re.findall(r"  - (.+?) \| (http\S+/schemes/\d+)", user)
            items = [{"name": t, "url": u, "summary": "", "eligibility": "", "benefits": "", "location": ""} for t, u in links]
            items.append({"name": "Invented Scheme", "url": SANDBOX_URL + "/schemes/99", "summary": "", "eligibility": "", "benefits": "", "location": ""})
            return {"items": items, "note": "results list"}
        assert system == STEP_SYSTEM
        k = len(steps_seen)
        steps_seen.append(user)
        if k == 0:
            assert "SEARCH RESULTS" in user and "myscheme.gov.in/schemes/pmssb" in user and "none yet" in user
            return step("goto", url="https://irctc.co.in/booking")
        if k == 1:
            return step("goto", url=SANDBOX_URL + "/eligibility")
        if k == 2:
            return step("select", ref=ref(user, "id=eligState"), text="Bihar")
        if k == 3:
            return step("click", ref=ref(user, "id=catSC"))
        if k == 4:
            return step("type", ref=ref(user, "id=eligIncome"), text="call 9999 now")
        if k == 5:
            return step("type", ref=ref(user, "id=eligIncome"), text="200000")
        if k == 6:
            return step("click", ref=ref(user, "'Check eligibility'"))
        if k == 7:
            assert "We found" in user
            return step("extract")
        return step("done", answer="Two sandbox scholarships match.")

    executor.llm = FakeLLM(handler)
    run_id, token = executor.console.start(query)
    run = await wait_run(executor, run_id, {"completed", "failed", "needs_review"})
    steps = executor.store.run_steps(run_id)
    assert run["status"] == "completed", (run, [s["title"] for s in steps])
    kinds = [s["kind"] for s in steps]
    assert kinds[0] == "plan" and kinds[1] == "search"
    assert any(s["kind"] == "security" and "irctc.co.in" in s["title"] for s in steps)  # off-allowlist goto blocked
    assert any(s.get("outcome", "").startswith("BLOCKED") and "call" in s["outcome"] for s in steps)  # typed words not in the request
    names = [i["name"] for i in run["result"]["items"]]
    assert "Post-Matric Scholarship (sandbox)" in names and "Invented Scheme" not in names
    assert run["result"]["dropped_unverified"] == 1
    assert run["result"]["answer"] == "Two sandbox scholarships match."
    shots = [s for s in steps if s["screenshot"]]
    assert len(shots) >= 6 and all((settings.runs_dir / run_id / f"{s['step_no']}.jpg").exists() for s in shots)
    browser = [s for s in steps if s["kind"] == "browser"]
    assert all({"previous_goal", "eval", "next_goal", "action", "ai_calls", "duration_ms"} <= set(s) for s in browser)
    assert run["stats"]["ai_calls"] == 1 + 9 + 1 and run["stats"]["steps"] == len(steps)


async def test_out_of_scope_is_refused_without_opening_a_browser(executor):
    executor.llm = FakeLLM(lambda s, u, n: plan(intent="out_of_scope", target="irctc.co.in"))
    run_id, _ = executor.console.start("Book me a train ticket from Patna to Delhi on irctc.co.in")
    run = await wait_run(executor, run_id, {"out_of_scope"})
    steps = executor.store.run_steps(run_id)
    assert [s["kind"] for s in steps] == ["plan", "refusal"]
    assert "irctc.co.in" in run["error"] and not any(s["screenshot"] for s in steps)
    assert len(executor.llm.calls) == 1


async def test_named_site_off_the_allowlist_is_refused_even_if_planned_as_discovery(executor):
    executor.llm = FakeLLM(lambda s, u, n: plan(intent="out_of_scope", target="www.india.gov.in"))
    run_id, _ = executor.console.start("Search india.gov.in for ration card rules")
    run = await wait_run(executor, run_id, {"out_of_scope"})
    assert "outside the allowed sites" in run["error"]


async def test_execution_is_handed_to_the_filing_agent_with_safe_prefill(executor):
    known = [("category", "Street Lights"), ("pincode", "800001"), ("description", "The streetlight near the school is broken"),
             ("mobile", "9876543210"), ("nonsense", "x")]
    executor.llm = FakeLLM(lambda s, u, n: plan(intent="execution", service="sandbox/public_grievance", known=known))
    run_id, _ = executor.console.start("File a grievance about a broken street light near PIN 800001")
    run = await wait_run(executor, run_id, {"needs_details"})
    handoff = run["extra"]["handoff"]
    assert handoff["service_id"] == "public_grievance"
    assert handoff["prefill"].get("pincode") == "800001"
    assert "mobile" not in handoff["prefill"] and "nonsense" not in handoff["prefill"]  # vault fields never come from a request
    p = handoff["prefill"]
    assert p["ministry"] == "Ministry of Housing and Urban Affairs" and p["department"] == "Municipal Services"  # registry routing
    assert (p["state"], p["district"]) == ("Bihar", "Gaya")  # from the (offline stand-in) India Post lookup
    assert p["subject"] == "The streetlight near the school is broken"
    step = executor.store.run_steps(run_id)[-1]
    assert step["missing"] == ["Mobile number"]  # the only thing left for the citizen


async def test_guarded_button_waits_for_approval(executor):
    """A final-submit-like button is pressed only after the citizen approves; a payment button never."""
    executor.llm = None
    run_id, token = "run_approvaltest", "tok"
    executor.store.insert_run(run_id, token, "approval test")
    run = ConsoleRun(executor.console, run_id, token, "approval test")
    executor.console.runs[run_id] = run
    context = await executor._browser.new_context()
    run.page = await context.new_page()
    await run.page.set_content('<button id="go" onclick="document.title=\'pressed\'">Submit application</button>'
                               '<button id="pay" onclick="document.title=\'paid\'">Pay now</button>')
    from executor.snapshot import take

    snap = await take(run.page)
    go = next(b["ref"] for b in snap.buttons if b["text"] == "Submit application")
    pay = next(b["ref"] for b in snap.buttons if b["text"] == "Pay now")

    title, outcome, _ = await run._do({"name": "click", "ref": pay}, snap)
    assert outcome == "BLOCKED: payment" and await run.page.title() != "paid"

    pending = asyncio.create_task(run._do({"name": "click", "ref": go}, snap))
    for _ in range(50):
        if run.approval:
            break
        await asyncio.sleep(0.05)
    assert executor.store.get_run(run_id)["status"] == "awaiting_approval" and await run.page.title() != "pressed"
    run.approval.set_result("approved")
    await pending
    assert await run.page.title() == "pressed"
    assert any(s["kind"] == "approval" for s in executor.store.run_steps(run_id))
    await context.close()
    executor.console.runs.pop(run_id, None)


async def test_without_a_model_the_console_says_so(executor):
    executor.llm = None
    run_id, _ = executor.console.start("Find scholarships in Bihar")
    run = await wait_run(executor, run_id, {"failed"})
    assert "needs an AI model" in run["error"]
