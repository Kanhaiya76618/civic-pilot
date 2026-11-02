"""Report a problem, after filing: English for the desk, blurred public proof, the citizen's word on the repair, hotspots."""

import random
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

import server.api as api
from server.auth import create_access_token
from server.db import SessionLocal, User
from server.privacy import blur_faces

SAMPLE_WITH_FACES = Path(cv2.__file__).parents[1] / "ultralytics" / "assets" / "zidane.jpg"  # ships with ultralytics


def png(w=320, h=240) -> bytes:
    img = np.full((h, w, 3), 180, np.uint8)
    cv2.rectangle(img, (40, 40), (200, 160), (60, 60, 60), -1)
    return cv2.imencode(".png", img)[1].tobytes()


@pytest.fixture(scope="module")
def client():
    from executor.api import make_app
    with TestClient(make_app()) as c:
        yield c


@pytest.fixture(scope="module")
def admin(client):
    return {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={"email": "admin@demo.in"}).json()["access_token"]}


def citizen_headers() -> dict:
    """A fresh citizen of their own, so tests never act on someone else's reports."""
    db = SessionLocal()
    try:
        user = User(id=str(uuid.uuid4()), email=f"c{uuid.uuid4().hex[:10]}@example.test", name="Test Citizen", role="citizen",
                    created_at=datetime.now(timezone.utc))
        db.add(user)
        db.commit()
        return {"Authorization": "Bearer " + create_access_token({"sub": user.id, "email": user.email, "role": "citizen"})}
    finally:
        db.close()


@pytest.fixture
def fake_translator(monkeypatch):
    calls = []

    async def english_version(text, voice=None, media_type="audio/webm", transcript=None):
        calls.append((text, voice, transcript))
        if not voice and not transcript and not api.needs_english(text):
            return None
        return {"language": "hi-IN", "language_name": "Hindi", "english": "The streetlight near the school has been off for ten days.",
                "transcript": "स्कूल के पास की लाइट बंद है" if voice else None, "spoken_language": "hi-IN" if voice else None,
                "machine_translated": True}

    monkeypatch.setattr(api, "english_version", english_version)
    return calls


def file_report(client, who, description="Streetlight off near the school for ten days.", voice=None):
    lat, lng = 18.5065 + random.uniform(-0.01, 0.01), 73.829 + random.uniform(-0.01, 0.01)
    files = {"voice": ("voice-note.webm", voice, "audio/webm")} if voice else None
    r = client.post("/api/v1/reports", headers=who, files=files,
                    data={"category": "streetlights", "description": description, "latitude": lat, "longitude": lng})
    assert r.status_code == 200, r.text
    return r.json()


def resolve(client, admin, report_id, photo=None):
    r = client.post(f"/api/v1/admin/reports/{report_id}/resolve", headers=admin, data={"resolution_notes": "Lamp replaced."},
                    files={"proof_photo": ("proof.png", photo or png(), "image/png")})
    assert r.status_code == 200, r.text
    return r.json()


def queue_item(client, admin, report_id):
    return next(x for x in client.get("/api/v1/admin/queue", headers=admin).json() if x["id"] == report_id)


# ------------------------------------------------------------------ privacy
def test_public_proof_photos_have_faces_blurred_and_no_metadata():
    out, n = blur_faces(png())
    assert n == 0 and out[:2] == b"\xff\xd8"  # still re-encoded: metadata gone
    if not SAMPLE_WITH_FACES.exists():
        pytest.skip("sample photo with faces is not installed")
    out, n = blur_faces(SAMPLE_WITH_FACES.read_bytes())
    assert n >= 2
    original = cv2.imread(str(SAMPLE_WITH_FACES))
    blurred = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)
    assert blurred.shape == original.shape and not np.array_equal(blurred, original)


