"""Part 1 explainer, offline: quote verification, allow-listed fetching, translation mapping, honest fallbacks."""

import os
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from executor import explainer as E
from executor.llm import LLMResult

pytestmark = pytest.mark.asyncio

NOTICE = """GOVERNMENT OF EXAMPLE STATE - Department of Social Welfare
Notification No. SW/12/2026 dated 1 October 2026
1. Every widow aged 40 years or above whose family income is below Rs. 1,00,000 per annum shall be entitled to a pension of Rs. 1,500 per month.
2. Applications shall be submitted at the Block Development Office before 31 December 2026.
3. Shops and small enterprises employing widows shall receive a wage subsidy of 10 per cent for two years.
""" * 2  # long enough to be a real notice


class FakeLLM:
    def __init__(self):
        self.calls = []

    async def decide(self, system, user, schema, max_tokens=4000):
        self.calls.append((system, user, max_tokens))
        if system == E.REASON_SYSTEM:
            return LLMResult({
                "title": "Widow pension notification", "issuer": "Department of Social Welfare", "date": "1 October 2026",
                "doc_type": "notification", "summary": "Widows aged 40+ with low income get Rs. 1,500 a month.",
                "answer": "Yes, if your family income is below Rs. 1,00,000.",
                "rights": [{"text": "A monthly pension of Rs. 1,500.", "quote": "shall be entitled to a pension of Rs. 1,500 per month"},
                           {"text": "Free bus travel.", "quote": "widows shall travel free on state buses"}],  # not in the document
                "eligibility": [{"text": "Aged 40 or above", "quote": "aged 40 years or above", "met": "yes", "note": "You are 45."}],
                "impacts_citizens": [], "impacts_business": [{"text": "10% wage subsidy for two years.", "quote": "wage subsidy of 10 per cent for two years"}],
                "deadlines": [{"text": "Apply before 31 December 2026.", "quote": "before 31 December 2026"}], "how_to_act": [],
            }, 5)
        items = __import__("json").loads(user)["items"]
        return LLMResult({"items": [{"id": i["id"], "text": "HI:" + i["text"]} for i in items if i["id"] != "summary"],
                          "voice_script": "HI script"}, 5)


def tts_failing(request: httpx.Request):
    return httpx.Response(500, json={"error": "down"})


@pytest.fixture
def svc(tmp_path, monkeypatch):
    from executor.config import settings
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setenv("AIMLAPI_KEY", "test-key")
    E.transport = httpx.MockTransport(tts_failing)
    yield E.Explainer(SimpleNamespace(llm=FakeLLM(), _browser=None))
    E.transport = None


async def test_explain_keeps_only_quoted_points_and_translates(svc):
    doc = svc._save("Widow pension", "pasted_text", None, [NOTICE])
    out = await svc.explain(doc["doc_id"], "I am a 45-year-old widow", "hi-IN")
    assert [r["text"] for r in out["rights"]] == ["HI:A monthly pension of Rs. 1,500."]  # the invented right is gone
    assert out["dropped_unverified"] == 1
    assert out["rights"][0]["quote"] == "shall be entitled to a pension of Rs. 1,500 per month"  # quotes stay in the original
    assert out["rights"][0]["page"] == 1
    assert out["eligibility"][0]["met"] is True and out["eligibility"][0]["note"] == "HI:You are 45."
    assert out["impacts"]["business"][0]["text"].startswith("HI:")
    assert out["summary"] == "Widows aged 40+ with low income get Rs. 1,500 a month." and out["untranslated"] == 1  # missed line stays English
    assert out["audio_url"] is None and out["voice_provider"].startswith("device voice")  # TTS down: says so, no fake audio
    assert out["timing"]["ai_calls"] == 2
    again = await svc.explain(doc["doc_id"], "I am a 45-year-old widow", "hi-IN")
    assert again["cached"] is True and len(svc.ex.llm.calls) == 2
    view = svc.latest.view()
    assert [n["status"] for n in view["nodes"]][-3:] == ["done", "done", "idle"]


async def test_no_model_and_no_document_are_refused_honestly(svc):
    svc.ex.llm = None
    doc = svc._save("x", "pasted_text", None, [NOTICE])
    with pytest.raises(HTTPException) as e:
        await svc.explain(doc["doc_id"], "", "hi-IN")
    assert e.value.status_code == 503
    with pytest.raises(HTTPException):
        svc._save("tiny", "pasted_text", None, ["too short"])
    with pytest.raises(HTTPException):
        svc.load("../../etc/passwd")


