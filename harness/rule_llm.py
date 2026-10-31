"""Deterministic stand-in for the model in tests.

Each rule is (action, regex). The regex is matched against the snapshot lines
in the prompt; the first matching line's ref is used. This exercises the real
healer loop, the policy filter and the request log without an API key. It
says nothing about how well a real model picks elements: measure that with
`scripts/eval.py --llm` and an API key.
"""

from __future__ import annotations

import re

from executor.llm import LLMResult, log_request


class RuleLLM:
    def __init__(self, rules: list[tuple[str, str | None]]):
        self.rules = list(rules)
        self.requests: list[str] = []

    async def decide(self, system: str, user: str, schema: dict) -> LLMResult:
        log_request({"model": "rule-llm", "system": system, "messages": [{"role": "user", "content": user}]})
        self.requests.append(user)
        if not self.rules:
            return LLMResult({"reason": "no more rules", "action": "give_up", "ref": "", "human_kind": "none"}, 1)
        action, pattern = self.rules.pop(0)
        ref = None
        if pattern:
            for line in user.splitlines():
                m = re.search(r"ref=(e\d+)", line)
                if m and re.search(pattern, line):
                    ref = m.group(1)
                    break
        return LLMResult({"reason": f"rule {action} {pattern}", "action": action, "ref": ref or "", "human_kind": "none"}, 1)


class RuleExploreLLM:
    """Scripted stand-in for the model in explore mode.

    Each turn is (actions, status) where actions are (action, line_regex, value_key).
    line_regex picks the snapshot line, hence the element ref, the way a model would.
    Exercises the real explorer loop, policy checks, recording and replay; it says
    nothing about how well a real model plans (measure that with an API key).
    """

    def __init__(self, turns: list[tuple[list[tuple[str, str, str]], str]]):
        self.turns = list(turns)
        self.requests: list[str] = []

    async def decide(self, system: str, user: str, schema: dict) -> LLMResult:
        log_request({"model": "rule-explore-llm", "system": system, "messages": [{"role": "user", "content": user}]})
        self.requests.append(user)
        if not self.turns:
            return LLMResult({"reason": "script exhausted", "status": "give_up", "human_kind": "none", "actions": []}, 1)
        actions, status = self.turns.pop(0)
        out = []
        for action, pattern, key in actions:
            ref = ""
            for line in user.splitlines():
                m = re.search(r"ref=(e\d+)", line)
                if m and re.search(pattern, line):
                    ref = m.group(1)
                    break
            out.append({"action": action, "ref": ref, "value_key": key})
        return LLMResult({"reason": f"scripted turn ({len(out)} actions)", "status": status, "human_kind": "none", "actions": out}, 1)
