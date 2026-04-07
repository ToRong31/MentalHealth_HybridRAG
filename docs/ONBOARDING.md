# MentalHealth_HybridRAG — Developer Onboarding Guide

> **New developer?** Start here. This guide covers setup, architecture, and common tasks.
> Last updated: 2026-04-07

---

## 1. Project Overview

**What it does:** AI-powered mental health chatbot (Vietnamese + English) with crisis detection, symptom assessment, treatment guidance, and coping support.

**Architecture:** 6-agent microservices system where each agent is a standalone FastAPI service.

```
Frontend (React)
    ↓ HTTP
Backend API (FastAPI, port 8000) — API Gateway
    ↓ HTTP
SupervisorAgent (port 8001) — Intent router
    ↓ HTTP (parallel dispatch)
5 Domain Agents (ports 8101-8105)
    ↓
MemoryService → Redis (L2) → PostgreSQL (L3)
             → Milvus (vector DB)
             → Neo4j (knowledge graph)
```

---

## 2. Quick Start

### Prerequisites

| Dependency | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11+ | Runtime |
| Docker + Docker Compose | Latest | Infrastructure |
| NVIDIA API Key | — | LLM (or Gemini) |

### Setup

```bash
# 1. Clone and enter project
cd MentalHealth_HybridRAG

# 2. Copy environment
cp backend/.env.example backend/.env  # or create manually
# Edit backend/.env with your keys:
#   NVIDIA_API_KEY=your_key_here
#   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mental_health_db
#   REDIS_URL=redis://localhost:6379/0

# 3. Start all services (Docker)
docker-compose up --build

# OR locally without Docker:
python run_agents.py              # Start all 6 agents
cd backend && uvicorn src.main:app --port 8000  # Start backend
```

### Verify

```bash
# Check backend health
curl http://localhost:8000/api/v1/health

# Check supervisor agent health
curl http://localhost:8001/health

# Run tests
cd backend
pytest tests/ -v
```

---

## 3. Project Structure

```
MentalHealth_HybridRAG/
├── ai/                              # Agent microservices (6 agents)
│   ├── agents/
│   │   ├── supervisor/               # Router agent (port 8001)
│   │   │   ├── supervisor_agent.py  # Core routing logic
│   │   │   ├── main.py             # FastAPI entry point
│   │   │   ├── router.py            # Crisis gate + routing helpers
│   │   │   ├── skills/             # IntentClassification, PreliminaryContext
│   │   │   └── tools/              # routing_tools.py
│   │   ├── diagnostic/              # DSM-5 assessment (port 8101)
│   │   │   ├── diagnostic_agent.py
│   │   │   ├── main.py
│   │   │   └── skills/            # SymptomExtraction, DiagnosticRetrieval, ClinicalReasoning
│   │   ├── theory/                 # Psychological knowledge (port 8102)
│   │   │   ├── theory_agent.py
│   │   │   └── skills/            # ConceptRetrieval, EducationalExplanation
│   │   ├── treatment/              # Treatment guidance (port 8103)
│   │   │   ├── treatment_agent.py
│   │   │   └── skills/            # TreatmentRetrieval, TreatmentPlanning
│   │   ├── support/               # Emotional support (port 8104)
│   │   │   ├── support_agent.py
│   │   │   └── skills/            # CopingRetrieval, EmotionalSupport, SkillBuilding
│   │   └── crisis/                # Crisis intervention (port 8105)
│   │       ├── crisis_agent.py
│   │       └── skills/            # CrisisDetection, ImmediateResponse
│   └── shared/                    # Shared by all agents
│       ├── agent_based/           # BaseAgent, GlobalState, constants
│       ├── communication/         # AgentHTTPClient, http_schemas, events
│       ├── rag/                   # Milvus, Neo4j, LLM clients, reranker
│       └── services/              # MemoryService
│
├── backend/                        # FastAPI backend (port 8000)
│   ├── src/
│   │   ├── main.py               # FastAPI app entry
│   │   ├── api/v1/endpoints/     # chat.py, auth.py, health.py
│   │   ├── core/                 # config.py, deps.py, security.py
│   │   └── db/                   # SQLAlchemy models
│   └── tests/                     # Unit + integration tests
│       ├── unit/
│       └── integration/
│
├── docs/                           # Architecture docs
│   ├── ARCHITECTURE.md           # Old LangGraph architecture
│   ├── AGENTS.md                 # Agent specifications (NEW)
│   ├── ONBOARDING.md            # ← You are here
│   └── REFACTOR-PLAN-PART*.md   # 6-part refactor plan
│
├── docker-compose.yml              # Full stack (agents + infra + backend)
├── run_agents.py                   # Start all agents locally (no Docker)
└── REFACTOR_CHECKLIST.md          # Progress tracker
```

---

## 4. Key Concepts

### Agent = 1 Goal + N Skills + N Tools

Each agent is self-contained — it owns a complete user goal from A to Z.

```
SupervisorAgent  → Routes intent (no domain logic)
DiagnosticAgent  → Extracts slots + DSM-5 reasoning → has_disorder?
TheoryAgent     → Retrieves + explains psychological concepts
TreatmentAgent  → Retrieves + plans treatment options
SupportAgent    → Coping strategies + emotional support
CrisisAgent     → Crisis detection + intervention
```

### Skills vs Tools

