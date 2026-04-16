"""ChatBrowserAgent — UI layer on top of AgentService.

Adds:
- Conversation history across multiple turns
- SSE event queue (consumed by server.py)
- BROWSE vs ANSWER routing (orchestrator LLM)
- Direct answers without browser
- Pause/resume with pending-message queuing and resume briefing
- Security human-in-the-loop (approve / reject)
- Session file saving (answer.md, log.md)
- Keep-browser-open decision and UI close button
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from browser_use.browser.profile import BrowserProfile, ViewportSize
from browser_use.llm.messages import SystemMessage, UserMessage

from agent_service import AgentService, friendly_error
from app.llm import create_llm, create_orchestrator_llm, create_judge_llm
from app.profiles import get_active_profile
from security_judge import SecurityJudge
from skills import SkillRegistry
from app.user_config import load_settings

_SESSIONS_DIR   = Path.home() / ".viro" / "sessions"
_CONFIG_DIR     = Path(__file__).parent / "config"
_SYS_EXT_PATH   = _CONFIG_DIR / "system_extension.md"
_SENS_DATA_PATH = _CONFIG_DIR / "sensitive_data.json"

_ROUTER_PROMPT = """\
Decide if answering the following request requires browsing the web or not.
Reply with exactly one word: BROWSE or ANSWER.
- BROWSE: needs live web data, searching, visiting URLs, or interacting with websites.
- ANSWER: can be answered from general knowledge, conversation context, or is conversational \
(greetings, follow-up questions on prior results, etc.).

