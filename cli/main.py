"""CLI entry point — runs a skill directly, without the Viro UI."""

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")  # shared config
load_dotenv(Path(__file__).parent / ".env")          # CLI-specific (overrides shared)

from agent_service.orchestrator import AgentOrchestrator
from core.llm import create_llm_for, get_default_model
from core.models import SkillPreset
from core.profiles import build_browser_profile, detect_profiles

_SUBJECT          = os.getenv("SUBJECT", "שופרסל")
_SKILL_NAMES      = [s.strip() for s in os.getenv("SKILLS", "branches").split(",")]
_TASK             = os.getenv("TASK", "{subject}").format(subject=_SUBJECT)
_MODEL            = os.getenv("GEMINI_MODEL") or get_default_model()
_BROWSER_PROFILE  = os.getenv("BROWSER_PROFILE", "")
_ALLOWED_ACTIONS  = os.getenv("ALLOWED_ACTIONS", "")
_DENIED_ACTIONS   = os.getenv("DENIED_ACTIONS", "")
_KEEP_BROWSER     = os.getenv("KEEP_BROWSER_OPEN", "false").lower() == "true"
_MAX_STEPS        = int(os.getenv("MAX_STEPS", "100"))
_OUTPUT_DIR       = Path(__file__).parent / "output"


@dataclass
class _Credentials:
    """LLMSettings-compatible credentials read from environment."""
    gemini_api_key:       str = ""
    google_cloud_project: str = ""
    llm_location:         str = ""
    groq_api_key:         str = ""
    openai_api_key:       str = ""
    anthropic_api_key:    str = ""


def _load_credentials() -> _Credentials:
    return _Credentials(
        gemini_api_key       = os.getenv("GEMINI_API_KEY",       ""),
        google_cloud_project = os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        llm_location         = os.getenv("LLM_LOCATION",         ""),
        groq_api_key         = os.getenv("GROQ_API_KEY",         ""),
        openai_api_key       = os.getenv("OPENAI_API_KEY",       ""),
        anthropic_api_key    = os.getenv("ANTHROPIC_API_KEY",    ""),
    )


async def main() -> None:
    creds = _load_credentials()
    llm   = create_llm_for(_MODEL, creds)

    profile, browser_profile = build_browser_profile(_BROWSER_PROFILE)

    profiles = detect_profiles()
    print("Browser profiles:")
    for p in profiles:
        marker = ">" if p["id"] == profile["id"] else " "
        print(f"  {marker} {p['id']:<25} {p['label']}")
    print()
    print(f"Task  : {_TASK}")
    print(f"Skills: {', '.join(_SKILL_NAMES)}")
    print("-" * 60)

    has_policy = bool(_ALLOWED_ACTIONS.strip() or _DENIED_ACTIONS.strip())

    orchestrator = AgentOrchestrator(
        agent_llm        = llm,
        orchestrator_llm = llm,
        browser_profile  = browser_profile,
        browser_profile_id = profile["id"],
        allowed_actions  = _ALLOWED_ACTIONS,
        denied_actions   = _DENIED_ACTIONS,
        judge_llm        = create_llm_for(_MODEL, creds) if has_policy else None,
        keep_browser_open= _KEEP_BROWSER,
        max_steps        = _MAX_STEPS,
        agent_log_dir      = _OUTPUT_DIR / "sessions",
        full_results_dir   = _OUTPUT_DIR,
        final_response_dir = _OUTPUT_DIR,
    )

    await orchestrator.start(
        _TASK,
        preset_skills=[SkillPreset(name=name, params={"subject": _SUBJECT}) for name in _SKILL_NAMES],
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
