import asyncio
from pathlib import Path

from browser_use.browser.profile import BrowserProfile
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import SystemMessage, UserMessage

from core.agent_setup import build_agent_policy
from core.prompts import (
    KEEP_BROWSER_PROMPT,
    RESUME_BRIEFING_CONTEXT,
    RESUME_BRIEFING_HEADER,
    RESUME_BRIEFING_MESSAGES_HEADER,
    RESUME_BRIEFING_PAUSED_AT,
    ROUTER_PROMPT,
)
from core.models import SkillMatch, SkillPreset
from agent_service.skill_registry import SkillRegistry

from .security_judge import SecurityJudge, Verdict

from .session_output import FinalResponseSaver
from .errors import friendly_error
from .service import AgentService


class AgentOrchestrator:
    """Top-level runtime controller: builds agent policy, owns AgentService."""

    def __init__(
        self,
        *,
        agent_llm: BaseChatModel,
        orchestrator_llm: BaseChatModel,
        browser_profile: BrowserProfile,
        browser_profile_id: str | None = None,
        allowed_actions: str = "",
        denied_actions: str = "",
        judge_llm: BaseChatModel | None = None,
        flash_mode: bool = False,
        max_steps: int = 100,
        keep_browser_open: bool = False,
        preset_skills: list[SkillPreset] | None = None,
        agent_log_dir: Path,
        full_results_dir: Path | None = None,
        final_response_dir: Path,
    ) -> None:
        system_ext, sensitive_data = build_agent_policy(
            allowed_actions=allowed_actions,
            denied_actions=denied_actions,
        )
        self._service = AgentService(
            agent_llm=agent_llm,
            browser_profile=browser_profile,
            browser_profile_id=browser_profile_id,
            system_ext=system_ext,
            sensitive_data=sensitive_data,
            flash_mode=flash_mode,
            max_steps=max_steps,
            agent_log_dir=agent_log_dir,
            full_results_dir=full_results_dir,
        )
        self._orchestrator_llm = orchestrator_llm
        self._system_ext = system_ext
        self._final_response_dir = final_response_dir
        self._judge = (
            SecurityJudge(llm=judge_llm, allowed_actions=allowed_actions, denied_actions=denied_actions)
            if judge_llm and SecurityJudge.is_needed(allowed_actions, denied_actions)
            else None
        )
        self._keep_browser_open = keep_browser_open
        self._registry = SkillRegistry()
        self._preset_skills = (
            self._registry.resolve_presets(preset_skills) if preset_skills else None
        )
        self._service.set_should_keep_browser_open(self._decide_keep_browser_open)

        self.queue: asyncio.Queue = asyncio.Queue()
        self._current_task: str = ""
        self._pending_messages: list[str] = []
        self._pre_pause_url: str | None = None
        self._pending_security: tuple[str, str] | None = None
        self._steps_log: list[dict] = []
        self._session_prefix: str = ""
        self._run_task: asyncio.Task | None = None

    async def start(
        self,
        task: str,
        *,
        conversation: str | None = None,
        session_prefix: str,
    ) -> None:
        self._current_task = task
        self._steps_log = []
        self._session_prefix = session_prefix
        rendered_task = conversation or task

        try:
            needs_browser = await self._should_browse(rendered_task)
        except Exception as e:
            await self.queue.put({"type": "error", "message": friendly_error(e)})
            return

        if needs_browser:
            self._run_task = asyncio.create_task(self._run_browser_task(task, self._preset_skills))
        else:
            self._run_task = asyncio.create_task(self._answer_directly(task, rendered_task))

    async def _run_browser_task(self, task: str, preset_skills: list[SkillMatch] | None) -> None:
        try:
            matches = (
                preset_skills
                if preset_skills is not None
                else await self._registry.find(
                    task,
                    self._orchestrator_llm,
                    SystemMessage(content=self._system_ext) if self._system_ext else None,
                )
            )
            if matches:
                agent_task   = self._registry.build_prompt(matches)
                output_schema = self._registry.output_schema(matches)
                await self.queue.put(
                    {"type": "skill_matched", "skills": [m.skill.name for m in matches]}
                )
            else:
                agent_task    = task
                output_schema = None

            async for event in self._service.run(agent_task, output_schema=output_schema):
                await self._handle_service_event(event)
        except Exception as e:
            await self.queue.put({"type": "error", "message": friendly_error(e)})

    async def _handle_service_event(self, event: dict) -> None:
        if event["type"] == "step":
            self._steps_log.append(event)
            await self.queue.put(event)
            await self._apply_security_policy(event)
            return

        if event["type"] == "done":
            self._steps_log.append(event)
            final_saved = self._save_final_response(event.get("result", ""))
            event["saved"] = {**event.get("saved", {}), **final_saved}
            event["answer_path"] = final_saved.get("answer_path", "")
            event["log_path"] = final_saved.get("log_path", "")
            await self.queue.put(event)
            return

        if event["type"] in ("stopped", "error"):
            self._steps_log.append(event)
            await self.queue.put(event)
            return

        await self.queue.put(event)

    async def _apply_security_policy(self, event: dict) -> None:
        if not self._judge:
            return

        goal = event.get("goal", "")
        action = event.get("action", "")
        if self._judge.is_approved(goal, action):
            return

        verdict, reason = await self._judge.evaluate(goal, action, self._service.current_url)
        if verdict == Verdict.CRITICAL:
            self._service.stop()
            stop_event = {
                "type": "security_stop",
                "reason": reason,
                "goal": goal,
                "action": action,
            }
            self._steps_log.append(stop_event)
            await self.queue.put(stop_event)
        elif verdict == Verdict.WARNING:
            self._service.pause()
            self._pending_security = (goal, action)
            warning_event = {
                "type": "security_warning",
                "reason": reason,
                "goal": goal,
                "action": action,
            }
            self._steps_log.append(warning_event)
            await self.queue.put(warning_event)

    def _system_msg(self) -> SystemMessage | None:
        return SystemMessage(content=self._system_ext) if self._system_ext else None

    async def _should_browse(self, task: str) -> bool:
        messages = []
        sys_msg = self._system_msg()
        if sys_msg:
            messages.append(sys_msg)
        messages.append(UserMessage(content=ROUTER_PROMPT.format(task=task)))
        response = await self._orchestrator_llm.ainvoke(messages)
        return "BROWSE" in response.completion.upper()

    async def _decide_keep_browser_open(self, task: str, result: str) -> bool:
        if self._keep_browser_open:
            return True
        prompt = KEEP_BROWSER_PROMPT.format(task=task, result=(result or "")[:500])
        try:
            response = await self._orchestrator_llm.ainvoke([UserMessage(content=prompt)])
            return "YES" in response.completion.upper()
        except Exception:
            return True

    async def _answer_directly(self, task: str, rendered_task: str) -> None:
        try:
            messages = []
            sys_msg = self._system_msg()
            if sys_msg:
                messages.append(sys_msg)
            messages.append(UserMessage(content=rendered_task))
            response = await self._orchestrator_llm.ainvoke(messages)
            result = response.completion
            saved = self._save_final_response(result)
            await self.queue.put(
                {
                    "type": "done",
                    "result": result,
                    "browser_open": False,
                    "answer_path": saved.get("answer_path", ""),
                    "log_path": saved.get("log_path", ""),
                }
            )
        except Exception as e:
            await self.queue.put({"type": "error", "message": friendly_error(e)})

    def _save_final_response(self, result: str) -> dict[str, str]:
        return FinalResponseSaver.save(
            task=self._current_task,
            result=result,
            steps_log=self._steps_log,
            output_dir=self._final_response_dir,
            prefix=self._session_prefix,
        )

    def pause(self) -> None:
        self._service.pause()
        self._pre_pause_url = self._service.current_url or None
        asyncio.create_task(self.queue.put({"type": "paused"}))

    def resume(self) -> None:
        parts = [RESUME_BRIEFING_HEADER]
        if self._pre_pause_url:
            parts.append(RESUME_BRIEFING_PAUSED_AT.format(url=self._pre_pause_url))
        parts.append(RESUME_BRIEFING_CONTEXT)
        if self._pending_messages:
            parts.append(RESUME_BRIEFING_MESSAGES_HEADER)
            for msg in self._pending_messages:
                parts.append(f"  - {msg}")
            self._pending_messages.clear()

        self._service.resume("\n".join(parts))
        self._pre_pause_url = None
        asyncio.create_task(self.queue.put({"type": "resumed"}))

    def stop(self) -> None:
        self._service.stop()

    def send(self, message: str) -> None:
        if not self.is_running:
            return
        if self._service.is_paused:
            self._pending_messages.append(message)
            asyncio.create_task(self.queue.put({"type": "queued", "message": message}))
        else:
            self._service.send(message)

    def reset(self) -> None:
        if self.is_running:
            self.stop()
        self._steps_log.clear()
        self._current_task = ""
        self._pending_messages.clear()
        self._session_prefix = ""
        self._pre_pause_url = None
        self._pending_security = None

    def security_approve(self) -> None:
        if self._pending_security:
            goal, action = self._pending_security
            if self._judge:
                self._judge.approve(goal, action)
            approved_event = {
                "type": "security_approved",
                "goal": goal,
                "action": action,
            }
            self._steps_log.append(approved_event)
            asyncio.create_task(self.queue.put(approved_event))
        self._pending_security = None
        self.resume()

    def security_reject(self) -> None:
        if self._pending_security:
            goal, action = self._pending_security
            rejected_event = {
                "type": "security_rejected",
                "goal": goal,
                "action": action,
            }
            self._steps_log.append(rejected_event)
            asyncio.create_task(self.queue.put(rejected_event))
        self._pending_security = None
        self._service.stop()

    async def close_browser(self) -> None:
        await self._service.close_browser()

    @property
    def is_running(self) -> bool:
        return self._run_task is not None and not self._run_task.done()

    @property
    def is_paused(self) -> bool:
        return self._service.is_paused

    @property
    def is_active(self) -> bool:
        return self.is_running or self.is_paused

    @property
    def has_pending_security(self) -> bool:
        return self._pending_security is not None
