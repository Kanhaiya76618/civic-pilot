import pytest

from server.civic_guide import CivicGuide, GuideUnavailable, OfficialSource, redact_sensitive


def test_civic_guide_redacts_common_high_risk_values():
    safe = redact_sensitive("My Aadhaar 123456789012 and OTP 998877; card 4111 1111 1111 1111")
    assert "123456789012" not in safe
    assert "998877" not in safe
    assert "4111" not in safe


@pytest.mark.asyncio
async def test_civic_guide_declines_when_no_official_source_is_available(monkeypatch):
    guide = CivicGuide()

    async def no_sources(_question):
        return []

    monkeypatch.setattr(guide, "sources_for", no_sources)
    result = await guide.answer("I have a question about a bank loan repayment")
    assert result["retrieval_status"] == "no_official_sources"
    assert result["sources"] == []


@pytest.mark.asyncio
async def test_civic_guide_never_calls_a_model_without_a_server_key(monkeypatch):
    guide = CivicGuide()

    async def official_source(_question):
        return [OfficialSource("RBI guidance", "https://www.rbi.org.in/example", "Official material")]

    monkeypatch.setattr(guide, "sources_for", official_source)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(GuideUnavailable, match="not configured"):
        await guide.answer("What should I do about loan recovery calls?")


@pytest.mark.asyncio
async def test_portal_guide_needs_no_model_or_official_web_search():
    result = await CivicGuide().answer("How do I use this website to report a pothole?", scope="portal")
    assert result["mode"] == "portal"
    assert any(action["path"] == "/grievance" for action in result["actions"])
