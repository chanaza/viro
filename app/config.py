import os

# Developer-facing config — change here, not in the user's config.json

# Agent behavior limits (not exposed in UI)
MAX_FAILURES:          int = 5
MAX_ACTIONS_PER_STEP:  int = 5

# Skill behavior
# When True: collect from ALL sources regardless of findings.
# When False (default): stop after the first source that yields results.
COLLECT_ALL: bool = os.getenv("COLLECT_ALL", "false").lower() == "true"

# Available Gemini models shown in the settings dropdown
GEMINI_MODELS: list[str] = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.5-pro",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]
