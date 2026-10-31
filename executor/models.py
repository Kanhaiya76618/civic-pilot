"""The five shared contracts (frozen on Day 0; only additive changes after that).

These Pydantic models are the source of truth. `scripts/export_contracts.py`
writes them to /contracts as JSON Schema for Part 1 and Part 2.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CitizenProfile(_Contract):
    """Non-sensitive attributes only. Phone, email, bank details live in the vault."""

    citizen_id: str
    state: str
    district: str | None = None
    category: str | None = Field(None, description="Social category, e.g. General, OBC, SC, ST, EWS")
    course_level: str | None = None
    preferred_language: str = Field("en-IN", description="BCP-47 tag, e.g. hi-IN, ta-IN")
    vault_ref: str | None = Field(None, description="Pointer to encrypted sensitive fields held by Part 3")
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)


class ConsentRecord(_Contract):
    consent_id: str
    citizen_id: str
    portal_ids: list[str]
    service_ids: list[str]
    purpose: str
    granted_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    revoked: bool = False


class DocumentRef(_Contract):
    key: str = Field(description="Matches a document key declared by the route, e.g. photo")
    uri: str = Field(description="doc://<id> from POST /v1/documents, or an https URL")
    media_type: str | None = None


class TaskMode(str, Enum):
    dry_run = "dry_run"  # stop at the final review page, never submit
    assist = "assist"  # submit after human approval


class ApplicationTask(_Contract):
    idempotency_key: str
    citizen_id: str
    portal_id: str
    service_id: str
    inputs: dict[str, Any] = Field(default_factory=dict, description="Non-sensitive values keyed by route input key")
    documents: list[DocumentRef] = Field(default_factory=list)
    vault_ref: str | None = None
    consent_id: str
    mode: TaskMode = TaskMode.dry_run
    callback_url: str | None = None
    origin: Literal["part1", "part2", "citizen", "eval"] = "citizen"
    strategy: Literal["auto", "route", "explore"] = Field(
        "auto", description="auto: replay the recorded route when one exists, else let the AI explore; explore: force a live AI run"
    )
    origin_ref: str | None = Field(None, description="Caller's own id, e.g. the Part 2 issue id")


class TaskStatus(str, Enum):
    queued = "queued"
    validating = "validating"
    preparing_docs = "preparing_docs"
    running = "running"
    awaiting_human = "awaiting_human"
    awaiting_approval = "awaiting_approval"
    submitting = "submitting"
    verifying = "verifying"
    completed = "completed"
    failed = "failed"
    needs_review = "needs_review"


TERMINAL_STATUSES = {TaskStatus.completed, TaskStatus.failed, TaskStatus.needs_review}


class Timing(_Contract):
    agent_ms: int = Field(0, description="Browser + model time: what the agent itself spent")
    browser_ms: int = 0
    model_ms: int = 0
    human_wait_ms: int = 0
    total_ms: int = 0
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class TaskEvent(_Contract):
    task_id: str
    seq: int = 0
    status: TaskStatus
    kind: Literal[
        "status", "step", "human_needed", "approval_needed", "heal", "security", "receipt", "info", "error", "reasoning"
    ] = "status"
    step_id: str | None = None
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    timing: Timing = Field(default_factory=Timing)
    at: datetime = Field(default_factory=utcnow)


class EvidenceItem(_Contract):
    name: str
    sha256: str


class Receipt(_Contract):
    receipt_id: str
    task_id: str
    portal_id: str
    service_id: str
    mode: TaskMode
    outcome: Literal["submitted", "dry_run_complete", "information_retrieved"]
    reference_no: str | None = None
    submitted_at: datetime
    approved_by: str | None = Field(None, description="Who approved: 'citizen' via the approval card")
    evidence: list[EvidenceItem] = Field(default_factory=list)
    tracking: dict[str, str] = Field(default_factory=dict, description="Status-page URL and hints for Part 2")
    result: dict[str, Any] | None = Field(
        None, description="For read-only services: what the portal returned (source_url, retrieved_at, count, items)"
    )
    origin_ref: str | None = None
    timing: Timing = Field(default_factory=Timing)
    signer_key_id: str = ""
    signature: str = Field("", description="Base64 Ed25519 over the canonical JSON of every other field")


class TaskView(BaseModel):
    """What GET /v1/tasks/{id} returns."""

    task_id: str
    status: TaskStatus
    task: ApplicationTask
    created_at: datetime
    updated_at: datetime
    error: str | None = None
    receipt: Receipt | None = None
    citizen_url: str | None = None
