# Mental Health Hybrid RAG — Current Architecture

> **Trạng thái**: Workflow-based system (chưa phải True Multi-Agent)
> **Ngày cập nhật**: 2026-03-19

---

## Tổng Quan

Đây là hệ thống chatbot tâm lý sử dụng **Hybrid RAG Architecture** với **LangGraph StateGraph** làm workflow orchestrator. Hệ thống kết hợp Knowledge Graph (Neo4j), Vector Search (Milvus), và LLM (Gemini) để cung cấp hỗ trợ sức khỏe tâm thần.

### Điểm mạnh
- Hybrid RAG: Graph + Vector + LLM
- Persistent state (PostgreSQL Checkpointer)
- Crisis detection 4-stage
- Multi-turn memory (buffer + summary + slots)
- Bilingual: Vietnamese ↔ English

### Hạn chế (cần cải tiến)
- **Chưa phải True Multi-Agent** — chỉ là workflow orchestration
- Các "agent" chỉ là nhánh cố định, không tự quyết định
- Không có tool-calling thực sự
- Không có self-reflection
- Không có autonomous planning

---

## 1. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           USER LAYER                                      │
│                   React 19 + TypeScript + Tailwind CSS                    │
│              Radix UI Components │ Axios | JWT Bearer Auth                 │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │ HTTPS
                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND (Python 3.11+)                     │
│                                                                          │
│  ┌─────────────┐    ┌────────────────────────────────────────────┐    │
│  │  Auth Layer │    │         LangGraph Workflow Engine (STATIC)    │    │
│  │  JWT Bearer  │    │  ┌──────────────────────────────────────┐   │    │
│  └─────────────┘    │  │   Query Pipeline (Sequential)        │   │    │
│                     │  │   • translate_question_node         │   │    │
│  ┌─────────────┐    │  │   • classify_type_query_node        │   │    │
│  │ ChatService │    │  │   • router_node                     │   │    │
│  │             │    │  │   • safety_check_node               │   │    │
│  │ process_    │    │  │   • slot_filling_node                │   │    │
│  │ message()   │    │  │   • query_rewriter_node             │   │    │
│  └─────────────┘    │  │   • assessment_node                  │   │    │
│                     │  └──────────────────────────────────────┘   │    │
│  ┌─────────────┐    │                    │                        │    │
│  │ run_rag_    │    │                    ▼                        │    │
│  │ workflow()  │◄───┼──┐    ┌──────────────────────────────────┐  │    │
│  │ (Entry Pt) │    │  │    │   4 Specialized "Agents"          │  │    │
│  └─────────────┘    │  │    │  (Fixed branches in graph)        │  │    │
│                     │  │    │  🎓 Theoretical  💊 Treatment    │  │    │
│                     │  │    │  🔍 Diagnostic   😌 Normal/Adj.   │  │    │
│                     │  │    └──────────────────────────────────┘  │    │
│                     │  │                    │                        │    │
│                     │  │                    ▼                        │    │
│                     │  │    ┌──────────────────────────────────┐  │    │
│                     │  │    │   Retrieval Pipeline (Static)     │  │    │
│                     │  │    │  E5 Embed → Milvus → Rerank →   │  │    │
│                     │  │    │  Neo4j → Gemini Answer            │  │    │
│                     │  │    └──────────────────────────────────┘  │    │
│                     │  │                    │                        │    │
│                     │  │                    ▼                        │    │
│                     │  │    ┌──────────────────────────────────┐  │    │
│                     │  │    │   conversation_memory_node        │  │    │
│                     │  │    │   • Update buffer (last 3 Q&A)  │  │    │
│                     │  │    │   • Update summary (older)      │  │    │
│                     │  │    │   • Merge filled slots           │  │    │
│                     │  │    └──────────────────────────────────┘  │    │
│                     │  └────────────────────────────────────────────┘    │
│                     └────────────────────────────────────────────────────┘
└────────────────────────────┬─────────────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┬────────────────────┐
         │                   │                   │                    │
         ▼                   ▼                   ▼                    ▼
  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐
  │  PostgreSQL  │    │   Milvus    │    │    Neo4j    │    │   Cohere API    │
  │  (State DB) │    │  (Vectors)  │    │  (Graph KG) │    │   (Reranker)    │
  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────────┘
                            │
                            ▼
                     ┌─────────────┐
                     │ Gemini API  │
                     │ (LLM Core)  │
                     └─────────────┘
