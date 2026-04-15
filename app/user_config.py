"""User settings — single source of truth for all user-configurable parameters."""
import json
import os
from pathlib import Path

from pydantic import BaseModel

_CONFIG_PATH = Path.home() / ".viro" / "config.json"


class UserSettings(BaseModel):
    # General
    model:                str = "gemini-2.5-flash"   # agent LLM (browsing)
    orchestrator_model:   str = ""                    # orchestrator LLM (routing + direct answers); empty = same as model
    max_steps:            int = 100
    browser_profile:      str = "viro"
    # Google / Vertex AI
    gemini_api_key:       str = ""
    google_cloud_project: str = ""
    llm_location:         str = ""
    # Other providers
    groq_api_key:         str = ""
    openai_api_key:       str = ""
    anthropic_api_key:    str = ""


def load_settings() -> UserSettings:
    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}

    defaults = UserSettings()
    return UserSettings(
        # Support legacy key "gemini_model" from older config files
        model                = data.get("model") or data.get("gemini_model") or os.getenv("GEMINI_MODEL", defaults.model),
        orchestrator_model   = data.get("orchestrator_model",   defaults.orchestrator_model),
        max_steps            = data.get("max_steps",            defaults.max_steps),
        browser_profile      = data.get("browser_profile",      defaults.browser_profile),
        gemini_api_key       = data.get("gemini_api_key")       or os.getenv("GEMINI_API_KEY",       ""),
        google_cloud_project = data.get("google_cloud_project") or os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        llm_location         = data.get("llm_location")         or os.getenv("LLM_LOCATION",         ""),
        groq_api_key         = data.get("groq_api_key")         or os.getenv("GROQ_API_KEY",         ""),
        openai_api_key       = data.get("openai_api_key")       or os.getenv("OPENAI_API_KEY",       ""),
        anthropic_api_key    = data.get("anthropic_api_key")    or os.getenv("ANTHROPIC_API_KEY",    ""),
    )


def save_settings(s: UserSettings) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(
        json.dumps(s.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
