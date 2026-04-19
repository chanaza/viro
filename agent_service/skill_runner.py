"""SkillRunner — resolves skills for a given task (pre-matched or via LLM)."""
from browser_use.llm.messages import SystemMessage

from config import COLLECT_ALL
from skills import SkillMatch, SkillRegistry


class SkillRunner:
    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    async def resolve(
        self,
        task: str,
        pre_matched: SkillMatch | None,
        orchestrator_llm,
        system_ext: str | None,
    ) -> tuple[str, type | None, SkillMatch | None]:
        """Resolve skill for a task. Returns (agent_task, output_schema, skill_match).

        Args:
            pre_matched: Caller-supplied match (CLI). When given, skips LLM matching.
        """
        if pre_matched is not None:
            return (
                self._registry.build_prompt(pre_matched, COLLECT_ALL),
                self._registry.output_schema(pre_matched),
                pre_matched,
            )

        skill_match = None
        try:
            sys_msg = SystemMessage(content=system_ext) if system_ext else None
            skill_match = await self._registry.find(task, orchestrator_llm, sys_msg)
        except Exception:
            pass

        if skill_match:
            return (
                self._registry.build_prompt(skill_match, COLLECT_ALL),
                self._registry.output_schema(skill_match),
                skill_match,
            )

        return task, None, None