```

---

## 2. Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend Framework** | FastAPI | REST API |
| **Workflow Engine** | LangGraph StateGraph | Orchestration (workflow, NOT agent) |
| **LLM** | Google Gemini 2.0 Flash | Answer generation, classification |
| **Embeddings** | E5 Large v2 (1024-dim) | Semantic representation |
| **Vector DB** | Milvus | Semantic search |
| **Graph DB** | Neo4j | Knowledge graph, subgraph expansion |
| **State Persistence** | PostgreSQL + LangGraph AsyncPostgresSaver | Multi-turn state |
| **Reranking** | Cohere Rerank API | Anchor reranking |
| **Auth** | JWT Bearer Token | User authentication |
| **Frontend** | React 19 + TypeScript | Chat UI |
| **UI Components** | Radix UI + Tailwind CSS | UI library |
| **Container** | Docker + Docker Compose | Deployment |

---

## 3. Cấu Trúc Project

```
MentalHealth_HybridRAG/
├── backend/                           # FastAPI
│   ├── main.py                         # App entry, lifespan (init all)
│   ├── src/
│   │   ├── api/v1/endpoints/
│   │   │   ├── chat.py                 # POST /api/v1/chat (main endpoint)
│   │   │   ├── auth.py                 # Login, register, refresh token
│   │   │   ├── conversations.py        # CRUD conversations
│   │   │   └── health.py               # Health check
│   │   ├── core/
│   │   │   ├── config.py               # Pydantic BaseSettings
│   │   │   └── security.py             # JWT, password hashing
│   │   ├── db/
│   │   │   ├── models/                 # SQLAlchemy (User, Conversation, Message)
│   │   │   ├── repositories/           # Data access
│   │   │   └── session.py             # AsyncSession factory, init_db
│   │   ├── rag/
│   │   │   ├── engine.py               # run_rag_workflow() — ENTRY POINT
│   │   │   ├── config.py              # RAG config
│   │   │   ├── workflow/
│   │   │   │   ├── workflow.py         # build_kg_graph() — StateGraph
│   │   │   │   ├── state.py           # KGState TypedDict
│   │   │   │   ├── checkpointer.py    # PostgreSQL checkpointer
│   │   │   │   └── graph_nodes/       # 24 node implementations
│   │   │   │       ├── translate_question.py
│   │   │   │       ├── query_type_classifier.py
│   │   │   │       ├── router.py
│   │   │   │       ├── safety_check.py
│   │   │   │       ├── slot_filling.py
│   │   │   │       ├── query_rewriter.py
│   │   │   │       ├── assessment.py
│   │   │   │       ├── diagnostic_retrieval.py
│   │   │   │       ├── disease_conclusion.py
│   │   │   │       ├── treatment_retrieval.py
│   │   │   │       ├── graph_retrieval.py
│   │   │   │       ├── answer_with_graph.py
│   │   │   │       ├── answer_with_theoretical.py
│   │   │   │       ├── answer_with_treatment.py
│   │   │   │       ├── conversation_memory.py
│   │   │   │       ├── crisis_response.py
│   │   │   │       ├── normal_adjustment_retrieval.py
│   │   │   │       ├── theoretical_retrieval.py
│   │   │   │       ├── request_more_info.py
│   │   │   │       ├── not_mental_health.py
│   │   │   │       └── crisis_*.py
│   │   │   ├── llm/
│   │   │   │   ├── llm_gemini.py       # Gemini API wrapper
│   │   │   │   └── answer_nodes/       # LLM logic per type
│   │   │   │       ├── router.py
│   │   │   │       ├── translator.py
│   │   │   │       ├── safety_check.py
│   │   │   │       ├── disease_conclusion.py
│   │   │   │       └── crisis_response.py
│   │   │   ├── retrieval/
│   │   │   │   ├── base_retrieval.py  # Base class + RetrievalResult
│   │   │   │   ├── graph_retrieval.py # GraphRAG pipeline
│   │   │   │   ├── dense_retrieval.py # Vector-only retrieval
│   │   │   │   └── assessment_retrieval.py
│   │   │   ├── vectors/
│   │   │   │   ├── embeddings.py      # E5 encode + pooling
│   │   │   │   ├── milvus_client.py   # Milvus search wrapper
│   │   │   │   └── dense_retriever.py # Milvus operations
│   │   │   ├── graph/
│   │   │   │   ├── neo4j_client.py    # Neo4j driver
│   │   │   │   ├── graph_retriever.py # build_context, retrieve_subgraph
│   │   │   │   └── graph_builder.py
│   │   │   ├── reranker/
│   │   │   │   └── reranker.py       # Cohere rerank
│   │   │   ├── ingestion/             # Data ingestion
│   │   │   │   ├── graph/            # Neo4j loader
│   │   │   │   │   ├── run.py        # run_full_pipeline()
│   │   │   │   │   ├── llm_extractor.py
│   │   │   │   │   ├── nodes_embedder.py
│   │   │   │   │   └── neo4j_writer.py
│   │   │   │   └── vectors/
│   │   │   │       └── index.py      # Milvus batch insert
│   │   │   ├── prompts/
│   │   │   │   └── loader.py         # load_prompts, format_prompt
│   │   │   └── utils/
│   │   │       ├── slots.py          # Slot management
│   │   │       ├── memory.py         # Buffer/summary formatting
│   │   │       └── disease_translation.py
│   │   ├── schemas/                  # Pydantic models
│   │   └── services/
│   │       ├── chat_service.py      # process_message orchestration
│   │       ├── conversation_service.py
│   │       └── auth_service.py
│   ├── data/
│   │   ├── raw/                     # JSONL source data
│   │   └── processed/               # Embeddings + IDs
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                        # React 19 + TypeScript
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Home.tsx             # Main chat page
│   │   │   ├── Login.tsx
│   │   │   ├── Register.tsx
│   │   │   └── Chat.tsx
│   │   ├── components/
│   │   │   ├── Chat.tsx            # Chat UI
│   │   │   └── ui/                 # 50+ Radix UI components
│   │   ├── services/
│   │   │   └── api.ts              # Axios client + JWT
│   │   ├── context/
│   │   │   └── AuthContext.tsx     # Auth state
│   │   └── routes/
│   ├── package.json
│   └── Dockerfile
│
├── docs/
│   └── images/                     # Demo screenshots
├── nginx/
├── docker-compose.yml
├── docker-compose-dev.yml
└── README.md
```

---

## 4. LangGraph Workflow — Chi Tiết

### 4.1 State Schema (KGState)

```python
class KGState(TypedDict):
    # Core
    question: str
    original_question: str
    user_language: str               # "vi" | "en"
    is_mental_health_related: bool
    is_high_risk: bool              # Crisis flag

    # Slot Filling
    slots: Optional[Dict[str, Any]]
    missing_slots: Optional[List[str]]
    has_sufficient_slots: bool
    rewritten_query: Optional[str]

    # Conversation Memory
    conversation_buffer: Optional[List[Dict]]  # Last 3 Q&A pairs
    summary_context: Optional[str]             # Summarized older pairs

    # Retrieval Results
    graph_context: str
    anchors: List[Dict]
    nodes: List, rels: List

    # Assessment
    assessment_category: str         # normal | adjustment | disorder
    normal_stress_score: float
    adjustment_reaction_score: float

    # Diagnosis
    detected_disease: str
    diagnostic_confidence: float

    # Treatment
    treatment_chunks: List[str]
    awaiting_treatment_confirmation: bool
    wants_treatment: bool

    # Crisis
    crisis_level: str               # critical | high | moderate
    crisis_indicators: List[str]
    crisis_response_count: int

    # Output
    answer: str
    done: bool
