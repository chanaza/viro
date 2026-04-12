import os

from browser_use.llm.google.chat import ChatGoogle


def create_llm() -> ChatGoogle:
    """
    Creates the LLM client based on available credentials.

    - If GEMINI_API_KEY is set: uses Gemini API key (no Google Cloud needed).
    - Otherwise: uses Vertex AI (requires GOOGLE_CLOUD_PROJECT + LLM_LOCATION).
    """
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    api_key = os.getenv("GEMINI_API_KEY")

    if api_key:
        return ChatGoogle(model=model, api_key=api_key)

    return ChatGoogle(
        model=model,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location=os.getenv("LLM_LOCATION"),
        vertexai=True,
    )
