"""LLM factory — builds the right provider from UserSettings.

Adding a new provider:
  1. Write a _build_<provider>(model, s) function below.
  2. Register it in _BUILDERS.
  3. Add models to app/config/models.json with "provider": "<provider>".
"""
import json
import logging
from functools import lru_cache
from pathlib import Path

from browser_use.llm.base import BaseChatModel
from app.user_config import UserSettings, load_settings

_MODELS_PATH = Path(__file__).parent / "config" / "models.json"


@lru_cache(maxsize=1)
def _load_models() -> list[dict]:
    return json.loads(_MODELS_PATH.read_text(encoding="utf-8"))


def get_models() -> list[dict]:
    return _load_models()


def get_default_model() -> str:
    models = _load_models()
    return next((m["value"] for m in models if m.get("default")), models[0]["value"])


def get_provider(model_value: str) -> str:
    for m in _load_models():
        if m["value"] == model_value:
            return m["provider"]
    logging.warning("[LLMFactory] Unknown model '%s' — defaulting to google.", model_value)
    return "google"


# ── Per-provider builders ─────────────────────────────────────────────────────

def _build_google(model: str, s: UserSettings) -> BaseChatModel:
    from browser_use.llm.google.chat import ChatGoogle
    if s.gemini_api_key:
        return ChatGoogle(model=model, api_key=s.gemini_api_key)
    return ChatGoogle(
        model=model,
        project=s.google_cloud_project,
        location=s.llm_location,
        vertexai=True,
    )


def _build_groq(model: str, s: UserSettings) -> BaseChatModel:
    from browser_use.llm.groq.chat import ChatGroq
    return ChatGroq(model=model, api_key=s.groq_api_key)


def _build_openai(model: str, s: UserSettings) -> BaseChatModel:
    from browser_use.llm.openai.chat import ChatOpenAI
    return ChatOpenAI(model=model, api_key=s.openai_api_key)


def _build_anthropic(model: str, s: UserSettings) -> BaseChatModel:
    from browser_use.llm.anthropic.chat import ChatAnthropic
    return ChatAnthropic(model=model, api_key=s.anthropic_api_key)


_BUILDERS = {
    "google":    _build_google,
    "groq":      _build_groq,
    "openai":    _build_openai,
    "anthropic": _build_anthropic,
}


# ── Public API ────────────────────────────────────────────────────────────────

def create_llm() -> BaseChatModel:
    """Create the agent LLM from current settings."""
    s = load_settings()
    return create_llm_for(s.model or get_default_model(), s)


def create_orchestrator_llm() -> BaseChatModel:
    """Create the orchestrator LLM (routing + direct answers).
    Falls back to the agent model if orchestrator_model is not set."""
    s = load_settings()
    model = s.orchestrator_model or s.model or get_default_model()
    return create_llm_for(model, s)


def create_llm_for(model_value: str, s: UserSettings | None = None) -> BaseChatModel:
    """Create an LLM for a specific model value using current settings for credentials."""
    if s is None:
        s = load_settings()
    provider = get_provider(model_value)
    builder  = _BUILDERS.get(provider)
    if not builder:
        raise ValueError(f"[LLMFactory] No builder registered for provider '{provider}'")
    logging.info("[LLMFactory] %s / %s", provider, model_value)
    return builder(model_value, s)
