"""Loaders for agent configuration files."""
import json
from pathlib import Path

_CONFIG_DIR        = Path(__file__).parent / "config"
_SYS_EXT_PATH      = _CONFIG_DIR / "system_extension.md"
_SENSITIVE_DATA_PATH = _CONFIG_DIR / "sensitive_data.json"


def load_system_extension() -> str | None:
    try:
        text = _SYS_EXT_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    lines = [
        line for line in text.splitlines()
        if not line.startswith("#") and not line.startswith("<!--")
    ]
    content = "\n".join(lines).strip()
    return content if content else None


def load_sensitive_data() -> dict[str, str] | None:
    try:
        data = json.loads(_SENSITIVE_DATA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    result = {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, str)}
    return result if result else None
