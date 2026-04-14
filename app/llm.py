import os

from browser_use.llm.google.chat import ChatGoogle
from app.profiles import get_config_value


def create_llm() -> ChatGoogle:
    model   = get_config_value("gemini_model",   os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
    api_key = get_config_value("gemini_api_key", os.getenv("GEMINI_API_KEY"))

    if api_key:
        return ChatGoogle(model=model, api_key=api_key)

    return ChatGoogle(
        model=model,
        project=get_config_value("google_cloud_project", os.getenv("GOOGLE_CLOUD_PROJECT")),
        location=get_config_value("llm_location",        os.getenv("LLM_LOCATION")),
        vertexai=True,
    )
