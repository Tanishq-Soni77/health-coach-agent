# Vitali — Health Coach AI Agent

> An AI-powered health coaching agent with adaptive daily check-ins, personalized profiling, and protocol-grounded Q&A.

**Live Demo:** `https://health-coach-agent.onrender.com`  
**GitHub:** `https://github.com/YOUR_USERNAME/health-coach-agent`

---

## What it does

Vitali is a conversational health coach that:

- **Onboards patients** by parsing free-text input into a structured profile (age, goals, sleep habits, concerns)
- **Runs adaptive daily check-ins** that change based on what day of the protocol the user is on — Day 1 feels like an introduction, Day 5 follows up on habits
- **Answers protocol questions** using RAG (retrieval-augmented generation) grounded only in the provided wellness document — no hallucination
- **Maintains session memory** so every response is informed by what was said earlier in the conversation

---

## Architecture

```
User (Browser)
     │
     ▼
FastAPI Backend  ──►  Claude (claude-sonnet-4-20250514)
     │
     ├──► Profile Extraction Agent
     ├──► Daily Check-in Agent  ──►  RAG Retriever ──► Protocol Document
     ├──► Q&A Agent             ──►  RAG Retriever
     └──► Session Memory (in-process dict → Redis in prod)
```

**Three agent modes, one routing layer:**
| Mode | Trigger | Uses RAG |
|------|---------|----------|
| `onboard` | First message in session | No |
| `checkin` | Conversational messages | Yes (day-specific) |
| `qa` | Questions (contains `?`, `can I`, `should I`, etc.) | Yes (query-matched) |

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| LLM | Claude Sonnet | Best reasoning, structured output reliability |
| Backend | FastAPI | Fast, async, auto docs at `/docs` |
| RAG | Custom keyword retriever | No external DB needed, fast, deployable |
| Memory | In-process dict | Session-scoped, zero infra |
| Frontend | Vanilla HTML/JS | No build step, instant deployment |
| Deployment | Render | Free tier, GitHub deploy, one-click |

---

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/health-coach-agent
cd health-coach-agent

# Install dependencies
pip install -r requirements.txt

# Set your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Run
uvicorn backend.main:app --reload --port 8000
```

Open `http://localhost:8000` in your browser.

---

## Usage

1. **Onboard** — Type your name, age, goals, and sleep habits in the first message
2. **Check-in** — The agent will ask you questions based on your protocol day
3. **Ask questions** — Ask anything like "Can I have coffee after 2 PM?" or "What supplements does the protocol recommend?"
4. **Change day** — Use the day simulator buttons to see how check-ins adapt across the 30-day protocol

### Example onboarding message:
```
Hi, I'm Priya, 27 years old. I want to sleep better, lose some weight, 
and feel less stressed. I currently sleep around 5-6 hours a night 
and don't exercise much. I work a desk job.
```

---

## API Documentation

Full interactive docs at `/docs` (Swagger UI).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Frontend |
| `/session/new` | POST | Create a new session |
| `/session/{id}` | GET | Get session state + profile |
| `/session/{id}/day` | POST | Update protocol day |
| `/chat` | POST | Main chat endpoint |
| `/checkin/start/{id}` | POST | Start check-in (agent opens) |
| `/health` | GET | Health check |

**Chat request:**
```json
POST /chat
{
  "session_id": "abc123",
  "message": "I slept 7 hours and feel pretty good today"
}
```

**Chat response:**
```json
{
  "response": "That's great to hear! 7 hours is solid...",
  "mode": "checkin",
  "day": 3,
  "profile_complete": true,
  "session_id": "abc123"
}
```

---

## Project Structure

```
health-coach-agent/
├── backend/
│   ├── main.py              # FastAPI app, routes
│   ├── agents/
│   │   └── health_coach.py  # Core agent logic, routing
│   ├── prompts/
│   │   └── prompts.py       # All LLM prompts
│   ├── rag/
│   │   └── retriever.py     # Protocol retrieval
│   └── memory/
│       └── session_store.py # Session management
├── frontend/
│   └── index.html           # Complete UI
├── data/
│   └── wellness_protocol.txt # Protocol document
├── requirements.txt
├── render.yaml
└── README.md
```

---

## Deployment (Render)

1. Push to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your repo
4. Set environment variable: `ANTHROPIC_API_KEY`
5. Build command: `pip install -r requirements.txt`
6. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
7. Deploy

---

## Design Decisions

**Why no vector database?** For a 30-day protocol document (~1500 words), a simple TF-IDF keyword retriever is more reliable, faster, and requires zero infra. Vector DBs add value at scale — not for a single document MVP.

**Why in-memory sessions?** This is MVP v1. The session_store module has a single swap point (the dict) — replace it with Redis or Supabase for multi-server production use.

**Why vanilla HTML?** No build step, instant Render deploy, easily readable codebase. React would be overkill for a single-page chat UI.

**Why classify messages heuristically?** A simple keyword check (does the message contain `?` or question phrases?) avoids an extra LLM call, saving cost and latency. Works well for this domain.