def test_resolving_blurs_the_proof_and_rejects_unreadable_photos(client, admin, fake_translator):
    me = citizen_headers()
    rep = file_report(client, me)
    bad = client.post(f"/api/v1/admin/reports/{rep['id']}/resolve", headers=admin, data={"resolution_notes": "x"},
                      files={"proof_photo": ("proof.png", b"\x89PNG not really", "image/png")})
    assert bad.status_code == 400
    photo = SAMPLE_WITH_FACES.read_bytes() if SAMPLE_WITH_FACES.exists() else png()
    done = resolve(client, admin, rep["id"], photo)
    assert done["faces_blurred"] >= (2 if SAMPLE_WITH_FACES.exists() else 0)
    served = client.get(done["resolution_proof_url"])
    assert served.status_code == 200 and served.content[:2] == b"\xff\xd8" and served.content != photo


# ------------------------------------------------------------------ the citizen's word on a repair
def test_citizen_confirms_the_repair_and_the_board_shows_it(client, admin, fake_translator):
    me = citizen_headers()
    rep = file_report(client, me)
    assert client.post(f"/api/v1/reports/{rep['id']}/confirm", headers=me).status_code == 409  # not resolved yet
    resolve(client, admin, rep["id"])
    mine = next(r for r in client.get("/api/v1/me/reports", headers=me).json() if r["id"] == rep["id"])
    assert mine["awaiting_your_check"] and mine["resolution_notes"] == "Lamp replaced."

    assert client.post(f"/api/v1/reports/{rep['id']}/confirm", headers=citizen_headers()).status_code == 404  # not theirs
    assert client.post(f"/api/v1/reports/{rep['id']}/confirm", headers=me).json()["citizen_verdict"] == "confirmed"
    assert client.post(f"/api/v1/reports/{rep['id']}/confirm", headers=me).status_code == 409  # only once

    board = next(r for r in client.get("/api/public/reports").json() if r["id"] == rep["id"])
    assert board["citizen_verdict"] == "confirmed"
    assert client.get("/api/public/stats").json()["citizen_confirmed"] >= 1
    assert queue_item(client, admin, rep["id"])["citizen_verdict"] == "confirmed"


def test_citizen_dispute_reopens_higher_and_a_new_fix_asks_again(client, admin, fake_translator):
    me = citizen_headers()
    rep = file_report(client, me)
    severity = queue_item(client, admin, rep["id"])["severity"]
    resolve(client, admin, rep["id"])
    out = client.post(f"/api/v1/reports/{rep['id']}/dispute", headers=me, data={"reason": "Still dark at night."})
    assert out.status_code == 200, out.text
    item = queue_item(client, admin, rep["id"])
    assert item["status"] in {"TRIAGED", "ASSIGNED"} and item["resolution_proof_url"] is None
    assert item["severity"] == api.SEVERITY_UP[severity] and item["last_dispute"] == "Still dark at night."
    assert client.post(f"/api/v1/reports/{rep['id']}/dispute", headers=me).status_code == 409  # open again: nothing to dispute

    resolve(client, admin, rep["id"])  # fixed again: the citizen is asked again
    mine = next(r for r in client.get("/api/v1/me/reports", headers=me).json() if r["id"] == rep["id"])
    assert mine["awaiting_your_check"] and mine["citizen_verdict"] is None


def test_signed_out_and_officers_cannot_speak_for_the_citizen(client, admin):
    client.cookies.clear()  # the admin login above also set a session cookie
    assert client.get("/api/v1/me/reports").status_code == 401
    assert client.post(f"/api/v1/reports/{uuid.uuid4()}/confirm", headers=admin).status_code == 403


# ------------------------------------------------------------------ languages
def test_reports_in_indian_languages_get_english_for_the_desk(client, admin, fake_translator):
    me = citizen_headers()
    english = file_report(client, me)
    assert english["translating"] is False  # English text, no voice note: nothing to translate

    hindi = file_report(client, me, "स्कूल के पास की स्ट्रीट लाइट दस दिनों से बंद है।")
    assert hindi["translating"] is True
    item = queue_item(client, admin, hindi["id"])
    assert item["translation"]["english"].startswith("The streetlight") and item["translation"]["language_name"] == "Hindi"
    assert item["description"].startswith("स्कूल")  # the citizen's own words are kept
    assert not item["needs_translation"]

    spoken = file_report(client, me, "Light problem", voice=b"\x1aE\xdf\xa3 fake webm")
    assert spoken["translating"] is True
    assert queue_item(client, admin, spoken["id"])["translation"]["transcript"]

    mine = {r["id"]: r for r in client.get("/api/v1/me/reports", headers=me).json()}
    assert mine[hindi["id"]]["language"] == "Hindi"


