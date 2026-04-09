import os

# ─── LLM settings ─────────────────────────────────────────────────────────────

LLM_MAX_OUTPUT_TOKENS = 32000

# ─── Agent behavior ───────────────────────────────────────────────────────────

# When True: collect from all sources regardless of findings.
# When False (default): stop after the first source that yields results.
COLLECT_ALL = os.getenv("COLLECT_ALL", "false").lower() == "true"
