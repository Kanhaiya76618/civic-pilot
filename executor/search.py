"""Web search for the agent console, restricted to the allow-listed sites.

Providers are tried in the order of CIVIC_SEARCH (default "duckduckgo,site"):

  duckduckgo  DuckDuckGo's HTML results page, no key needed. If it answers with
              its bot check, we stop there: it is never solved or bypassed.
  site        No server-side search: the agent opens the site's own search page
              (Portal.search_url) and types the query there, in the browser.

Only results on allow-listed hosts are kept.
"""

from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass
from urllib.parse import parse_qs, urlparse

import httpx

DDG_URL = "https://html.duckduckgo.com/html/"
UA = "CivicPulse/0.1 (hackathon research agent; allow-listed government sites only)"
transport: httpx.AsyncBaseTransport | None = None  # tests inject a MockTransport

_ANCHOR = re.compile(r'<a\b([^>]*)>(.*?)</a>', re.S | re.I)
_HREF = re.compile(r'href="([^"]+)"', re.I)
_TAG = re.compile(r"<[^>]+>")


@dataclass
class Hit:
    title: str
    url: str
    snippet: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SearchOutcome:
    provider: str
    hits: list[Hit]
    note: str


def host_allowed(host: str, domains: list[str]) -> bool:
    host = (host or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub("", fragment))).strip()


def _unwrap(href: str) -> str:
    href = html.unescape(href)
    if href.startswith("//"):
        href = "https:" + href
    u = urlparse(href)
    if u.hostname and u.hostname.endswith("duckduckgo.com") and u.path.startswith("/l/"):
        return parse_qs(u.query).get("uddg", [""])[0]
    return href


def parse_ddg(page: str, domains: list[str], limit: int = 8) -> list[Hit]:
    """Every link to an allow-listed host, in page order, with the nearest snippet. Independent of DDG's CSS classes."""
    hits: dict[str, Hit] = {}
    for attrs, inner in _ANCHOR.findall(page):
        m = _HREF.search(attrs)
        if not m:
            continue
        url = _unwrap(m.group(1))
        host = urlparse(url).hostname or ""
        if not url.startswith("http") or not host_allowed(host, domains):
            continue
        text = _text(inner)
        if not text:
            continue
        key = url.split("#")[0].rstrip("/")
        if "snippet" in attrs:
            if key in hits and not hits[key].snippet:
                hits[key].snippet = text[:300]
            continue
        if key not in hits and not re.fullmatch(r"(https?://)?[\w.-]+(/\S*)?", text):  # skip bare-URL link texts
            hits[key] = Hit(title=text[:140], url=url)
    return list(hits.values())[:limit]


async def duckduckgo(query: str, domains: list[str]) -> SearchOutcome:
    sites = " OR ".join(f"site:{d}" for d in domains)
    q = f"{query} ({sites})" if len(domains) > 1 else f"{query} site:{domains[0]}"
    try:
        async with httpx.AsyncClient(timeout=6, transport=transport, headers={"User-Agent": UA}) as c:
            r = await c.post(DDG_URL, data={"q": q})
    except httpx.HTTPError as e:
        return SearchOutcome("duckduckgo", [], f"DuckDuckGo could not be reached ({type(e).__name__})")
    if r.status_code == 202 or "anomaly-modal" in r.text:
        return SearchOutcome("duckduckgo", [], "DuckDuckGo asked for a human check; we never solve or bypass those")
    if r.status_code != 200:
        return SearchOutcome("duckduckgo", [], f"DuckDuckGo answered {r.status_code}")
    hits = parse_ddg(r.text, domains)
    return SearchOutcome("duckduckgo", hits, f"{len(hits)} results on allow-listed sites" if hits else "no results on allow-listed sites")


async def search(query: str, domains: list[str], providers: list[str]) -> list[SearchOutcome]:
    """Run providers in order until one returns results. Returns every attempt, for the run log."""
    attempts: list[SearchOutcome] = []
    for p in providers:
        if p == "duckduckgo" and domains:
            out = await duckduckgo(query, domains)
            attempts.append(out)
            if out.hits:
                break
        elif p == "site":
            attempts.append(SearchOutcome("site", [], "using the official site's own search page"))
            break
    return attempts
