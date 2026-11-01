"""Signed-in features for the home page: live news and the citizen's own history.

History is per account (the server's sign-in token decides whose) and holds only what a citizen
would recognise again: a title, a short note and a link back. Never private fields, OTPs or documents.
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Any, Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from . import news
from server.auth import require_role

if TYPE_CHECKING:
    from .worker import Executor

Kind = Literal["explain", "agent", "lookup", "filing", "report", "news"]
signed_in = require_role(["citizen", "admin"])


class HistoryIn(BaseModel):
    kind: Kind
    title: str = Field(min_length=1, max_length=200)
    subtitle: str | None = Field(None, max_length=300)
    link: str | None = Field(None, max_length=2000)  # Google News article links run to ~750 characters
    meta: dict[str, Any] = Field(default_factory=dict)


def make_account_router(ex: Callable[[], "Executor"]) -> APIRouter:
    r = APIRouter()

    @r.get("/app/news")
    async def get_news(refresh: bool = False):
        return await news.latest(force=refresh)

    @r.get("/app/me/history")
    async def my_history(kind: Kind | None = None, limit: int = Query(100, le=300), user=Depends(signed_in)):
        return ex().store.list_history(str(user.id), kind, limit)

    @r.post("/app/me/history", status_code=201)
    async def add_history(body: HistoryIn, user=Depends(signed_in)):
        if body.link and not (body.link.startswith("/") or body.link.startswith("https://")):
            raise HTTPException(400, "links must be app paths or https")
        if len(str(body.meta)) > 2000:
            raise HTTPException(413, "meta is too large")
        if body.kind == "news" and body.link and (dup := ex().store.history_has(str(user.id), "news", body.link)):
            return {**dup, "already_saved": True}  # saving the same article twice keeps one copy
        return ex().store.add_history("h_" + uuid.uuid4().hex[:14], str(user.id), body.kind, body.title.strip(),
                                      body.subtitle, body.link, body.meta)

    @r.delete("/app/me/history/{entry_id}")
    async def delete_one(entry_id: str, user=Depends(signed_in)):
        if not re.fullmatch(r"h_[0-9a-f]{14}", entry_id):
            raise HTTPException(404, "no such entry")
        if not ex().store.delete_history(str(user.id), entry_id=entry_id):
            raise HTTPException(404, "no such entry")
        return {"ok": True}

    @r.delete("/app/me/history")
    async def clear(kind: Kind | None = None, user=Depends(signed_in)):
        return {"deleted": ex().store.delete_history(str(user.id), kind=kind)}

    return r
