"""App-level LLM helpers for settings and UI integration.

This module wraps the shared core LLM factory and keeps app-specific
settings loading in the app layer.
"""
from browser_use.llm.base import BaseChatModel

from app.user_config import UserSettings, load_settings
from core.llm import create_llm_for, get_default_model, get_models, get_provider


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


def create_judge_llm() -> BaseChatModel:
    """Create the security judge LLM.
    Falls back to orchestrator_model, then agent model."""
    s = load_settings()
    model = s.judge_model or s.orchestrator_model or s.model or get_default_model()
    return create_llm_for(model, s)
