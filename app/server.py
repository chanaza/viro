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

def _require_agent():
    if not _agent or not _agent.is_running:
        raise HTTPException(400, "No active session. Start one first.")
