"""Detect available browser profiles on the system."""
import json
import os
from pathlib import Path


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
        "id":         "viro",
        "label":      "Viro (dedicated profile)",
        "path":       str(path),
        "browser":    "edge" if _find_exe(_EDGE_CANDIDATES) else "chrome",
        "executable": exe,
    }


def _profile_label(prefs: dict, entry_name: str) -> str:
    """Build a human-readable label: 'Name (email)' or fallback."""
    name = prefs.get("profile", {}).get("name", "") or entry_name
    # Try to get email from account_info list
    accounts = prefs.get("account_info", [])
    if isinstance(accounts, list) and accounts:
        email = accounts[0].get("email", "")
        if email:
            return f"{name} ({email})"
    return name


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
                "id":         f"{browser_name.lower()}-{entry.name}",
                "label":      f"{browser_name} — {label}",
                "path":       str(entry),
                "browser":    browser_name.lower(),
                "executable": exe,
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


def get_active_profile() -> dict:
    profile_id = load_config().get("browser_profile", "viro")
    for p in detect_profiles():
        if p["id"] == profile_id:
            return p
    return _viro_profile()
