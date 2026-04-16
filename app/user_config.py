"""User settings — single source of truth for all user-configurable parameters."""
import json
import os
from pathlib import Path

from pydantic import BaseModel

_CONFIG_PATH = Path.home() / ".viro" / "config.json"


class UserSettings(BaseModel):
    # LLM
    model:                str  = "gemini-2.5-flash"   # agent LLM (browsing)
    orchestrator_model:   str  = ""                    # orchestrator LLM (routing + direct answers); empty = same as model
    # Agent behaviour
    max_steps:            int  = 100
    flash_mode:           bool = False                 # faster / cheaper browsing mode
    # Browser
    browser_profile:      str  = "viro"
    headless:             bool = False                 # run browser without a visible window
    keep_browser_open:    bool = False                 # always keep browser open after done (overrides agent decision)
    allowed_domains:      str  = ""                    # comma-separated whitelist (empty = all)
    prohibited_domains:   str  = ""                    # comma-separated blacklist
    # Security Judge (active only when allowed_actions or denied_actions is non-empty)
    judge_model:          str  = ""     # empty → same as orchestrator_model
    allowed_actions:      str  = ""     # free text: what the agent MAY do
    denied_actions:       str  = ""     # free text: what the agent must NOT do
    # Google / Vertex AI
    gemini_api_key:       str  = ""
    google_cloud_project: str  = ""
    llm_location:         str  = ""
    # Other providers
    groq_api_key:         str  = ""
    openai_api_key:       str  = ""
    anthropic_api_key:    str  = ""


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
        flash_mode           = data.get("flash_mode",           defaults.flash_mode),
        browser_profile      = data.get("browser_profile",      defaults.browser_profile),
        headless             = data.get("headless",             defaults.headless),
        keep_browser_open    = data.get("keep_browser_open",    defaults.keep_browser_open),
        allowed_domains      = data.get("allowed_domains",      defaults.allowed_domains),
        prohibited_domains   = data.get("prohibited_domains",   defaults.prohibited_domains),
        judge_model          = data.get("judge_model",          defaults.judge_model),
        allowed_actions      = data.get("allowed_actions",      defaults.allowed_actions),
        denied_actions       = data.get("denied_actions",       defaults.denied_actions),
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
