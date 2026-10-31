"""A simulated citizen for tests and evals.

It acts only through the same channels a real citizen uses: the live-view
input events (click / type) and the approve / done buttons. It reads the OTP
from the sandbox portal's "phone" (/__sms), as a person would read their SMS.
"""

from __future__ import annotations

import asyncio
import re
import time

import httpx

from executor.models import TERMINAL_STATUSES, TaskStatus


class SimHuman:
    def __init__(self, executor, sandbox_url: str, approve: bool = True, captcha: str = "7KQ2M",
                 wrong_captcha_first: bool = False, approval_delay_s: float = 0.0):
        self.ex = executor
        self.sandbox_url = sandbox_url
        self.approve = approve
        self.captcha = captcha
        self.wrong_first = wrong_captcha_first
        self.approval_delay_s = approval_delay_s
        self.captcha_attempts = 0
        self.actions: list[str] = []

    async def drive(self, task_id: str, timeout_s: float = 180) -> TaskStatus:
        handled: set[int] = set()
        start = time.monotonic()
        while time.monotonic() - start < timeout_s:
            status = TaskStatus(self.ex.store.get_task(task_id)["status"])
            if status in TERMINAL_STATUSES:
                return status
            ch = self.ex.gateway.channels.get(task_id)
            if ch and ch.human and id(ch.human) not in handled:
                handled.add(id(ch.human))
                await self._human(task_id, ch)
            if ch and ch.approval and not ch.approval.decision.done():
                await asyncio.sleep(self.approval_delay_s)
                self.ex.gateway.decide(task_id, "approved" if self.approve else "rejected")
                self.actions.append("approve" if self.approve else "reject")
            await asyncio.sleep(0.15)
        raise TimeoutError(f"task {task_id} did not finish in {timeout_s}s")

    async def _click(self, live, page, selector: str) -> None:
        loc = page.locator(selector)
        await loc.wait_for(state="visible", timeout=10000)
        vp = page.viewport_size
        box = await loc.bounding_box()
        if box["y"] < 0 or box["y"] + box["height"] > vp["height"]:
            await live.dispatch({"t": "scroll", "dy": box["y"] - vp["height"] / 2})
            await asyncio.sleep(0.3)
            box = await loc.bounding_box()
        await live.dispatch({"t": "click", "x": (box["x"] + box["width"] / 2) / vp["width"], "y": (box["y"] + box["height"] / 2) / vp["height"]})

    async def _human(self, task_id: str, ch) -> None:
        live = await self.ex.gateway.live(task_id)
        page = ch.page
        kind = ch.human.kind
        if kind == "otp":
            otp = None
            for _ in range(20):
                async with httpx.AsyncClient() as c:
                    msgs = (await c.get(f"{self.sandbox_url}/__sms")).json()["messages"]
                if msgs:
                    otp = re.search(r"\b(\d{6})\b", msgs[-1]["text"]).group(1)
                    break
                await asyncio.sleep(0.2)
            await self._click(live, page, "#otp")
            await live.dispatch({"t": "type", "text": otp})
            await self._click(live, page, "#verifyOtp")
            self.actions.append("otp")
        elif kind == "captcha":
            self.captcha_attempts += 1
            answer = "WRONG" if self.wrong_first and self.captcha_attempts == 1 else self.captcha
            await self._click(live, page, "#captchaInput")
            await live.dispatch({"t": "type", "text": answer})
            await asyncio.sleep(0.2)
            self.ex.gateway.human_done(task_id)
            self.actions.append(f"captcha:{'wrong' if answer == 'WRONG' else 'ok'}")
        else:
            self.ex.gateway.human_done(task_id)
            self.actions.append(kind)
