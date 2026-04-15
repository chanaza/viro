import asyncio
import ctypes
import os
import sys
from datetime import datetime
from pathlib import Path

from browser_use import Agent
from browser_use.browser.profile import BrowserProfile, ViewportSize
from browser_use.llm.messages import UserMessage
from app.config import MAX_FAILURES, MAX_ACTIONS_PER_STEP
from app.llm import create_llm
from app.profiles import get_active_profile
from app.user_config import load_settings

_SESSIONS_DIR = Path.home() / ".viro" / "sessions"

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


def _friendly_error(exc: Exception) -> str:
    msg = str(exc)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
        return "חרגת ממכסת ה-API של Gemini. המתן עד מחר או עדכן את פרטי החיבור ב-Viro."
    if "Reauthentication" in msg or "reauthenticate" in msg:
        return "פג תוקף האימות ל-Google Cloud. הרץ: gcloud auth application-default login"
    if "401" in msg or "403" in msg or "API_KEY_INVALID" in msg or "PERMISSION_DENIED" in msg:
        return "שגיאת אימות — בדוק את ה-API key או פרטי Vertex AI בהגדרות Viro."
    if "UNAVAILABLE" in msg or "503" in msg or "connection" in msg.lower():
        return "שירות Gemini לא זמין כרגע. נסה שוב בעוד מספר שניות."
    return f"שגיאה: {msg}"


class ChatBrowserAgent:
    """Browser-use agent with conversational memory across multiple tasks."""

    def __init__(self):
        if sys.platform == "win32":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")

        self._llm = create_llm()
        bw = int(os.getenv("BROWSER_W", 1100))
        bh = int(os.getenv("BROWSER_H", 900))
        profile = get_active_profile()
        self._browser_profile = BrowserProfile(
            args=["--ignore-certificate-errors"],
            window_size=ViewportSize(width=bw, height=bh),
            window_position=ViewportSize(width=0, height=0),
            stealth=True,
            user_data_dir=profile["user_data_dir"],
            profile_directory=profile.get("profile_directory", "Default"),
            browser_binary_path=profile.get("executable"),
        )
        self._agent:       Agent | None        = None
        self._run_task:    asyncio.Task | None = None
        self._max_steps:   int                 = load_settings().max_steps
        self.queue:        asyncio.Queue       = asyncio.Queue()  # outgoing SSE events
        self._history:     list[dict]          = []               # [{role, content}, ...]
        self._steps_log:   list[dict]          = []               # [{step, goal, action}, ...]
        self._answer_path: Path | None         = None
        self._log_path:    Path | None         = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self, task: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self._answer_path = _SESSIONS_DIR / f"{timestamp}_answer.md"
        self._log_path    = _SESSIONS_DIR / f"{timestamp}_log.md"
        self._steps_log = []
        self._history.append({"role": "user", "content": task})
        try:
            needs_browser = await self._needs_browser(task)
        except Exception as e:
            await self.queue.put({"type": "error", "message": _friendly_error(e)})
            return
        if needs_browser:
            if sys.platform == "win32":
                ctypes.windll.user32.AllowSetForegroundWindow(-1)
            self._agent = Agent(
                task=self._build_task(task),
                llm=self._llm,
                browser_profile=self._browser_profile,
                register_new_step_callback=self._on_step,
                register_done_callback=self._on_done,
                max_failures=MAX_FAILURES,
                max_actions_per_step=MAX_ACTIONS_PER_STEP,
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
            self._save_session(task, result)
            await self.queue.put({
                "type": "done", "result": result,
                "answer_path": str(self._answer_path) if self._answer_path else "",
                "log_path":    str(self._log_path)    if self._log_path    else "",
            })
        except Exception as e:
            await self.queue.put({"type": "error", "message": _friendly_error(e)})

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
            await self._agent.run(max_steps=self._max_steps)
        except asyncio.CancelledError:
            await self.queue.put({"type": "stopped"})
        except Exception as e:
            await self.queue.put({"type": "error", "message": _friendly_error(e)})
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

        self._steps_log.append({"step": step_num, "goal": goal, "action": action_name})
        await self.queue.put({
            "type":   "step",
            "step":   step_num,
            "goal":   goal,
            "action": action_name,
        })

    def _save_session(self, task: str, result: str) -> None:
        try:
            # Answer file — for the user
            if self._answer_path:
                self._answer_path.write_text(result or "(no result)", encoding="utf-8")

            # Log file — for the developer
            if self._log_path:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                lines = [f"# Viro Log — {ts}", "", "## Task", task, ""]
                if self._steps_log:
                    lines += ["## Steps", ""]
                    for s in self._steps_log:
                        action = f" → `{s['action']}`" if s.get("action") else ""
                        lines.append(f"{s['step']}. {s['goal']}{action}")
                    lines.append("")
                self._log_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass

    async def _on_done(self, history) -> None:
        result = history.final_result() if history else ""
        if result:
            self._history.append({"role": "assistant", "content": result})
        self._save_session(self._history[0]["content"] if self._history else "", result or "")
        await self.queue.put({
            "type": "done", "result": result or "",
            "answer_path": str(self._answer_path) if self._answer_path else "",
            "log_path":    str(self._log_path)    if self._log_path    else "",
        })
