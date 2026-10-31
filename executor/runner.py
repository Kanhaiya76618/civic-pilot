"""Tier 1: the deterministic route runner.

For each step: resolve the locator, act, check the postcondition, record timing.
No model calls. On a failure it can't fix itself it hands the step to the
Tier 2 healer, and if that fails too it stops and asks a human.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from playwright.async_api import BrowserContext, Dialog, Page, Request, Route as PWRoute
from playwright.async_api import Error as PWError
from playwright.async_api import TimeoutError as PWTimeout

from .config import settings
from .db import Store
from .docprep import PreparedDoc
from .handoff import Gateway, HumanRequest
from .healer import Healer
from .locators import LocatorError, build, resolve
from .models import ApplicationTask, TaskEvent, TaskMode, TaskStatus, Timing
from .models import utcnow
from .registry import Expect, Extract, Portal, Route, Step, Target
from .snapshot import Snapshot, take
from .vault import PLACEHOLDER, VaultSession, mask

HUMAN_INSTRUCTIONS = {
    "otp": "The portal has sent an OTP to your phone. Type it into the page below and press the portal's Verify button.",
    "captcha": "Type the characters shown in the CAPTCHA image into the page below, then tap Done.",
    "login": "The portal needs you to log in. Complete the login in the page below, then tap Done.",
    "payment": "Complete the payment in the page below. The agent never sees your payment details. Tap Done when finished.",
    "other": "The agent needs your help on this page. Complete what the page asks, then tap Done.",
}

# Third-party trackers and heavy assets that never matter for filling a form.
BLOCKED_HOST_SUFFIXES = (
    "google-analytics.com", "googletagmanager.com", "doubleclick.net", "facebook.net", "hotjar.com", "clarity.ms",
)
BLOCKED_RESOURCE_TYPES = {"font", "media"}


class StepFailure(Exception):
    def __init__(self, kind: str, detail: str, healable: bool = False, transient: bool = False):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail
        self.healable = healable
        self.transient = transient


class Stop(Exception):
    """Ends the run with a terminal status."""

    def __init__(self, status: TaskStatus, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


class DryRunDone(Exception):
    pass


@dataclass
class Clock:
    started: float = field(default_factory=time.monotonic)
    model_ms: int = 0
    human_wait_ms: int = 0
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def timing(self) -> Timing:
        total = int((time.monotonic() - self.started) * 1000)
        agent = max(0, total - self.human_wait_ms)
        return Timing(
            agent_ms=agent, browser_ms=max(0, agent - self.model_ms), model_ms=self.model_ms,
            human_wait_ms=self.human_wait_ms, total_ms=total, model_calls=self.model_calls,
            input_tokens=self.input_tokens, output_tokens=self.output_tokens,
        )


@dataclass
class RunState:
    approved: bool = False
    filled: dict[str, dict] = field(default_factory=dict)
    aux_actions: list[str] = field(default_factory=list)
    heals: list[dict] = field(default_factory=list)
    suspicious: list[str] = field(default_factory=list)
    captured: dict[str, str] = field(default_factory=dict)
    recover_counts: dict[str, int] = field(default_factory=dict)
    human_retries: dict[str, int] = field(default_factory=dict)
    drift_mode: bool = False
    patched: bool = False
    patch_ok: bool = True
    outcome: str | None = None
    approval_card: dict | None = None
    evidence: dict[str, Path] = field(default_factory=dict)
    blocked_navigations: list[str] = field(default_factory=list)
    result: dict | None = None
    human_fixes: dict[str, int] = field(default_factory=dict)
    explored: bool = False


class RouteRunner:
    def __init__(
        self,
        *,
        task_id: str,
        task: ApplicationTask,
        portal: Portal,
        route: Route,
        context: BrowserContext,
        page: Page,
        vault: VaultSession,
        docs: dict[str, PreparedDoc],
        gateway: Gateway,
        publish: Callable[[TaskEvent], TaskEvent],
        store: Store,
        healer: Healer,
        evidence_dir: Path,
        citizen_url: str,
        profile: dict | None,
    ):
        self.task_id = task_id
        self.task = task
        self.portal = portal
        self.route = route
        self.steps: list[Step] = [s.model_copy(deep=True) for s in route.steps]
        self.context = context
        self.page = page
        self.vault = vault
        self.docs = docs
        self.gateway = gateway
        self._publish = publish
        self.store = store
        self.healer = healer
        self.evidence_dir = evidence_dir
        self.citizen_url = citizen_url
        self.profile = profile or {}
        self.status = TaskStatus.running
        self.clock = Clock()
        self.state = RunState()
        self._new_pages: list[Page] = []
        self._stale_error: str | None = None

    # events --------------------------------------------------------------------
    def emit(self, kind: str, message: str, step_id: str | None = None, data: dict | None = None) -> None:
        self._publish(
            TaskEvent(
                task_id=self.task_id, status=self.status, kind=kind, step_id=step_id,
                message=self.vault.redact(message), data=data or {}, timing=self.clock.timing(),
            )
        )

    def set_status(self, status: TaskStatus, message: str = "", data: dict | None = None) -> None:
        self.status = status
        self.store.set_status(self.task_id, status.value)
        self.emit("status", message or status.value, data=data)

    def emit_heal(self, step_id: str, message: str) -> None:
        self.emit("heal", message, step_id)

    def emit_security(self, step_id: str | None, message: str) -> None:
        self.emit("security", message, step_id)

    def note_suspicious(self, snap: Snapshot, step_id: str) -> None:
        for text in snap.suspicious:
            if text not in self.state.suspicious:
                self.state.suspicious.append(text)
                self.emit_security(
                    step_id,
                    f"Page text addressed to an AI agent was found and treated as data, not instructions: {text!r}",
                )

    # setup ---------------------------------------------------------------------
    async def setup(self) -> None:
        await self.context.route("**/*", self._guard_request)
        self.context.on("page", self._on_new_page)
        self._watch_page(self.page)
        await self.gateway.attach_page(self.task_id, self.page)

    def owner_of(self, el: dict, step_id: str) -> str | None:
        """Id of another route step that already targets this element by id or name, if any."""
        for s in self.steps:
            if s.id == step_id or not s.target:
                continue
            for t in (s.target, *s.target.alt):
                if (t.id and t.id == el.get("id")) or (t.name and t.name == el.get("name")):
                    return s.id
        return None

    def host_allowed(self, host: str) -> bool:
        host = (host or "").lower()
        return any(host == d or host.endswith("." + d) for d in self.portal.allowed_domains)

    async def _guard_request(self, route: PWRoute, request: Request) -> None:
        url = request.url
        if request.is_navigation_request() and not url.startswith(("about:", "data:", "blob:")):
            host = urlparse(url).hostname or ""
            if not self.host_allowed(host):
                main_frame = request.frame.parent_frame is None
                if host not in self.state.blocked_navigations:
                    self.state.blocked_navigations.append(host)
                    if main_frame:
                        self.emit_security(None, f"Blocked navigation to {host}: not in this portal's allowed domains")
                    else:
                        self.emit("info", f"Blocked an embedded third-party frame from {host}")
                await route.abort("blockedbyclient")
                return
        if self.portal.block_resources and (
            request.resource_type in BLOCKED_RESOURCE_TYPES
            or (urlparse(url).hostname or "").endswith(BLOCKED_HOST_SUFFIXES)
        ):
            await route.abort("blockedbyclient")
            return
        await route.continue_()

    def _on_new_page(self, page: Page) -> None:
        self._new_pages.append(page)
        self._watch_page(page)

    def _watch_page(self, page: Page) -> None:
        page.on("dialog", self._on_dialog)

    async def _on_dialog(self, dialog: Dialog) -> None:
        self.emit("info", f"Portal dialog ({dialog.type}) accepted: {dialog.message[:200]}")
        try:
            await dialog.accept()
        except PWError:
            pass

    async def _adopt_popup(self) -> None:
        await asyncio.sleep(0.3)
        if not self._new_pages:
            return
        page = self._new_pages.pop()
        self._new_pages.clear()
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=settings.step_timeout_ms)
        except PWTimeout:
            pass
        self.page = page
        await self.gateway.attach_page(self.task_id, page)
        self.emit("info", f"Portal opened a new tab; continuing there ({urlparse(page.url).path})")

    # values ----------------------------------------------------------------------
    def resolve_value(self, template: str, step_id: str) -> str:
        def sub(m: re.Match) -> str:
            ns, key = m.group(1), m.group(2)
            if ns == "portal":
                return str(getattr(self.portal, key))
            if ns == "doc":
                if key not in self.docs:
                    raise StepFailure("missing_value", f"document '{key}' was not prepared")
                return str(self.docs[key].path)
            spec = self.route.input(key)
            if not spec:
                raise StepFailure("missing_value", f"'{ns}.{key}' is not declared in the route inputs")
            if ns == "vault":
                if spec.source != "vault":
                    raise StepFailure("missing_value", f"'{key}' is not a vault field")
                return self.vault.get(key, step_id)
            if spec.source != "input":
                raise StepFailure("missing_value", f"'{key}' must come from the vault")
            if key not in self.task.inputs:
                raise StepFailure("missing_value", f"input '{key}' was not provided")
            return str(self.task.inputs[key])

        return PLACEHOLDER.sub(sub, template)

    def render_target(self, target: Target, step_id: str) -> Target:
        """Fill input placeholders inside a locator, e.g. answer{{input.gender}}. Vault values never go into locators."""
        def fill(text: str) -> str:
            if "{{" not in text:
                return text
            if "vault." in text:
                raise StepFailure("missing_value", "vault values cannot be used inside a locator")
            return self.resolve_value(text, step_id)

        return target.render(fill)

    def when_ok(self, step: Step) -> bool:
        for key, allowed in (step.when or {}).items():
            have = str(self.task.inputs.get(key, "")).strip().lower()
            if have not in {a.strip().lower() for a in allowed}:
                return False
        return True

    def display_value(self, template: str | None, step_id: str) -> tuple[str, str]:
        if not template:
            return "", ""
        m = PLACEHOLDER.fullmatch(template.strip())
        if m and m.group(1) == "vault":
            return mask(self.vault.get(m.group(2), step_id)), "vault (encrypted profile)"
        if m and m.group(1) == "doc":
            d = self.docs.get(m.group(2))
            return (f"{d.path.name} ({d.size_kb:.0f} KB)" if d else "?"), "document"
        return self.resolve_value(template, step_id), "your application details"

    # postconditions ----------------------------------------------------------------
    async def _error_text(self) -> str | None:
        try:
            loc = self.page.locator(self.portal.error_selector)
            for i in range(min(await loc.count(), 5)):
                el = loc.nth(i)
                if await el.is_visible():
                    text = (await el.inner_text()).strip()
                    if len(text) >= 3:  # skip required-field markers such as "*"
                        return text[:300]
        except PWError:
            return None
        return None

    async def _expect_once(self, exp: Expect | None) -> tuple[bool, str, str | None]:
        try:
            if exp is None or exp.no_error:
                err = await self._error_text()
                if err:
                    return False, f"portal shows an error: {err}", err
            if exp is None:
                return True, "", None
            if exp.url_contains and exp.url_contains not in self.page.url:
                return False, f"expected URL containing {exp.url_contains!r}, at {urlparse(self.page.url).path}", None
            if exp.visible_text and not await self.page.get_by_text(exp.visible_text).first.is_visible():
                return False, f"text {exp.visible_text!r} not visible", None
            if exp.heading and not await self.page.get_by_role("heading", name=exp.heading).first.is_visible():
                return False, f"heading {exp.heading!r} not visible", None
            if exp.hidden_text and await self.page.get_by_text(exp.hidden_text).first.is_visible():
                return False, f"text {exp.hidden_text!r} still visible", None
            if exp.field_filled:
                loc = build(self.page, exp.field_filled)
                if await loc.count() == 0 or not await loc.first.input_value():
                    return False, "field is still empty", None
            return True, "", None
        except PWError as e:  # navigation in progress
            return False, f"page changing: {str(e).splitlines()[0][:120]}", None

    async def _same_document(self) -> bool:
        try:
            return bool(await self.page.evaluate("() => window.__cpMark === true"))
        except PWError:
            return False

    async def _before_click(self) -> None:
        """Remember any error already on the page, so a stale banner is not read as the click's result."""
        self._stale_error = await self._error_text()
        try:
            await self.page.evaluate("() => { window.__cpMark = true; }")
        except PWError:
            pass

    async def _wait_expect(self, exp: Expect | None, timeout_ms: int) -> tuple[bool, str, str | None]:
        stale, self._stale_error = self._stale_error, None
        deadline = time.monotonic() + timeout_ms / 1000
        seen_err = None
        while True:
            ok, reason, err = await self._expect_once(exp)
            if ok:
                return ok, reason, err
            if err:
                if not (stale and err == stale and await self._same_document()):
                    return ok, reason, err
                seen_err = err
            if time.monotonic() >= deadline:
                return False, reason, seen_err
            await asyncio.sleep(0.25)

    async def _readback(self, step: Step, loc, value: str | None) -> bool:
        try:
            if step.do == "fill":
                return (await loc.input_value()) == value
            if step.do == "select":
                return bool(await loc.evaluate(
                    "(el, v) => { const o = el.options[el.selectedIndex];"
                    " return !!o && (o.value === v || o.text.trim().toLowerCase() === v.trim().toLowerCase()); }",
                    value,
                ))
            if step.do == "check":
                return await loc.is_checked()
            if step.do == "upload":
                return (await loc.evaluate("el => el.files ? el.files.length : 0")) > 0
        except PWError:
            return False
        return True

    async def verify_step(self, step: Step, timeout_ms: int | None = None) -> tuple[bool, str, str | None]:
        return await self._wait_expect(step.expect, timeout_ms or step.timeout_ms or settings.step_timeout_ms)

    # actions -----------------------------------------------------------------------
    async def _select(self, loc, value: str, timeout_ms: int = 8000) -> None:
        want = value.strip().lower()
        norm = lambda x: re.sub(r"[^a-z0-9]", "", x.lower().replace("&", "and"))
        deadline = time.monotonic() + min(timeout_ms, 8000) / 1000
        while True:  # many portals fill a dropdown's options after the page appears
            options = await loc.evaluate("el => [...el.options].map(o => ({v: o.value, t: o.text.trim()}))")
            match = next((o for o in options if o["v"].lower() == want or o["t"].lower() == want), None)
            # "Dadra and Nagar Haveli" vs "Dadra & Nagar Haveli", extra spaces, case
            match = match or next((o for o in options if o["v"] and norm(o["t"]) == norm(value)), None)
            if match or time.monotonic() >= deadline:
                break
            await asyncio.sleep(0.25)
        if not match:
            raise StepFailure("value_not_available", f"the portal has no option matching the requested value ({len(options)} options)")
        await loc.select_option(value=match["v"])

    async def _wait_options(self, target: Target, timeout_ms: int) -> None:
        loc = await resolve(self.page, target, timeout_ms)
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if await loc.evaluate("el => [...el.options].filter(o => o.value !== '').length") > 0:
                return
            await asyncio.sleep(0.2)
        raise StepFailure("timeout", "dependent dropdown did not load its options", transient=True)

    async def _act(self, step: Step, target: Target | None, timeout_ms: int) -> None:
        if step.do == "goto":
            url = self.resolve_value(step.url, step.id)
            host = urlparse(url).hostname or ""
            if not self.host_allowed(host):
                raise Stop(TaskStatus.failed, f"route tried to open {host}, which is not allow-listed")
            try:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            except PWTimeout:
                raise StepFailure("timeout", f"page {urlparse(url).path} did not load", transient=True)
            return
        if step.do == "press":
            await self.page.keyboard.press(step.key or "Enter")
            return
        if step.do == "wait_for":
            return
        if step.do == "extract":
            await self._extract(step.extract, step.id, timeout_ms)
            return
        try:
            loc = await resolve(self.page, self.render_target(target, step.id), timeout_ms, attached_only=step.do == "upload")
        except LocatorError as e:
            raise StepFailure(e.kind, str(e), healable=True)

        value = self.resolve_value(step.value, step.id) if step.value else None
        if step.do == "fill":
            await loc.fill(value or "")
        elif step.do == "select":
            await self._select(loc, value or "", timeout_ms)
        elif step.do == "check":
            want = value not in {"false", "no", "0"}
            box = await loc.bounding_box()
            if box and (box["width"] <= 2 or box["height"] <= 2):
                # Visually hidden input styled through its label (common on React portals): use the label.
                if await loc.is_checked() != want:
                    await loc.evaluate("el => (el.labels && el.labels[0] ? el.labels[0] : el).click()")
            else:
                try:
                    await loc.set_checked(want, timeout=2500)
                except PWError:
                    if await loc.is_checked() != want:
                        await loc.evaluate("el => (el.labels && el.labels[0] ? el.labels[0] : el).click()")
        elif step.do == "upload":
            await loc.set_input_files(value)
        elif step.do == "click":
            await self._before_click()
            await loc.click(timeout=timeout_ms)
            await self._adopt_popup()
            return

        ok = await self._readback(step, loc, value)
        shown, source = self.display_value(step.value, step.id) if step.value else ("ticked", "agent")
        chosen = PLACEHOLDER.search((target.id or "") if target else "")
        if step.do == "check" and not step.value and chosen and chosen.group(1) == "input":
            shown, source = str(self.task.inputs.get(chosen.group(2), "")), "your application details"
        spec = self.route.input(PLACEHOLDER.fullmatch(step.value).group(2)) if step.value and PLACEHOLDER.fullmatch(step.value) else None
        self.state.filled[step.id] = {
            "step_id": step.id,
            "label": step.label or (spec.label if spec and spec.label else None) or step.intent or step.id,
            "value": shown,
            "source": source,
            "readback_ok": ok,
        }
        if not ok:
            self.emit("info", f"Read-back after {step.do} did not match; flagged on the approval card", step.id)
        if step.wait_options:
            await self._wait_options(step.wait_options, timeout_ms)

    def _timeout_for(self, step: Step) -> int:
        if self.state.drift_mode and step.do in {"fill", "select", "check", "click", "upload"}:
            return 1500  # layout drifted: probe briefly, then go straight to Tier 2
        if step.optional and not step.timeout_ms:
            return 2500  # optional questions often never appear; do not wait long
        return step.timeout_ms or settings.step_timeout_ms

    async def _tier1(self, step: Step) -> None:
        timeout = self._timeout_for(step)
        await self._act(step, step.target, timeout)
        if step.do != "click" and step.expect is None:
            return
        ok, reason, err = await self._wait_expect(step.expect, step.timeout_ms or settings.step_timeout_ms)
        if ok:
            return
        if err:
            raise StepFailure("validation_error", reason)
        if self.portal.login_detect and (await self._expect_once(self.portal.login_detect))[0]:
            raise StepFailure("session_expired", "the portal returned to its login page (session expired)")
        raise StepFailure("unexpected_page", reason, healable=True)

    # used by the healer ----------------------------------------------------------
    async def perform_step_on(self, step: Step, target: Target) -> tuple[bool, str]:
        try:
            await self._act(step, target, 5000)
        except StepFailure as e:
            return False, e.detail
        except PWError as e:
            return False, str(e).splitlines()[0][:160]
        filled = self.state.filled.get(step.id)
        if filled and not filled["readback_ok"]:
            return False, "value did not stick in this field"
        ok, reason, _ = await self.verify_step(step, 8000 if step.expect else 1000)
        return ok, reason

    async def perform_aux(self, action: str, target: Target, step_id: str) -> tuple[bool, str]:
        try:
            loc = await resolve(self.page, target, 5000)
            if action == "click":
                await loc.click(timeout=5000)
                await self._adopt_popup()
                try:
                    await self.page.wait_for_load_state("domcontentloaded", timeout=8000)
                except PWTimeout:
                    pass
            else:
                await loc.set_checked(True)
        except (LocatorError, PWError) as e:
            return False, str(e).splitlines()[0][:160]
        self.state.aux_actions.append(f"{action}: {target.describe()}")
        return True, ""

    # drift check -------------------------------------------------------------------
    async def _drift_check(self, step: Step) -> None:
        if not step.fingerprint:
            return
        snap = await take(self.page)
        self.note_suspicious(snap, step.id)
        expected = set(step.fingerprint)
        missing = expected - snap.field_keys()
        ratio = len(missing) / len(expected)
        if ratio > settings.drift_threshold:
            self.state.drift_mode = True
            self.emit_heal(step.id, f"Layout drift: {ratio:.0%} of expected fields missing ({sorted(missing)}). Skipping slow Tier 1 lookups; Tier 2 will repair.")

    # human steps -------------------------------------------------------------------
    async def _human(self, step: Step) -> None:
        kind = step.kind or "other"
        await self._ask_human(step.id, kind, step.intent or HUMAN_INSTRUCTIONS[kind], step.expect, step.completion == "auto")

    async def _ask_human(self, step_id: str, kind: str, instructions: str, exp: Expect | None, auto: bool) -> None:
        self.set_status(
            TaskStatus.awaiting_human, f"Waiting for the citizen: {kind}",
            data={"kind": kind, "instructions": instructions, "citizen_url": self.citizen_url},
        )
        self.emit("human_needed", instructions, step_id, {"kind": kind, "citizen_url": self.citizen_url})
        if exp and exp.field_filled:
            # Put the cursor where the citizen must type, so they need not tap precisely on a phone.
            try:
                field_loc = build(self.page, exp.field_filled).first
                await field_loc.scroll_into_view_if_needed(timeout=3000)
                await field_loc.focus(timeout=3000)
            except PWError:
                pass
        req = HumanRequest(step_id, kind, instructions)
        ok, reason, waited = await self.gateway.wait_human(
            self.task_id, req, lambda: self._human_check(exp), auto, settings.human_timeout_s,
            on_retry=lambda r: self.emit("human_needed", f"Not done yet: {r}", step_id, {"kind": kind}),
        )
        self.clock.human_wait_ms += waited
        if not ok:
            raise Stop(TaskStatus.needs_review if "cancel" in reason else TaskStatus.failed, f"{kind} step: {reason}")
        self.set_status(TaskStatus.running, f"Citizen completed the {kind} step")

    async def _human_check(self, exp: Expect | None) -> tuple[bool, str]:
        ok, reason, _ = await self._expect_once(exp)
        return ok, reason

    # approval ----------------------------------------------------------------------
    def _differences(self) -> list[str]:
        diffs = [f"{v['label']}: the value read back from the page did not match" for v in self.state.filled.values() if not v["readback_ok"]]
        for key in self.route.profile_match:
            given, held = self.task.inputs.get(key), self.profile.get(key)
            if given and held and str(given).strip().lower() != str(held).strip().lower():
                diffs.append(f"{key}: application says {given!r}, your profile says {held!r}")
        return diffs

    async def _approval(self, step: Step, submit_text: str) -> None:
        shot = self.evidence_dir / "approval.png"
        await self.page.screenshot(path=str(shot), full_page=True)
        self.state.evidence["approval_screenshot"] = shot
        card = {
            "task_id": self.task_id,
            "portal": {"name": self.portal.name, "is_sandbox": self.portal.is_sandbox},
            "service": self.route.description or self.route.service_id,
            "mode": self.task.mode.value,
            "values": [v for v in self.state.filled.values() if v["source"] != "document"],
            "documents": [{"key": d.key, "size_kb": round(d.size_kb, 1), "note": d.note} for d in self.docs.values()],
            "agent_extra_actions": self.state.aux_actions,
            "differences": self._differences(),
            "warnings": [f"This page contained text addressed to an AI agent; it was ignored: {t!r}" for t in self.state.suspicious],
            "next": (
                f"If you approve, the agent presses '{submit_text}' once and reads back the reference number. "
                "It never retries a submission automatically."
                if self.task.mode == TaskMode.assist
                else "Dry run: nothing will be submitted. This is what the portal would receive."
            ),
            "expires_in_s": settings.approval_timeout_s,
        }
        self.state.approval_card = card
        if self.task.mode == TaskMode.dry_run:
            self.state.outcome = "dry_run_complete"
            self.emit("approval_needed", "Dry run reached the final review page; stopping before submit.", step.id, {"card": card})
            raise DryRunDone()
        self.set_status(TaskStatus.awaiting_approval, "Waiting for the citizen to approve", data={"citizen_url": self.citizen_url})
        self.emit("approval_needed", "Review and approve the submission", step.id, {"card": card, "citizen_url": self.citizen_url})
        decision, waited = await self.gateway.request_approval(self.task_id, card, settings.approval_timeout_s)
        self.clock.human_wait_ms += waited
        if decision == "approved":
            self.state.approved = True
            self.set_status(TaskStatus.running, "Citizen approved the submission")
        elif decision == "rejected":
            raise Stop(TaskStatus.failed, "citizen rejected the submission")
        else:
            raise Stop(TaskStatus.failed, "approval timed out; nothing was submitted")

    # submit ------------------------------------------------------------------------
    async def _submit(self, step: Step, index: int) -> int:
        if not self.state.approved:
            raise Stop(TaskStatus.failed, f"step {step.id} is a final submit but there is no approval")
        if self.task.mode != TaskMode.assist or not self.portal.submission_enabled:
            raise Stop(TaskStatus.failed, "submission is disabled for this task or portal")
        self.set_status(TaskStatus.submitting, "Submitting once, as approved")
        try:
            await self._act(step, step.target, self._timeout_for(step))
        except StepFailure as f:
            if f.kind.startswith("locator"):
                raise  # nothing was clicked; safe to repair
            raise Stop(TaskStatus.needs_review, f"submit step failed before the click completed: {f.detail}")
        except PWError as e:
            raise Stop(TaskStatus.needs_review, f"Submit click raised an error; the submission state is unknown. Do not resubmit; check the portal. ({str(e)[:120]})")
        self.set_status(TaskStatus.verifying, "Reading the portal's response")
        ok, reason, err = await self._wait_expect(step.expect, step.timeout_ms or settings.step_timeout_ms)
        if not ok:
            for rec in step.recover:
                if err and rec.error_contains.lower() in err.lower():
                    n = self.state.recover_counts.get(rec.goto, 0)
                    if n < rec.max_times:
                        self.state.recover_counts[rec.goto] = n + 1
                        self.emit("info", f"Portal rejected the submission ({err[:120]}); nothing was filed. Going back to '{rec.goto}'.", step.id)
                        self.set_status(TaskStatus.running)
                        return next(i for i, s in enumerate(self.steps) if s.id == rec.goto)
            raise Stop(
                TaskStatus.needs_review,
                f"Could not confirm the submission ({reason}). Do NOT resubmit; check the portal's status page first.",
            )
        await self._capture(step)
        self.state.outcome = "submitted"
        return index + 1

    async def _extract(self, spec: Extract, step_id: str, timeout_ms: int) -> None:
        """Read results straight off the page. Nothing here comes from a model."""
        out: dict = {"source_url": self.page.url, "retrieved_at": utcnow().isoformat(), "items": []}
        if spec.items_css:
            items = self.page.locator(spec.items_css)
            deadline = time.monotonic() + timeout_ms / 1000
            empty = False
            while True:  # wait for results, or for the portal's own "nothing found" message
                if await items.count() > 0:
                    break
                if spec.empty_regex and re.search(spec.empty_regex, await self.page.inner_text("body")):
                    empty = True
                    break
                if time.monotonic() >= deadline:
                    raise StepFailure("unexpected_page", "no result items appeared on the page")
                await asyncio.sleep(0.25)
            if empty:
                out["count"] = 0
                self.state.result = out
                self.emit("info", "The portal found no matching results for these details", step_id, {"result": out})
                return
            out["items"] = await items.evaluate_all(
                "(els, n) => els.slice(0, n).map(e => ({title: e.innerText.trim(), url: e.href || null}))", spec.limit
            )
        if spec.count_regex:
            m = re.search(spec.count_regex, await self.page.inner_text("body"))
            out["count"] = int(m.group(1)) if m and m.group(1).isdigit() else (m.group(1) if m else None)
        self.state.result = out
        self.emit("info", f"Read {len(out['items'])} results from the portal" + (f" (portal reports {out['count']})" if out.get("count") is not None else ""), step_id, {"result": out})

    async def _capture(self, step: Step) -> None:
        if not step.capture:
            return
        body = await self.page.inner_text("body")
        for name, pattern in step.capture.items():
            m = re.search(pattern, body)
            if m:
                self.state.captured[name] = m.group(1)
        if "reference_no" in step.capture and "reference_no" not in self.state.captured:
            self.emit("info", "Submitted, but the reference number pattern did not match the confirmation page", step.id)

    # heal --------------------------------------------------------------------------
    async def _heal(self, step: Step, index: int, f: StepFailure) -> int:
        phase = "postcondition" if f.kind == "unexpected_page" else "locate"
        self.emit_heal(step.id, f"Tier 1 failed at '{step.id}' ({f.kind}): {f.detail}. Starting Tier 2 repair.")
        res = await self.healer.heal(self, step, f.detail, phase)
        self.clock.model_ms += res.model_ms
        self.clock.model_calls += res.model_calls
        self.clock.input_tokens += res.input_tokens
        self.clock.output_tokens += res.output_tokens
        self.state.heals.append({"step_id": step.id, "failure": f.kind, "ok": res.ok, "strategy": res.strategy, "reason": res.reason, "model_calls": res.model_calls})
        if not res.ok:
            if res.human_kind:
                n = self.state.human_retries.get(step.id, 0)
                if n == 0:
                    self.state.human_retries[step.id] = 1
                    await self._ask_human(step.id, res.human_kind, HUMAN_INSTRUCTIONS.get(res.human_kind, HUMAN_INSTRUCTIONS["other"]), None, auto=False)
                    if phase == "locate":
                        return index  # rerun the step from Tier 1
                    ok, reason, _ = await self.verify_step(step, 3000)
                    if ok:
                        return index + 1
                    raise Stop(TaskStatus.needs_review, f"After the citizen's help, step '{step.id}' still fails: {reason}")
            raise Stop(TaskStatus.needs_review, f"Could not repair step '{step.id}': {res.reason}")

        self.emit_heal(step.id, f"Repaired '{step.id}' with {res.strategy}: {res.reason}", )
        self.state.patched = True
        aux_steps: list[Step] = []
        for n, a in enumerate(a for a in res.actions if not a.is_step_action):
            if a.target is None:
                self.state.patch_ok = False
                continue
            aux_steps.append(Step(id=f"{step.id}_auto{n + 1}", do=a.do, target=a.target, intent=f"Added by healer: {a.do} {a.desc}"))
        step_actions = [a for a in res.actions if a.is_step_action]
        if step_actions:
            new_target = step_actions[-1].target
            if new_target is None:
                self.state.patch_ok = False
            else:
                old = step.target.model_copy(update={"alt": []}) if step.target else None
                new_target = new_target.model_copy(update={"alt": ([old] if old else []) + (step.target.alt if step.target else [])})
                step.target = new_target
        if phase == "locate":
            self.steps[index:index] = aux_steps
            return index + len(aux_steps) + 1
        self.steps[index + 1:index + 1] = aux_steps
        return index + 1 + len(aux_steps)

    # main loop -----------------------------------------------------------------------
    def _guard(self) -> None:
        if self.store.get_flag("kill_switch", False):
            raise Stop(TaskStatus.failed, "kill switch is on")
        if self.clock.timing().agent_ms > settings.task_budget_s * 1000:
            raise Stop(TaskStatus.failed, "task time budget exceeded")

    async def _run_step(self, step: Step, index: int) -> int:
        if step.when and not self.when_ok(step):
            return index + 1
        self.emit("step", f"{step.id}: {step.do}" + (f" ({step.intent})" if step.intent else ""), step.id)
        if step.do == "human_step":
            await self._human(step)
            return index + 1
        if step.do == "approval_gate":
            submit = next((s for s in self.steps[index + 1:] if s.submit), None)
            names = [t.role_name or t.text for t in ([submit.target, *submit.target.alt] if submit and submit.target else [])]
            submit_text = next((n for n in names if n), None) or (submit.label if submit else None) or "Submit"
            await self._approval(step, submit_text)
            return index + 1
        attempt = 0
        while True:
            try:
                if step.submit:
                    return await self._submit(step, index)
                await self._tier1(step)
                await self._drift_check(step)
                return index + 1
            except StepFailure as f:
                if f.transient and step.retry == "once" and attempt == 0:
                    attempt += 1
                    self.emit("info", f"Transient failure at '{step.id}' ({f.detail}); retrying once", step.id)
                    continue
                if step.optional and (f.kind.startswith("locator") or f.kind == "missing_value"):
                    self.emit("info", f"Optional step '{step.id}' skipped: {f.detail}", step.id)
                    return index + 1
                if f.healable:
                    return await self._heal(step, index, f)
                if f.kind == "validation_error" and not self.state.human_fixes.get(step.id):
                    # The portal asked for something we have no answer for, or rejected a value.
                    # Never guess on the citizen's behalf: show them the portal's message.
                    self.state.human_fixes[step.id] = 1
                    msg = f.detail.removeprefix("portal shows an error: ")
                    await self._ask_human(
                        step.id, "other",
                        f"The portal says: \u201c{msg}\u201d. Please answer or correct this in the page below, "
                        "go on to the next page, then tap Done.",
                        step.expect, auto=False,
                    )
                    return index + 1
                if step.optional:
                    self.emit("info", f"Optional step '{step.id}' skipped: {f.detail}", step.id)
                    return index + 1
                if f.kind == "session_expired":
                    raise Stop(TaskStatus.needs_review, "The portal session expired mid-run. The citizen must log in again; restart the task.")
                raise Stop(TaskStatus.needs_review, f"Step '{step.id}' failed ({f.kind}): {f.detail}")
            except PWError as e:
                if attempt == 0 and step.retry == "once" and not step.submit:
                    attempt += 1
                    self.emit("info", f"Browser error at '{step.id}'; retrying once", step.id)
                    continue
                raise Stop(TaskStatus.needs_review, f"Browser error at '{step.id}': {str(e).splitlines()[0][:200]}")

    async def run(self) -> None:
        await self.setup()
        self.set_status(TaskStatus.running, f"Running {self.route.portal_id}/{self.route.service_id} v{self.route.version} ({self.task.mode.value})")
        try:
            if self.route.explore and (self.task.strategy == "explore" or not self.steps):
                from .engines import explore_engine

                self.state.explored = True
                await explore_engine(self.healer.llm).run(self)
            else:
                i = 0
                while i < len(self.steps):
                    self._guard()
                    i = await self._run_step(self.steps[i], i)
        except DryRunDone:
            pass
        if self.route.read_only and self.state.outcome is None:
            self.state.outcome = "information_retrieved"
        await self._final_evidence()

    async def _final_evidence(self) -> None:
        try:
            shot = self.evidence_dir / "final.png"
            await self.page.screenshot(path=str(shot), full_page=True)
            self.state.evidence["final_screenshot"] = shot
            html = await self.page.content()
            (self.evidence_dir / "final_page.sha256").write_text(hashlib.sha256(html.encode()).hexdigest())
            self.state.evidence["final_page_hash"] = self.evidence_dir / "final_page.sha256"
        except PWError:
            pass
        manifest = {
            "route": f"{self.route.portal_id}/{self.route.service_id}@v{self.route.version}",
            "values": list(self.state.filled.values()),
            "documents": {k: {"size_kb": round(d.size_kb, 1), "note": d.note} for k, d in self.docs.items()},
            "vault_keys_used": self.vault.access_log,
            "heals": self.state.heals,
            "agent_extra_actions": self.state.aux_actions,
            "blocked_navigations": self.state.blocked_navigations,
            "captured": self.state.captured,
            "result": self.state.result,
        }
        path = self.evidence_dir / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2))
        self.state.evidence["manifest"] = path

    def patched_route(self) -> Route:
        return self.route.model_copy(
            update={"steps": self.steps, "status": "candidate", "version": self.route.version + 1, "patched_from": self.route.version, "verified_runs": 0}
        )
