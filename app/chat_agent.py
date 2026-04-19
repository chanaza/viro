"""ChatBrowserAgent - UI wrapper around AgentOrchestrator."""

import asyncio
import os
import sys
from datetime import datetime

from browser_use.browser.profile import ViewportSize

from agent_service.orchestrator import AgentOrchestrator
from app.llm_config import create_judge_llm, create_llm, create_orchestrator_llm
from app.user_config import SESSIONS_DIR, load_settings
from core.profiles import build_browser_profile


class ChatBrowserAgent:
    """UI adapter for chat sessions."""

    def __init__(self):
        if sys.platform == "win32":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

        settings = load_settings()
        browser_w = int(os.getenv("BROWSER_W", 1100))
        browser_h = int(os.getenv("BROWSER_H", 900))

        profile, browser_profile = build_browser_profile(
            settings.browser_profile,
            window_size=ViewportSize(width=browser_w, height=browser_h),
            window_position=ViewportSize(width=0, height=0),
            headless=settings.headless or None,
            allowed_domains=settings.allowed_domains,
            prohibited_domains=settings.prohibited_domains,
        )
        has_policy = bool(settings.allowed_actions.strip() or settings.denied_actions.strip())

        self._orchestrator = AgentOrchestrator(
            agent_llm=create_llm(),
            orchestrator_llm=create_orchestrator_llm(),
            browser_profile=browser_profile,
            browser_profile_id=profile["id"],
            allowed_actions=settings.allowed_actions,
            denied_actions=settings.denied_actions,
            judge_llm=create_judge_llm() if has_policy else None,
            flash_mode=settings.flash_mode,
            max_steps=settings.max_steps,
            keep_browser_open=settings.keep_browser_open,
            agent_log_dir=SESSIONS_DIR,
            full_results_dir=SESSIONS_DIR if settings.save_full_results else None,
            final_response_dir=SESSIONS_DIR,
        )
        self.queue: asyncio.Queue = asyncio.Queue()
        self._history: list[dict[str, str]] = []
        self._relay_task: asyncio.Task | None = None

    async def start(self, task: str) -> None:
        self._history.append({"role": "user", "content": task})
        self._start_relay()
        await self._orchestrator.start(
            task,
            conversation=self._build_conversation(task),
            session_prefix=datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        )

    def _start_relay(self) -> None:
        if self._relay_task is None or self._relay_task.done():
            self._relay_task = asyncio.create_task(self._relay_events())

    async def _relay_events(self) -> None:
        while True:
            event = await self._orchestrator.queue.get()
            if event["type"] == "done" and event.get("result"):
                self._history.append({"role": "assistant", "content": event["result"]})
            await self.queue.put(event)
            if event["type"] in ("done", "stopped", "error"):
                break

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

    def pause(self) -> None:
        self._orchestrator.pause()

    def resume(self) -> None:
        self._orchestrator.resume()

    def stop(self) -> None:
        self._orchestrator.stop()

    def send(self, message: str) -> None:
        if self.is_running:
            self._history.append({"role": "user", "content": message})
        self._orchestrator.send(message)

    def reset(self) -> None:
        self._orchestrator.reset()
        self._history.clear()

    def security_approve(self) -> None:
        self._orchestrator.security_approve()

    def security_reject(self) -> None:
        self._orchestrator.security_reject()

    async def close_browser(self) -> None:
        await self._orchestrator.close_browser()

    @property
    def is_running(self) -> bool:
        return self._orchestrator.is_running

    @property
    def is_paused(self) -> bool:
        return self._orchestrator.is_paused

    @property
    def is_active(self) -> bool:
        return self._orchestrator.is_active

    @property
    def has_pending_security(self) -> bool:
        return self._orchestrator.has_pending_security
