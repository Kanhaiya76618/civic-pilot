"""Human hand-off gateway: approval before any final submit, and live control for OTP/CAPTCHA/payment.

The citizen types the OTP or CAPTCHA into the portal page through the live
view. Keystrokes pass through this server to Playwright's keyboard but are
never logged, stored, or shown to the model. Screencast frames are kept in
memory only.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from playwright.async_api import Page

log = logging.getLogger("civic.handoff")

ALLOWED_KEYS = {"Backspace", "Enter", "Tab", "Delete", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Escape"}


class LiveView:
    """CDP Page.startScreencast -> JPEG frames -> websocket clients."""

    def __init__(self, page: Page):
        self.page = page
        self.cdp = None
        self.subscribers: set[asyncio.Queue] = set()
        self.last_frame: dict | None = None
        self._bg: set[asyncio.Task] = set()

    async def start(self) -> None:
        if self.cdp:
            return
        self.cdp = await self.page.context.new_cdp_session(self.page)
        self.cdp.on("Page.screencastFrame", self._on_frame)
        await self.cdp.send(
            "Page.startScreencast", {"format": "jpeg", "quality": 60, "maxWidth": 1280, "maxHeight": 1600}
        )

    def _on_frame(self, params: dict) -> None:
        t = asyncio.create_task(self._handle(params))
        self._bg.add(t)
        t.add_done_callback(self._bg.discard)

    async def _handle(self, params: dict) -> None:
        try:
            await self.cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})
        except Exception:  # page closed between frame and ack
            return
        meta = params.get("metadata", {})
        frame = {"data": params["data"], "w": meta.get("deviceWidth"), "h": meta.get("deviceHeight")}
        self.last_frame = frame
        for q in list(self.subscribers):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(frame)

    async def stop(self) -> None:
        if not self.cdp:
            return
        try:
            await self.cdp.send("Page.stopScreencast")
            await self.cdp.detach()
        except Exception:
            pass
        self.cdp = None

    async def dispatch(self, msg: dict) -> None:
        """Apply one input event from the citizen. Content is never logged."""
        t = msg.get("t")
        vp = self.page.viewport_size or {"width": 1280, "height": 900}
        if t == "click":
            x, y = float(msg["x"]), float(msg["y"])
            if not (0 <= x <= 1 and 0 <= y <= 1):
                return
            await self.page.mouse.click(x * vp["width"], y * vp["height"])
        elif t == "type":
            text = str(msg.get("text", ""))[:200]
            await self.page.keyboard.type(text)
        elif t == "key" and msg.get("key") in ALLOWED_KEYS:
            await self.page.keyboard.press(msg["key"])
        elif t == "scroll":
            await self.page.mouse.wheel(0, max(-2000, min(2000, float(msg.get("dy", 0)))))


@dataclass
class HumanRequest:
    step_id: str
    kind: str
    instructions: str
    done: asyncio.Event = field(default_factory=asyncio.Event)
    cancelled: bool = False


@dataclass
class ApprovalRequest:
    card: dict
    decision: asyncio.Future


@dataclass
class Channel:
    task_id: str
    token: str
    page: Page | None = None
    live: LiveView | None = None
    human: HumanRequest | None = None
    approval: ApprovalRequest | None = None


class Gateway:
    def __init__(self):
        self.channels: dict[str, Channel] = {}

    def open(self, task_id: str, token: str) -> Channel:
        ch = Channel(task_id, token)
        self.channels[task_id] = ch
        return ch

    async def close(self, task_id: str) -> None:
        ch = self.channels.pop(task_id, None)
        if ch and ch.live:
            await ch.live.stop()

    def check_token(self, task_id: str, token: str) -> Channel | None:
        ch = self.channels.get(task_id)
        return ch if ch and token and ch.token == token else None

    async def attach_page(self, task_id: str, page: Page) -> None:
        ch = self.channels[task_id]
        if ch.page is page:
            return
        if ch.live:
            await ch.live.stop()
            ch.live = None
        ch.page = page

    async def live(self, task_id: str) -> LiveView | None:
        ch = self.channels.get(task_id)
        if not ch or not ch.page:
            return None
        if not ch.live:
            ch.live = LiveView(ch.page)
            await ch.live.start()
        return ch.live

    def input_allowed(self, task_id: str) -> bool:
        ch = self.channels.get(task_id)
        return bool(ch and ch.human and not ch.human.done.is_set())

    # human steps -----------------------------------------------------------
    async def wait_human(
        self,
        task_id: str,
        req: HumanRequest,
        check: Callable[[], Awaitable[tuple[bool, str]]],
        auto_complete: bool,
        timeout_s: float,
        on_retry: Callable[[str], None] | None = None,
    ) -> tuple[bool, str, int]:
        """Wait until the step's postcondition holds. Returns (ok, reason, waited_ms)."""
        ch = self.channels[task_id]
        ch.human = req
        start = time.monotonic()
        try:
            while time.monotonic() - start < timeout_s:
                if req.cancelled:
                    return False, "citizen cancelled", int((time.monotonic() - start) * 1000)
                if auto_complete:
                    ok, _ = await check()
                    if ok:
                        return True, "", int((time.monotonic() - start) * 1000)
                    try:
                        await asyncio.wait_for(req.done.wait(), timeout=0.7)
                    except asyncio.TimeoutError:
                        continue
                else:
                    try:
                        await asyncio.wait_for(req.done.wait(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                if req.cancelled:
                    continue
                ok, reason = await check()
                if ok:
                    return True, "", int((time.monotonic() - start) * 1000)
                req.done.clear()
                if on_retry:
                    on_retry(reason)
            return False, "timed out waiting for the citizen", int((time.monotonic() - start) * 1000)
        finally:
            ch.human = None

    def human_done(self, task_id: str) -> bool:
        ch = self.channels.get(task_id)
        if not ch or not ch.human:
            return False
        ch.human.done.set()
        return True

    def human_cancel(self, task_id: str) -> bool:
        ch = self.channels.get(task_id)
        if not ch or not ch.human:
            return False
        ch.human.cancelled = True
        ch.human.done.set()
        return True

    # approval --------------------------------------------------------------
    async def request_approval(self, task_id: str, card: dict, timeout_s: float) -> tuple[str, int]:
        """Returns ('approved' | 'rejected' | 'timeout', waited_ms). There is no auto-approve."""
        ch = self.channels[task_id]
        fut = asyncio.get_running_loop().create_future()
        ch.approval = ApprovalRequest(card, fut)
        start = time.monotonic()
        try:
            decision = await asyncio.wait_for(fut, timeout=timeout_s)
        except asyncio.TimeoutError:
            decision = "timeout"
        finally:
            ch.approval = None
        return decision, int((time.monotonic() - start) * 1000)

    def decide(self, task_id: str, decision: str) -> bool:
        ch = self.channels.get(task_id)
        if not ch or not ch.approval or ch.approval.decision.done():
            return False
        if decision not in {"approved", "rejected"}:
            return False
        ch.approval.decision.set_result(decision)
        return True