def test_desk_can_translate_on_demand(client, admin, fake_translator, monkeypatch):
    me = citizen_headers()
    with monkeypatch.context() as m:
        m.setattr(api, "needs_english", lambda text: False)  # pretend the background step did not run
        rep = file_report(client, me, "बिजली का खंभा गिरा हुआ है")
    item = queue_item(client, admin, rep["id"])
    assert item["translation"] is None and item["needs_translation"] is True
    out = client.post(f"/api/v1/admin/reports/{rep['id']}/translate", headers=admin).json()
    assert out["translation"]["language"] == "hi-IN"
    assert queue_item(client, admin, rep["id"])["needs_translation"] is False
    assert client.post(f"/api/v1/admin/reports/{rep['id']}/translate", headers=me).status_code == 403


# ------------------------------------------------------------------ hotspots
def test_hotspots_rank_wards_by_open_reports():
    now = datetime.now(timezone.utc)

    class R:
        def __init__(self, ward, status, category="garbage", late=False):
            self.ward_name, self.ward_id, self.city, self.status, self.category = ward, ward, "Pune", status, category
            self.sla_deadline = now.replace(year=now.year - 1) if late else None

    spots = api.hotspots([R("Kothrud", "TRIAGED", late=True), R("Kothrud", "ASSIGNED"), R("Aundh", "RESOLVED"),
                          R("Aundh", "TRIAGED", "water"), R("Baner", "RESOLVED")], now)
    assert [s["ward"] for s in spots] == ["Kothrud", "Aundh", "Baner"]
    assert spots[0] == {"ward": "Kothrud", "city": "Pune", "reports": 2, "open": 2, "past_deadline": 1, "top_category": "garbage"}
    assert spots[2]["open"] == 0


def test_public_stats_include_hotspots(client):
    stats = client.get("/api/public/stats").json()
    assert isinstance(stats["hotspots"], list) and len(stats["hotspots"]) <= 5
    for h in stats["hotspots"]:
        assert {"ward", "city", "reports", "open", "past_deadline", "top_category"} <= set(h)


def test_english_version_keeps_the_original_and_transcribes_voice(monkeypatch):
    import asyncio

    import server.language as language
    from executor.llm import LLMResult

    seen = {}

    class FakeLLM:
        async def decide(self, system, user, schema, max_tokens=4000, images=None):
            seen["user"] = user
            return LLMResult({"language": "ta-IN", "english": "Garbage has not been collected for a week."}, 1)

    async def heard(audio, media_type, lang):
        return {"text": "ஒரு வாரமாக குப்பை எடுக்கவில்லை", "language": "ta-IN"}

    monkeypatch.setattr(language, "default_llm", lambda: FakeLLM())
    monkeypatch.setattr(language, "transcribe_audio", heard)
    assert asyncio.run(language.english_version("Garbage not collected")) is None  # English, no voice: nothing to do
    out = asyncio.run(language.english_version("குப்பை", b"voice", "audio/webm;codecs=opus"))
    assert out["language_name"] == "Tamil" and out["transcript"].startswith("ஒரு") and out["machine_translated"]
    assert "குப்பை" in seen["user"] and "Voice note (transcript)" in seen["user"]
    monkeypatch.setattr(language, "default_llm", lambda: None)
    with pytest.raises(language.TranslationUnavailable):
        asyncio.run(language.english_version("குப்பை"))


