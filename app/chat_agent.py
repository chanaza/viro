import asyncio
import os
import sys

from browser_use import Agent
from browser_use.browser.profile import BrowserProfile
from browser_use.llm.google.chat import ChatGoogle


class ChatBrowserAgent:
    """Thin wrapper around browser-use Agent for conversational, unstructured use."""

    def __init__(self):
        self._agent: Agent | None = None
        self._run_task: asyncio.Task | None = None
        self.queue: asyncio.Queue = asyncio.Queue()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self, task: str) -> None:
        if sys.platform == "win32":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")

        llm = ChatGoogle(
            model=os.getenv("GEMINI_MODEL"),
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("LLM_LOCATION"),
            vertexai=True,
        )
        browser_profile = BrowserProfile(args=["--ignore-certificate-errors"])

        self._agent = Agent(
            task=task,
            llm=llm,
            browser_profile=browser_profile,
            register_new_step_callback=self._on_step,
        )
        self._run_task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        try:
            result = await self._agent.run()
            await self.queue.put({"type": "done", "result": result.final_result() or ""})
        except asyncio.CancelledError:
            await self.queue.put({"type": "stopped"})
        except Exception as e:
            await self.queue.put({"type": "error", "message": str(e)})

    # ── Control ───────────────────────────────────────────────────────────────

    def pause(self) -> None:
        if self._agent:
            self._agent.pause()
            asyncio.create_task(self.queue.put({"type": "paused"}))

    def resume(self) -> None:
        if self._agent:
            self._agent.resume()
            asyncio.create_task(self.queue.put({"type": "resumed"}))

    def stop(self) -> None:
        if self._agent:
            self._agent.stop()

    def send(self, message: str) -> None:
        """Inject a new instruction; auto-resumes if paused."""
        if self._agent:
            self._agent.add_new_task(message)
            if self._agent.state.paused:
                self._agent.resume()

    @property
    def is_running(self) -> bool:
        return self._run_task is not None and not self._run_task.done()

    # ── Callback ──────────────────────────────────────────────────────────────

    async def _on_step(self, state, output, step_num: int) -> None:
        try:
            action_dict = output.action[0].model_dump(exclude_none=True) if output.action else {}
            action_name = next(iter(action_dict), "")
            goal = output.current_state.next_goal if output.current_state else ""
        except Exception:
            action_name, goal = "", ""

        await self.queue.put({
            "type":   "step",
            "step":   step_num,
            "goal":   goal,
            "action": action_name,
        })
