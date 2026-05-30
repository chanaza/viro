"""Core LLM provider registry and factory.

This module is shared by all callers, including app and CLI.
It does not depend on application runtime or web-specific layers.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from browser_use.llm.base import BaseChatModel

from .models import LLMSettings

_MODELS_PATH = Path(__file__).parent / "config" / "models.json"
_MAX_OUTPUT_TOKENS = 65_536


# ── Per-provider builders ─────────────────────────────────────────────────────

def _build_google(model: str, s: LLMSettings) -> BaseChatModel:
    from browser_use.llm.google.chat import ChatGoogle

    if s.gemini_api_key:
        return ChatGoogle(model=model, api_key=s.gemini_api_key,
                          max_output_tokens=_MAX_OUTPUT_TOKENS,
                          thinking_budget=0)
    return ChatGoogle(
        model=model,
        project=s.google_cloud_project,
        location=s.llm_location,
        vertexai=True,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        thinking_budget=0,
    )


def _build_groq(model: str, s: LLMSettings) -> BaseChatModel:
    from browser_use.llm.groq.chat import ChatGroq, JsonSchemaModels
    from browser_use.llm.schema import SchemaOptimizer
    from browser_use.llm.views import ChatInvokeCompletion
    from browser_use.llm.exceptions import ModelProviderError

    if model in JsonSchemaModels:
        return ChatGroq(model=model, api_key=s.groq_api_key)

    # Models outside JsonSchemaModels don't support json_schema response format.
    # Override _invoke_structured_output to use tool calling instead.
    async def _tool_calling_structured(self, groq_messages, output_format):
        schema = SchemaOptimizer.create_optimized_json_schema(output_format)
        response = await self._invoke_with_tool_calling(groq_messages, output_format, schema)
        content = response.choices[0].message.content
        if not content:
            tc = response.choices[0].message.tool_calls
            content = tc[0].function.arguments if tc else None
        if not content:
            raise ModelProviderError(
                message='No structured output in response', status_code=500, model=self.name)
        parsed = output_format.model_validate_json(content)
        return ChatInvokeCompletion(completion=parsed, usage=self._get_usage(response))

    GroqFixed = type('ChatGroqFixed', (ChatGroq,), {'_invoke_structured_output': _tool_calling_structured})
    return GroqFixed(model=model, api_key=s.groq_api_key)


def _build_openai(model: str, s: LLMSettings) -> BaseChatModel:
    from browser_use.llm.openai.chat import ChatOpenAI
    return ChatOpenAI(model=model, api_key=s.openai_api_key)


def _build_anthropic(model: str, s: LLMSettings) -> BaseChatModel:
    from browser_use.llm.anthropic.chat import ChatAnthropic
    if s.anthropic_api_key:
        return ChatAnthropic(model=model, api_key=s.anthropic_api_key,
                             max_tokens=_MAX_OUTPUT_TOKENS)
    # No API key → route through Google Cloud Vertex AI
    if not s.google_cloud_project:
        raise ValueError("Anthropic via Vertex AI requires a GCP Project ID. Set it in Settings.")
    import re
    from anthropic import AsyncAnthropicVertex
    vertex_model = re.sub(r'-(\d{8})$', r'@\1', model)
    project, region = s.google_cloud_project, (s.llm_location or "us-east5")
    def _get_client(self):
        return AsyncAnthropicVertex(project_id=project, region=region)
    AnthropicVertexCls = type("AnthropicVertex", (ChatAnthropic,), {"get_client": _get_client})
    return AnthropicVertexCls(model=vertex_model, max_tokens=_MAX_OUTPUT_TOKENS)


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
