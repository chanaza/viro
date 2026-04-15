import os
import sys

# Derive install dir from the executable: viro-env/Scripts/python(w).exe -> ../..
_scripts = os.path.dirname(os.path.abspath(sys.executable))   # .../viro-env/Scripts
_venv    = os.path.dirname(_scripts)                           # .../viro-env
_base    = os.path.dirname(_venv)                              # .../Viro  (install dir)
if _base not in sys.path:
    sys.path.insert(0, _base)

_log_path = os.path.join(_base, "viro.log")
_log_file = open(_log_path, "w", encoding="utf-8", buffering=1)
sys.stdout = _log_file
sys.stderr = _log_file

import asyncio
import logging
import socket
import subprocess
import tempfile
import threading
import time
import uvicorn

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

_PORT = 8000
_URL  = f"http://127.0.0.1:{_PORT}"

_EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "msedge",
]


def _screen_size() -> tuple[int, int]:
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
        return 1920, 1080


def _open_app_window(server: uvicorn.Server) -> None:
    time.sleep(1.5)
    sw, sh = _screen_size()
    app_w = sw // 4
    app_x = sw - app_w
    os.environ["BROWSER_W"] = str(app_x + 8)
    os.environ["BROWSER_H"] = str(sh)
    profile_dir = os.path.join(tempfile.gettempdir(), "viro-app-profile")
    args = [
        f"--app={_URL}",
        f"--window-size={app_w},{sh}",
        f"--window-position={app_x},0",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--disable-extensions",
    ]
    proc = None
    for exe in _EDGE_CANDIDATES:
        try:
            proc = subprocess.Popen([exe] + args)
            break
        except FileNotFoundError:
            continue
    if proc is None:
        import webbrowser
        webbrowser.open(_URL)
        return
    # When the Edge window is closed, kill the entire process
    proc.wait()
    os._exit(0)


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _kill_port(port: int) -> None:
    """Kill whatever process is holding the port (Windows)."""
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "TCP"],
            text=True, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                pid = line.split()[-1]
                subprocess.call(
                    ["taskkill", "/F", "/PID", pid],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
    except Exception:
        pass


if __name__ == "__main__":
    try:
        if _port_in_use(_PORT):
            # Stale server from a previous session — kill it and start fresh
            _kill_port(_PORT)
            # Wait up to 3s for the port to free
            for _ in range(6):
                time.sleep(0.5)
                if not _port_in_use(_PORT):
                    break

        config = uvicorn.Config(
            "app.server:app",
            host="127.0.0.1",
            port=_PORT,
            loop="asyncio",
            log_config=None,
        )
        logging.basicConfig(
            filename=_log_path,
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        server = uvicorn.Server(config)
        threading.Thread(target=_open_app_window, args=(server,), daemon=True).start()
        asyncio.run(server.serve())
    except Exception:
        import traceback
        print("RUNTIME ERROR:", traceback.format_exc(), flush=True)
        _log_file.flush()
        sys.exit(1)
