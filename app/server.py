import asyncio
import json
import os
import traceback
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load .env from repo root
load_dotenv(Path(__file__).parent.parent / ".env")

from app.chat_agent import ChatBrowserAgent
from app.llm import get_models, get_provider
from app.profiles import detect_profiles
from app.user_config import UserSettings, load_settings, save_settings

app = FastAPI()
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    try:
        log = Path(__file__).parent.parent / "viro.log"
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"\n=== EXCEPTION ===\n{tb}\n")
    except Exception:
        pass
    return JSONResponse(status_code=500, content={"detail": tb})

_agent: ChatBrowserAgent | None = None


# ── Request bodies ────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    task: str

class SendRequest(BaseModel):
    message: str

class OpenFileRequest(BaseModel):
    path: str

class SettingsRequest(UserSettings):
    """Extends UserSettings with the UI-only google_auth_type field."""
    google_auth_type: str = "vertex"   # "apikey" | "vertex" — not stored, clears the other Google credentials


# ── Agent routes ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


@app.post("/start")
async def start(body: StartRequest):
    global _agent
    if _agent and _agent.is_running:
        raise HTTPException(400, "Agent is already running. Stop it first.")
    if not _agent:
        _agent = ChatBrowserAgent()
    await _agent.start(body.task)
    return {"status": "started"}


@app.get("/stream")
async def stream():
    if not _agent:
        raise HTTPException(400, "No active session.")

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(_agent.queue.get(), timeout=30)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event["type"] in ("done", "stopped", "error"):
                    break
            except asyncio.TimeoutError:
                yield "data: {\"type\": \"ping\"}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/pause")
async def pause():
    _require_agent()
    _agent.pause()
    return {"status": "paused"}


@app.post("/resume")
async def resume():
    _require_agent()
    _agent.resume()
    return {"status": "resumed"}


@app.post("/stop")
async def stop():
    _require_agent()
    _agent.stop()
    return {"status": "stopping"}


@app.post("/send")
async def send(body: SendRequest):
    _require_agent()
    _agent.send(body.message)
    return {"status": "sent"}


# ── Models ────────────────────────────────────────────────────────────────────

@app.get("/models")
async def models():
    return {"models": get_models()}


# ── Settings ──────────────────────────────────────────────────────────────────

@app.get("/settings")
async def get_settings():
    s = load_settings()
    return {
        **s.model_dump(),
        "google_auth_type": "apikey" if s.gemini_api_key else "vertex",
    }


@app.post("/settings")
async def post_settings(body: SettingsRequest):
    if _agent and _agent.is_running:
        raise HTTPException(400, "Cannot change settings while agent is running.")
    s = UserSettings(
        model                = body.model,
        max_steps            = body.max_steps,
        browser_profile      = body.browser_profile,
        gemini_api_key       = body.gemini_api_key       if body.google_auth_type == "apikey" else "",
        google_cloud_project = body.google_cloud_project if body.google_auth_type == "vertex" else "",
        llm_location         = body.llm_location         if body.google_auth_type == "vertex" else "",
        groq_api_key         = body.groq_api_key,
        openai_api_key       = body.openai_api_key,
        anthropic_api_key    = body.anthropic_api_key,
    )
    save_settings(s)
    global _agent
    _agent = ChatBrowserAgent()
    return {"status": "ok"}


# ── Profiles ──────────────────────────────────────────────────────────────────

@app.get("/profiles")
async def profiles():
    return {"profiles": detect_profiles(), "active": load_settings().browser_profile}


# ── Open file ─────────────────────────────────────────────────────────────────

@app.post("/open-file")
async def open_file(body: OpenFileRequest):
    import subprocess
    p = Path(body.path)
    if not p.exists():
        raise HTTPException(404, f"File not found: {body.path}")
    subprocess.Popen(["cmd", "/c", "start", "", str(p)],
                     creationflags=subprocess.CREATE_NO_WINDOW)
    return {"status": "opened"}


# ── Google Auth ───────────────────────────────────────────────────────────────

@app.post("/auth-google")
async def auth_google():
    import subprocess, shutil
    gcloud = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    if not gcloud:
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"),
            os.path.expandvars(r"%ProgramFiles%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"),
        ]
        for c in candidates:
            if os.path.exists(c):
                gcloud = c
                break
    if not gcloud:
        raise HTTPException(500, "gcloud not found. Install Google Cloud SDK first.")
    subprocess.Popen(
        [gcloud, "auth", "application-default", "login"],
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return {"status": "launched"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_agent():
    if not _agent or not _agent.is_running:
        raise HTTPException(400, "No active session. Start one first.")
