"""Live news for the home page: headlines about schemes, citizens' rights, civic issues and digital services.

Sources, fetched together and cached for NEWS_TTL_S:
  - Google News RSS searches (public feeds, past 7 days, India edition), one per topic
  - PIB (Press Information Bureau) releases, the Government of India's own press office (titles in Hindi)

"Trending" is counted, not invented: the words that appear in the most current headlines.
If every source fails, the last good result is served and marked stale.
"""

from __future__ import annotations

import asyncio
import html
import re
import time
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import httpx

UA = "Swayam-sevak/0.1 (citizen news; headlines only)"
NEWS_TTL_S = 20 * 60
transport: httpx.AsyncBaseTransport | None = None  # tests inject a MockTransport

# Citizen services only: party politics and elections are excluded, so the feed stays neutral.
NEUTRAL = " -election -elections -poll -polls -BJP -Congress -AAP -TMC -rally -campaign"
TOPICS = {
    "schemes": ("Schemes & welfare", "(scheme OR yojana) (launched OR approved OR beneficiaries OR eligibility OR pension OR scholarship) India" + NEUTRAL),
    "rights": ("Rights & rules", '("consumer rights" OR "consumer commission" OR "right to information" OR RTI OR "rules notified" OR "gazette notification") India' + NEUTRAL),
    "civic": ("Civic issues", "(municipal OR civic) (complaint OR grievance OR pothole OR garbage OR streetlight OR water supply) India" + NEUTRAL),
    "digital": ("Digital services", "(e-governance OR DigiLocker OR UMANG OR \"online portal\" OR \"digital services\") citizens India" + NEUTRAL),
}
# Words the searches themselves ask for: counting them as "trending" would say nothing.
QUERY_WORDS = set("""scheme schemes yojana launched launches approved approves approval beneficiaries eligibility pension scholarship
consumer rights commission right information rti rules notified notification gazette municipal civic complaint complaints grievance
grievances pothole potholes garbage streetlight streetlights water supply e-governance digilocker umang online portal digital services
citizens citizen corporation""".split())
PIB_URL = "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"
STOP = set("""a an the of to in on for and or with by from at as is are be its it this that after over into new india indian
govt government says said will under amid more than about up out how why what who when news today live day week year crore lakh
rs per two one three four five state centre central minister ministry union his her their our your all not no vs top""".split())

_cache: dict = {"at": 0.0, "data": None}
_lock = asyncio.Lock()


def _tag(xml: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.S)
    text = m.group(1) if m else ""
    text = re.sub(r"^<!\[CDATA\[|\]\]>$", "", text.strip())
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def _when(raw: str) -> str | None:
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def parse_google(xml: str, topic: str) -> list[dict]:
    out = []
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
        title, source = _tag(item, "title"), _tag(item, "source")
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)]  # Google appends " - <publisher>"
        link = _tag(item, "link")
        if title and link.startswith("https://"):
            out.append({"title": title, "url": link, "source": source or "News", "published": _when(_tag(item, "pubDate")),
                        "topic": topic, "official": source.lower().startswith("pib") or "pib.gov.in" in source.lower(), "lang": "en"})
    return out


def parse_pib(xml: str) -> list[dict]:
    out = []
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
        title, link = _tag(item, "title"), _tag(item, "link")
        if title and link.startswith("https://pib.gov.in/"):
            out.append({"title": title, "url": link, "source": "PIB (Govt. of India)", "published": _when(_tag(item, "pubDate")),
                        "topic": "official", "official": True, "lang": "hi" if re.search(r"[ऀ-ॿ]", title) else "en"})
    return out


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9ऀ-ॿ]+", " ", t.lower()).strip()[:80]


def trending(items: list[dict], top: int = 8) -> list[dict]:
    """Words (and two-word phrases) that appear in the most distinct English headlines right now."""
    counts: Counter = Counter()
    for it in items:
        if it["lang"] != "en":
            continue
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", it["title"]) if w.lower() not in STOP]
        grams = {w.title() if w.islower() else w for w in words if w.lower() not in QUERY_WORDS}
        grams |= {f"{a} {b}" for a, b in zip(words, words[1:]) if a[0].isupper() and b[0].isupper()
                  and not (a.lower() in QUERY_WORDS and b.lower() in QUERY_WORDS)}
        counts.update(grams)
    best = [(t, n) for t, n in counts.most_common(40) if n >= 2]
    # Prefer a phrase over its single words when both are counted equally often.
    phrases = {t for t, _ in best if " " in t}
    kept = [(t, n) for t, n in best if " " in t or not any(t in p.split() and counts[p] >= n for p in phrases)]
    return [{"term": t, "count": n} for t, n in kept[:top]]


async def _get(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        r = await client.get(url)
        return r.text if r.status_code == 200 else None
    except httpx.HTTPError:
        return None


async def fetch() -> dict:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, transport=transport, headers={"User-Agent": UA}) as c:
        urls = {k: f"https://news.google.com/rss/search?q={quote(q + ' when:7d')}&hl=en-IN&gl=IN&ceid=IN:en" for k, (_, q) in TOPICS.items()}
        texts = await asyncio.gather(*(_get(c, u) for u in urls.values()), _get(c, PIB_URL))
    items, ok_sources = [], []
    for (topic, _), text in zip(TOPICS.items(), texts[:-1]):
        if text:
            got = parse_google(text, topic)[:25]
            items += got
            ok_sources.append(f"Google News: {TOPICS[topic][0]}")
    if texts[-1]:
        items += parse_pib(texts[-1])[:15]
        ok_sources.append("PIB")
    seen, unique = set(), []
    for it in items:  # the same story under two topics is shown once, under the first
        key = norm_title(it["title"])
        if key not in seen:
            seen.add(key)
            unique.append(it)
    unique.sort(key=lambda it: it["published"] or "", reverse=True)
    return {"updated_at": datetime.now(timezone.utc).isoformat(), "items": unique, "trending": trending(unique),
            "topics": [{"id": k, "label": v[0]} for k, v in TOPICS.items()] + [{"id": "official", "label": "PIB official"}],
            "sources": ok_sources, "stale": False}


async def latest(force: bool = False) -> dict:
    async with _lock:
        fresh = _cache["data"] and time.monotonic() - _cache["at"] < NEWS_TTL_S
        if fresh and not force:
            return _cache["data"]
        data = await fetch()
        if data["items"]:
            _cache.update(at=time.monotonic(), data=data)
            return data
        if _cache["data"]:  # every source failed: keep showing the last good headlines, marked stale
            return {**_cache["data"], "stale": True}
        return data
