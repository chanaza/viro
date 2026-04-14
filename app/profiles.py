"""Detect available browser profiles on the system."""
import json
import os
from pathlib import Path


def _viro_profile() -> dict:
    path = Path.home() / ".viro" / "browser-profile"
    path.mkdir(parents=True, exist_ok=True)
    return {"id": "viro", "label": "Viro (dedicated)", "path": str(path)}


def detect_profiles() -> list[dict]:
    profiles = [_viro_profile()]
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return profiles

    candidates = [
        ("Chrome", Path(local) / "Google" / "Chrome" / "User Data"),
        ("Edge",   Path(local) / "Microsoft" / "Edge" / "User Data"),
    ]
    for browser, base in candidates:
        if not base.exists():
            continue
        for entry in sorted(base.iterdir()):
            if entry.name != "Default" and not entry.name.startswith("Profile "):
                continue
            prefs_file = entry / "Preferences"
            if not prefs_file.exists():
                continue
            try:
                prefs = json.loads(prefs_file.read_text(encoding="utf-8", errors="ignore"))
                name = prefs.get("profile", {}).get("name") or entry.name
            except Exception:
                name = entry.name
            profiles.append({
                "id":    f"{browser.lower()}-{entry.name}",
                "label": f"{browser} — {name}",
                "path":  str(entry),
            })

    return profiles


# ── Config (saved choice) ─────────────────────────────────────────────────────

_CONFIG_PATH = Path.home() / ".viro" / "config.json"


def load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_active_profile_path() -> str:
    profile_id = load_config().get("browser_profile", "viro")
    for p in detect_profiles():
        if p["id"] == profile_id:
            return p["path"]
    return _viro_profile()["path"]
