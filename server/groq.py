"""Groq, the server's open-model provider for reports: speech to text (Whisper) and JSON chat (translation).
The key stays on the server; nothing here is ever sent to the browser."""

import json
import os

import httpx

BASE = "https://api.groq.com/openai/v1"
transport: httpx.AsyncBaseTransport | None = None  # tests inject a MockTransport


class GroqUnavailable(RuntimeError):
    pass


def available() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))


def _auth() -> dict:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise GroqUnavailable("GROQ_API_KEY is not set on the server.")
    return {"Authorization": f"Bearer {key}"}


async def chat_json(system: str, user: str, max_tokens: int = 1500) -> dict:
    """One JSON object from the chat model (GROQ_MODEL; llama-3.3-70b was retired on 2026-08-16)."""
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    reasoning = model.startswith("openai/gpt-oss")
    body = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": max(max_tokens, 2000) if reasoning else max_tokens,  # its reasoning counts against the limit
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        **({"reasoning_effort": "low", "include_reasoning": False} if reasoning else {}),
    }
    try:
        async with httpx.AsyncClient(timeout=40, transport=transport) as c:
            r = await c.post(f"{BASE}/chat/completions", headers=_auth(), json=body)
        if r.status_code >= 400:
            raise GroqUnavailable(f"Groq answered {r.status_code}.")
        return json.loads(r.json()["choices"][0]["message"]["content"])
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise GroqUnavailable("Groq did not return a usable answer.") from exc


async def transcribe(audio: bytes, filename: str, media_type: str) -> dict:
    """{text, language}: Whisper on Groq, which detects the language and writes it in its own script."""
    data = {"model": os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo"), "response_format": "verbose_json", "temperature": "0"}
    try:
        async with httpx.AsyncClient(timeout=60, transport=transport) as c:
            r = await c.post(f"{BASE}/audio/transcriptions", headers=_auth(), data=data, files={"file": (filename, audio, media_type)})
        if r.status_code >= 400:
            raise GroqUnavailable(f"Groq speech-to-text answered {r.status_code}.")
        out = r.json()
        return {"text": (out.get("text") or "").strip(), "language": out.get("language")}
    except (httpx.HTTPError, ValueError) as exc:
        raise GroqUnavailable("Groq speech-to-text is unavailable.") from exc
