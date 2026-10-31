"""Turn a registry Target into a Playwright locator, and resolve it to exactly one element."""

from __future__ import annotations

import json

from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PWTimeout

from .registry import Target


def _attr(name: str, value: str) -> str:
    return f"[{name}={json.dumps(value)}]"


def build(page: Page, t: Target) -> Locator:
    root = page.frame_locator(t.frame) if t.frame else page
    if t.id:
        loc = root.locator(_attr("id", t.id))
    elif t.name:
        loc = root.locator(_attr("name", t.name))
    elif t.label:
        loc = root.get_by_label(t.label, exact=True)
    elif t.placeholder:
        loc = root.get_by_placeholder(t.placeholder, exact=True)
    elif t.role:
        loc = root.get_by_role(t.role, name=t.role_name, exact=True) if t.role_name else root.get_by_role(t.role)
    elif t.text:
        loc = root.get_by_text(t.text, exact=True)
    elif t.after_text:
        loc = root.get_by_text(t.after_text).first.locator(f"xpath=following::{t.tag}[1]")
    elif t.css:
        loc = root.locator(t.css)
    else:
        raise ValueError("empty target")
    if t.nth is not None:
        loc = loc.nth(t.nth)
    return loc


class LocatorError(Exception):
    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind  # locator_missing | locator_ambiguous


async def resolve(page: Page, target: Target, timeout_ms: int, attached_only: bool = False) -> Locator:
    """Try the target, then each alt, sharing the time budget. Returns a locator matching one element."""
    specs = [target, *target.alt]
    per_spec = max(1000, timeout_ms // len(specs))
    last = LocatorError("locator_missing", f"no element for {target.describe()}")
    for spec in specs:
        loc = build(page, spec)
        try:
            await loc.first.wait_for(state="attached" if attached_only else "visible", timeout=per_spec)
        except PWTimeout:
            last = LocatorError("locator_missing", f"no element for {spec.describe()}")
            continue
        count = await loc.count()
        if count == 1:
            return loc
        last = LocatorError("locator_ambiguous", f"{count} elements match {spec.describe()}")
    raise last
