"""Swappable engines for the parts that use a model.

The runner, policy gate, vault, hand-off and receipts stay fixed. The two
model-driven parts are behind small interfaces, chosen by environment variable:

  CIVIC_REPAIR_ENGINE   fixes one broken route step     (default: builtin = executor.healer.Healer)
  CIVIC_EXPLORE_ENGINE  runs a service with no route    (default: builtin = executor.explorer.Explorer)

To plug in another agent (browser-use, Stagehand, Skyvern, a teammate's own),
write a class with the method below and register a factory here. It gets the
live RouteRunner, so it can use runner.page (the Playwright page), the citizen's
details (runner.task.inputs; vault values only via runner.resolve_value), the
domain allow-list (runner.host_allowed) and the human hand-off
(runner._ask_human). Keep the guarantees: no typed values chosen by a model, no
navigation off the allow-list, no final-submit or payment clicks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Protocol

from .config import settings
from .llm import LLM

if TYPE_CHECKING:
    from .healer import HealResult
    from .registry import Step
    from .runner import RouteRunner


class RepairEngine(Protocol):
    llm: LLM | None

    async def heal(self, runner: "RouteRunner", step: "Step", failure: str, phase: str = "locate") -> "HealResult": ...


class ExploreEngine(Protocol):
    async def run(self, runner: "RouteRunner") -> None: ...


def _builtin_repair(llm: LLM | None) -> RepairEngine:
    from .healer import Healer
    return Healer(llm)


def _builtin_explore(llm: LLM | None) -> ExploreEngine:
    from .explorer import Explorer
    return Explorer(llm)


REPAIR_ENGINES: dict[str, Callable[[LLM | None], RepairEngine]] = {"builtin": _builtin_repair}
EXPLORE_ENGINES: dict[str, Callable[[LLM | None], ExploreEngine]] = {"builtin": _builtin_explore}


def repair_engine(llm: LLM | None) -> RepairEngine:
    return REPAIR_ENGINES[settings.repair_engine](llm)


def explore_engine(llm: LLM | None) -> ExploreEngine:
    return EXPLORE_ENGINES[settings.explore_engine](llm)
