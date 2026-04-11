import asyncio
import os
import sys

from browser_use import Agent
from browser_use.browser.profile import BrowserProfile, ViewportSize
from browser_use.llm.google.chat import ChatGoogle

_SYSTEM = (
    "You are a helpful browser assistant. "
    "Use Google (engine='google') for any web searches — never DuckDuckGo. "
    "Language rule: if the user's message contains any Hebrew characters, your final answer must be in Hebrew. Otherwise respond in the user's language."
)


class ChatBrowserAgent:
    """Browser-use agent with conversational memory across multiple tasks."""

    def __init__(self):
        self._agent:    Agent | None        = None
        self._run_task: asyncio.Task | None = None
        self._pending:  asyncio.Queue       = asyncio.Queue()  # incoming user messages
        self.queue:     asyncio.Queue       = asyncio.Queue()  # outgoing SSE events
        self._history:  list[dict]          = []               # [{role, content}, ...]

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
        browser_profile = BrowserProfile(
            args=["--ignore-certificate-errors"],
            window_size=ViewportSize(width=960, height=1040),
            window_position=ViewportSize(width=960, height=0),
        )

        self._history.append({"role": "user", "content": task})
        self._agent = Agent(
            task=self._build_task(task),
            llm=llm,
            browser_profile=browser_profile,
            register_new_step_callback=self._on_step,
            register_done_callback=self._on_done,
        )
        self._run_task = asyncio.create_task(self._run_loop())

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
            while True:
                await self.queue.put({"type": "waiting"})
                next_msg = await asyncio.wait_for(self._pending.get(), timeout=300)
                if next_msg is None:
                    break
                self._history.append({"role": "user", "content": next_msg})
                self._agent.add_new_task(self._build_task(next_msg))
                await self._agent.run()
        except asyncio.TimeoutError:
            await self.queue.put({"type": "stopped"})
        except asyncio.CancelledError:
            await self.queue.put({"type": "stopped"})
        except Exception:
            import traceback
            await self.queue.put({"type": "error", "message": traceback.format_exc()})

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
        self._pending.put_nowait(None)

    def send(self, message: str) -> None:
        if self._agent and not self._run_task.done():
            if self._agent.state.paused:
                self._history.append({"role": "user", "content": message})
                self._agent.add_new_task(self._build_task(message))
                self._agent.resume()
            else:
                self._pending.put_nowait(message)

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
