"""Portal registry: git-versioned YAML, interpreted (never executed as code).

registry/<portal_id>/portal.yaml          domains, human-step kinds, rate limit
registry/<portal_id>/<service>.route.yaml  steps, inputs, documents, status
registry/<portal_id>/patches/*.route.yaml  healer output, status=candidate
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import settings

RECON_MARKER = re.compile(r"<\s*(confirm|regex confirmed|recon)[^>]*>", re.I)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Target(_Strict):
    """Locator spec. Order of preference: id/name, label, role+name, text, css."""

    id: str | None = None
    name: str | None = None
    label: str | None = None
    placeholder: str | None = None
    role: str | None = None
    role_name: str | None = None
    text: str | None = None
    css: str | None = None
    after_text: str | None = Field(None, description="Legacy forms: the first <tag> after this visible text")
    tag: str = Field("select", description="Element tag used with after_text")
    frame: str | None = Field(None, description="CSS selector of the iframe that holds the element")
    nth: int | None = None
    alt: list["Target"] = Field(default_factory=list, description="Fallback specs, tried in order")

    def describe(self) -> str:
        parts = [f"{k}={v!r}" for k, v in self.model_dump(exclude={"alt", "tag"}, exclude_none=True).items()]
        return ", ".join(parts) or "<empty>"

    def render(self, fn: Callable[[str], str]) -> "Target":
        """Copy with placeholders such as answer{{input.gender}} filled in (string fields only)."""
        data = {k: (fn(v) if isinstance(v, str) else v) for k, v in self.model_dump(exclude={"alt"}).items()}
        return Target(**data, alt=[a.render(fn) for a in self.alt])


class Expect(_Strict):
    url_contains: str | None = None
    visible_text: str | None = None
    heading: str | None = None
    hidden_text: str | None = None
    field_filled: Target | None = None
    no_error: bool = True


class Extract(_Strict):
    """Read results off the page. Only what is on the page is returned (no model involved)."""

    count_regex: str | None = Field(None, description="Regex with one group, e.g. 'We found (\\d+) schemes'")
    items_css: str | None = Field(None, description="Elements whose text (and href, for links) become result items")
    empty_regex: str | None = Field(None, description="Text the portal shows when there are no results")
    limit: int = 10


class Recover(_Strict):
    """A portal error that is safe to recover from, e.g. a mistyped CAPTCHA the portal rejected."""

    error_contains: str
    goto: str = Field(description="Step id to go back to")
    max_times: int = 2


class Step(_Strict):
    id: str
    do: Literal[
        "goto", "fill", "select", "check", "click", "upload", "press", "wait_for", "human_step", "approval_gate", "extract"
    ]
    intent: str = Field("", description="Plain-language goal, used by the Tier 2 healer")
    url: str | None = None
    target: Target | None = None
    value: str | None = None
    key: str | None = Field(None, description="Key for press")
    kind: Literal["otp", "captcha", "login", "payment", "other"] | None = None
    completion: Literal["auto", "human_done"] = "auto"
    wait_options: Target | None = Field(None, description="Cascading dropdown: child select to wait for")
    expect: Expect | None = None
    capture: dict[str, str] | None = Field(None, description="name -> regex with one group, read from the page")
    retry: Literal["once", "never"] = "once"
    submit: bool = Field(False, description="Final submit: never retried, runs only after approval")
    optional: bool = False
    timeout_ms: int | None = None
    fingerprint: list[str] | None = Field(None, description="Field ids/names expected on the page after this step")
    label: str | None = Field(None, description="Label shown on the approval card")
    recover: list[Recover] = Field(default_factory=list)
    when: dict[str, list[str]] | None = Field(
        None, description="Run only if each input key has one of the listed values, e.g. {is_student: [No]}"
    )
    extract: Extract | None = None

    @model_validator(mode="after")
    def _check(self) -> "Step":
        needs_target = {"fill", "select", "check", "click", "upload"}
        if self.do in needs_target and not self.target:
            raise ValueError(f"step {self.id}: '{self.do}' needs a target")
        if self.do == "goto" and not self.url:
            raise ValueError(f"step {self.id}: goto needs url")
        if self.do == "human_step" and not self.kind:
            raise ValueError(f"step {self.id}: human_step needs kind")
        if self.submit and self.retry != "never":
            raise ValueError(f"step {self.id}: submit steps must have retry: never")
        if self.do == "extract" and not self.extract:
            raise ValueError(f"step {self.id}: extract needs an 'extract' block")
        return self


class InputDef(_Strict):
    key: str
    source: Literal["input", "vault"] = "input"
    required: bool = True
    free_text: bool = False
    max_len: int = 200
    pattern: str | None = None
    enum: list[str] | None = None
    label: str | None = None
    verify: Literal["ifsc", "pincode"] | None = Field(None, description="Checked against a live public API before the run")

    @property
    def sensitive(self) -> bool:
        return self.source == "vault"


class DocDef(_Strict):
    key: str
    required: bool = True
    max_kb: int
    formats: list[str]
    max_px: int | None = None
    label: str | None = None


class ExploreSpec(_Strict):
    """No recorded route yet: the model plans the steps live, and the run is recorded as a draft route."""

    start_url: str
    goal: str
    finish_when: Expect = Field(description="Deterministic check that the goal is reached; the model's word is not enough")
    extract: Extract | None = None
    max_actions: int = 40
    max_seconds: int = 300


class Route(_Strict):
    portal_id: str
    service_id: str
    version: int
    status: Literal["draft", "candidate", "stable", "broken"]
    description: str = ""
    last_verified_at: datetime | None = None
    verified_runs: int = 0
    inputs: list[InputDef] = Field(default_factory=list)
    documents: list[DocDef] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    read_only: bool = Field(False, description="Looks information up; never submits anything, so no approval gate")
    explore: ExploreSpec | None = None
    tracking: dict[str, str] = Field(default_factory=dict)
    profile_match: list[str] = Field(
        default_factory=list, description="Input keys that should equal the citizen profile; differences are flagged on the approval card"
    )
    patched_from: int | None = None

    @model_validator(mode="after")
    def _check(self) -> "Route":
        if not self.steps and not self.explore:
            raise ValueError(f"{self.portal_id}/{self.service_id}: a route needs steps or an explore block")
        if self.read_only and any(s.submit or s.do == "approval_gate" for s in self.steps):
            raise ValueError(f"{self.service_id}: read-only routes cannot submit")
        if not self.read_only and any(s.submit for s in self.steps):
            gate = next((i for i, s in enumerate(self.steps) if s.do == "approval_gate"), None)
            first_submit = next(i for i, s in enumerate(self.steps) if s.submit)
            if gate is None or gate > first_submit:
                raise ValueError(f"{self.service_id}: every submit needs an approval_gate before it")
        return self

    def input(self, key: str) -> InputDef | None:
        return next((i for i in self.inputs if i.key == key), None)

    def unresolved_recon(self) -> list[str]:
        raw = yaml.safe_dump(self.model_dump(mode="json"))
        return RECON_MARKER.findall(raw)


class RateLimit(_Strict):
    max_concurrent: int = 1
    min_gap_s: float = 0
    jitter_s: float = 0


class Portal(_Strict):
    portal_id: str
    name: str
    base_url: str
    allowed_domains: list[str]
    is_sandbox: bool = False
    submission_enabled: bool = True
    error_selector: str = "[role=alert], .error, .alert-danger"
    login_detect: Expect | None = None
    human_steps: list[str] = Field(default_factory=list)
    rate_limit: RateLimit = Field(default_factory=RateLimit)
    terms_url: str | None = None
    block_resources: bool = Field(False, description="Skip fonts, media and trackers to load pages faster")
    public_demo: bool = Field(False, description="Offered in the public citizen console")
    notes: str = ""


class RegistryError(Exception):
    pass


def _expand_env(obj: Any) -> Any:
    if isinstance(obj, str):
        return obj.replace("${SANDBOX_URL}", settings.sandbox_url)
    if isinstance(obj, list):
        return [_expand_env(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _expand_env(v) for k, v in obj.items()}
    return obj


def _read_yaml(path: Path) -> dict:
    with path.open() as f:
        return _expand_env(yaml.safe_load(f))


class Registry:
    def __init__(self, root: Path | None = None):
        self.root = root or settings.registry_dir

    def portal(self, portal_id: str) -> Portal:
        path = self.root / portal_id / "portal.yaml"
        if not path.exists():
            raise RegistryError(f"portal '{portal_id}' is not in the registry")
        return Portal(**_read_yaml(path))

    def route_path(self, portal_id: str, service_id: str) -> Path:
        return self.root / portal_id / f"{service_id}.route.yaml"

    def route(self, portal_id: str, service_id: str) -> Route:
        path = self.route_path(portal_id, service_id)
        if not path.exists():
            raise RegistryError(f"service '{service_id}' is not registered for portal '{portal_id}'")
        route = Route(**_read_yaml(path))
        if route.portal_id != portal_id or route.service_id != service_id:
            raise RegistryError(f"{path} declares {route.portal_id}/{route.service_id}")
        return route

    def list(self) -> list[dict]:
        out = []
        for portal_dir in sorted(p for p in self.root.iterdir() if (p / "portal.yaml").exists()):
            portal = self.portal(portal_dir.name)
            for route_file in sorted(portal_dir.glob("*.route.yaml")):
                route = Route(**_read_yaml(route_file))
                out.append(
                    {
                        "portal_id": portal.portal_id,
                        "portal_name": portal.name,
                        "service_id": route.service_id,
                        "description": route.description,
                        "status": route.status,
                        "is_sandbox": portal.is_sandbox,
                        "submission_enabled": portal.submission_enabled,
                        "public_demo": portal.public_demo,
                        "is_sandbox": portal.is_sandbox,
                        "read_only": route.read_only,
                        "explorable": route.explore is not None,
                        "has_recorded_route": bool(route.steps),
                        "inputs": [i.model_dump() for i in route.inputs],
                        "documents": [d.model_dump() for d in route.documents],
                    }
                )
        return out

    def save_patch(self, route: Route, note: str, folder: str = "patches", tag: str = "") -> Path:
        out_dir = self.root / route.portal_id / folder
        out_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = out_dir / f"{route.service_id}.v{route.version}{tag}.{stamp}.route.yaml"
        body = yaml.safe_dump(route.model_dump(mode="json", exclude_none=True, exclude_defaults=False), sort_keys=False)
        path.write_text(f"# {note}\n# Review the diff against the stable route before promoting.\n{body}")
        return path
