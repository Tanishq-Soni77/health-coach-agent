"""
FastAPI backend for Health Coach Agent
Routes:
  POST /chat          — main chat endpoint
  POST /session/new   — create session
  GET  /session/{id}  — get session state
  POST /session/{id}/day — update day number
  GET  /health        — health check
"""

import uuid
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from agents.health_coach import chat, run_checkin
from memory import session_store

app = FastAPI(
    title="Health Coach Agent API",
    description="AI-powered health coaching with adaptive check-ins and protocol Q&A",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
def serve_frontend():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "Health Coach API is running. Frontend not found."}


# ── Request/Response models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    response: str
    mode: str
    day: int
    profile_complete: bool
    session_id: str


class NewSessionResponse(BaseModel):
    session_id: str
    message: str


class DayUpdateRequest(BaseModel):
    day: int


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "health-coach-agent"}


@app.post("/session/new", response_model=NewSessionResponse)
def create_session():
    """Create a new coaching session."""
    session_id = str(uuid.uuid4())[:8]
    session_store.create_session(session_id)
    return {
        "session_id": session_id,
        "message": "Session created. Send your first message to start onboarding."
    }


@app.get("/session/{session_id}")
def get_session(session_id: str):
    """Get current session state."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session_id,
        "day": session["day_number"],
        "onboarding_complete": session["onboarding_complete"],
        "profile": session.get("profile"),
        "message_count": len(session["conversation"])
    }


@app.post("/session/{session_id}/day")
def update_day(session_id: str, body: DayUpdateRequest):
    """Update the protocol day for a session."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session_store.set_day(session_id, body.day)
    return {"session_id": session_id, "day": body.day}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(body: ChatRequest):
    """
    Main chat endpoint. Handles:
    - Onboarding (first message)
    - Daily check-ins
    - Protocol Q&A
    """
    session = session_store.get_or_create_session(body.session_id)

    try:
        result = chat(body.session_id, body.message)
        return ChatResponse(
            response=result["response"],
            mode=result["mode"],
            day=result["day"],
            profile_complete=result["profile_complete"],
            session_id=body.session_id
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.post("/checkin/start/{session_id}")
def start_checkin(session_id: str):
    """Start a daily check-in (no user message needed — agent opens)."""
    if not session_store.is_onboarded(session_id):
        raise HTTPException(status_code=400, detail="Complete onboarding first")
    response = run_checkin(session_id, user_message="")
    day = session_store.get_day(session_id)
    return {"response": response, "day": day, "session_id": session_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
