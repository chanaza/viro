"""AgentService — thin wrapper around browser-use Agent."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Awaitable, Callable

from browser_use import Agent
from browser_use.browser.profile import BrowserProfile
from browser_use.llm.base import BaseChatModel

from .session_output import ArtifactsSaver
from config import MAX_ACTIONS_PER_STEP, MAX_FAILURES
from core.profiles import get_profile

from .errors import friendly_error

type ShouldKeepBrowserOpen = Callable[[str, str], Awaitable[bool]]


def _allow_browser_foreground() -> None:
    """Allow the browser window to take foreground focus when it opens."""
    import sys

    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.AllowSetForegroundWindow(-1)


class AgentService:
    """Wrap browser-use Agent and expose structured runtime events."""

    def __init__(
        self,
        *,
        agent_llm: BaseChatModel,
        browser_profile: BrowserProfile,
        browser_profile_id: str | None = None,
        system_ext: str | None = None,
        sensitive_data: dict | None = None,
        flash_mode: bool = False,
        max_steps: int = 100,
        agent_log_dir: Path,
        full_results_dir: Path | None = None,
        should_keep_browser_open: ShouldKeepBrowserOpen | None = None,
    ) -> None:
        if browser_profile_id is not None and not get_profile(browser_profile_id):
            raise ValueError(f"Browser profile id not found: {browser_profile_id}")

        self._agent_llm = agent_llm
        self._browser_profile_id = browser_profile_id
        self._browser_profile = browser_profile
        self._system_ext = system_ext
        self._sensitive = sensitive_data
        self._flash_mode = flash_mode
        self._max_steps = max_steps
        self._agent_log_dir = agent_log_dir
        self._full_results_dir = full_results_dir
        self._should_keep_browser_open: ShouldKeepBrowserOpen | None = should_keep_browser_open
        self._output_schema: type | None = None

        self._agent: Agent | None = None
        self._current_task: str = ""
        self._current_url: str = ""
        self._run_prefix: str = ""
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._run_task: asyncio.Task | None = None

    def set_should_keep_browser_open(
        self,
        decider: ShouldKeepBrowserOpen | None,
    ) -> None:
        self._should_keep_browser_open = decider

    async def run(
        self,
        task: str,
        output_schema: type | None = None,
        prefix: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Run a prepared browser task and yield events until done/error/stopped."""
        self._agent_log_dir.mkdir(parents=True, exist_ok=True)
        run_prefix = prefix or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        conv_path = self._agent_log_dir / f"{run_prefix}_conversation.json"

        self._current_url = ""
        self._event_queue = asyncio.Queue()
        self._current_task = task
        self._output_schema = output_schema
        self._run_prefix = run_prefix

        _allow_browser_foreground()

        self._agent = Agent(
            task=task,
            llm=self._agent_llm,
            browser_profile=self._browser_profile,
            output_model_schema=self._output_schema,
            register_new_step_callback=self._on_step,
            register_done_callback=self._on_done,
            max_failures=MAX_FAILURES,
            max_actions_per_step=MAX_ACTIONS_PER_STEP,
            flash_mode=self._flash_mode,
            save_conversation_path=str(conv_path),
            extend_system_message=self._system_ext,
            sensitive_data=self._sensitive,
        )

        self._run_task = asyncio.create_task(self._run_loop())

        while True:
            event = await self._event_queue.get()
            yield event
            if event["type"] in ("done", "stopped", "error"):
                break

    def pause(self) -> None:
        if self._agent:
            self._agent.pause()

    def resume(self, message: str) -> None:
        if not self._agent:
            return
        was_paused = self._agent.state.paused
        if message.strip():
            self._agent.add_new_task(message)
        if was_paused:
            self._agent.resume()

    def stop(self) -> None:
        if self._agent:
            self._agent.stop()
            if self._agent.state.paused:
                self._agent.resume()

    def send(self, message: str) -> None:
        if self._agent:
            self._agent.add_new_task(message)

    async def close_browser(self) -> None:
        if self._agent:
            try:
                await self._agent.browser_session.kill()
            except Exception:
                pass

    @property
    def system_ext(self) -> str | None:
        return self._system_ext

    @property
    def is_running(self) -> bool:
        return self._run_task is not None and not self._run_task.done()

    @property
    def is_paused(self) -> bool:
        return bool(self._agent and self._agent.state.paused)

    @property
    def current_url(self) -> str:
        return self._current_url

    async def _run_loop(self) -> None:
        agent = self._agent
        if agent is None:
            return
        try:
            await agent.run(max_steps=self._max_steps)
        except asyncio.CancelledError:
            await self._event_queue.put({"type": "stopped"})
        except Exception as e:
            await self._event_queue.put({"type": "error", "message": friendly_error(e)})
        finally:
            try:
                await agent.close()
            except Exception:
                pass

    async def _on_step(self, state, output, step_num: int) -> None:
        try:
            action_dict = output.action[0].model_dump(exclude_none=True) if output.action else {}
            action_name = next(iter(action_dict), "")
            goal = output.current_state.next_goal if output.current_state else ""
            self._current_url = state.url or ""
        except Exception:
            action_name, goal = "", ""

        await self._event_queue.put({"type": "step", "step": step_num, "goal": goal, "action": action_name})

    async def _on_done(self, history) -> None:
        result = history.final_result() if history else ""
        saved = {}
        if self._full_results_dir and history:
            saved = ArtifactsSaver.save(history, self._full_results_dir, result or "", self._run_prefix, self._output_schema)

        keep_open = False
        if self._should_keep_browser_open:
            try:
                keep_open = await self._should_keep_browser_open(self._current_task, result or "")
            except Exception:
                keep_open = False

        try:
            if self._agent:
                self._agent.browser_session.browser_profile.keep_alive = keep_open
        except Exception:
            keep_open = False

        await self._event_queue.put(
            {
                "type": "done",
                "result": result or "",
                "browser_open": keep_open,
                "saved": saved,
                "answer_path": saved.get("answer_path", ""),
                "log_path": saved.get("log_path", ""),
            }
        )