async def test_links_must_stay_on_government_hosts(svc):
    for bad in ["https://example.com/notice.pdf", "http://127.0.0.1:8000/x", "https://gov.in.evil.com/x"]:
        with pytest.raises(HTTPException) as e:
            await svc.from_url(bad)
        assert e.value.status_code == 400

    def redirecting(request: httpx.Request):
        return httpx.Response(302, headers={"location": "https://evil.example/steal"})
    E.transport = httpx.MockTransport(redirecting)
    with pytest.raises(HTTPException) as e:
        await svc.from_url("https://www.example.gov.in/notice")
    assert "evil.example" in e.value.detail  # every redirect hop is checked

    def page(request: httpx.Request):
        return httpx.Response(200, headers={"content-type": "text/html"},
                              text=f"<html><title>Notice</title><body><script>x()</script><p>{NOTICE}</p></body></html>")
    E.transport = httpx.MockTransport(page)
    doc = await svc.from_url("https://socialwelfare.example.nic.in/notice")
    assert doc["title"] == "Notice" and doc["source"] == "web_page" and "x()" not in svc.load(doc["doc_id"])["pages"][0]


async def test_long_documents_keep_the_relevant_parts():
    filler = ["Annexure table row " * 100] * 60
    parts = E.chunks(["Title page"] + filler + ["The widow pension shall be Rs. 1,500 per month for eligible applicants."])
    picked = E.retrieve(parts, "widow pension amount", budget=8000)
    assert picked[0][0] == 1 and any("widow pension" in t for _, t in picked) and sum(len(t) for _, t in picked) <= 8000


def scanned_pdf(pages: int = 2) -> bytes:
    """A real image-only PDF (no text layer), like a scanned gazette page."""
    import io

    from PIL import Image, ImageDraw
    imgs = []
    for i in range(pages):
        im = Image.new("L", (600, 300), 255)
        ImageDraw.Draw(im).text((20, 20), f"Scanned page {i + 1}", fill=0)
        imgs.append(im)
    buf = io.BytesIO()
    imgs[0].save(buf, "PDF", save_all=True, append_images=imgs[1:])
    return buf.getvalue()


class OcrLLM(FakeLLM):
    async def decide(self, system, user, schema, max_tokens=4000, images=None):
        if system == E.OCR_SYSTEM:
            self.calls.append((system, user, len(images or [])))
            first = int(user.split("pages ")[1].split(" ")[0])
            return LLMResult({"pages": [{"page": first + i, "text": NOTICE} for i in range(len(images))]}, 5)
        return await super().decide(system, user, schema, max_tokens)


async def test_scanned_pdf_is_read_from_page_images_and_charged(svc):
    svc.ex.llm = OcrLLM()
    charged = []
    meta = await svc.pdf_doc(scanned_pdf(4), "scan.pdf", "pdf_upload", None, lambda: charged.append(1))
    assert meta["ocr"] == {"pages_read": 4, "pages_total": 4, "reason": "scanned"} and meta["source"] == "pdf_upload_scan"
    assert [c[2] for c in svc.ex.llm.calls] == [3, 1]  # pages go three at a time
    assert charged == [1]  # reading a scan counts against the visitor's limit
    out = await svc.explain(meta["doc_id"], "", "en-IN")
    assert out["doc"]["ocr"]["reason"] == "scanned" and out["rights"]


async def test_scan_without_a_model_is_refused(svc):
    svc.ex.llm = None
    with pytest.raises(HTTPException) as e:
        await svc.pdf_doc(scanned_pdf(1), "scan.pdf", "pdf_upload", None)
    assert e.value.status_code == 503


async def test_indian_script_share():
    assert E.indic_share("प्रधान मंत्री जीवन ज्योति बीमा योजना") > 0.9
    assert E.indic_share("Pradhan Mantri scheme with one word योजना in Hindi") < 0.3
    assert E.indic_share("") == 0.0


async def test_apply_offers_only_real_services(svc):
    from executor.registry import Registry
    from executor.console import ConsoleManager
    reg = Registry()
    fake = SimpleNamespace(registry=reg)
    svc.ex.console = ConsoleManager(fake)
    offered = svc._services()
    assert "myscheme/find_schemes" in offered and "sandbox/public_grievance" in offered
    assert not any(s["portal"].is_sandbox and s["route"].read_only for s in offered.values())  # sandbox test lookups are hidden
    assert svc._apply("myscheme/find_schemes")["label"].startswith("Find every scheme you qualify for on myScheme")
    assert svc._apply("sandbox/public_grievance")["label"] == "Apply with the agent (sandbox replica)"
    assert svc._apply("sandbox/eligibility_check") is None and svc._apply("") is None


