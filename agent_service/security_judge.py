"""SecurityJudge — evaluates planned agent actions against a security policy.

Verdict levels:
  OK       — proceed silently
  WARNING  — pause and wait for human approval
  CRITICAL — stop the agent immediately
"""
from __future__ import annotations

import hashlib
import logging
from enum import Enum

from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import UserMessage

from core.prompts import JUDGE_PROMPT

logger = logging.getLogger(__name__)


class Verdict(str, Enum):
    OK       = "ok"
    WARNING  = "warning"
    CRITICAL = "critical"


class SecurityJudge:
    """Evaluates planned agent actions against a security policy."""

    def __init__(self, llm: BaseChatModel, allowed_actions: str, denied_actions: str):
        self._llm             = llm
        self._allowed_actions = allowed_actions.strip()
        self._denied_actions  = denied_actions.strip()
        self._approved:       set[str] = set()

    async def evaluate(self, goal: str, action: str, url: str) -> tuple[Verdict, str]:
        """Call the judge LLM and return (verdict, reason)."""
        policy_lines: list[str] = []
        if self._allowed_actions:
            policy_lines.append(f"ALLOWED actions:\n{self._allowed_actions}")
        if self._denied_actions:
            policy_lines.append(f"DENIED actions:\n{self._denied_actions}")
        policy_block = "\n\n".join(policy_lines) if policy_lines else "No specific policy defined."

        prompt = JUDGE_PROMPT.format(
            policy_block=policy_block,
            url=url or "(unknown)",
            goal=goal or "(none)",
            action=action or "(none)",
        )
        try:
            response = await self._llm.ainvoke([UserMessage(content=prompt)])
            return _parse_verdict(response.completion.strip())
        except Exception as e:
            logger.warning("[SecurityJudge] LLM call failed: %s — defaulting to OK", e)
            return Verdict.OK, ""

    def is_approved(self, goal: str, action: str) -> bool:
        return _key(goal, action) in self._approved

    def approve(self, goal: str, action: str) -> None:
        self._approved.add(_key(goal, action))

    @classmethod
    def is_needed(cls, allowed_actions: str, denied_actions: str) -> bool:
        return bool(allowed_actions.strip() or denied_actions.strip())


def _key(goal: str, action: str) -> str:
    return hashlib.sha1(f"{goal}|{action}".encode()).hexdigest()


def _parse_verdict(text: str) -> tuple[Verdict, str]:
    upper = text.upper()
    if upper.startswith("CRITICAL"):
        return Verdict.CRITICAL, text[len("CRITICAL"):].lstrip(": ").strip()
    if upper.startswith("WARNING"):
        return Verdict.WARNING, text[len("WARNING"):].lstrip(": ").strip()
    return Verdict.OK, ""
