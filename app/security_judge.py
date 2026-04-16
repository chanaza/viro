"""Security Judge — evaluates each planned agent action before execution.

Verdict levels:
  OK       — proceed silently
  WARNING  — pause and wait for human approval
  CRITICAL — stop the agent immediately

The judge is only active when at least one of allowed_actions / denied_actions
is non-empty. Empty policy = no judge needed.
"""
from __future__ import annotations

import hashlib
import logging
from enum import Enum

from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import UserMessage

logger = logging.getLogger(__name__)

_JUDGE_PROMPT = """\
You are a security judge for an autonomous browser agent. Your job is to decide \
whether the agent's planned action is safe to execute, based on the policy below.

=== SECURITY POLICY ===
{policy_block}
=== END POLICY ===

=== PLANNED ACTION ===
URL    : {url}
Goal   : {goal}
Action : {action}
=== END PLANNED ACTION ===

Respond with EXACTLY one of these three lines (nothing else):
OK
WARNING: <one-sentence reason>
CRITICAL: <one-sentence reason>

Rules:
- Use CRITICAL only for irreversible, high-impact actions (payments, deletions, \
data submission with personal info, account changes).
- Use WARNING for potentially risky but reversible actions, or anything not \
clearly covered by the policy.
- Use OK for clearly safe, read-only, or explicitly allowed actions.
- If the policy has no relevant rule for this action, use OK.
"""


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
        self._approved:       set[str] = set()   # hashes of approved (goal, action) pairs

    # ── Public API ────────────────────────────────────────────────────────────

    async def evaluate(self, goal: str, action: str, url: str) -> tuple[Verdict, str]:
        """Call the judge LLM and return (verdict, reason)."""
        policy_lines: list[str] = []
        if self._allowed_actions:
            policy_lines.append(f"ALLOWED actions:\n{self._allowed_actions}")
        if self._denied_actions:
            policy_lines.append(f"DENIED actions:\n{self._denied_actions}")
        policy_block = "\n\n".join(policy_lines) if policy_lines else "No specific policy defined."

        prompt = _JUDGE_PROMPT.format(
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
        """Return True if this (goal, action) was already approved by the user."""
        return _key(goal, action) in self._approved

    def approve(self, goal: str, action: str) -> None:
        self._approved.add(_key(goal, action))

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def is_needed(cls, allowed_actions: str, denied_actions: str) -> bool:
        """Judge is only needed if at least one policy field is non-empty."""
        return bool(allowed_actions.strip() or denied_actions.strip())


# ── Helpers ───────────────────────────────────────────────────────────────────

def _key(goal: str, action: str) -> str:
    return hashlib.sha1(f"{goal}|{action}".encode()).hexdigest()


def _parse_verdict(text: str) -> tuple[Verdict, str]:
    upper = text.upper()
    if upper.startswith("CRITICAL"):
        reason = text[len("CRITICAL"):].lstrip(": ").strip()
        return Verdict.CRITICAL, reason
    if upper.startswith("WARNING"):
        reason = text[len("WARNING"):].lstrip(": ").strip()
        return Verdict.WARNING, reason
    return Verdict.OK, ""
