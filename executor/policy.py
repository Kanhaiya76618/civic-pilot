"""Policy gate: runs before any browser starts. Fails closed."""

from __future__ import annotations

import asyncio
import random
import re
import time
import unicodedata
from datetime import datetime, timezone

from . import enrich
from .db import Store
from .models import ApplicationTask, ConsentRecord, TaskMode
from .registry import Portal, Registry, RegistryError, Route
from .vault import Vault, VaultError


class PolicyError(Exception):
    pass


def clean_free_text(value: str, max_len: int) -> str:
    """Strip control and zero-width characters; keep newlines and normal punctuation."""
    out = "".join(ch for ch in value if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    return out.strip()[:max_len]


class PolicyGate:
    def __init__(self, store: Store, registry: Registry, vault: Vault):
        self.store = store
        self.registry = registry
        self.vault = vault
        self._locks: dict[str, asyncio.Semaphore] = {}
        self._last_start: dict[str, float] = {}

    def check(self, task: ApplicationTask) -> tuple[Portal, Route, ApplicationTask]:
        if self.store.get_flag("kill_switch", False):
            raise PolicyError("kill switch is on")
        self._check_consent(task)
        try:
            portal = self.registry.portal(task.portal_id)
            route = self.registry.route(task.portal_id, task.service_id)
        except RegistryError as e:
            raise PolicyError(str(e)) from e
        if route.status not in {"stable", "candidate"}:
            raise PolicyError(f"route status is '{route.status}'; only stable or candidate routes run")
        if route.unresolved_recon():
            raise PolicyError("route still contains '<confirm in recon>' placeholders")
        if not route.read_only:
            if task.mode == TaskMode.assist and not portal.submission_enabled:
                raise PolicyError(f"{portal.name}: live submission is disabled in the registry; use dry_run")
            if task.mode == TaskMode.assist and route.status != "stable":
                raise PolicyError("only stable routes may submit; candidate routes run as dry_run")
            if task.mode == TaskMode.assist and (task.strategy == "explore" or not route.steps):
                raise PolicyError("an AI-explored run never submits; use dry_run, review the recorded route, then submit")
        if (task.strategy == "explore" or not route.steps) and not route.explore:
            raise PolicyError("this service has no explore spec; it can only replay its recorded route")
        task = task.model_copy(update={"inputs": self._check_inputs(task, route)})
        self._check_vault(task, route)
        provided = {d.key for d in task.documents}
        missing = [d.key for d in route.documents if d.required and d.key not in provided]
        if missing:
            raise PolicyError(f"missing documents: {missing}")
        unknown_docs = provided - {d.key for d in route.documents}
        if unknown_docs:
            raise PolicyError(f"documents not declared by the route: {sorted(unknown_docs)}")
        return portal, route, task

    async def verify_live(self, task: ApplicationTask, route: Route) -> list[str]:
        """Check inputs marked `verify:` against live public APIs.
        Raises PolicyError when a value is definitely wrong; returns notes (including 'could not check')."""
        norm = lambda x: re.sub(r"[^a-z]", "", str(x).lower().replace("&", "and"))
        notes: list[str] = []
        for spec in route.inputs:
            if not spec.verify or spec.source != "input" or spec.key not in task.inputs:
                continue
            value = str(task.inputs[spec.key])
            res = await (enrich.ifsc(value) if spec.verify == "ifsc" else enrich.pincode(value))
            name = spec.label or spec.key
            if res.ok is False:
                raise PolicyError(f"{name}: {res.error} (checked live against {res.source})")
            if res.ok is None:
                notes.append(f"Could not verify {name} right now ({res.error}); continuing without it")
            elif spec.verify == "ifsc":
                notes.append(f"IFSC verified live: {res.data['bank']}, {res.data['branch']} branch ({res.source})")
            else:
                notes.append(f"PIN code verified live: {', '.join(res.data['districts'])}, {res.data['state']} ({res.source})")
                given = task.inputs.get("state")
                if given and norm(given) != norm(res.data["state"]):
                    notes.append(f"Check: PIN code {value} is in {res.data['state']}, but the application says {given}")
        return notes

    def _check_consent(self, task: ApplicationTask) -> None:
        raw = self.store.get_consent(task.consent_id)
        if not raw:
            raise PolicyError("no consent record")
        c = ConsentRecord(**raw)
        if c.revoked:
            raise PolicyError("consent was revoked")
        if c.citizen_id != task.citizen_id:
            raise PolicyError("consent belongs to a different citizen")
        if c.expires_at < datetime.now(timezone.utc):
            raise PolicyError("consent has expired")
        if task.portal_id not in c.portal_ids or task.service_id not in c.service_ids:
            raise PolicyError("consent does not cover this portal and service")

    def _check_inputs(self, task: ApplicationTask, route: Route) -> dict:
        declared = {i.key: i for i in route.inputs if i.source == "input"}
        unknown = set(task.inputs) - set(declared)
        if unknown:
            raise PolicyError(f"inputs not declared by the route: {sorted(unknown)}")
        clean: dict = {}
        for key, spec in declared.items():
            if key not in task.inputs or task.inputs[key] in (None, ""):
                if spec.required:
                    raise PolicyError(f"missing input '{key}'")
                continue
            value = str(task.inputs[key])
            if spec.free_text:
                value = clean_free_text(value, spec.max_len)
            else:
                if len(value) > spec.max_len or "\n" in value or "<" in value:
                    raise PolicyError(f"input '{key}' is not a valid structured value")
                if spec.pattern and not re.fullmatch(spec.pattern, value):
                    raise PolicyError(f"input '{key}' does not match the expected format")
                if spec.enum and value not in spec.enum:
                    raise PolicyError(f"input '{key}' must be one of {spec.enum}")
            clean[key] = value
        return clean

    def _check_vault(self, task: ApplicationTask, route: Route) -> None:
        needed = {i.key for i in route.inputs if i.source == "vault" and i.required}
        if not needed:
            return
        if not task.vault_ref:
            raise PolicyError("route needs vault fields but the task has no vault_ref")
        try:
            have = self.vault.keys(task.vault_ref)
        except VaultError as e:
            raise PolicyError(str(e)) from e
        missing = needed - have
        if missing:
            raise PolicyError(f"vault is missing: {sorted(missing)}")

    async def acquire(self, portal: Portal) -> asyncio.Semaphore:
        """One live session per portal (by default), with a jittered gap between sessions."""
        sem = self._locks.setdefault(portal.portal_id, asyncio.Semaphore(portal.rate_limit.max_concurrent))
        await sem.acquire()
        gap = portal.rate_limit.min_gap_s + random.uniform(0, portal.rate_limit.jitter_s)
        wait = self._last_start.get(portal.portal_id, 0) + gap - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_start[portal.portal_id] = time.monotonic()
        return sem
