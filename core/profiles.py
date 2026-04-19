import json
import os
from pathlib import Path
from typing import TypedDict

from browser_use.browser.profile import BrowserProfile, ViewportSize

class ProfileDict(TypedDict):
    id: str
    label: str
    user_data_dir: str
    profile_directory: str
    browser: str
    executable: str | None

_EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
_CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]
_GENERIC_NAMES = {"default", "profile 1", "your chrome", "person 1", "profile"}
_DEFAULT_BROWSER_ARGS = ["--ignore-certificate-errors"]


def _find_exe(candidates: list[str]) -> str | None:
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def _viro_profile() -> ProfileDict:
    path = Path.home() / ".viro" / "browser-profile"
    path.mkdir(parents=True, exist_ok=True)
    exe = _find_exe(_EDGE_CANDIDATES) or _find_exe(_CHROME_CANDIDATES)
    browser = "edge" if _find_exe(_EDGE_CANDIDATES) else "chrome"
    return {
        "id":               "viro",
        "label":            "Viro (dedicated profile)",
        "user_data_dir":    str(path),
        "profile_directory": "Default",
        "browser":          browser,
        "executable":       exe,
    }


def _profile_label(prefs: dict, entry_name: str) -> str:
    name = prefs.get("profile", {}).get("name", "") or entry_name
    accounts = prefs.get("account_info", [])
    email = ""
    if isinstance(accounts, list) and accounts:
        email = accounts[0].get("email", "")
    display_name = email if (name.lower() in _GENERIC_NAMES and email) else name
    return f"{display_name} ({email})" if (email and display_name != email) else display_name or name


def detect_profiles() -> list[ProfileDict]:
    profiles = [_viro_profile()]
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return profiles

    browsers = [
        ("Chrome", Path(local) / "Google" / "Chrome" / "User Data", _CHROME_CANDIDATES),
        ("Edge", Path(local) / "Microsoft" / "Edge" / "User Data", _EDGE_CANDIDATES),
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
                "user_data_dir":     str(base),
                "profile_directory": entry.name,
                "browser":           browser_name.lower(),
                "executable":        exe,
            })

    return profiles


def get_profile(profile_id: str) -> ProfileDict | None:
    for profile in detect_profiles():
        if profile["id"] == profile_id:
            return profile
    return None


def get_active_profile(profile_id: str) -> ProfileDict:
    return get_profile(profile_id) or _viro_profile()


def parse_domain_list(raw: str | list[str] | None) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        parts = [domain.strip() for domain in raw.split(",") if domain.strip()]
        return parts if parts else None

    parts = [domain.strip() for domain in raw if domain.strip()]
    return parts if parts else None


def profile_to_browser_profile(profile: ProfileDict, **kwargs) -> BrowserProfile:
    return BrowserProfile(
        args=kwargs.get("args", []),
        window_size=kwargs.get("window_size"),
        window_position=kwargs.get("window_position"),
        headless=kwargs.get("headless"),
        user_data_dir=profile.get("user_data_dir"),
        profile_directory=profile.get("profile_directory", "Default"),
        executable_path=profile.get("executable"),
        allowed_domains=kwargs.get("allowed_domains"),
        prohibited_domains=kwargs.get("prohibited_domains"),
    )


def build_browser_profile(
    profile_id: str,
    *,
    args: list[str] | None = None,
    window_size: ViewportSize | None = None,
    window_position: ViewportSize | None = None,
    headless: bool | None = None,
    allowed_domains: str | list[str] | None = None,
    prohibited_domains: str | list[str] | None = None,
) -> tuple[ProfileDict, BrowserProfile]:
    profile = get_active_profile(profile_id)
    browser_profile = profile_to_browser_profile(
        profile,
        args=args if args is not None else list(_DEFAULT_BROWSER_ARGS),
        window_size=window_size,
        window_position=window_position,
        headless=headless,
        allowed_domains=parse_domain_list(allowed_domains),
        prohibited_domains=parse_domain_list(prohibited_domains),
    )
    return profile, browser_profile