```

### 4.2 24 Workflow Nodes

```
┌─────────────────────────────────────────────────────────────┐
│  ENTRY → translate_question                                   │
│              ↓                                               │
│         classify_type_query                                   │
│         (follow_up | topic_change | off_topic)               │
│              ↓                                               │
│              ├─ off_topic → not_mental_health → END          │
│              └─ router                                        │
│                    ├─ theoretical → theoretical_retrieval    │
│                    │                    ↓                     │
│                    │               answer_with_theoretical    │
│                    │                    ↓                     │
│                    └─ safety_check                            │
│                              ├─ high_risk → crisis flow (4 nodes) → END
│                              └─ safe → slot_filling           │
│                                          ├─ insufficient → request_more_info → conv_memory → END
│                                          └─ sufficient → query_rewriter → assessment  │
│                                                                    ├─ normal → normal_coping → answer → conv_memory → END  │
│                                                                    ├─ adjustment → adjustment_retrieval → answer → conv_memory → END  │
│                                                                    └─ disorder → diagnostic_retrieval → disease_conclusion  │
│                                                                                      ├─ confirmed → treatment? → conv_memory → END
│                                                                                      └─ unconfirmed → graph_retrieval → answer → conv_memory → END
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Routing Logic

```python
# 7 conditional routing functions:

route_after_classify_query()
  → "off_topic" → not_mental_health
  → "follow_up" / "topic_change" → router

route_after_router()
  → "theoretical" → theoretical_retrieval
  → "personal" → safety_check
  → "treatment_retrieval" → answer_with_treatment

route_after_safety_check()
  → is_high_risk → crisis_immediate_response
  → recent_crisis → crisis_to_normal_transition
  → safe → slot_filling

route_after_slot_filling()
  → insufficient → request_more_info
  → sufficient → query_rewriter

route_after_assessment()
  → normal_response → normal_coping_retrieval
  → adjustment_reaction → adjustment_retrieval
  → possible_disorder → diagnostic_retrieval

route_after_disease_conclusion()
  → disease_detected → conversation_memory (ask treatment)
  → no_disease → graph_retrieval

route_after_crisis_follow_up()
  → immediate_danger → crisis_escalation
  → seeking_help → crisis_contextual_support
  → declining_help → crisis_gentle_persistence / contextual_support
  → de_escalated → crisis_to_normal_transition
```

