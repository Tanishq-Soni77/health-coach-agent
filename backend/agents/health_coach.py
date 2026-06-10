import json, re, os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prompts.prompts import PROFILE_EXTRACTION_PROMPT, CHECKIN_PROMPT, QA_PROMPT
from rag.retriever import retrieve, get_day_protocol
from memory import session_store
import google.generativeai as genai

_model = None

def _get_model():
    global _model
    if _model is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel("gemini-1.5-flash")
    return _model

def _call_llm(prompt, max_tokens=800):
    model = _get_model()
    response = model.generate_content(prompt)
    return response.text.strip()

def _parse_json_safe(raw, fallback):
    try:
        clean = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start != -1 and end > start:
            clean = clean[start:end]
        result = json.loads(clean)
        if isinstance(result, dict):
            return result
        return fallback
    except Exception:
        return fallback

def onboard_patient(session_id, onboarding_text):
    try:
        prompt = PROFILE_EXTRACTION_PROMPT.format(onboarding_text=onboarding_text)
        raw = _call_llm(prompt)
        fallback = {"name": None, "age": None, "wellness_goals": ["general wellness"], "sleep_hours": None, "sleep_quality": None, "activity_level": None, "diet_notes": None, "health_concerns": [], "other_notes": onboarding_text[:200]}
        profile = _parse_json_safe(raw, fallback)
        if not isinstance(profile, dict):
            profile = fallback
        session_store.update_profile(session_id, profile)
        session_store.add_message(session_id, "user", onboarding_text)
        return profile
    except Exception:
        raise Exception(f"onboard_patient failed: {traceback.format_exc()}")

def run_checkin(session_id, user_message=""):
    if user_message:
        session_store.add_message(session_id, "user", user_message)
    day = session_store.get_day(session_id)
    profile_json = session_store.get_profile_json(session_id)
    conversation_history = session_store.get_conversation_history(session_id, last_n=8)
    protocol_context = get_day_protocol(day)
    prompt = CHECKIN_PROMPT.format(profile_json=profile_json, day_number=day, conversation_history=conversation_history, protocol_context=protocol_context)
    response = _call_llm(prompt)
    session_store.add_message(session_id, "assistant", response)
    return response

def answer_question(session_id, question):
    session_store.add_message(session_id, "user", question)
    day = session_store.get_day(session_id)
    profile_json = session_store.get_profile_json(session_id)
    protocol_context = retrieve(question, day_number=day, top_k=4)
    prompt = QA_PROMPT.format(profile_json=profile_json, protocol_context=protocol_context, question=question)
    response = _call_llm(prompt)
    session_store.add_message(session_id, "assistant", response)
    return response

def classify_message(message):
    question_words = ["can i", "should i", "what is", "how many", "is it ok", "allowed", "what does", "when should", "why", "what about", "how do", "what are", "?"]
    msg_lower = message.lower()
    for qw in question_words:
        if qw in msg_lower:
            return "qa"
    return "checkin"

def chat(session_id, message):
    if not session_store.is_onboarded(session_id):
        profile = onboard_patient(session_id, message)
        day = session_store.get_day(session_id)
        protocol_context = get_day_protocol(day)
        name = profile.get("name") or "there"
        goals = profile.get("wellness_goals", ["your wellness"])
        goals_str = ", ".join(goals[:2]) if goals else "your wellness"
        welcome_prompt = f"You are a warm health coach. Patient: {name}. Goals: {goals_str}. Day 1.\n\nProtocol:\n{protocol_context}\n\nWrite a warm welcome under 120 words. Greet by name, acknowledge goals, mention daily check-ins, ask how they slept."
        response = _call_llm(welcome_prompt)
        session_store.add_message(session_id, "assistant", response)
        return {"response": response, "mode": "onboard", "day": day, "profile_complete": True, "profile": profile}
    mode = classify_message(message)
    day = session_store.get_day(session_id)
    response = answer_question(session_id, message) if mode == "qa" else run_checkin(session_id, message)
    return {"response": response, "mode": mode, "day": day, "profile_complete": True}
