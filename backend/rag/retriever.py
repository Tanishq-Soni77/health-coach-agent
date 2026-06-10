"""
RAG (Retrieval-Augmented Generation) module.
Loads the wellness protocol and retrieves relevant chunks for any query.
Uses simple keyword + TF-IDF-style matching (no external vector DB needed).
"""

import re
import math
from collections import Counter
from pathlib import Path

PROTOCOL_PATH = Path(__file__).parent.parent.parent / "data" / "wellness_protocol.txt"


def load_protocol() -> str:
    """Load the full protocol text."""
    if PROTOCOL_PATH.exists():
        return PROTOCOL_PATH.read_text()
    return ""


def chunk_text(text: str, chunk_size: int = 300) -> list[dict]:
    """Split protocol into overlapping chunks with metadata."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    for i, para in enumerate(paragraphs):
        chunks.append({
            "id": i,
            "text": para,
            "section": _detect_section(para)
        })
    return chunks


def _detect_section(text: str) -> str:
    """Detect which section a chunk belongs to."""
    text_lower = text.lower()
    if "week 1" in text_lower or "day 1" in text_lower:
        return "week1"
    elif "week 2" in text_lower or "day 8" in text_lower:
        return "week2"
    elif "week 3" in text_lower or "day 15" in text_lower:
        return "week3"
    elif "week 4" in text_lower or "day 22" in text_lower:
        return "week4"
    elif "don't" in text_lower or "do:" in text_lower or "dos and don" in text_lower:
        return "rules"
    elif "supplement" in text_lower:
        return "supplements"
    elif "track" in text_lower or "log" in text_lower:
        return "tracking"
    return "general"


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer."""
    return re.findall(r'\b[a-z]+\b', text.lower())


def _score_chunk(chunk_tokens: list[str], query_tokens: list[str]) -> float:
    """Score a chunk against a query using term frequency."""
    if not chunk_tokens:
        return 0.0
    chunk_freq = Counter(chunk_tokens)
    score = sum(chunk_freq.get(t, 0) for t in query_tokens)
    return score / (math.log(len(chunk_tokens) + 1) + 1)


def retrieve(query: str, day_number: int = 1, top_k: int = 4) -> str:
    """
    Retrieve the most relevant protocol chunks for a query.
    Also injects the day-specific context automatically.
    """
    protocol = load_protocol()
    if not protocol:
        return "Protocol not loaded."

    chunks = chunk_text(protocol)
    query_tokens = _tokenize(query)

    # Add day-related terms to query
    day_terms = _get_day_terms(day_number)
    query_tokens += _tokenize(day_terms)

    # Score all chunks
    scored = []
    for chunk in chunks:
        chunk_tokens = _tokenize(chunk["text"])
        score = _score_chunk(chunk_tokens, query_tokens)
        scored.append((score, chunk))

    # Sort by score, take top_k
    scored.sort(key=lambda x: x[0], reverse=True)
    top_chunks = [c["text"] for score, c in scored[:top_k] if score > 0]

    if not top_chunks:
        # Fallback: return general dos/don'ts
        top_chunks = [c["text"] for c in chunks if c["section"] in ("rules", "general")][:3]

    return "\n\n---\n\n".join(top_chunks)


def get_day_protocol(day_number: int) -> str:
    """Get protocol content specifically for a given day."""
    protocol = load_protocol()
    chunks = chunk_text(protocol)

    day_query = f"day {day_number} week {_day_to_week(day_number)}"
    return retrieve(day_query, day_number=day_number, top_k=3)


def _day_to_week(day: int) -> int:
    if day <= 7: return 1
    if day <= 14: return 2
    if day <= 21: return 3
    return 4


def _get_day_terms(day: int) -> str:
    """Return search terms relevant for a given day."""
    if day == 1:
        return "orientation baseline water intake energy"
    elif day == 2:
        return "sleep hygiene caffeine screen bedtime"
    elif day == 3:
        return "movement walk exercise morning"
    elif day == 4:
        return "nutrition breakfast vegetables meals"
    elif day == 5:
        return "hydration water coffee energy tracking"
    elif day in range(6, 8):
        return "stress breathing gratitude meditation"
    elif day in range(8, 15):
        return "movement strength training rest recovery protein"
    elif day in range(15, 22):
        return "habit consistency sleep log stretching yoga"
    else:
        return "integrate habits meals planning goals"
