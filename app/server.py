import asyncio
import json
import logging
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
from app.config import GEMINI_MODELS
from app.profiles import detect_profiles, load_config, save_config

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

class SettingsRequest(BaseModel):
    browser_profile:     str
    auth_type:           str            # "apikey" | "vertex"
    gemini_api_key:      str = ""
    google_cloud_project: str = ""
    llm_location:        str = ""
    gemini_model:        str = "gemini-2.0-flash"
    max_steps:           int = 100


# ── Routes ────────────────────────────────────────────────────────────────────

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
    """SSE endpoint — yields events from the agent queue."""
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


# ── Helpers ───────────────────────────────────────────────────────────────────

@app.post("/auth-google")
async def auth_google():
    """Run gcloud auth silently — opens browser for Google sign-in automatically."""
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
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {"status": "launched"}


@app.get("/profiles")
async def profiles():
    return {"profiles": detect_profiles(), "active": load_config().get("browser_profile", "viro")}


@app.get("/settings")
async def get_settings():
    cfg = load_config()
    auth_type = "apikey" if cfg.get("gemini_api_key") or os.getenv("GEMINI_API_KEY") else "vertex"
    return {
        "auth_type":            auth_type,
        "gemini_api_key":       cfg.get("gemini_api_key",       os.getenv("GEMINI_API_KEY", "")),
        "google_cloud_project": cfg.get("google_cloud_project", os.getenv("GOOGLE_CLOUD_PROJECT", "")),
        "llm_location":         cfg.get("llm_location",         os.getenv("LLM_LOCATION", "")),
        "gemini_model":         cfg.get("gemini_model",         os.getenv("GEMINI_MODEL", "gemini-2.0-flash")),
        "max_steps":            cfg.get("max_steps",            100),
        "browser_profile":      cfg.get("browser_profile",      "viro"),
        "available_models":     GEMINI_MODELS,
    }


@app.post("/settings")
async def post_settings(body: SettingsRequest):
    if _agent and _agent.is_running:
        raise HTTPException(400, "Cannot change settings while agent is running.")
    cfg = load_config()
    cfg["browser_profile"]      = body.browser_profile
    cfg["gemini_model"]         = body.gemini_model
    cfg["max_steps"]            = body.max_steps
    if body.auth_type == "apikey":
        cfg["gemini_api_key"]       = body.gemini_api_key
        cfg.pop("google_cloud_project", None)
        cfg.pop("llm_location", None)
    else:
        cfg["google_cloud_project"] = body.google_cloud_project
        cfg["llm_location"]         = body.llm_location
        cfg.pop("gemini_api_key", None)
    save_config(cfg)
    global _agent
    _agent = ChatBrowserAgent()
    return {"status": "ok"}


def _require_agent():
    if not _agent or not _agent.is_running:
        raise HTTPException(400, "No active session. Start one first.")