**Skills** are executors with a system prompt + logic inside an agent. They are NOT separate agents.
**Tools** are functions agents call (e.g., Milvus search, Redis read).

```
Agent
├── Skill: SymptomExtraction
│   ├── LLM with system prompt
│   └── Tools: extract_emotion(), extract_trigger()...
└── Tool: save_to_buffer()    ← Shared via MemoryService
```

### MemoryService (NOT an Agent)

MemoryService is a plain Python service injected into agents. It provides:
- Buffer: last 3 Q&A pairs
- Slots: accumulated structured patient info
- Summary: older turns
- Crisis state: risk level tracking

### HTTP Communication

Agents don't call each other directly. They communicate via HTTP:

```
SupervisorAgent                    Domain Agent
    │                                   ▲
    │  POST /agent/{name}               │
    │  AgentRequest                     │ AgentResponse
    └───────────────────────────────────┘
```

`AgentHTTPClient` handles retry, circuit breaker, and timeout.

---

## 5. Common Development Tasks

### Adding a New Skill to an Agent

1. Create the skill class in `ai/agents/{agent}/skills/my_skill.py`:

```python
class MySkill:
    def __init__(self, llm=None):
        self.llm = llm

    async def execute(self, **kwargs) -> dict:
        # Your skill logic here
        return {"result": "value"}
```

2. Register it in the agent's `__init__`:

```python
self._skills["MySkill"] = MySkill(llm=llm)
```

3. Call it in the agent's `run()` method.

### Adding a New Agent

1. Create `ai/agents/new_agent/` directory
2. Write `new_agent.py` (extends `BaseAgent`)
3. Create `skills/` with skill classes
4. Create `main.py` (FastAPI microservice)
5. Add to `ai/shared/agent_manager.py` (if using in-process)
6. Add URL to `AgentHTTPClient.DEFAULT_AGENT_URLS` in `http_client.py`
7. Add to `docker-compose.yml`
8. Add to `run_agents.py`
9. Write tests

### Debugging a Failing Agent

```bash
# Check agent logs
docker logs agent_supervisor     # Docker
# or
python -m uvicorn ai.agents.supervisor.main:app --port 8001 --log-level debug

# Check if agent is healthy
curl http://localhost:8001/health

# Test routing manually
curl -X POST http://localhost:8001/engine/route \
  -H "Content-Type: application/json" \
  -d '{"message": "Tôi buồn", "conversation_id": "test", "user_id": "u1", "language": "vi"}'
```

### Running Tests

```bash
# All tests
pytest backend/tests/ -v

# Specific test file
pytest backend/tests/unit/services/test_memory_service.py -v

# With coverage
pytest backend/tests/ --cov=ai --cov-report=html
```

---

## 6. Infrastructure

### Docker Services

| Service | Port | Description |
|---------|------|-------------|
| `postgres` | 5432 | PostgreSQL 15 — conversation memory |
| `redis` | 6379 | Redis 7 — L2 cache |
| `milvus-standalone` | 19530 | Milvus 2.4 — vector DB |
| `neo4j` | 7687 | Neo4j 5 — knowledge graph |
| `agent-supervisor` | 8001 | Supervisor microservice |
| `agent-diagnostic` | 8101 | Diagnostic microservice |
| `agent-theory` | 8102 | Theory microservice |
| `agent-treatment` | 8103 | Treatment microservice |
| `agent-support` | 8104 | Support microservice |
| `agent-crisis` | 8105 | Crisis microservice |
| `backend` | 8000 | FastAPI backend |

### Environment Variables

**Required for agents:**
```
REDIS_URL=redis://redis:6379/0
NEO4J_URI=bolt://neo4j:7687
NEO4J_PASSWORD=your_password
MILVUS_HOST=milvus-standalone
MILVUS_PORT=19530
NVIDIA_API_KEY=your_key
OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1
OPENAI_MODEL=openai/gpt-oss-120b
```

**Required for backend:**
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/...
SUPERVISOR_AGENT_URL=http://agent-supervisor:8001
SECRET_KEY=your_jwt_secret
```

---

## 7. Troubleshooting

### "Cannot connect to SupervisorAgent"

```bash
# Check if supervisor is running
curl http://localhost:8001/health

# Check Docker logs
docker logs agent_supervisor

# Restart
docker-compose restart agent-supervisor
```

### "Redis connection refused"

```bash
# Start Redis
docker-compose up redis -d

# Or locally
redis-server
```

### "No LLM response"

Check that `NVIDIA_API_KEY` or `GEMINI_API_KEY` is set in `.env`.

---

## 8. Key Files Reference

| File | Purpose |
|------|---------|
| `ai/shared/agent_based/base_agent.py` | Abstract base for all agents |
| `ai/shared/agent_based/state.py` | GlobalState + AgentState |
| `ai/shared/communication/http_client.py` | HTTP client for agent-to-agent calls |
| `ai/shared/communication/http_schemas.py` | AgentRequest/AgentResponse schemas |
| `ai/shared/services/memory_service.py` | L1+L2+L3 memory service |
| `ai/agents/supervisor/supervisor_agent.py` | Pure router — no ReAct loop |
| `ai/agents/supervisor/router.py` | `check_crisis_gate()`, keyword matching |
| `ai/shared/agent_manager.py` | Singleton agent registry |
| `docs/AGENTS.md` | Full agent specifications |
| `REFACTOR_CHECKLIST.md` | Implementation progress tracker |