---

## 5. Retrieval Pipeline

```
Query
  │
  ├─► encode_e5("query: {query}")    [E5 Large v2, 1024-dim]
  │                                     CUDA/CPU
  │   ↓
  │► milvus_search(embedding, k=50)  [Semantic search]
  │     threshold=0.8
  │   ↓
  │► get_node_names_neo4j(node_ids)  [Map IDs → Names]
  │   ↓
  │► reranker.rerank(query,          [Cohere Rerank API]
  │     candidates, top_k=3)
  │   ↓
  │► _apply_slot_rerank_bonus()      [5% bonus if slot keyword match]
  │   ↓
  │► graph_retriever.retrieve_       [Neo4j 2-hop expansion]
  │     subgraph(anchor_ids)          from anchor nodes
  │   ↓
  └► graph_retriever.build_context() [Nodes + Rels → String]
          │
          ▼
      Graph Context String
```

**4 Retrieval Collections trong Milvus:**

| Collection | Kích thước | Mục đích |
|-----------|-----------|---------|
| `kg_entities` | - | Main graph entities |
| `theoretical_knowledge` | - | Educational content |
| `mental_health_treatment_guidance` | - | Treatment protocols |
| `mental_health_diagnostic_support` | - | DSM-5 diagnostic |
| `normal_responses` | - | Coping strategies |

---

## 6. Database Schema

### 6.1 PostgreSQL (Users & State)

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    full_name VARCHAR,
    created_at TIMESTAMP
);

-- Conversations
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    title VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Messages
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    role VARCHAR,  -- "user" | "assistant"
    content TEXT,
    is_high_risk BOOLEAN DEFAULT FALSE,
    detected_disease VARCHAR,
    created_at TIMESTAMP
);

-- LangGraph Checkpoints (auto-created by AsyncPostgresSaver)
CREATE TABLE checkpoints (...);
CREATE TABLE checkpoint_writes (...);
```

### 6.2 Neo4j Knowledge Graph

```cypher
// Nodes
(:DISORDER {name, description, symptoms, dsm_criteria, ...})
(:TREATMENT {name, type, description, evidence_level, ...})
(:SYMPTOM {name, category, severity, ...})
(:EMOTION)
(:TRIGGER)
(:COPING_STRATEGY)

// Relationships
(:DISORDER)-[:HAS_SYMPTOM]->(:SYMPTOM)
(:DISORDER)-[:TREATED_BY]->(:TREATMENT)
(:DISORDER)-[:DIFFERENTIAL_DIAGNOSIS]->(:DISORDER)
(:SYMPTOM)-[:RELATED_TO]->(:SYMPTOM)
(:DISORDER)-[:CAUSED_BY]->(:TRIGGER)
```

---

## 7. Conversation Memory

### 7.1 Memory Structure

```
conversation_memory_node xử lý:

conversation_buffer (Ring Buffer - max 3 pairs):
  Pair 1: {"user": "Q1", "bot": "A1"}
  Pair 2: {"user": "Q2", "bot": "A2"}
  Pair 3: {"user": "Q3", "bot": "A3"}

summary_context (older pairs summarized):
  "User mentioned stress at work, trouble sleeping.
   Bot suggested relaxation techniques. User tried them..."

filled_slots (accumulated across turns):
  {
    "emotion": "buồn",
    "trigger": "công việc",
    "duration": "2 tuần",
    "sleep": "không ngủ được",  // filled in turn 2
    "support": "có gia đình hỗ trợ"  // filled in turn 3
  }