# ------------------------------------------------------------------ intake: voice to text, photo check, the ticket
def test_voice_note_comes_back_in_its_own_language(client, monkeypatch):
    import server.groq as groq
    import server.language as language

    async def heard(audio, filename, media_type):
        return {"text": "सड़क पर बड़ा गड्ढा है", "language": "hindi"}

    monkeypatch.setattr(groq, "transcribe", heard)
    me = citizen_headers()
    out = client.post("/api/v1/reports/transcribe", headers=me, files={"audio": ("v.webm", b"voice", "audio/webm")}).json()
    assert out == {"text": "सड़क पर बड़ा गड्ढा है", "language": "hi-IN", "language_name": "Hindi"}
    assert language.language_code("hi") == "hi-IN" and language.language_code("swahili") is None
    client.cookies.clear()
    assert client.post("/api/v1/reports/transcribe", files={"audio": ("v.webm", b"voice", "audio/webm")}).status_code == 401


def test_preview_saves_nothing_and_explains_the_routing(client):
    me = citizen_headers()
    before = len(client.get("/api/v1/me/reports", headers=me).json())
    out = client.post("/api/v1/reports/preview", headers=me, files={"photo": ("p.png", png(), "image/png")},
                      data={"category": "Road and Bridges", "description": "Big pothole", "latitude": 18.5065, "longitude": 73.829}).json()
    assert out["department"] == "Roads & Engineering" and out["severity"] in {"P1", "P2", "P3"} and out["sla_hours"] > 0
    assert out["findings"] and out["reasons"] and out["annotated_photo"].startswith("data:image/jpeg;base64,")
    assert len(client.get("/api/v1/me/reports", headers=me).json()) == before  # nothing was filed
    photo_only = client.post("/api/v1/reports/preview", headers=me, files={"photo": ("p.png", png(), "image/png")},
                             data={"category": "Street Lights"}).json()
    assert "severity" not in photo_only and photo_only["department"] == "Electrical (Street Lighting)"
    bad = client.post("/api/v1/reports/preview", headers=me, files={"photo": ("p.exe", b"MZ", "application/x-msdownload")})
    assert bad.status_code in {400, 415}


def test_submit_creates_a_desk_ticket_with_everything_the_officer_needs(client, admin, fake_translator):
    me = citizen_headers()
    r = client.post("/api/v1/reports", headers=me, files={"photo": ("p.png", png(), "image/png")}, data={
        "category": "Road and Bridges", "description": "Pothole near the bus stop", "latitude": 18.5065, "longitude": 73.829,
        "district": "Pune", "state": "Maharashtra", "pincode": "411038", "transcript": "बस स्टॉप के पास गड्ढा", "language": "hi-IN"})
    assert r.status_code == 200, r.text
    filed = r.json()
    assert filed["ticket"] == "CIV-" + filed["id"].replace("-", "")[:8].upper() and filed["department"] == "Roads & Engineering"
    assert fake_translator[-1][2] == "बस स्टॉप के पास गड्ढा"  # the citizen's checked transcript is what gets translated
    item = queue_item(client, admin, filed["id"])
    assert item["ticket"] == filed["ticket"] and item["department"] == "Roads & Engineering"
    assert item["photo_urls"] and item["findings"] and item["reasons"] and item["transcript"] == "बस स्टॉप के पास गड्ढा"
    assert item["place"] == "Pune, Maharashtra, 411038"
    assert client.get(item["photo_urls"][0], headers=admin).status_code == 200
    mine = next(x for x in client.get("/api/v1/me/reports", headers=me).json() if x["id"] == filed["id"])
    assert mine["ticket"] == filed["ticket"]


def test_places_outside_our_ward_maps_are_never_given_a_made_up_ward():
    from server.triage import lookup_ward
    assert lookup_ward(19.07, 72.87, "Mumbai") == ("UNMAPPED", "Ward not mapped yet", "Mumbai")
    assert lookup_ward(26.9, 75.8)[0] == "UNMAPPED"


