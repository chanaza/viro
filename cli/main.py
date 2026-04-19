"""CLI entry point — runs a skill directly, without the Viro UI."""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")  # shared config
load_dotenv(Path(__file__).parent / ".env")          # CLI-specific (overrides shared)

from agent_service.orchestrator import AgentOrchestrator
from app.llm_config import create_judge_llm, create_llm, create_orchestrator_llm
from app.user_config import load_settings
from core.profiles import build_browser_profile
from core.models import SkillPreset

_SUBJECT     = os.getenv("SUBJECT", "שופרסל")
_SKILL_NAMES = [s.strip() for s in os.getenv("SKILLS", "branches").split(",")]
_OUTPUT_DIR  = Path(__file__).parent / "output"


async def main() -> None:
    print(f"Skills: {', '.join(_SKILL_NAMES)} | Subject: {_SUBJECT}")
    print("-" * 60)

    settings = load_settings()
    profile, browser_profile = build_browser_profile(settings.browser_profile)
    has_policy = bool(settings.allowed_actions.strip() or settings.denied_actions.strip())

    orchestrator = AgentOrchestrator(
        agent_llm=create_llm(),
        orchestrator_llm=create_orchestrator_llm(),
        browser_profile=browser_profile,
        browser_profile_id=profile["id"],
        allowed_actions=settings.allowed_actions,
        denied_actions=settings.denied_actions,
        judge_llm=create_judge_llm() if has_policy else None,
        keep_browser_open=settings.keep_browser_open,
        preset_skills=[SkillPreset(name=name, params={"subject": _SUBJECT}) for name in _SKILL_NAMES],
        agent_log_dir=_OUTPUT_DIR / "sessions",
        full_results_dir=_OUTPUT_DIR,
        final_response_dir=_OUTPUT_DIR / "sessions",
    )

    await orchestrator.start(
        _SUBJECT,
        session_prefix=datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
    )

    while True:
        event = await orchestrator.queue.get()
        t = event["type"]
        if t == "skill_matched":
            pass
        elif t == "step":
            print(f"  [{event['step']}] {event['goal']}" + (f"  → {event['action']}" if event.get("action") else ""))
        elif t == "done":
            print("\n✅ Done.")
            if event.get("result"):
                print(event["result"][:1000])
            saved = event.get("saved", {})
            if saved.get("csv_path"):
                print(f"📄 Results : {saved['csv_path']} ({saved.get('count', '?')} items)")
            if saved.get("log_csv_path"):
                print(f"📄 Sources : {saved['log_csv_path']}")
            if saved.get("history_path"):
                print(f"📄 History : {saved['history_path']}")
            break
        elif t == "error":
            print(f"\n❌ Error: {event['message']}")
            break
        elif t == "stopped":
            print("\n⏹ Stopped.")
            break
        elif t == "security_warning":
            print(f"\n⚠️  Security warning: {event['reason']}")
            print("   (CLI mode — auto-rejecting and stopping)")
            orchestrator.security_reject()
        elif t == "security_stop":
            print(f"\n🛑 Security stop: {event['reason']}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
