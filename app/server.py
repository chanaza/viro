from __future__ import annotations

import asyncio
import json
import os
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load .env from repo root
load_dotenv(Path(__file__).parent.parent / ".env")

# chat_agent is intentionally NOT imported here — it pulls in browser_use and
# the full agent stack (~1.5 s). Import lazily on first use instead.
if TYPE_CHECKING:
    from app.chat_agent import ChatBrowserAgent

from app.skills_api import router as skills_router, registry as skill_registry
from app.user_config import UserSettings, load_settings, save_settings
# core.llm and core.profiles are deferred — imported inside their endpoints
# (they pull in browser_use SDK and add ~0.8s to startup)

app = FastAPI()
app.include_router(skills_router)
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
    """Extends UserSettings with UI-only auth-type fields (not stored, used to clear the right credentials)."""
    google_auth_type:    str = "vertex"  # "apikey" | "vertex"
    anthropic_auth_type: str = "apikey"  # "apikey" | "vertex"


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
        from app.chat_agent import ChatBrowserAgent
        _agent = ChatBrowserAgent(registry=skill_registry)
    await _agent.start(body.task)
    return {"status": "started"}


@app.get("/stream")
async def stream():
    # Don't require is_active: fast ANSWER responses complete before the
    # SSE connection is established. The done event sits in the queue.
    if not _agent:
        raise HTTPException(400, "No active session. Start one first.")
    agent = _agent

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(agent.queue.get(), timeout=30)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event["type"] in ("done", "stopped", "error"):
                    break
            except asyncio.TimeoutError:
                yield "data: {\"type\": \"ping\"}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/pause")
async def pause():
    agent = _require_agent()
    agent.pause()
    return {"status": "paused"}


@app.post("/resume")
async def resume():
    agent = _require_agent()
    agent.resume()
    return {"status": "resumed"}


@app.post("/stop")
async def stop():
    agent = _require_agent()
    agent.stop()
    return {"status": "stopping"}


@app.post("/send")
async def send(body: SendRequest):
    agent = _require_agent()
    # Allow send while paused (queues) or running (injects). Not while idle/done.
    if not agent.is_running and not agent.is_paused:
        raise HTTPException(400, "Agent is not running. Start a new session.")
    agent.send(body.message)
    return {"status": "sent"}


@app.post("/reset")
async def reset():
    global _agent
    if _agent:
        _agent.reset()
    return {"status": "reset"}


@app.post("/close-browser")
async def close_browser_endpoint():
    agent = _require_agent()
    await agent.close_browser()
    return {"status": "closed"}


@app.post("/security-approve")
async def security_approve():
    agent = _require_agent()
    if not agent.has_pending_security:
        raise HTTPException(400, "No security warning pending.")
    agent.security_approve()
    return {"status": "approved"}


@app.post("/security-reject")
async def security_reject():
    agent = _require_agent()
    if not agent.has_pending_security:
        raise HTTPException(400, "No security warning pending.")
    agent.security_reject()
    return {"status": "rejected"}


# ── Models ────────────────────────────────────────────────────────────────────

@app.get("/models")
async def models():
    from core.llm import get_models
    return {"models": get_models()}


# ── Settings ──────────────────────────────────────────────────────────────────

@app.get("/settings")
async def get_settings():
    from core.llm import get_provider, get_models
    s = load_settings()
    models = get_models()
    model_label = next((m["label"] for m in models if m["value"] == s.model), s.model)
    return {
        **s.model_dump(),
        "google_auth_type":    "apikey" if s.gemini_api_key    else "vertex",
        "anthropic_auth_type": "apikey" if s.anthropic_api_key else "vertex",
        "model_provider": get_provider(s.model),
        "model_label":    model_label,
    }


@app.post("/settings")
async def post_settings(body: SettingsRequest):
    global _agent
    if _agent and _agent.is_running:
        raise HTTPException(400, "Cannot change settings while agent is running.")
    s = UserSettings(
        model                = body.model,
        orchestrator_model   = body.orchestrator_model,
        max_steps            = body.max_steps,
        flash_mode           = body.flash_mode,
        browser_profile      = body.browser_profile,
        headless             = body.headless,
        keep_browser_open    = body.keep_browser_open,
        allowed_domains      = body.allowed_domains,
        prohibited_domains   = body.prohibited_domains,
        judge_model          = body.judge_model,
        allowed_actions      = body.allowed_actions,
        denied_actions       = body.denied_actions,
        save_full_results    = body.save_full_results,
        gemini_api_key       = body.gemini_api_key    if body.google_auth_type    == "apikey" else "",
        google_cloud_project = body.google_cloud_project,
        llm_location         = body.llm_location,
        groq_api_key         = body.groq_api_key,
        openai_api_key       = body.openai_api_key,
        anthropic_api_key    = body.anthropic_api_key if body.anthropic_auth_type == "apikey" else "",
    )
    save_settings(s)
    _agent = None  # recreated on next task start with updated settings
    return {"status": "ok"}


# ── Profiles ──────────────────────────────────────────────────────────────────

@app.get("/profiles")
async def profiles():
    from core.profiles import detect_profiles
    return {"profiles": detect_profiles(), "active": load_settings().browser_profile}


# ── Open file ─────────────────────────────────────────────────────────────────

@app.post("/open-file")
async def open_file(body: OpenFileRequest):
    p = Path(body.path)
    if not p.exists():
        raise HTTPException(404, f"File not found: {body.path}")
    os.startfile(str(p))
    return {"status": "opened"}


# ── Google Auth ───────────────────────────────────────────────────────────────

_GOOGLE_CLIENT_CONFIG = {
    "installed": {
        "client_id": "764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com",
        "client_secret": "d-FL95Q19q7MQmFpd7hHD0Ty",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}
_GOOGLE_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


@app.post("/auth-google")
async def auth_google():
    import asyncio
    import json
    from google_auth_oauthlib.flow import InstalledAppFlow

    def _do_auth():
        flow = InstalledAppFlow.from_client_config(_GOOGLE_CLIENT_CONFIG, _GOOGLE_SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
        adc_dir = Path(os.environ.get("APPDATA", str(Path.home()))) / "gcloud"
        adc_dir.mkdir(parents=True, exist_ok=True)
        (adc_dir / "application_default_credentials.json").write_text(
            json.dumps({
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "refresh_token": creds.refresh_token,
                "type": "authorized_user",
            }, indent=2),
            encoding="utf-8",
        )

    loop = asyncio.get_event_loop()
    try:
        await asyncio.wait_for(loop.run_in_executor(None, _do_auth), timeout=300)
    except asyncio.TimeoutError:
        raise HTTPException(408, "Authentication timed out. Please try again.")

    global _agent
    from app.chat_agent import ChatBrowserAgent
    _agent = ChatBrowserAgent(registry=skill_registry)
    return {"status": "ok"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_agent() -> ChatBrowserAgent:
    if not _agent or not _agent.is_active:
        raise HTTPException(400, "No active session. Start one first.")
    assert _agent is not None
    return _agent