```

### 7.2 State Persistence

```
Checkpoint Table (PostgreSQL):
thread_id = f"conversation_{conversation_id}"
↓
Mỗi message mới:
  1. Load checkpoint (buffer + summary + slots)
  2. Merge với initial_state
  3. Execute graph (node-by-node)
  4. Save checkpoint after each node (AutoPostgresSaver)
  5. Return final answer
```

---

## 8. Crisis Detection System

### 8.1 4-Stage Flow

```
Stage 1: crisis_immediate_response
  - LLM context-aware detection (history + summary + buffer)
  - Keyword fallback: "tự tử", "tự sát", "suicide", "kill myself"...
  - Indicators: plan, means, intent, immediate_action, active_harm
  - Crisis levels:
    • critical: có kế hoạch + phương tiện + ý định
    • high: suicidal ideation hoặc self-harm urges

Stage 2: crisis_follow_up_classifier
  - Phân loại phản hồi user sau crisis message:
    • immediate_danger → escalation
    • seeking_help → contextual_support
    • declining_help → gentle_persistence (max 2 lần)
    • de_escalated → transition_to_normal

Stage 3: contextual_support / gentle_persistence / escalation
  - Contextual: Hỗ trợ dựa trên graph context
  - Persistence: Tiếp tục thuyết phục nhẹ nhàng
  - Escalation: Liên hệ chuyên gia

Stage 4: crisis_to_normal_transition
  - Quay về flow bình thường với safety monitoring tăng cao
```

---

## 9. Slot Filling System

### 9.1 8 Slots

```
REQUIRED (7) — phải điền đủ ≥5 mới chạy retrieval:
  1. emotion         — Cảm xúc chính (buồn, lo âu, sợ hãi...)
  2. trigger         — Yếu tố khởi phát
  3. duration        — Thời gian (bao lâu rồi)
  4. intensity       — Mức độ nghiêm trọng
  5. impact          — Ảnh hưởng đến cuộc sống
  6. need            — Người dùng cần gì
  7. stress_level    — Mức độ stress

OPTIONAL (1) — không block retrieval:
  8. sleep           — Tình trạng giấc ngủ
```

### 9.2 2-Phase Flow

```
Phase 1 (BLOCKING — before retrieval):
  if REQUIRED slots < 5:
    → request_more_info node
    → Ask user missing required slots
    → Wait for response
    → END (không generate answer)

Phase 2 (NON-BLOCKING — after answer):
  if OPTIONAL slots unfilled:
    → Append optional questions to answer
    → Không block answer generation
```

---

## 10. API Endpoints

```
Authentication:
  POST /api/v1/auth/register
  POST /api/v1/auth/login
  POST /api/v1/auth/refresh-token

Chat:
  POST /api/v1/chat          ← Main chat endpoint
  POST /api/v1/chat/stream   ← Streaming response

Conversations:
  GET  /api/v1/conversations/
  POST /api/v1/conversations/
  GET  /api/v1/conversations/{id}
  DELETE /api/v1/conversations/{id}
  GET  /api/v1/conversations/{id}/messages

Health:
  GET /health
  GET /api
```

---

## 11. Data Files (JSONL)

```
backend/data/raw/
├── mental_health_diagnostic_support.jsonl    → Diagnostic Agent
├── mental_health_treatment_guidance.jsonl    → Treatment Agent
├── normal_responses.jsonl                     → Normal/Adjustment Agent
└── theoretical_knowledge.jsonl                → Theoretical Agent
```

Mỗi file JSONL chứa dữ liệu domain-specific được:
1. LLM extract entities + relationships
2. Embed bằng E5 → insert vào Milvus
3. Ghi nodes + edges vào Neo4j

---

## 12. Hạn Chế Cần Cải Tiến

| # | Hạn chế | Mô tả |
|---|---------|-------|
| 1 | **Không phải true agent** | Workflow cố định, các "agent" chỉ là nhánh static |
| 2 | **Không có tool-calling** | Không có ReAct loop, LLM không gọi tool tự động |
| 3 | **Không có self-reflection** | Agent không tự đánh giá answer đã đủ chưa |
| 4 | **Router là if/else** | Phân loại agent dựa trên hàm Python, không phải LLM reasoning |
| 5 | **Không có planning** | Mỗi turn chạy cùng flow, không tự lập kế hoạch |
| 6 | **Retrieval cứng** | 4 collection cố định, không tự chọn collection phù hợp |
| 7 | **Không có memory agent** | Memory chỉ là state update, không phải agent độc lập |

Xem: [multi-agent-plan.md](./multi-agent-plan.md) — Kế hoạch refactor thành True Multi-Agent System.
