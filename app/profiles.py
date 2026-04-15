"""Browser profile detection."""
import json
import os
from pathlib import Path

from app.user_config import load_settings


_EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
_CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]


def _find_exe(candidates: list[str]) -> str | None:
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _viro_profile() -> dict:
    path = Path.home() / ".viro" / "browser-profile"
    path.mkdir(parents=True, exist_ok=True)
    exe = _find_exe(_EDGE_CANDIDATES) or _find_exe(_CHROME_CANDIDATES)
    return {
        "id":               "viro",
        "label":            "Viro (dedicated profile)",
        "user_data_dir":    str(path),
        "profile_directory": "Default",
        "browser":          "edge" if _find_exe(_EDGE_CANDIDATES) else "chrome",
        "executable":       exe,
    }


_GENERIC_NAMES = {"default", "profile 1", "your chrome", "person 1", "profile"}

def _profile_label(prefs: dict, entry_name: str) -> str:
    name = prefs.get("profile", {}).get("name", "") or entry_name
    accounts = prefs.get("account_info", [])
    email = ""
    if isinstance(accounts, list) and accounts:
        email = accounts[0].get("email", "")
    # If the profile name is a generic placeholder, show just the email (if available)
    display_name = email if (name.lower() in _GENERIC_NAMES and email) else name
    return f"{display_name} ({email})" if (email and display_name != email) else display_name or name


def detect_profiles() -> list[dict]:
    profiles = [_viro_profile()]
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return profiles

    browsers = [
        ("Chrome", Path(local) / "Google"    / "Chrome" / "User Data", _CHROME_CANDIDATES),
        ("Edge",   Path(local) / "Microsoft" / "Edge"   / "User Data", _EDGE_CANDIDATES),
    ]
    for browser_name, base, exe_candidates in browsers:
        if not base.exists():
            continue
        exe = _find_exe(exe_candidates)
        for entry in sorted(base.iterdir()):
            if entry.name != "Default" and not entry.name.startswith("Profile "):
                continue
            prefs_file = entry / "Preferences"
            if not prefs_file.exists():
                continue
            try:
                prefs = json.loads(prefs_file.read_text(encoding="utf-8", errors="ignore"))
                label = _profile_label(prefs, entry.name)
            except Exception:
                label = entry.name
            profiles.append({
                "id":                f"{browser_name.lower()}-{entry.name}",
                "label":             f"{browser_name} — {label}",
                "user_data_dir":     str(base),       # e.g. ...Chrome\User Data
                "profile_directory": entry.name,      # e.g. Default, Profile 1
                "browser":           browser_name.lower(),
                "executable":        exe,
            })

    return profiles


def get_active_profile() -> dict:
    profile_id = load_settings().browser_profile
    for p in detect_profiles():
        if p["id"] == profile_id:
            return p
    return _viro_profile()