# ------------------------------------------------------------------ accounts for the municipal desk
def test_judges_demo_login_only_when_switched_on(client, monkeypatch):
    monkeypatch.delenv("CIVIC_JUDGE_DEMO", raising=False)
    assert client.post("/api/v1/auth/judge-demo/admin").status_code == 404
    monkeypatch.setenv("CIVIC_JUDGE_DEMO", "1")
    officer = client.post("/api/v1/auth/judge-demo/admin").json()
    assert officer["user"]["role"] == "admin" and officer["user"]["email"] == "officer.demo@example.org"
    assert client.get("/api/v1/admin/queue", headers={"Authorization": "Bearer " + officer["access_token"]}).status_code == 200
    assert client.post("/api/v1/auth/judge-demo/citizen").json()["user"]["role"] == "citizen"
    assert client.post("/api/v1/auth/judge-demo/root").status_code == 404
    assert client.get("/app/config").json()["judge_demo"] is True


def test_municipal_sign_up_needs_the_access_code(client, monkeypatch):
    body = {"name": "New Officer", "email": "new.officer@example.org", "password": "long-enough-1", "officer_code": "guess"}
    monkeypatch.delenv("CIVIC_OFFICER_SIGNUP_CODE", raising=False)
    assert client.post("/api/v1/auth/signup", json=body).status_code == 403  # no code configured: nobody can
    monkeypatch.setenv("CIVIC_OFFICER_SIGNUP_CODE", "the-real-code")
    assert client.post("/api/v1/auth/signup", json=body).status_code == 403
    assert client.get("/app/config").json()["officer_signup"] is True


def test_groq_client_reads_transcripts_and_json(monkeypatch):
    import asyncio
    import json as _json

    import httpx

    import server.groq as groq

    def answer(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        if request.url.path.endswith("/audio/transcriptions"):
            return httpx.Response(200, json={"text": " ಗುಂಡಿ ಇದೆ ", "language": "kannada"})
        body = _json.loads(request.content)
        assert body["model"] == "openai/gpt-oss-120b" and body["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"language": "kn-IN", "english": "There is a pothole."}'}}]})

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.setattr(groq, "transport", httpx.MockTransport(answer))
    assert asyncio.run(groq.transcribe(b"a", "v.webm", "audio/webm")) == {"text": "ಗುಂಡಿ ಇದೆ", "language": "kannada"}
    assert asyncio.run(groq.chat_json("s", "u"))["english"] == "There is a pothole."
    monkeypatch.setattr(groq, "transport", httpx.MockTransport(lambda r: httpx.Response(404, json={})))
    with pytest.raises(groq.GroqUnavailable):
        asyncio.run(groq.chat_json("s", "u"))


def test_a_voice_note_storage_refuses_does_not_block_the_report(client, monkeypatch, fake_translator):
    real = api.upload_evidence

    def picky(file_bytes, filename, content_type, report_id):
        if content_type.startswith("audio/"):
            raise RuntimeError("400 Bad Request: mime type audio/webm is not supported")
        return real(file_bytes=file_bytes, filename=filename, content_type=content_type, report_id=report_id)

    monkeypatch.setattr(api, "upload_evidence", picky)
    filed = file_report(client, citizen_headers(), "Pothole near the school gate", voice=b"\x1aE\xdf\xa3 webm")
    assert filed["ticket"].startswith("CIV-")


def test_ids_from_postgres_are_text_in_payloads_and_lookups(client, monkeypatch, fake_translator):
    """PostgreSQL returns UUID objects for ids; SQLite returns text. Both must work."""
    import uuid as _uuid

    import server.triage as triage
    me = citizen_headers()
    first = file_report(client, me)
    real = triage.find_duplicate_report
    monkeypatch.setattr(triage, "find_duplicate_report", lambda *a, **k: str(real(*a, **k)) if real(*a, **k) else None)
    assert api._report_or_404(next(api.get_db()), _uuid.UUID(first["id"])).id == first["id"]
    lat, lng = 18.5065, 73.829
    for _ in range(2):  # the second report sits on the first: a duplicate whose id goes into the event payload
        r = client.post("/api/v1/reports", headers=me, data={"category": "streetlights", "description": "Same lamp off",
                                                             "latitude": lat, "longitude": lng})
        assert r.status_code == 200, r.text
