import os

# Agent behavior limits
MAX_FAILURES:         int  = 5
MAX_ACTIONS_PER_STEP: int  = 5

# Skill behavior — stop after first successful source (False) or collect all (True)
COLLECT_ALL: bool = os.getenv("COLLECT_ALL", "false").lower() == "true"
