from browser_use.llm.google.chat import ChatGoogle
from app.user_config import load_settings


def create_llm() -> ChatGoogle:
    s = load_settings()
    if s.gemini_api_key:
        return ChatGoogle(model=s.gemini_model, api_key=s.gemini_api_key)
    return ChatGoogle(
        model=s.gemini_model,
        project=s.google_cloud_project,
        location=s.llm_location,
        vertexai=True,
    )
