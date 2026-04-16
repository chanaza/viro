"""AgentService — pure browsing logic with no UI concerns.

Runs browser-use Agent, matches skills, handles security judge,
and yields structured events as an async generator.

Consumers (ChatBrowserAgent, CLI) iterate over run() and handle
events however they like — SSE queue, print, file, etc.
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from browser_use import Agent
from browser_use.browser.profile import BrowserProfile
from browser_use.llm.messages import SystemMessage, UserMessage

from config import MAX_FAILURES, MAX_ACTIONS_PER_STEP, COLLECT_ALL
from security_judge import SecurityJudge, Verdict
from skills import SkillMatch, SkillRegistry

_DEFAULT_SKILL_OUTPUT_DIR   = Path.home() / ".viro" / "output"    # user-facing skill results (CSV etc.)
_DEFAULT_SESSION_OUTPUT_DIR = Path.home() / ".viro" / "sessions"   # technical artifacts (conversation.json)


class AgentService:
    """Encapsulates all browser-use logic. UI-agnostic.

    Args:
        skill_output_dir:   Where to write user-facing skill results (CSV, source log, URLs).
                            Defaults to ~/.viro/output/.
                            CLI callers pass cli/output/.
        session_output_dir: Where to write technical artifacts (conversation.json).
                            Defaults to ~/.viro/sessions/.
    """

    def __init__(
        self,
        *,
        agent_llm,
        orchestrator_llm,
        browser_profile: BrowserProfile,
        skill_registry: SkillRegistry,
        system_ext: str | None       = None,
        sensitive_data: dict | None  = None,
        judge: SecurityJudge | None  = None,
        keep_browser_open: bool      = False,
        flash_mode: bool             = False,
        max_steps: int               = 100,
        skill_output_dir: Path | None   = None,
        session_output_dir: Path | None = None,
    ):
        self._agent_llm         = agent_llm
        self._orchestrator_llm  = orchestrator_llm
        self._browser_profile   = browser_profile
        self._skill_registry    = skill_registry
        self._system_ext        = system_ext
        self._sensitive         = sensitive_data
        self._judge             = judge
        self._keep_browser_open = keep_browser_open
        self._flash_mode        = flash_mode
        self._max_steps         = max_steps
        self._skill_output_dir   = skill_output_dir   or _DEFAULT_SKILL_OUTPUT_DIR
        self._session_output_dir = session_output_dir or _DEFAULT_SESSION_OUTPUT_DIR

        # Runtime state — reset on each run()
        self._agent:                Agent | None       = None
        self._skill_match:          SkillMatch | None  = None
        self._current_task:         str                = ""
        self._current_url:          str                = ""
        self._security_stop_reason: str | None         = None
        self._event_queue:          asyncio.Queue      = asyncio.Queue()
        self._run_task:             asyncio.Task | None = None

    # ── Public entry point ────────────────────────────────────────────────────

    async def run(
        self,
        task: str,
        skill_match: SkillMatch | None = None,
    ) -> AsyncIterator[dict]:
        """Run the agent for a task. Yields event dicts until done/error/stopped.

        Args:
            task:        Raw user request (for auto-matching) or subject string (CLI).
            skill_match: Pre-matched skill (CLI). When provided, skips LLM intent matching.
        """
        self._skill_output_dir.mkdir(parents=True, exist_ok=True)
        self._session_output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        conv_path = self._session_output_dir / f"{timestamp}_conversation.json"

        self._security_stop_reason = None
        self._current_url          = ""
        self._event_queue          = asyncio.Queue()
        self._current_task         = task

        # ── Skill resolution ─────────────────────────────────────────────────
        if skill_match is not None:
            # Pre-matched by caller (CLI): build prompt directly, skip LLM matching
            self._skill_match = skill_match
            agent_task    = self._skill_registry.build_prompt(skill_match, COLLECT_ALL)
            output_schema = self._skill_registry.output_schema(skill_match)
            yield {
                "type":   "skill_matched",
                "skill":  skill_match.skill.name,
                "params": skill_match.params,
            }
        else:
            # Auto-match via LLM (chat UI)
            self._skill_match = None
            try:
                sys_msg = SystemMessage(content=self._system_ext) if self._system_ext else None
                self._skill_match = await self._skill_registry.find(
                    task, self._orchestrator_llm, sys_msg
                )
            except Exception:
                pass

            if self._skill_match:
                agent_task    = self._skill_registry.build_prompt(self._skill_match, COLLECT_ALL)
                output_schema = self._skill_registry.output_schema(self._skill_match)
                yield {
                    "type":   "skill_matched",
                    "skill":  self._skill_match.skill.name,
                    "params": self._skill_match.params,
                }
            else:
                agent_task    = task
                output_schema = None

        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(-1)

        self._agent = Agent(
            task=agent_task,
            llm=self._agent_llm,
            browser_profile=self._browser_profile,
            output_model_schema=output_schema,
            register_new_step_callback=self._on_step,
            register_done_callback=self._on_done,
            register_should_stop_callback=self._should_stop if self._judge else None,
            max_failures=MAX_FAILURES,
            max_actions_per_step=MAX_ACTIONS_PER_STEP,
            flash_mode=self._flash_mode,
            save_conversation_path=str(conv_path),
            extend_system_message=self._system_ext,
            sensitive_data=self._sensitive,
        )

        self._run_task = asyncio.create_task(self._run_loop())

        # Drain event queue until terminal event
        while True:
            event = await self._event_queue.get()
            yield event
            if event["type"] in ("done", "stopped", "error"):
                break

    # ── Agent control ─────────────────────────────────────────────────────────

    def pause(self) -> str | None:
        """Pause the agent. Returns current page URL or None."""
        if not self._agent:
            return None
        self._agent.pause()
        return self._current_url or None

    def resume(self, briefing: str) -> None:
        """Resume with a briefing message built by the caller."""
        if not self._agent:
            return
        was_paused = self._agent.state.paused
        self._agent.add_new_task(briefing)
        if was_paused:
            self._agent.resume()

    def stop(self) -> None:
        if self._agent:
            self._agent.stop()
            if self._agent.state.paused:
                self._agent.resume()

    def send(self, message: str) -> bool:
        """Inject message mid-run. Returns True if agent is paused (caller should queue)."""
        if not self._agent:
            return False
        if self._agent.state.paused:
            return True
        self._agent.add_new_task(message)
        return False

    def security_approve(self, goal: str, action: str) -> None:
        if self._judge:
            self._judge.approve(goal, action)

    def security_reject(self) -> None:
        self.stop()

    async def close_browser(self) -> None:
        agent = self._agent
        if agent:
            try:
                await agent.browser_session.kill()
            except Exception:
                pass

    @property
    def is_running(self) -> bool:
        return self._run_task is not None and not self._run_task.done()

    @property
    def is_paused(self) -> bool:
        return bool(self._agent and self._agent.state.paused)

    # ── Internal: agent callbacks ─────────────────────────────────────────────

    async def _on_step(self, state, output, step_num: int) -> None:
        try:
            action_dict = output.action[0].model_dump(exclude_none=True) if output.action else {}
            action_name = next(iter(action_dict), "")
            goal = output.current_state.next_goal if output.current_state else ""
        except Exception:
            action_name, goal = "", ""

        try:
            self._current_url = state.url or ""
        except Exception:
            pass

        await self._event_queue.put({
            "type": "step", "step": step_num,
            "goal": goal, "action": action_name,
        })

        if not self._judge or self._judge.is_approved(goal, action_name):
            return

        verdict, reason = await self._judge.evaluate(goal, action_name, self._current_url)
        if verdict == Verdict.CRITICAL:
            self._security_stop_reason = reason
            await self._event_queue.put({
                "type": "security_stop", "reason": reason,
                "goal": goal, "action": action_name,
            })
        elif verdict == Verdict.WARNING:
            agent = self._agent
            if agent:
                agent.pause()
            await self._event_queue.put({
                "type": "security_warning", "reason": reason,
                "goal": goal, "action": action_name,
            })

    async def _on_done(self, history) -> None:
        result = history.final_result() if history else ""

        # Save skill-structured results (CSV, source log, action history, URLs)
        saved = {}
        if self._skill_match and history:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                prefix    = f"{self._skill_match.skill.name}_{timestamp}"
                saved     = self._skill_registry.save_result(
                    self._skill_match, history, self._skill_output_dir, prefix
                )
            except Exception:
                pass

        # Decide whether to keep the browser open
        keep_open = await self._decide_keep_browser(result or "")
        agent = self._agent
        try:
            if agent:
                agent.browser_session.browser_profile.keep_alive = keep_open
        except Exception:
            keep_open = False

        await self._event_queue.put({
            "type":         "done",
            "result":       result or "",
            "browser_open": keep_open,
            "saved":        saved,
        })

    async def _should_stop(self) -> bool:
        return self._security_stop_reason is not None

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

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _decide_keep_browser(self, result: str) -> bool:
        if self._keep_browser_open:
            return True
        # Research/skill tasks deliver their result as structured data — close by default
        if self._skill_match:
            return False
        prompt = _KEEP_BROWSER_PROMPT.format(
            task=self._current_task,
            result=(result or "")[:500],
        )
        try:
            messages = []
            if self._system_ext:
                messages.append(SystemMessage(content=self._system_ext))
            messages.append(UserMessage(content=prompt))
            response = await self._orchestrator_llm.ainvoke(messages)
            return "YES" in response.completion.upper()
        except Exception:
            return True   # on failure, keep open (safer)


_KEEP_BROWSER_PROMPT = """\
A browser automation task has just completed. Decide whether the browser should stay open.

Keep open (YES) if: the result is something the user will likely want to act on directly \
in the browser — a filled cart, a product page, a booking form, a recommendation page, \
a course to purchase, or any page requiring a follow-up action by the user.

Close (NO) if: the task was purely informational — research, data extraction, answering a \
question — and the result has been delivered as text. No browser interaction is needed.

When in doubt, answer YES.

Task: {task}
Result summary: {result}

Reply with exactly one word: YES or NO.
"""


def friendly_error(exc: Exception) -> str:
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