async def test_runs_are_limited_per_visitor(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from executor.config import settings
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setenv("CIVIC_EXPLAINS_PER_HOUR", "2")
    llm = FakeLLM()
    app = FastAPI()
    app.include_router(E.make_explainer_router(lambda: SimpleNamespace(llm=llm, _browser=None)))
    E.transport = httpx.MockTransport(tts_failing)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            doc = (await c.post("/app/part1/api/documents", data={"text": NOTICE})).json()
            codes = []
            for q in ["a?", "b?", "c?"]:
                codes.append((await c.post("/app/part1/api/explain", json={"doc_id": doc["doc_id"], "question": q, "language": "en-IN"})).status_code)
            assert codes == [200, 200, 429]
            again = await c.post("/app/part1/api/explain", json={"doc_id": doc["doc_id"], "question": "a?", "language": "en-IN"})
            assert again.status_code == 200 and again.json()["cached"] is True  # a cached answer costs nothing
    finally:
        E.transport = None


async def test_headings_are_translated_with_the_answer(svc):
    doc = svc._save("Widow pension", "pasted_text", None, [NOTICE])
    out = await svc.explain(doc["doc_id"], "", "ta-IN")
    assert out["labels"]["rights"] == "HI:Your rights" and out["labels"]["what_to_do"] == "HI:What to do"
    assert out["untranslated"] == 1  # only the content line the fake skipped; headings are not counted


class LangLLM(FakeLLM):
    async def decide(self, system, user, schema, max_tokens=4000, images=None):
        out = await super().decide(system, user, schema, max_tokens)
        if system == E.REASON_SYSTEM:
            assert "question_language" in schema["properties"]
            out.data["question_language"] = "ta-IN"
        return out


async def test_answer_follows_the_question_language_only_when_not_chosen(svc):
    svc.ex.llm = LangLLM()
    doc = svc._save("Widow pension", "pasted_text", None, [NOTICE])
    auto = await svc.explain(doc["doc_id"], "எனக்கு ஓய்வூதியம் கிடைக்குமா?", "hi-IN", auto_language=True)
    assert auto["language"] == "ta-IN" and auto["language_from_question"] is True
    chosen = await svc.explain(doc["doc_id"], "எனக்கு ஓய்வூதியம் கிடைக்குமா?", "hi-IN")
    assert chosen["language"] == "hi-IN" and chosen["language_from_question"] is False


def stt_service(captured: list):
    def handler(request: httpx.Request):
        if request.url.path.endswith("/v1/stt/create"):
            captured.append(request.content)
            return httpx.Response(201, json={"generation_id": "job1", "status": "queued"})
        if request.url.path.endswith("/v1/stt/job1"):
            return httpx.Response(200, json={"status": "completed", "result": {"results": {"channels": [
                {"detected_language": "ta", "alternatives": [{"transcript": " எனக்கு ஓய்வூதியம் கிடைக்குமா "}]}]}}})
        return httpx.Response(404)
    return httpx.MockTransport(handler)


async def test_voice_question_is_transcribed_and_its_language_found(svc):
    sent: list = []
    E.transport = stt_service(sent)
    detected = await svc.transcribe(b"\x1aE\xdf\xa3" + b"0" * 2000, "audio/webm", None)
    assert detected == {"text": "எனக்கு ஓய்வூதியம் கிடைக்குமா", "language": "ta-IN"}
    assert b"detect_language" in sent[-1] and b"#g1_whisper-large" in sent[-1]
    await svc.transcribe(b"0" * 2000, "audio/webm", "hi-IN")
    assert b'name="language"\r\n\r\nhi' in sent[-1] and b"detect_language" not in sent[-1]


async def test_voice_question_needs_a_key_and_short_audio(svc, monkeypatch, tmp_path):
    monkeypatch.delenv("AIMLAPI_KEY")
    with pytest.raises(HTTPException) as e:
        await svc.transcribe(b"0" * 2000, "audio/webm", None)
    assert e.value.status_code == 503
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(E.make_explainer_router(lambda: svc.ex))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        big = await c.post("/app/part1/api/transcribe", files={"audio": ("q", b"0" * (E.MAX_AUDIO_BYTES + 1), "audio/webm")})
        assert big.status_code == 413
        wrong = await c.post("/app/part1/api/transcribe", files={"audio": ("q", b"0" * 2000, "text/plain")})
        assert wrong.status_code == 415
