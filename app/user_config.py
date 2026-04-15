"""User settings — single source of truth for all user-configurable parameters."""
import json
import os
from pathlib import Path

from pydantic import BaseModel

_CONFIG_PATH = Path.home() / ".viro" / "config.json"


class UserSettings(BaseModel):
    gemini_model:         str = "gemini-2.0-flash"
    gemini_api_key:       str = ""
    google_cloud_project: str = ""
    llm_location:         str = ""
    max_steps:            int = 100
    browser_profile:      str = "viro"


def load_settings() -> UserSettings:
    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return UserSettings(
        gemini_model         = data.get("gemini_model")         or os.getenv("GEMINI_MODEL",         UserSettings.model_fields["gemini_model"].default),
        gemini_api_key       = data.get("gemini_api_key")       or os.getenv("GEMINI_API_KEY",       ""),
        google_cloud_project = data.get("google_cloud_project") or os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        llm_location         = data.get("llm_location")         or os.getenv("LLM_LOCATION",         ""),
        max_steps            = data.get("max_steps",            UserSettings.model_fields["max_steps"].default),
        browser_profile      = data.get("browser_profile",      UserSettings.model_fields["browser_profile"].default),
    )


def save_settings(s: UserSettings) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(
        json.dumps(s.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
