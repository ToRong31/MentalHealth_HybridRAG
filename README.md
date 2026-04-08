# 🧠 Mental Health Hybrid RAG System

A sophisticated mental health chatbot powered by Hybrid RAG (Retrieval-Augmented Generation) combining Knowledge Graphs, Vector Search, and Advanced LLMs.

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Development](#development)
- [API Documentation](#api-documentation)
- [Disclaimer](#disclaimer)

## 🌟 Overview

This Mental Health Chatbot system leverages a **Hybrid RAG architecture** that combines:

- **Knowledge Graph (Neo4j)**: Structured medical knowledge with relationships
- **Vector Database (Milvus)**: Semantic search over embeddings
- **Multi-Agent System**: Orchestrated multi-step reasoning with 7 specialized agents
- **Advanced LLMs**: Google Gemini for natural conversations
- **Cohere Reranker**: Improved retrieval accuracy

The system provides empathetic, evidence-based mental health support through intelligent information retrieval and generation.

### 🤖 Seven Specialized Agents

The system employs **7 distinct specialized agents**:

| Agent | Port | Description |
|-------|------|-------------|
| **Supervisor** | 8001 | Main orchestrator, routes queries to specialized agents |
| **Memory** | 8002 | Conversation history and context management |
| **Diagnostic** | 8101 | Symptom assessment and diagnostic support |
| **Theory** | 8102 | Educational information and mental health concepts |
| **Treatment** | 8103 | Evidence-based treatment guidance and therapy options |
| **Support** | 8104 | Emotional support and coping strategies |
| **Crisis** | 8105 | Crisis detection and immediate intervention |

## ✨ Key Features

### 🔍 Hybrid RAG Architecture
- Multi-stage retrieval: Dense retrieval (Milvus) → Graph traversal (Neo4j) → Reranking (Cohere)
- Context-aware reranking for improved accuracy
- E5 Large v2 embeddings (1024-dim)

### 🧠 Advanced AI Capabilities
- **Multi-Agent System**: Supervisor + 6 specialized agents working in concert
- **LangGraph Workflow**: State management and multi-turn conversations
- **Gemini LLM**: Natural, empathetic conversation generation
- **PostgreSQL Checkpointer**: Persistent conversation state across sessions
- **Crisis Detection**: Safety monitoring with immediate intervention routing

### 💬 User Experience
- Real-time streaming responses
- Conversation history management
- Authentication & user management
- Clean, responsive React UI

### 🔒 Security & Reliability
- JWT-based authentication
- Environment-based configuration
- Docker containerization
- CORS protection

## 🏗️ Architecture

```
┌─────────────┐
│   User UI   │
│  (React)    │
└──────┬──────┘
       │
       ▼
┌────────────────────────────────────────────────────┐
│              FastAPI Backend                       │
│         (port 8000, /api/v1/*)                    │
└──────┬────────────────────────────────────────────┘
       │ HTTP
       ▼
┌────────────────────────────────────────────────────┐
│           Supervisor Agent (port 8001)            │
│  ┌──────────────────────────────────────────────┐  │
│  │         Query Classifier & Router            │  │
│  │  ├─ Safety Check (Crisis Detection)          │  │
│  │  ├─ Query Type Classification                │  │
│  │  └─ Agent Router                             │  │
│  └──────────────────────────────────────────────┘  │
│                    ↓                                │
│  ┌─────────────────────────────────────────────┐   │
│  │    6 Specialized Agents                      │   │
│  │  🔍 Diagnostic  🎓 Theory   💊 Treatment    │   │
│  │  😌 Support     💾 Memory   🚨 Crisis      │   │
│  └─────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────┘
       │         │         │         │
       ▼         ▼         ▼         ▼
   ┌──────┐  ┌──────┐  ┌────────┐  ┌──────────┐
   │Milvus│  │Neo4j │  │PostgreSQL│  │  Redis   │
   │Vector│  │Graph │  │ State DB  │  │  Cache   │
   └──────┘  └──────┘  └─────────┘  └──────────┘
```

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **AI/ML**: LangChain, LangGraph, Google Gemini, E5 Embeddings, Cohere Reranker
- **Databases**: PostgreSQL, Neo4j, Milvus, Redis

### AI Agents
- **Framework**: LangGraph with custom multi-agent orchestration
- **LLM**: Google Gemini (primary), Cohere (reranking)
- **State**: PostgreSQL checkpointer + Redis

### Frontend
- **Framework**: React 19 + TypeScript
- **Build Tool**: Vite
- **UI**: Radix UI + Tailwind CSS

### Infrastructure
- **Containerization**: Docker & Docker Compose
- **Web Server**: Nginx (frontend)
- **Storage**: MinIO (object storage for Milvus)

## 📦 Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 8GB+ RAM recommended

### API Keys Required
- Google Gemini API key
- Cohere API key

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/ToRong31/MentalHealth_HybridRAG.git
cd MentalHealth_HybridRAG
```

### 2. Environment Configuration

Create `.env` file in the project root:

```bash
# Database
DB_USER=postgres
DB_PASSWORD=postgres123
DB_NAME=mental_health_db

# Neo4j
NEO4J_PASSWORD=kguser2005

# LLM Providers
GEMINI_API_KEY=your_gemini_api_key
COHERE_API_KEY=your_cohere_api_key

# Security
SECRET_KEY=your-secret-key-here
```

### 3. Start All Services

Start infrastructure + agents, then backend, then frontend:

```bash
# 1. Start infrastructure (PostgreSQL, Redis, Neo4j, Milvus, etcd, MinIO)
docker-compose -f ai/docker-compose.yml up -d

# 2. Start AI agents (Supervisor, Memory, Diagnostic, Theory, Treatment, Support, Crisis)
# (already included in ai/docker-compose.yml above)

# 3. Start backend
docker-compose -f backend/docker-compose.yml up -d

# 4. Start frontend
docker-compose -f frontend/docker-compose.yml up -d
```

Or use the root-level compose files together:

```bash
docker-compose -f ai/docker-compose.yml -f backend/docker-compose.yml -f frontend/docker-compose.yml up -d
```

### 4. Access the Application

| Service | URL |
|---------|-----|
| Frontend | http://localhost:8080 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Neo4j Browser | http://localhost:7474 |
| MinIO Console | http://localhost:9001 |
| pgAdmin | http://localhost:5050 |

## 📁 Project Structure

```
MentalHealth_HybridRAG/
├── ai/                          # AI agent microservices
│   ├── agents/
│   │   ├── supervisor/          # Main orchestrator agent
│   │   ├── memory/              # Conversation memory agent
│   │   ├── diagnostic/          # Diagnostic support agent
│   │   ├── theory/              # Theory/education agent
│   │   ├── treatment/           # Treatment guidance agent
│   │   ├── support/             # Emotional support agent
│   │   └── crisis/              # Crisis detection agent
│   ├── shared/                  # Shared utilities (prompts, circuit breaker, etc.)
│   ├── Dockerfile              # Builds all agent images
│   └── docker-compose.yml      # Infrastructure + agent services
│
├── backend/                     # FastAPI backend
│   ├── src/
│   │   ├── api/v1/endpoints/   # API routes (auth, chat, health)
│   │   ├── core/               # Config, security, deps
│   │   └── db/                 # DB models (SQLAlchemy)
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
│
├── frontend/                    # React TypeScript frontend
│   ├── src/                    # React components, pages, services
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── docs/                        # Documentation
├── CLAUDE.md                    # Code intelligence config
└── README.md
```

## 🔧 Development

### Run Agents Locally

```bash
# Run a specific agent
cd ai
python -m uvicorn ai.agents.supervisor.main:app --host 0.0.0.0 --port 8001
```

### Run Backend Locally

```bash
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Run Frontend Locally

```bash
cd frontend
npm install
npm run dev
```

### Run Tests

```bash
# Backend tests
cd backend
pytest tests/

# Frontend tests
cd frontend
npm test
```

## 📖 API Documentation

Once the backend is running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

```bash
# Register
POST /api/v1/auth/register
{ "email": "user@example.com", "password": "securepass", "full_name": "John Doe" }

# Login
POST /api/v1/auth/login
{ "email": "user@example.com", "password": "securepass" }

# Send message (streaming)
POST /api/v1/chat/stream
{ "message": "I'm feeling anxious", "conversation_id": "optional-uuid" }

# Get conversations
GET /api/v1/conversations/
```

## ⚠️ Disclaimer

This system is designed for **educational and research purposes only**. It should not replace professional mental health care. Always consult qualified healthcare professionals for medical advice.

---

Built with ❤️ for better mental health support
