def friendly_error(exc: Exception) -> str:
    msg = str(exc)
    low = msg.lower()

    # ── Google / Gemini ───────────────────────────────────────────────────────
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in low:
        return (
            "API quota exceeded. You've hit the rate limit for your Gemini plan. "
            "Wait a few minutes and try again, or switch to a different model in Settings."
        )
    if "Reauthentication" in msg or "reauthenticate" in msg or "application default credentials" in low:
        return (
            "Google authentication expired. Click the 'Google Auth' button in the header "
            "to re-authenticate, or run: gcloud auth application-default login"
        )
    if "API_KEY_INVALID" in msg or "api key not valid" in low:
        return (
            "Invalid API key. Check your Gemini API key in Settings — "
            "make sure it's correct and hasn't been revoked."
        )
    if "PERMISSION_DENIED" in msg or "403" in msg:
        return (
            "Permission denied. Check that your Google Cloud project and region are correct in Settings, "
            "and that the Vertex AI API is enabled for your project."
        )
    if "401" in msg or "unauthorized" in low or "authentication" in low:
        return (
            "Authentication failed. Check your API key or credentials in Settings."
        )

    # ── Network / availability ────────────────────────────────────────────────
    if "UNAVAILABLE" in msg or "503" in msg:
        return "The AI service is temporarily unavailable. Wait a few seconds and try again."
    if "connection" in low and ("refused" in low or "reset" in low or "aborted" in low):
        return "Connection failed. Check your internet connection and try again."
    if "timeout" in low or "timed out" in low or "deadline" in low:
        return (
            "The request timed out. The page may be too complex or the AI service is slow. "
            "Try again, or reduce Max Steps in Settings."
        )

    # ── Browser ───────────────────────────────────────────────────────────────
    if "browser" in low and ("crash" in low or "closed" in low or "disconnect" in low):
        return (
            "The browser closed unexpectedly. Click Reset and try again. "
            "If this keeps happening, try a different browser profile in Settings."
        )
    if "playwright" in low or "chromium" in low:
        return (
            "Browser error. Make sure Playwright is installed: "
            "run 'playwright install chromium' in the project directory."
        )
    if "target page, context or browser has been closed" in low:
        return "The browser tab was closed during the task. Click Reset and try again."

    # ── Groq ─────────────────────────────────────────────────────────────────
    if "groq" in low or "gsk_" in low:
        if "401" in msg or "invalid" in low:
            return "Invalid Groq API key. Check your Groq key in Settings."
        if "429" in msg or "rate" in low:
            return "Groq rate limit reached. Wait a moment and try again."

    # ── OpenAI ───────────────────────────────────────────────────────────────
    if "openai" in low or "sk-" in low:
        if "401" in msg or "invalid" in low:
            return "Invalid OpenAI API key. Check your OpenAI key in Settings."
        if "429" in msg or "quota" in low:
            return "OpenAI quota exceeded. Check your usage limits at platform.openai.com."

    # ── Anthropic ────────────────────────────────────────────────────────────
    if "anthropic" in low or "claude" in low:
        if "401" in msg or "invalid" in low:
            return "Invalid Anthropic API key. Check your Anthropic key in Settings."
        if "529" in msg or "overloaded" in low:
            return "Anthropic API is overloaded. Wait a moment and try again."

    # ── Skill / config ────────────────────────────────────────────────────────
    if "skill" in low and ("not found" in low or "missing" in low):
        return f"Skill not found. Check that the skill is correctly defined in the skills/ directory. ({msg})"

    # ── Fallback ──────────────────────────────────────────────────────────────
    return f"Something went wrong: {msg}"
