"""
Health Coach Agent
Orchestrates three modes:
  1. onboard  - extract patient profile from free text
  2. checkin  - run adaptive daily check-in
  3. qa       - answer protocol questions with RAG
"""

import json
import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompts.prompts import (
    PROFILE_EXTRACTION_PROMPT,
    CHECKIN_PROMPT,
    QA_PROMPT,
    CONVERSATION_SUMMARY_PROMPT,
)
from rag.retriever import retrieve, get_day_protocol
from memory import session_store

import anthropic

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _call_claude(prompt: str, max_tokens: int = 800) -> str:
    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def _parse_json_safe(raw: str, fallback: dict) -> dict:
    """Robustly extract JSON from LLM response."""
    try:
        # Remove code fences
        clean = re.sub(r'```(?:json)?', '', raw).strip()
        # Find outermost { }
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start != -1 and end > start:
            clean = clean[start:end]
        return json.loads(clean)
    except Exception:
        return fallback


def onboard_patient(session_id: str, onboarding_text: str) -> dict:
    prompt = PROFILE_EXTRACTION_PROMPT.format(onboarding_text=onboarding_text)
    raw = _call_claude(prompt, max_tokens=600)

    fallback = {
        "name": None,
        "age": None,
        "wellness_goals": ["general wellness"],
        "sleep_hours": None,
        "sleep_quality": None,
        "activity_level": None,
        "diet_notes": None,
        "health_concerns": [],
        "other_notes": onboarding_text[:200]
    }
    profile = _parse_json_safe(raw, fallback)

    session_store.update_profile(session_id, profile)
    session_store.add_message(session_id, "user", onboarding_text)
    return profile


def run_checkin(session_id: str, user_message: str = "") -> str:
    if user_message:
        session_store.add_message(session_id, "user", user_message)

    day = session_store.get_day(session_id)
    profile_json = session_store.get_profile_json(session_id)
    conversation_history = session_store.get_conversation_history(session_id, last_n=8)
    protocol_context = get_day_protocol(day)

    prompt = CHECKIN_PROMPT.format(
        profile_json=profile_json,
        day_number=day,
        conversation_history=conversation_history,
        protocol_context=protocol_context
    )

    response = _call_claude(prompt, max_tokens=300)
    session_store.add_message(session_id, "assistant", response)
    return response


def answer_question(session_id: str, question: str) -> str:
    session_store.add_message(session_id, "user", question)

    day = session_store.get_day(session_id)
    profile_json = session_store.get_profile_json(session_id)
    protocol_context = retrieve(question, day_number=day, top_k=4)

    prompt = QA_PROMPT.format(
        profile_json=profile_json,
        protocol_context=protocol_context,
        question=question
    )

    response = _call_claude(prompt, max_tokens=250)
    session_store.add_message(session_id, "assistant", response)
    return response


def classify_message(message: str) -> str:
    question_words = ["can i", "should i", "what is", "how many", "is it ok",
                      "allowed", "what does", "when should", "why", "what about",
                      "how do", "what are", "?"]
    msg_lower = message.lower()
    for qw in question_words:
        if qw in msg_lower:
            return "qa"
    return "checkin"


def chat(session_id: str, message: str) -> dict:
    if not session_store.is_onboarded(session_id):
        profile = onboard_patient(session_id, message)
        day = session_store.get_day(session_id)
        protocol_context = get_day_protocol(day)

        name = profile.get("name") or "there"
        goals = profile.get("wellness_goals", ["your wellness"])
        goals_str = ", ".join(goals[:2]) if goals else "your wellness"

        welcome_prompt = f"""You are a warm health coach. A new patient just onboarded with these goals: {goals_str}.
Their name is {name}. It is their Day 1.

Protocol context for Day 1:
{protocol_context}

Write a warm, personal welcome message (under 120 words) that:
1. Greets them by name
2. Acknowledges their specific goals
3. Explains you will do daily check-ins
4. Asks one simple opening question (how did they sleep last night?)

Be warm but not over the top. Like a knowledgeable friend."""

        response = _call_claude(welcome_prompt, max_tokens=200)
        session_store.add_message(session_id, "assistant", response)

        return {
            "response": response,
            "mode": "onboard",
            "day": day,
            "profile_complete": True,
            "profile": profile
        }

    mode = classify_message(message)
    day = session_store.get_day(session_id)

    if mode == "qa":
        response = answer_question(session_id, message)
    else:
        response = run_checkin(session_id, message)

    return {
        "response": response,
        "mode": mode,
        "day": day,
        "profile_complete": True
    }
