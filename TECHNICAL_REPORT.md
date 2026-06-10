# Technical Report — Vitali: Health Coach AI Agent
**Submission for Interactly.ai AI Agents Internship Assignment**

---

## Problem Statement

The assignment required building an MVP health coach AI agent that could:
1. Parse unstructured patient onboarding data into structured state
2. Run adaptive daily check-ins based on protocol day
3. Answer protocol questions with minimal hallucination
4. Maintain session memory

The core challenge is designing an agent that feels personal and context-aware, not robotic — while staying grounded in a reference document and avoiding fabricating health advice.

---

## Architecture Overview

The system has three layers:

**Routing Layer** — A lightweight classifier in `health_coach.py` determines which agent mode to use for each message. It uses heuristic keyword matching (questions vs. conversational statements) to avoid unnecessary LLM calls.

**Agent Layer** — Three specialized prompt templates handle distinct tasks:
- Profile Extraction: structured JSON output from free text
- Check-in: adaptive questions using day number + patient profile + protocol context
- Q&A: RAG-bounded answers with explicit instructions to refuse out-of-scope questions

**Memory Layer** — Session state (patient profile + conversation history) is stored in-process. Every prompt injects the last 8 messages as context and the full structured profile, so the LLM always has a complete picture.

---

## Technology Stack Decisions

**LLM: Claude Sonnet (claude-sonnet-4-20250514)**
Claude was chosen over GPT-4o for three reasons: superior instruction-following for structured JSON extraction, better at refusing out-of-scope questions in RAG mode, and native support via the Anthropic SDK. The profile extraction prompt returns clean JSON with ~99% reliability due to Claude's strong format adherence.

**Backend: FastAPI**
FastAPI gives async-ready endpoints, automatic OpenAPI docs at `/docs`, and Pydantic validation with minimal boilerplate. The project is small enough that Django or Flask would be over-engineered; FastAPI is the right size.

**RAG: Custom TF-IDF Retriever**
I deliberately avoided ChromaDB, Pinecone, or any vector database. Reasons:
1. The protocol document is ~1500 words — a single file. Vector DBs solve a scale problem that doesn't exist here.
2. A simple term-frequency scorer with section-aware chunking is interpretable, debuggable, and has no external dependencies.
3. Deploy complexity is reduced to zero.

The retriever chunks the protocol by paragraph, scores each chunk against a query + day-context terms, and returns the top 4 chunks as context for the LLM.

**Session Memory: In-Process Dict**
Session state lives in a Python dictionary keyed by session ID. This is appropriate for MVP v1 with single-server deployment. The `session_store.py` module abstracts all storage access through clean functions, making it straightforward to swap the backing store to Redis, Supabase, or any other persistent store with a single file change.

**Frontend: Vanilla HTML + JS**
No React, no Next.js, no build pipeline. The entire UI is one HTML file served directly by FastAPI. This was the right call because:
- Zero deployment complexity
- Readable by anyone reviewing the codebase
- Chat UIs are inherently simple — a textarea, a message list, a send button

---

## Agentic Design

The agent operates in three modes that correspond to real stages of a coaching relationship:

**Onboarding** extracts structure from chaos. The patient writes naturally; the agent parses it into a JSON profile that every subsequent interaction is built on. If parsing fails, the agent falls back gracefully to a minimal profile rather than breaking.

**Check-in** is day-aware. The prompt includes the day number, and a day context guide in the prompt maps day ranges to appropriate question themes. Day 1 is introductory; Day 5 follows up on habits; Day 15 focuses on consistency. The protocol document chunk for that day is also injected, so the agent can reference specific protocol recommendations naturally.

**Q&A** is explicitly grounded. The Q&A prompt contains hard rules: "Answer ONLY from the protocol context above." If the answer isn't in the retrieved context, the agent is instructed to say so and recommend a doctor. This is the core anti-hallucination mechanism.

---

## Minimizing Hallucinations

Three-layer approach:
1. **Prompt-level instruction**: explicit "answer only from context" + fallback phrase
2. **Context injection**: RAG retrieves 4 relevant chunks, providing specific text to answer from
3. **Mode separation**: Q&A and check-in are separate prompts — a check-in response can never accidentally answer a protocol question without context

---

## Memory Design

The memory system maintains:
- **Patient profile** (structured JSON, extracted at onboarding)
- **Full conversation history** (timestamped, role-labeled)
- **Per-day conversation** (useful for summaries and weekly reviews)
- **Current protocol day** (drives check-in adaptation)

Every LLM call receives the profile JSON + last 8 messages as context. This ensures the agent never forgets the patient's goals mid-conversation.

---

## Challenges

**Structured output reliability**: Early versions of the profile extraction prompt sometimes returned JSON with extra text or missing fields. Solved with a try/except that falls back to a minimal profile, and by adding "Return ONLY the JSON object" as a hard instruction.

**Question classification**: Distinguishing "I feel tired today" (check-in) from "Can I exercise today?" (Q&A) without an LLM call. The keyword heuristic handles ~90% of cases correctly. Edge cases (e.g., "I wonder if I should eat before exercising?") route to check-in, which is acceptable — the check-in agent will handle it conversationally.

**RAG with no vector DB**: Term-frequency matching on short paragraphs works well but degrades on semantically distant but related queries. Addressed by injecting day-relevant terms into the query to boost recall for day-specific content.

---

## Future Improvements

1. **Persistent storage**: Replace in-memory sessions with Supabase or Redis for multi-session, multi-user deployments
2. **Vector embeddings**: Add sentence-transformers for semantic RAG once the protocol document grows
3. **Progress tracking**: Store daily logs (energy, sleep, water) and surface trend summaries in check-ins
4. **Multi-protocol support**: Allow PDF upload at runtime, chunk and index on the fly
5. **Push notifications**: Daily check-in reminders via email or SMS
6. **Voice interface**: The warm, concise tone of the agent is well-suited for TTS + STT

---

## What I Would Do Differently

If this were production-ready v2: I would introduce LangGraph for more explicit state machines (the three modes become graph nodes with transitions), add persistent storage from day one, and build a simple analytics layer to track patient compliance across days. The current architecture is the right simplicity for an MVP — but the abstractions (session_store, retriever, prompts) are designed to extend cleanly.
