"""Core LLM provider registry and factory.

This module is shared by all callers, including app and CLI.
It does not depend on application runtime or web-specific layers.
"""
import json
import logging
from functools import lru_cache
from pathlib import Path

from browser_use.llm.base import BaseChatModel

from .models import LLMSettings

_MODELS_PATH = Path(__file__).parent / "config" / "models.json"
_MAX_OUTPUT_TOKENS = 65_536


# ── Per-provider builders ─────────────────────────────────────────────────────

def _build_google(model: str, s: LLMSettings) -> BaseChatModel:
    from browser_use.llm.google.chat import ChatGoogle

    if s.gemini_api_key:
        return ChatGoogle(model=model, api_key=s.gemini_api_key,
                          max_output_tokens=_MAX_OUTPUT_TOKENS)
    return ChatGoogle(
        model=model,
        project=s.google_cloud_project,
        location=s.llm_location,
        vertexai=True,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
    )


def _build_groq(model: str, s: LLMSettings) -> BaseChatModel:
    from browser_use.llm.groq.chat import ChatGroq
    return ChatGroq(model=model, api_key=s.groq_api_key)


def _build_openai(model: str, s: LLMSettings) -> BaseChatModel:
    from browser_use.llm.openai.chat import ChatOpenAI
    return ChatOpenAI(model=model, api_key=s.openai_api_key)


def _build_anthropic(model: str, s: LLMSettings) -> BaseChatModel:
    from browser_use.llm.anthropic.chat import ChatAnthropic
    return ChatAnthropic(model=model, api_key=s.anthropic_api_key)


_BUILDERS = {
    "google":    _build_google,
    "groq":      _build_groq,
    "openai":    _build_openai,
    "anthropic": _build_anthropic,
}


# ── Model registry ────────────────────────────────────────────────────────────

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


# ── Factory ───────────────────────────────────────────────────────────────────

def create_llm_for(model_value: str, s: LLMSettings) -> BaseChatModel:
    """Create an LLM for a specific model value using the provided settings."""
    provider = get_provider(model_value)
    builder = _BUILDERS.get(provider)
    if not builder:
        raise ValueError(f"[LLMFactory] No builder registered for provider '{provider}'")
    logging.info("[LLMFactory] %s / %s", provider, model_value)
    return builder(model_value, s)
