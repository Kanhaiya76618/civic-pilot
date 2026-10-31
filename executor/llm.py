"""Model access for repair and explore. Every request body is appended to a JSONL log so the
canary test can prove no sensitive value ever reaches the model.

Providers (CIVIC_LLM_PROVIDER):
  anthropic  Anthropic's API (ANTHROPIC_API_KEY), with server-side fallback on refusals
  aimlapi    Claude through AIML API's Anthropic-compatible /v1/messages (AIMLAPI_KEY)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Protocol

import anthropic

from .config import settings


@dataclass
class LLMResult:
    data: dict | None
    ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None


class LLM(Protocol):
    async def decide(self, system: str, user: str, schema: dict) -> LLMResult: ...


def log_request(body: dict) -> None:
    settings.ensure_dirs()
    with settings.llm_log_path.open("a") as f:
        f.write(json.dumps(body, default=str) + "\n")


class ClaudeLLM:
    def __init__(self, model: str | None = None, effort: str | None = None, provider: str | None = None):
        self.provider = provider or settings.llm_provider
        model = model or settings.llm_model
        if self.provider == "aimlapi":
            # Same Messages API shape; AIML authenticates with a Bearer token and names models "anthropic/<id>".
            self.client = anthropic.AsyncAnthropic(
                base_url=settings.aimlapi_base_url, auth_token=os.environ.get("AIMLAPI_KEY"), api_key=None
            )
            self.model = model if "/" in model else f"anthropic/{model}"
        else:
            self.client = anthropic.AsyncAnthropic()
            self.model = model
        self.effort = effort or settings.llm_effort

    async def decide(self, system: str, user: str, schema: dict) -> LLMResult:
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4000,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
        }
        log_request(request)
        start = time.monotonic()
        try:
            if self.provider == "anthropic":
                # Server-side fallback re-runs a refused request on another model inside the same call.
                resp = await self.client.beta.messages.create(
                    **request, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
                )
            else:
                resp = await self.client.messages.create(**request)
        except anthropic.APIConnectionError as e:
            return LLMResult(None, int((time.monotonic() - start) * 1000), error=f"connection: {e}")
        except anthropic.RateLimitError:
            return LLMResult(None, int((time.monotonic() - start) * 1000), error="rate limited")
        except anthropic.APIStatusError as e:
            return LLMResult(None, int((time.monotonic() - start) * 1000), error=f"api {e.status_code}: {e.message}")
        ms = int((time.monotonic() - start) * 1000)
        usage = resp.usage
        if resp.stop_reason == "refusal":
            return LLMResult(None, ms, usage.input_tokens, usage.output_tokens, error="model refused")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return LLMResult(None, ms, usage.input_tokens, usage.output_tokens, error="invalid JSON from model")
        return LLMResult(data, ms, usage.input_tokens, usage.output_tokens)


class ScriptedLLM:
    """Test double: returns pre-set decisions in order, and logs requests like the real one."""

    def __init__(self, decisions: list[dict]):
        self.decisions = list(decisions)
        self.requests: list[dict] = []

    async def decide(self, system: str, user: str, schema: dict) -> LLMResult:
        body = {"model": "scripted", "system": system, "messages": [{"role": "user", "content": user}]}
        self.requests.append(body)
        log_request(body)
        if not self.decisions:
            return LLMResult({"action": "give_up", "reason": "script exhausted"}, 1)
        return LLMResult(self.decisions.pop(0), 1)


def default_llm() -> LLM | None:
    if not settings.llm_enabled:
        return None
    return ClaudeLLM()
