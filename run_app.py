import asyncio
import subprocess
import sys
import threading
import time

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

_PORT = 8000
_URL  = f"http://127.0.0.1:{_PORT}"

_EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "msedge",
]


def _screen_size() -> tuple[int, int]:
    """Returns screen dimensions in the same coordinate space Edge uses for --window-size/position."""
    try:
        out = subprocess.check_output([
            "powershell", "-NoProfile", "-Command",
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$s=[System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea;"
            "Write-Output \"$($s.Width) $($s.Height)\""
        ], text=True).strip()
        w, h = map(int, out.split())
        return w, h
    except Exception:
        return 1920, 1080  # safe fallback


def _open_app_window():
    time.sleep(1.5)  # wait for uvicorn to bind

    sw, sh = _screen_size()
    app_w = sw // 4          # chat panel = 25% of screen width
    app_x = sw - app_w       # pinned to right edge

    # Chrome windows have an ~8px invisible resize border outside the declared size.
    # Setting browser_w = app_x + 8 means the visible browser content ends exactly
    # where the visible app content begins — no gap, no overlap.
    import os
    os.environ["BROWSER_W"] = str(app_x + 8)
    os.environ["BROWSER_H"] = str(sh)

    import tempfile, os as _os
    profile_dir = _os.path.join(tempfile.gettempdir(), "browser-agent-app-profile")
    args = [
        f"--app={_URL}",
        f"--window-size={app_w},{sh}",
        f"--window-position={app_x},0",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--disable-extensions",
    ]
    for exe in _EDGE_CANDIDATES:
        try:
            subprocess.Popen([exe] + args)
            return
        except FileNotFoundError:
            continue
    import webbrowser
    webbrowser.open(_URL)


if __name__ == "__main__":
    threading.Thread(target=_open_app_window, daemon=True).start()
    uvicorn.run("app.server:app", host="127.0.0.1", port=_PORT)
