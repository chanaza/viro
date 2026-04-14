# Developer-facing config — change here, not in the user's config.json

# Agent behavior limits (not exposed in UI)
MAX_FAILURES:          int = 5
MAX_ACTIONS_PER_STEP:  int = 5

# Available Gemini models shown in the settings dropdown
GEMINI_MODELS: list[str] = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.5-pro",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]
