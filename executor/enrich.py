"""Live public data used to check and fill citizen input. No static datasets.

- PIN code -> post offices, district, state: India Post data via api.postalpincode.in
- IFSC -> bank, branch, city: RBI's IFSC data via Razorpay's open IFSC API (ifsc.razorpay.com)

Every lookup returns ok=True/False, or ok=None when the service could not be
reached, so callers can tell "invalid" from "could not check" and degrade
gracefully instead of blocking a citizen on someone else's outage.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import httpx

PINCODE_URL = "https://api.postalpincode.in/pincode/{}"
IFSC_URL = "https://ifsc.razorpay.com/{}"
TTL_S = 24 * 3600
_cache: dict[str, tuple[float, "Lookup"]] = {}
# Tests swap this for an httpx.MockTransport.
transport: httpx.AsyncBaseTransport | None = None


@dataclass
class Lookup:
    ok: bool | None  # None: the service could not be reached
    source: str
    data: dict = field(default_factory=dict)
    error: str | None = None


async def _get(url: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=6, transport=transport, headers={"User-Agent": "CivicPulse/0.1"}) as c:
        return await c.get(url)


async def pincode(pin: str) -> Lookup:
    source = "India Post (api.postalpincode.in)"
    if not re.fullmatch(r"[1-9]\d{5}", pin or ""):
        return Lookup(False, source, error="a PIN code has 6 digits and does not start with 0")
    key = f"pin:{pin}"
    if key in _cache and time.time() - _cache[key][0] < TTL_S:
        return _cache[key][1]
    try:
        r = await _get(PINCODE_URL.format(pin))
        body = r.json()[0]
    except (httpx.HTTPError, ValueError, IndexError, KeyError) as e:
        return Lookup(None, source, error=f"lookup unavailable: {type(e).__name__}")
    offices = body.get("PostOffice") or []
    if body.get("Status") != "Success" or not offices:
        res = Lookup(False, source, error=f"PIN code {pin} was not found")
    else:
        res = Lookup(True, source, {
            "pincode": pin,
            "state": offices[0]["State"],
            "districts": sorted({o["District"] for o in offices}),
            "post_offices": [o["Name"] for o in offices][:20],
        })
    _cache[key] = (time.time(), res)
    return res


async def ifsc(code: str) -> Lookup:
    source = "RBI IFSC data (ifsc.razorpay.com)"
    code = (code or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", code):
        return Lookup(False, source, error="an IFSC is 4 letters, a zero, then 6 letters or digits")
    key = f"ifsc:{code}"
    if key in _cache and time.time() - _cache[key][0] < TTL_S:
        return _cache[key][1]
    try:
        r = await _get(IFSC_URL.format(code))
    except httpx.HTTPError as e:
        return Lookup(None, source, error=f"lookup unavailable: {type(e).__name__}")
    if r.status_code == 404:
        res = Lookup(False, source, error=f"IFSC {code} does not exist")
    elif r.status_code != 200:
        return Lookup(None, source, error=f"lookup unavailable: HTTP {r.status_code}")
    else:
        d = r.json()
        res = Lookup(True, source, {k.lower(): d.get(k) for k in ("BANK", "BRANCH", "CITY", "DISTRICT", "STATE", "IFSC")})
    _cache[key] = (time.time(), res)
    return res
