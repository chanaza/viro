"""CLI entry point — runs a skill directly, without the Viro UI.

Depends on agent_service.py, skills/, app/ (llm, profiles, config).
Does NOT depend on legacy/src/ (kept for reference only).

Usage:
    SUBJECT="שופרסל" .venv/Scripts/python.exe cli/main.py

Environment variables (via .env or shell):
    SUBJECT      — skill subject parameter (default: שופרסל)
    SKILL        — skill name to run     (default: branches)
    COLLECT_ALL  — true / false          (default: false)
    + all LLM / credentials vars consumed by app/user_config.py
"""
import asyncio
import os
import sys
from pathlib import Path

# Allow importing from the repo root (app/, etc.)
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from agent_service import AgentService
from app.llm import create_llm, create_orchestrator_llm
from app.profiles import get_active_profile
from skills import SkillMatch, SkillRegistry
from browser_use.browser.profile import BrowserProfile

_SUBJECT     = os.getenv("SUBJECT", "שופרסל")
_SKILL_NAME  = os.getenv("SKILL",   "branches")
_OUTPUT_DIR  = Path(__file__).parent / "output"


async def main() -> None:
    registry = SkillRegistry()
    skill = registry._skills.get(_SKILL_NAME)
    if not skill:
        print(f"ERROR: skill '{_SKILL_NAME}' not found. Available: {list(registry._skills)}")
        sys.exit(1)

    match = SkillMatch(skill=skill, params={"subject": _SUBJECT})

    print(f"Skill: {skill.name} | Subject: {_SUBJECT}")
    print("-" * 60)

    profile = get_active_profile()
    browser_profile = BrowserProfile(
        args=["--ignore-certificate-errors"],
        user_data_dir=profile["user_data_dir"],
        profile_directory=profile.get("profile_directory", "Default"),
        executable_path=profile.get("executable"),
    )

    service = AgentService(
        agent_llm=create_llm(),
        orchestrator_llm=create_orchestrator_llm(),
        browser_profile=browser_profile,
        skill_registry=registry,
        skill_output_dir=_OUTPUT_DIR,   # cli/output/
    )

    async for event in service.run(task=_SUBJECT, skill_match=match):
        t = event["type"]
        if t == "skill_matched":
            pass   # already printed above
        elif t == "step":
            print(f"  [{event['step']}] {event['goal']}"
                  + (f"  → {event['action']}" if event.get("action") else ""))
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
        elif t == "error":
            print(f"\n❌ Error: {event['message']}")
        elif t == "stopped":
            print("\n⏹ Stopped.")
        elif t == "security_warning":
            print(f"\n⚠️  Security warning: {event['reason']}")
            print("   (CLI mode — auto-rejecting and stopping)")
            service.security_reject()
        elif t == "security_stop":
            print(f"\n🛑 Security stop: {event['reason']}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
