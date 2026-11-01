"""Home page: live news parsing and trending, per-account history, and the demo-login switch."""

import httpx
import pytest
from fastapi.testclient import TestClient

from executor import news
from executor.api import make_app

GOOGLE = """<rss><channel>
<item><title>Cabinet approves Pradhan Mantri Viksit Gram Swaraj Yojana - PM India</title><link>https://news.google.com/rss/articles/a1</link>
<pubDate>Wed, 28 Oct 2026 10:56:00 GMT</pubDate><source url="https://pmindia.gov.in">PM India</source></item>
<item><title>Viksit Gram Swaraj Yojana: who benefits - The Hindu</title><link>https://news.google.com/rss/articles/a2</link>
<pubDate>Thu, 29 Oct 2026 08:00:00 GMT</pubDate><source url="https://thehindu.com">The Hindu</source></item>
<item><title>Press Note Details - pib.gov.in</title><link>https://news.google.com/rss/articles/a3</link>
<pubDate>Sat, 31 Oct 2026 04:09:00 GMT</pubDate><source url="https://pib.gov.in">pib.gov.in</source></item>
</channel></rss>"""
PIB = """<rss><channel><item><title>सात हवाई अड्डों पर 'डिजी यात्रा' का ट्रायल शुरू</title>
<link>https://pib.gov.in/PressReleaseIframePage.aspx?PRID=2331231</link></item></channel></rss>"""


def test_google_items_are_cleaned_and_dated():
    items = news.parse_google(GOOGLE, "schemes")
    assert items[0]["title"] == "Cabinet approves Pradhan Mantri Viksit Gram Swaraj Yojana" and items[0]["source"] == "PM India"
    assert items[0]["published"].startswith("2026-10-28T10:56") and items[2]["official"] is True


def test_pib_items_are_official_and_hindi():
    items = news.parse_pib(PIB)
    assert items[0]["official"] and items[0]["lang"] == "hi" and items[0]["url"].startswith("https://pib.gov.in/")


def test_trending_counts_real_repeats_not_search_words():
    items = news.parse_google(GOOGLE, "schemes")
    terms = {t["term"]: t["count"] for t in news.trending(items)}
    assert terms.get("Gram Swaraj") == 2 or terms.get("Viksit Gram") == 2
    assert "Yojana" not in terms and "Scheme" not in terms  # the searches' own words say nothing


@pytest.mark.asyncio
async def test_feed_falls_back_to_last_good_headlines():
    def ok(request: httpx.Request):
        return httpx.Response(200, text=PIB if "pib.gov.in" in request.url.host else GOOGLE)
    news.transport = httpx.MockTransport(ok)
    news._cache.update(at=0.0, data=None)
    try:
        first = await news.latest(force=True)
        assert first["items"] and not first["stale"] and "PIB" in first["sources"]
        assert len({news.norm_title(i["title"]) for i in first["items"]}) == len(first["items"])  # same story once
        news.transport = httpx.MockTransport(lambda r: httpx.Response(503))
        down = await news.latest(force=True)
        assert down["stale"] is True and down["items"] == first["items"]
    finally:
        news.transport = None
        news._cache.update(at=0.0, data=None)


@pytest.fixture(scope="module")
def client():
    with TestClient(make_app()) as c:
        yield c


def login(client, email):
    r = client.post("/api/v1/auth/login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_history_is_private_per_account(client):
    citizen, admin = login(client, "citizen@demo.in"), login(client, "admin@demo.in")
    client.delete("/app/me/history", headers=citizen)
    client.cookies.clear()  # sign-in also sets a cookie; drop it to act as a signed-out visitor
    assert client.get("/app/me/history").status_code == 401  # signed out: nothing
    made = client.post("/app/me/history", headers=citizen, json={"kind": "explain", "title": "PMSBY rules", "link": "/schemes?url=x"})
    assert made.status_code == 201
    news_item = {"kind": "news", "title": "Headline", "link": "https://news.google.com/rss/articles/" + "C" * 740}  # real ones are this long
    assert client.post("/app/me/history", headers=citizen, json=news_item).status_code == 201
    assert client.post("/app/me/history", headers=citizen, json=news_item).json().get("already_saved") is True
    mine = client.get("/app/me/history", headers=citizen).json()
    assert [h["kind"] for h in mine] == ["news", "explain"]
    assert client.get("/app/me/history", headers=admin).json() == []  # another account sees none of it
    assert client.delete(f"/app/me/history/{made.json()['id']}", headers=admin).status_code == 404  # nor deletes it
    assert client.post("/app/me/history", headers=citizen, json={"kind": "news", "title": "x", "link": "javascript:alert(1)"}).status_code == 400
    assert client.get("/app/me/history?kind=news", headers=citizen).json()[0]["kind"] == "news"
    assert client.delete("/app/me/history?kind=news", headers=citizen).json()["deleted"] == 1
    assert client.delete(f"/app/me/history/{made.json()['id']}", headers=citizen).json() == {"ok": True}


def test_demo_login_needs_the_test_switch(client, monkeypatch):
    monkeypatch.delenv("CIVIC_ALLOW_DEMO_LOGIN")
    r = client.post("/api/v1/auth/login", json={"email": "admin@demo.in"})
    assert r.status_code == 422  # in a deployment, nobody gets the municipal desk without a password
