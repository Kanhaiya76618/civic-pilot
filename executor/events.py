"""Task events: stored in SQLite, fanned out to SSE subscribers, pushed to callback URLs."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time

import httpx

from .config import settings
from .db import Store
from .models import TaskEvent

log = logging.getLogger("civic.events")


def sign_body(body: bytes, timestamp: str, secret: str | None = None) -> str:
    key = (secret or settings.webhook_secret).encode()
    mac = hmac.new(key, timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def verify_signature(body: bytes, timestamp: str, signature: str, secret: str | None = None, max_age_s: int = 300) -> bool:
    """For Part 1 / Part 2 receivers: check X-CivicPulse-Signature and X-CivicPulse-Timestamp."""
    if abs(time.time() - int(timestamp)) > max_age_s:
        return False
    return hmac.compare_digest(sign_body(body, timestamp, secret), signature)


class EventBus:
    def __init__(self, store: Store):
        self.store = store
        self._subs: dict[str, set[asyncio.Queue]] = {}
        self._callbacks: dict[str, str] = {}
        self._bg: set[asyncio.Task] = set()

    def set_callback(self, task_id: str, url: str | None) -> None:
        if url:
            self._callbacks[task_id] = url

    def publish(self, event: TaskEvent) -> TaskEvent:
        payload = event.model_dump(mode="json")
        event.seq = self.store.add_event(event.task_id, payload)
        payload["seq"] = event.seq
        for q in list(self._subs.get(event.task_id, ())):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass
        url = self._callbacks.get(event.task_id)
        if url:
            self._spawn(self._post(url, {"type": "task_event", "event": payload}))
        return event

    def post_receipt(self, task_id: str, receipt: dict) -> None:
        url = self._callbacks.get(task_id)
        if url:
            self._spawn(self._post(url, {"type": "receipt", "receipt": receipt}))

    def subscribe(self, task_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subs.setdefault(task_id, set()).add(q)
        return q

    def unsubscribe(self, task_id: str, q: asyncio.Queue) -> None:
        self._subs.get(task_id, set()).discard(q)

    def _spawn(self, coro) -> None:
        t = asyncio.create_task(coro)
        self._bg.add(t)
        t.add_done_callback(self._bg.discard)

    async def _post(self, url: str, body: dict) -> None:
        raw = json.dumps(body, default=str).encode()
        ts = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-CivicPulse-Timestamp": ts,
            "X-CivicPulse-Signature": sign_body(raw, ts),
        }
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.post(url, content=raw, headers=headers)
                if r.status_code < 500:
                    return
            except httpx.HTTPError as e:
                log.warning("webhook %s failed (attempt %d): %s", url, attempt + 1, e)
            await asyncio.sleep(2**attempt)
