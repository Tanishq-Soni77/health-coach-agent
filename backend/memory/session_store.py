"""
In-memory session store.
Keeps patient profile + conversation history per session_id.
On a real deployment, swap this dict for Redis or Supabase.
"""

from typing import Optional
import json
import time

# In-memory store: { session_id: SessionData }
_sessions: dict[str, dict] = {}


def create_session(session_id: str) -> dict:
    """Initialize a new session."""
    session = {
        "session_id": session_id,
        "created_at": time.time(),
        "day_number": 1,
        "profile": None,
        "onboarding_complete": False,
        "conversation": [],  # List of {role, content, timestamp}
        "daily_conversations": {},  # {day_number: [messages]}
    }
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> Optional[dict]:
    """Get existing session or None."""
    return _sessions.get(session_id)


def get_or_create_session(session_id: str) -> dict:
    """Get session if exists, else create."""
    return get_session(session_id) or create_session(session_id)


def update_profile(session_id: str, profile: dict) -> None:
    """Save extracted patient profile to session."""
    session = get_or_create_session(session_id)
    session["profile"] = profile
    session["onboarding_complete"] = True


def add_message(session_id: str, role: str, content: str) -> None:
    """Append a message to conversation history."""
    session = get_or_create_session(session_id)
    msg = {"role": role, "content": content, "timestamp": time.time()}
    session["conversation"].append(msg)

    day = session["day_number"]
    if day not in session["daily_conversations"]:
        session["daily_conversations"][day] = []
    session["daily_conversations"][day].append(msg)


def get_conversation_history(session_id: str, last_n: int = 10) -> str:
    """Get recent conversation as formatted string."""
    session = get_session(session_id)
    if not session:
        return ""
    messages = session["conversation"][-last_n:]
    lines = []
    for m in messages:
        role_label = "Patient" if m["role"] == "user" else "Coach"
        lines.append(f"{role_label}: {m['content']}")
    return "\n".join(lines)


def get_profile_json(session_id: str) -> str:
    """Get profile as formatted JSON string."""
    session = get_session(session_id)
    if not session or not session.get("profile"):
        return "{}"
    return json.dumps(session["profile"], indent=2)


def set_day(session_id: str, day: int) -> None:
    """Update current protocol day."""
    session = get_or_create_session(session_id)
    session["day_number"] = day


def get_day(session_id: str) -> int:
    """Get current protocol day."""
    session = get_session(session_id)
    return session["day_number"] if session else 1


def is_onboarded(session_id: str) -> bool:
    """Check if patient has completed onboarding."""
    session = get_session(session_id)
    return bool(session and session.get("onboarding_complete"))


def list_sessions() -> list[str]:
    """List all active session IDs."""
    return list(_sessions.keys())


def delete_session(session_id: str) -> None:
    """Remove a session."""
    _sessions.pop(session_id, None)
