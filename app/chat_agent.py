import asyncio
import ctypes
import os
import sys
import traceback

from browser_use import Agent
from browser_use.browser.profile import BrowserProfile, ViewportSize
from browser_use.llm.messages import UserMessage
from app.llm import create_llm

_SYSTEM = (
    "You are a helpful browser assistant. "
    "Use Google (engine='google') for any web searches — never DuckDuckGo. "
    "Language rule: if the user's message contains any Hebrew characters, your final answer must be in Hebrew. Otherwise respond in the user's language."
)

_ROUTER_PROMPT = """\
Decide if answering the following request requires browsing the web or not.
Reply with exactly one word: BROWSE or ANSWER.
- BROWSE: needs live web data, searching, visiting URLs, or interacting with websites.
- ANSWER: can be answered from general knowledge, conversation context, or is conversational (greetings, follow-up questions on prior results, etc.).

Request: {task}
"""


class ChatBrowserAgent:
    """Browser-use agent with conversational memory across multiple tasks."""

    def __init__(self):
        if sys.platform == "win32":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")

        self._llm = create_llm()
        bw = int(os.getenv("BROWSER_W", 1100))
        bh = int(os.getenv("BROWSER_H", 900))
        self._browser_profile = BrowserProfile(
            args=["--ignore-certificate-errors"],
            window_size=ViewportSize(width=bw, height=bh),
            window_position=ViewportSize(width=0, height=0),
        )
        self._agent:    Agent | None        = None
        self._run_task: asyncio.Task | None = None
        self.queue:     asyncio.Queue       = asyncio.Queue()  # outgoing SSE events
        self._history:  list[dict]          = []               # [{role, content}, ...]

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self, task: str) -> None:
        self._history.append({"role": "user", "content": task})
        if await self._needs_browser(task):
            if sys.platform == "win32":
                ctypes.windll.user32.AllowSetForegroundWindow(-1)
            self._agent = Agent(
                task=self._build_task(task),
                llm=self._llm,
                browser_profile=self._browser_profile,
                register_new_step_callback=self._on_step,
                register_done_callback=self._on_done,
            )
            self._run_task = asyncio.create_task(self._run_loop())
        else:
            self._run_task = asyncio.create_task(self._answer_directly(task))

    async def _needs_browser(self, task: str) -> bool:
        prompt = _ROUTER_PROMPT.format(task=self._build_task(task))
        response = await self._llm.ainvoke([UserMessage(content=prompt)])
        return "BROWSE" in response.completion.upper()

    async def _answer_directly(self, task: str) -> None:
        try:
            response = await self._llm.ainvoke([UserMessage(content=self._build_task(task))])
            result = response.completion
            self._history.append({"role": "assistant", "content": result})
            await self.queue.put({"type": "done", "result": result})
        except Exception:
            await self.queue.put({"type": "error", "message": traceback.format_exc()})

    def _build_task(self, current_msg: str) -> str:
        """Builds the full task string: system + conversation history + current message."""
        parts = [_SYSTEM]
        prior = self._history[:-1]  # all turns before the current one
        if prior:
            parts.append("\n--- Conversation so far ---")
            for turn in prior:
                label = "User" if turn["role"] == "user" else "Assistant"
                parts.append(f"{label}: {turn['content']}")
            parts.append("--- End of conversation ---\n")
        parts.append(f"User: {current_msg}")
        return "\n".join(parts)

    async def _run_loop(self) -> None:
        try:
            await self._agent.run()
        except asyncio.CancelledError:
            await self.queue.put({"type": "stopped"})
        except Exception:
            await self.queue.put({"type": "error", "message": traceback.format_exc()})
        finally:
            try:
                await self._agent.close()
            except Exception:
                pass

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
            if self._agent.state.paused:
                self._agent.resume()  # unblock so run() can exit

    def send(self, message: str) -> None:
        if self._agent and not self._run_task.done():
            self._history.append({"role": "user", "content": message})
            self._agent.add_new_task(message)
            if self._agent.state.paused:
                self._agent.resume()

    @property
    def is_running(self) -> bool:
        return self._run_task is not None and not self._run_task.done()

    # ── Callbacks ─────────────────────────────────────────────────────────────

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

    async def _on_done(self, history) -> None:
        result = history.final_result() if history else ""
        if result:
            self._history.append({"role": "assistant", "content": result})
        await self.queue.put({"type": "done", "result": result or ""})
