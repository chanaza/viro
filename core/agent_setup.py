"""Agent policy — builds system extension and loads sensitive data."""
import json
from pathlib import Path

from core.prompts import ALLOWED_POLICY_BLOCK, DENIED_POLICY_BLOCK

_CONFIG_DIR = Path(__file__).parent / "config"
_SYS_EXT_PATH = _CONFIG_DIR / "system_extension.md"
_SENSITIVE_DATA_PATH = _CONFIG_DIR / "sensitive_data.json"


def _load_system_extension() -> str | None:
    try:
        text = _SYS_EXT_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None

    lines = [
        line
        for line in text.splitlines()
        if not line.startswith("#") and not line.startswith("<!--")
    ]
    content = "\n".join(lines).strip()
    return content if content else None


def _load_sensitive_data() -> dict[str, str] | None:
    try:
        data = json.loads(_SENSITIVE_DATA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None

    result = {
        key: value
        for key, value in data.items()
        if not key.startswith("_") and isinstance(value, str)
    }
    return result if result else None


def _build_system_extension(
    *,
    base_extension: str | None,
    allowed_actions: str,
    denied_actions: str,
) -> str | None:
    parts: list[str] = []
    if base_extension:
        parts.append(base_extension)
    if allowed_actions.strip():
        parts.append(ALLOWED_POLICY_BLOCK.format(allowed_actions=allowed_actions.strip()))
    if denied_actions.strip():
        parts.append(DENIED_POLICY_BLOCK.format(denied_actions=denied_actions.strip()))
    return "\n\n".join(parts) if parts else None


def build_agent_policy(
    *,
    allowed_actions: str,
    denied_actions: str,
) -> tuple[str | None, dict[str, str] | None]:
    return (
        _build_system_extension(
            base_extension=_load_system_extension(),
            allowed_actions=allowed_actions,
            denied_actions=denied_actions,
        ),
        _load_sensitive_data(),
    )