Request: {task}
"""


def _load_system_extension() -> str | None:
    try:
        text  = _SYS_EXT_PATH.read_text(encoding="utf-8").strip()
        lines = [l for l in text.splitlines()
                 if not l.startswith("#") and not l.startswith("<!--")]
        content = "\n".join(lines).strip()
        return content if content else None
    except FileNotFoundError:
        return None


def _load_sensitive_data() -> dict[str, str] | None:
    try:
        data   = json.loads(_SENS_DATA_PATH.read_text(encoding="utf-8"))
        result = {k: v for k, v in data.items()
                  if not k.startswith("_") and isinstance(v, str)}
        return result if result else None
    except FileNotFoundError:
        return None


class ChatBrowserAgent:
    """Browser-use agent with conversational memory across multiple tasks."""

    def __init__(self):
        if sys.platform == "win32":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

        s   = load_settings()
        bw  = int(os.getenv("BROWSER_W", 1100))
        bh  = int(os.getenv("BROWSER_H", 900))

        def _parse_domains(raw: str) -> list[str] | None:
            parts = [d.strip() for d in raw.split(",") if d.strip()]
            return parts if parts else None

        profile = get_active_profile()
        browser_profile = BrowserProfile(
            args=["--ignore-certificate-errors"],
            window_size=ViewportSize(width=bw, height=bh),
            window_position=ViewportSize(width=0, height=0),
            headless=s.headless or None,
            user_data_dir=profile["user_data_dir"],
            profile_directory=profile.get("profile_directory", "Default"),
            executable_path=profile.get("executable"),
            allowed_domains=_parse_domains(s.allowed_domains),
            prohibited_domains=_parse_domains(s.prohibited_domains),
        )

        judge = None
        if SecurityJudge.is_needed(s.allowed_actions, s.denied_actions):
            judge = SecurityJudge(
                llm=create_judge_llm(),
                allowed_actions=s.allowed_actions,
                denied_actions=s.denied_actions,
            )

        sensitive = _load_sensitive_data()

        parts = []
        raw_ext = _load_system_extension()
        if raw_ext:
            parts.append(raw_ext)
        if s.allowed_actions.strip():
            parts.append(f"ALLOWED actions policy:\n{s.allowed_actions.strip()}")
        if s.denied_actions.strip():
            parts.append(f"DENIED actions policy — never do these:\n{s.denied_actions.strip()}")
        sys_ext = "\n\n".join(parts) if parts else None

        self._orchestrator_llm = create_orchestrator_llm()
        self._sys_ext          = sys_ext
        self._service          = AgentService(
            agent_llm=create_llm(),
            orchestrator_llm=self._orchestrator_llm,
            browser_profile=browser_profile,
            skill_registry=SkillRegistry(),
            system_ext=sys_ext,
            sensitive_data=sensitive,
            judge=judge,
            keep_browser_open=s.keep_browser_open,
            flash_mode=s.flash_mode,
            max_steps=s.max_steps,
        )

        # UI state
        self.queue:             asyncio.Queue      = asyncio.Queue()
        self._history:          list[dict]         = []
        self._steps_log:        list[dict]         = []
        self._pending_messages: list[str]          = []
        self._pre_pause_url:    str | None         = None
        self._pending_security: tuple | None       = None
        self._run_task:         asyncio.Task | None = None
        self._answer_path:      Path | None        = None
        self._log_path:         Path | None        = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self, task: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self._answer_path = _SESSIONS_DIR / f"{timestamp}_answer.md"
        self._log_path    = _SESSIONS_DIR / f"{timestamp}_log.md"
        self._steps_log   = []
        self._history.append({"role": "user", "content": task})

        try:
            needs_browser = await self._needs_browser(task)
        except Exception as e:
            await self.queue.put({"type": "error", "message": friendly_error(e)})
            return

        if needs_browser:
            self._run_task = asyncio.create_task(self._run_service(task))
        else:
            self._run_task = asyncio.create_task(self._answer_directly(task))

    async def _run_service(self, task: str) -> None:
        """Drive AgentService.run() and forward events to the SSE queue."""
        try:
            async for event in self._service.run(task):
                # Track steps locally for session log
                if event["type"] == "step":
                    self._steps_log.append({
                        "type": "step",
                        "step": event["step"],
                        "goal": event["goal"],
                        "action": event["action"],
                    })
                elif event["type"] in ("security_warning", "security_stop",
                                       "security_approved", "security_rejected"):
                    self._steps_log.append(event)

                # Security warning: capture pending for approve/reject
                if event["type"] == "security_warning":
                    self._pending_security = (event["goal"], event["action"])

                # Done: save session files, forward with file paths
                if event["type"] == "done":
                    result = event.get("result", "")
                    if result:
                        self._history.append({"role": "assistant", "content": result})
                    self._save_session(task, result)
                    await self.queue.put({
                        **event,
                        "answer_path": str(self._answer_path) if self._answer_path else "",
                        "log_path":    str(self._log_path)    if self._log_path    else "",
                    })
                    return

                await self.queue.put(event)

        except Exception as e:
            await self.queue.put({"type": "error", "message": friendly_error(e)})

    # ── Routing ───────────────────────────────────────────────────────────────

    def _system_msg(self) -> SystemMessage | None:
        return SystemMessage(content=self._sys_ext) if self._sys_ext else None

    async def _needs_browser(self, task: str) -> bool:
        messages = []
        sys_msg = self._system_msg()
        if sys_msg:
            messages.append(sys_msg)
        messages.append(UserMessage(
            content=_ROUTER_PROMPT.format(task=self._build_conversation(task))
        ))
        response = await self._orchestrator_llm.ainvoke(messages)
        return "BROWSE" in response.completion.upper()

    async def _answer_directly(self, task: str) -> None:
        try:
            messages = []
            sys_msg = self._system_msg()
            if sys_msg:
                messages.append(sys_msg)
            messages.append(UserMessage(content=self._build_conversation(task)))
            response = await self._orchestrator_llm.ainvoke(messages)
            result   = response.completion
            self._history.append({"role": "assistant", "content": result})
            self._save_session(task, result)
            await self.queue.put({
                "type":        "done",
                "result":      result,
                "browser_open": False,
                "answer_path": str(self._answer_path) if self._answer_path else "",
                "log_path":    str(self._log_path)    if self._log_path    else "",
            })
        except Exception as e:
            await self.queue.put({"type": "error", "message": friendly_error(e)})

    def _build_conversation(self, current_msg: str) -> str:
        parts = []
        prior = self._history[:-1]
        if prior:
            parts.append("--- Conversation so far ---")
            for turn in prior:
                label = "User" if turn["role"] == "user" else "Assistant"
                parts.append(f"{label}: {turn['content']}")
            parts.append("--- End of conversation ---\n")
        parts.append(f"User: {current_msg}")
        return "\n".join(parts)

    # ── Controls ──────────────────────────────────────────────────────────────

    def pause(self) -> None:
        self._pre_pause_url = self._service.pause()
        asyncio.create_task(self.queue.put({"type": "paused"}))

    def resume(self) -> None:
        parts = ["[PAUSE RESUMED]"]
        if self._pre_pause_url:
            parts.append(f"You were paused at: {self._pre_pause_url}")
        parts.append(
            "The user may have interacted with the browser during the pause. "
            "Take a fresh screenshot and assess the current state before proceeding."
        )
        if self._pending_messages:
            parts.append("\nUser instructions added during pause:")
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
        self._history.append({"role": "user", "content": message})
        if self._service.is_paused:
            self._pending_messages.append(message)
            asyncio.create_task(self.queue.put({"type": "queued", "message": message}))
        else:
            self._service.send(message)

    def reset(self) -> None:
        if self.is_running:
            self.stop()
        self._history.clear()
        self._pending_messages.clear()
        self._steps_log.clear()
        self._pre_pause_url    = None
        self._pending_security = None

    def security_approve(self) -> None:
        if self._pending_security:
            goal, action = self._pending_security
            self._service.security_approve(goal, action)
            self._steps_log.append({"type": "security_approved", "goal": goal, "action": action})
        self._pending_security = None
        self.resume()

    def security_reject(self) -> None:
        if self._pending_security:
            goal, action = self._pending_security
            self._steps_log.append({"type": "security_rejected", "goal": goal, "action": action})
        self._pending_security = None
        self._service.security_reject()

    async def close_browser(self) -> None:
        await self._service.close_browser()

    @property
    def is_running(self) -> bool:
        return self._run_task is not None and not self._run_task.done()

    # ── Session saving ────────────────────────────────────────────────────────

    def _save_session(self, task: str, result: str) -> None:
        try:
            if self._answer_path:
                self._answer_path.write_text(result or "(no result)", encoding="utf-8")
            if self._log_path:
                ts    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                lines = [f"# Viro Log — {ts}", "", "## Task", task, ""]
                if self._steps_log:
                    lines += ["## Steps", ""]
                    for e in self._steps_log:
                        t = e.get("type", "step")
                        if t == "step":
                            action = f" → `{e['action']}`" if e.get("action") else ""
                            lines.append(f"{e['step']}. {e['goal']}{action}")
                        elif t == "security_warning":
                            lines.append(
                                f"  ⚠️  SECURITY WARNING (step {e.get('step','')}): {e['reason']}"
                                f" — goal: {e['goal']}, action: {e['action']}"
                            )
                        elif t == "security_approved":
                            lines.append(
                                f"  ✓  Security warning APPROVED by user"
                                f" — goal: {e['goal']}, action: {e['action']}"
                            )
                        elif t == "security_rejected":
                            lines.append(
                                f"  ✕  Security warning REJECTED by user — agent stopped"
                                f" — goal: {e['goal']}, action: {e['action']}"
                            )
                        elif t == "security_stop":
                            lines.append(
                                f"  🛑  SECURITY STOP (step {e.get('step','')}): {e['reason']}"
                                f" — goal: {e['goal']}, action: {e['action']}"
                            )
                    lines.append("")
                self._log_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass
