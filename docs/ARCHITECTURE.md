# Mental Health Hybrid RAG — Kiến Trúc Hệ Thống Chi Tiết

> **Mục lục:** [Tổng quan](#1-tổng-quan) · [High-Level](#2-high-level-architecture) · [Low-Level](#3-low-level-design) · [Cấu trúc](#4-cấu-trúc-project) · [Data Flow](#5-data-flow) · [Công nghệ](#6-công-nghệ-sử-dụng) · [Phân biệt Workflow vs Agent](#7-phân-biệt-workflow-vs-true-agent) · [Tính năng nổi bật](#8-tính-năng-nổi-bật)

---

## 1. Tổng Quan

**Mental Health Hybrid RAG** là một chatbot tâm lý chuyên sâu, sử dụng kiến trúc **Hybrid Retrieval-Augmented Generation (Hybrid RAG)** — kết hợp đa nguồn tri thức và AI để cung cấp hỗ trợ sức khỏe tâm thần dựa trên bằng chứng.

**Chức năng cốt lõi:**

- Trò chuyện đa turn (multi-turn) với bộ nhớ liên tục
- Phát hiện nguy cơ khủng hoảng (tự tử/tự gây thương tích)
- Phân loại & chuẩn đoán sơ bộ rối loạn tâm thần
- Đề xuất phương pháp điều trị dựa trên triệu chứng
- Hỗ trợ 2 ngôn ngữ: **Tiếng Việt** ↔ **Tiếng Anh**

**Lưu ý quan trọng về kiến trúc:**

Hệ thống này sử dụng **LangGraph StateGraph** (workflow-based), **chưa phải** là true multi-agent system. Xem [phần 7](#7-phân-biệt-workflow-vs-true-agent) để hiểu rõ sự khác biệt.

---

## 2. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           USER LAYER                                        │
│                   React 19 + TypeScript + Tailwind CSS                      │
│              Radix UI Components │ Axios │ JWT Bearer Auth                   │
└────────────────────────────┬─────────────────────────────────────────────────┘
                             │ HTTP/S (JWT Bearer Token)
                             ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND (Python 3.11+)                       │
│                                                                              │
│  ┌─────────────┐    ┌─────────────────────────────────────────────────┐     │
│  │  Auth Layer │    │         LangGraph Workflow Engine                │     │
│  │  JWT Bearer  │    │  ┌───────────────────────────────────────────┐  │     │
│  │  OAuth/Pwd   │    │  │   Query Pipeline (Parallel Flow)          │  │     │
│  └─────────────┘    │  │   1. translate_question_node                │  │     │
│                     │  │   2. classify_type_query_node               │  │     │
│  ┌─────────────┐    │  │   3. router_node (personal/theory)          │  │     │
│  │ ChatService │    │  └───────────────────────────────────────────┘  │     │
│  │ process_     │    │                    │                            │     │
│  │ message()    │    │                    ▼                            │     │
│  └─────────────┘    │  ┌───────────────────────────────────────────┐  │     │
│                     │  │   Safety & Crisis Detection                 │  │     │
│  ┌─────────────┐    │  │   • safety_check_node                      │  │     │
│  │ run_rag_     │    │  │   • crisis_immediate_response             │  │     │
│  │ workflow()   │◄───┼──│   • crisis_escalation                    │  │     │
│  │ (Entry Pt)  │    │  │   • crisis_contextual_support              │  │     │
│  └─────────────┘    │  │   • crisis_to_normal_transition            │  │     │
│                     │  └───────────────────────────────────────────┘  │     │
│                     │                    │                            │     │
│                     │                    ▼                            │     │
│                     │  ┌───────────────────────────────────────────┐  │     │
│                     │  │   4 Specialized Retrieval Branches         │  │     │
│                     │  │  🎓 Theoretical  💊 Treatment             │  │     │
│                     │  │  🔍 Diagnostic   😌 Normal/Adjustment      │  │     │
│                     │  └───────────────────────────────────────────┘  │     │
│                     │                    │                            │     │
│                     │                    ▼                            │     │
│                     │  ┌───────────────────────────────────────────┐  │     │
│                     │  │   Retrieval Pipeline                      │  │     │
│                     │  │  E5 Embedding → Milvus Search →          │  │     │
│                     │  │  Cohere Rerank → Neo4j Subgraph →        │  │     │
│                     │  │  Gemini LLM Answer Generation            │  │     │
│                     │  └───────────────────────────────────────────┘  │     │
│                     │                    │                            │     │
│                     │                    ▼                            │     │
│                     │  ┌───────────────────────────────────────────┐  │     │
│                     │  │   Conversation Memory Node                 │  │     │
│                     │  │   • Buffer (last 3 Q&A pairs)             │  │     │
│                     │  │   • Summary (older pairs)                │  │     │
│                     │  │   • Slot Filling State                   │  │     │
│                     │  └───────────────────────────────────────────┘  │     │
│                     └───────────────────────────────────────────────────┘     │
└────────────────────────────┬─────────────────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┬────────────────────┐
         │                   │                   │                    │
         ▼                   ▼                   ▼                    ▼
  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐
  │  PostgreSQL  │    │   Milvus    │    │    Neo4j    │    │   Cohere API    │
  │  (State DB)  │    │  (Vectors)  │    │  (Graph KG) │    │   (Reranker)    │
  │  • Users     │    │  • E5 embeds│    │  • Nodes    │    └─────────────────┘
  │  • Convs     │    │  • 1024-dim │    │  • Rels     │
  │  • Messages  │    │  • Semantic │    │  • Subgraph │
  │  • LangGraph │    │    search   │    │    expand   │
  │    Checkpoint│    │             │    │             │
  └─────────────┘    └─────────────┘    └─────────────┘
                            │
                            ▼
                     ┌─────────────┐
                     │ Gemini API  │
                     │ (LLM Core)  │
                     └─────────────┘
```

---

## 3. Low-Level Design

### 3.1 LangGraph Workflow (State Machine)

Workflow chính được định nghĩa trong **`workflow.py`** — sử dụng `StateGraph` của LangGraph với **24 nodes** và nhiều conditional edges.

#### State Schema (`state.py` — KGState)

```python
KGState (TypedDict)
├── question: str                       # Câu hỏi hiện tại
├── original_question: str
├── user_language: str                  # "vi" | "en"
│
├── # === SAFETY ===
├── is_high_risk: bool                  # Cờ nguy cơ khủng hoảng
├── is_mental_health_related: bool
├── crisis_level: str                   # "critical" | "high" | "moderate"
├── crisis_stage: int                   # 1: immediate, 2: follow-up, 3: supportive
├── crisis_indicators: List[str]
├── crisis_response_count: int
├── recent_crisis_detected: bool
├── crisis_sensitivity_increased: bool
│
├── # === SLOT FILLING (Thu thập thông tin bệnh nhân) ===
├── slots: Dict[str, Any]               # {emotion, trigger, duration, intensity, ...}
├── missing_slots: List[str]
├── relevant_missing_slots: List[str]
├── has_sufficient_slots: bool
├── rewritten_query: str               # Query đã viết lại với slots + conversation
│
├── # === QUERY ROUTING ===
├── query_type: str                     # "follow_up" | "topic_change" | "off_topic"
├── query_nature: str                   # "personal" | "theoretical"
├── awaiting_treatment_confirmation: bool
├── wants_treatment: bool
├── user_wants_treatment: bool
│
├── # === CONVERSATION MEMORY ===
├── conversation_buffer: List            # 3 cặp Q&A gần nhất
├── summary_context: str                # Tóm tắt các cặp cũ
│
├── # === RETRIEVAL RESULTS ===
├── graph_context: str                  # Context từ Neo4j graph
├── dense_context: str                  # Context từ Milvus vector
├── anchors: List                       # Anchor nodes từ retrieval
├── nodes: List, rels: List             # Subgraph data
│
├── # === ASSESSMENT & DIAGNOSIS ===
├── assessment_category: str            # "normal_response" | "adjustment_reaction" | "possible_disorder"
├── normal_stress_score: float
├── adjustment_reaction_score: float
├── diagnostic_chunks: str
├── detected_disease: str
├── diagnostic_confidence: float
│
├── # === TREATMENT ===
├── treatment_chunks: List
├── theoretical_chunks: List
│
├── answer: str                         # Final output
└── done: bool
```

#### 24 Workflow Nodes

| # | Node | File | Chức năng |
|---|------|------|-----------|
| 1 | `translate_question` | `translate_question.py` | Phát hiện ngôn ngữ (VI/EN), dịch EN→VI |
| 2 | `classify_type_query` | `query_type_classifier.py` | Phân loại: `follow_up` / `topic_change` / `off_topic` |
| 3 | `router` | `router.py` | Phân loại: `personal` / `theoretical` + xác nhận treatment |
| 4 | `safety_check` | `safety_check.py` | Phát hiện nguy cơ khủng hoảng (context-aware) |
| 5 | `slot_filling` | `slot_filling.py` | Trích xuất thông tin cấu trúc (8 slots) |
| 6 | `request_more_info` | `request_more_info.py` | Hỏi thêm nếu thiếu required slots |
| 7 | `query_rewriter` | `query_rewriter.py` | Viết lại query = slots + buffer + summary |
| 8 | `assessment` | `assessment.py` | Đánh giá: normal vs disorder |
| 9 | `normal_coping_retrieval` | `normal_adjustment_retrieval.py` | Retrieval nội dung bình thường |
| 10 | `adjustment_retrieval` | `normal_adjustment_retrieval.py` | Retrieval phản ứng điều chỉnh |
| 11 | `diagnostic_retrieval` | `diagnostic_retrieval.py` | Retrieval chuẩn đoán rối loạn |
| 12 | `disease_conclusion` | `disease_conclusion.py` | Kết luận bệnh (LLM reasoning) |
| 13 | `treatment_retrieval` | `treatment_retrieval.py` | Retrieval phác đồ điều trị |
| 14 | `theoretical_retrieval` | `theoretical_retrieval.py` | Retrieval kiến thức lý thuyết |
| 15 | `graph_retrieval` | `graph_retrieval.py` | Retrieval từ Knowledge Graph |
| 16 | `answer_with_graph` | `answer_with_graph.py` | Generate answer từ graph context |
| 17 | `answer_with_theoretical` | `answer_with_theoretical.py` | Generate answer lý thuyết |
| 18 | `answer_with_treatment` | `answer_with_treatment.py` | Generate answer điều trị |
| 19 | `conversation_memory` | `conversation_memory.py` | Cập nhật buffer + summary + slots |
| 20 | `not_mental_health` | `not_mental_health.py` | Từ chối câu hỏi ngoài tâm lý |
| 21 | `crisis_immediate_response` | `crisis_response.py` | Phản hồi khủng hoảng ngay lập tức |
| 22 | `crisis_follow_up_classifier` | `crisis_response.py` | Phân loại phản hồi người dùng |
| 23 | `crisis_escalation` | `crisis_response.py` | Leo thang khủng hoảng |
| 24 | `crisis_contextual_support` | `crisis_response.py` | Hỗ trợ theo ngữ cảnh |

#### Routing Logic (Conditional Edges)

```
Entry
  └── translate_question
        └── classify_type_query
              ├── "off_topic" → not_mental_health → END
              └── "router" → router
                    ├── "theoretical_retrieval"
                    │     → answer_with_theoretical → conversation_memory → END
                    ├── "safety_check" → safety_check
                    │     ├── "high_risk"
                    │     │     → crisis_immediate_response → END
                    │     ├── "recent_crisis"
                    │     │     → crisis_to_normal_transition → END
                    │     └── "safe" → slot_filling
                    │           ├── "insufficient_slots"
                    │           │     → request_more_info → conversation_memory → END
                    │           └── "sufficient_slots"
                    │                 → query_rewriter → assessment
                    │                       ├── "normal_response"
                    │                       │     → normal_coping_retrieval → answer_with_graph → conversation_memory → END
                    │                       ├── "adjustment_reaction"
                    │                       │     → adjustment_retrieval → answer_with_graph → conversation_memory → END
                    │                       └── "possible_disorder"
                    │                             → diagnostic_retrieval → disease_conclusion
                    │                                   ├── "disease_detected" → conversation_memory → END (chờ xác nhận)
                    │                                   └── "no_disease" → graph_retrieval → answer_with_graph → conversation_memory → END
                    └── "treatment_retrieval" → answer_with_treatment → conversation_memory → END
```

---

### 3.2 Retrieval Pipeline (GraphRAG)

**`graph_retrieval.py`** — Pipeline 6 bước:

```
1. encode_e5(query)
   → 1024-dim vector (E5 Large v2)
   → Query prefix: "query: {text}" (E5 convention)
   → Average pooling → L2 normalize
         │
         ▼
2. milvus_search(embedding, top=50)
   → Top-50 anchor nodes (vector similarity search)
         │
         ▼
3. get_node_names_neo4j(anchor_ids)
   → Gán tên nodes từ Neo4j
         │
         ▼
4. reranker.rerank_anchors(query, anchors, top=3)
   → Cohere Rerank API
   → Input: original query + top-50 anchors
   → Output: Top-3 anchors reranked
         │
         ▼
5. _apply_slot_rerank_bonus(anchors, slots)
   → Bonus nhỏ (5%) nếu slot keywords match anchor
         │
         ▼
6. graph_retriever.retrieve_subgraph(anchor_ids, depth=2)
   → Expand 2-hop neighbors từ anchor nodes
   → Build context string (nodes + relationships)
```

**Vector Embedding**: E5 Large v2 (1024 dimensions)

- Device: CUDA (GPU) hoặc CPU
- Model: `intfloat/e5-large-v2`

**Reranking**: Cohere Rerank API

- Input: original query + top-50 anchors
- Output: Top-3 anchors reranked by relevance

**Neo4j Graph Expansion**:

- Từ anchor nodes → lấy 2-hop neighbors
- Build subgraph → nodes + relationships → context string

---

### 3.3 Persistent State (PostgreSQL Checkpointer)

**`checkpointer.py`** — Singleton manager:

```python
PostgreSQL Checkpointer
├── AsyncPostgresSaver (LangGraph built-in)
├── AsyncConnectionPool
│   ├── max_size: 20 connections
│   ├── min_size: 5 connections
│   └── autocommit: True (for schema setup)
├── Tables: checkpoints, checkpoint_writes
└── Thread-based isolation: thread_id = f"conversation_{conversation_id}"
```

**Tại sao cần checkpointer?**

- Mỗi message trong conversation cần state từ message trước
- Slots (thông tin bệnh nhân) tích lũy qua nhiều turn
- Conversation buffer + summary cần persist
- Server restart không mất trạng thái

---

### 3.4 4 Specialized Retrieval Branches

| Branch | Trigger Condition | Retrieval Collection | Output |
|--------|-----------------|---------------------|--------|
| 🎓 **Theoretical** | `query_nature = "theoretical"` | `theoretical_knowledge` | Giải thích khái niệm, kiến thức tâm lý |
| 🔍 **Diagnostic** | `assessment_category = "possible_disorder"` | `mental_health_diagnostic_support` | Chuẩn đoán rối loạn (DSM-5 based) |
| 💊 **Treatment** | `awaiting_treatment_confirmation = True` + user muốn | `mental_health_treatment_guidance` | Phác đồ điều trị cụ thể |
| 😌 **Normal/Adjustment** | `normal_stress_score` hoặc `adjustment_reaction_score < 60` | `normal_responses` | Chiến lược ứng phó thông thường |

> **Lưu ý:** Đây là **4 nhánh retrieval cố định**, không phải 4 true agents. Xem [phần 7](#7-phân-biệt-workflow-vs-true-agent).

**Slot Filling (8 slots):**

```
REQUIRED: emotion, trigger, duration, intensity, impact, need, stress_level
OPTIONAL: sleep, appetite, coping, support_system
```

→ Yêu cầu tối thiểu **5/7 required slots** trước khi retrieval

---

### 3.5 Crisis Detection System (4-stage Adaptive)

```
Stage 1: crisis_immediate_response
  → Phát hiện keywords + LLM classification
  → Keywords: "tự tử", "tự sát", "suicide", "kill myself"...
  → Indicators: plan, means, intent, immediate_action, active_harm
  → Crisis levels: "critical" (có kế hoạch) vs "high" (có ý định)
  → Response override: Crisis template từ response_templates.yaml

Stage 2: crisis_follow_up_classifier
  → Phân loại phản hồi user:
    • immediate_danger → escalation
    • seeking_help → contextual_support
    • declining_help → gentle_persistence (max 2 lần)
    • de_escalated → normal_transition

Stage 3: contextual_support / gentle_persistence / escalation
  → Contextual: Hỗ trợ dựa trên graph context
  → Persistence: Tiếp tục thuyết phục nhẹ nhàng
  → Escalation: Liên hệ chuyên gia

Stage 4: crisis_to_normal_transition
  → Quay về flow bình thường với sensitivity tăng cao
```

---

## 4. Cấu Trúc Database

### 4.1 PostgreSQL (Users & Conversations)

```sql
users
├── id (UUID, PK)
├── email (unique)
├── hashed_password
├── full_name
└── created_at

conversations
├── id (UUID, PK)
├── user_id (FK → users)
├── title
├── created_at
└── updated_at

messages
├── id (UUID, PK)
├── conversation_id (FK → conversations)
├── role ("user" | "assistant")
├── content (text)
├── is_high_risk (bool)
├── detected_disease (nullable)
└── created_at
```

### 4.2 Neo4j Knowledge Graph

```
Nodes:
- DISORDER (name, description, symptoms, dsm_criteria, ...)
- TREATMENT (name, type, description, evidence_level, ...)
- SYMPTOM (name, category, severity, ...)
- EMOTION, TRIGGER, COPING_STRATEGY, ...

Relationships:
- (DISORDER)-[:HAS_SYMPTOM]->(SYMPTOM)
- (DISORDER)-[:TREATED_BY]->(TREATMENT)
- (SYMPTOM)-[:RELATED_TO]->(SYMPTOM)
- (DISORDER)-[:DIFFERENTIAL_DIAGNOSIS]->(DISORDER)
```

### 4.3 Milvus Vector Collections

```
kg_entities (1024-dim E5 embeddings)
├── entity_id (string, primary key)
├── content (text)
├── entity_type (DISORDER | TREATMENT | SYMPTOM | ...)
└── metadata (JSON)

normal_responses (normal stress content)
mental_health_treatment_guidance (treatment content)
mental_health_diagnostic_support (diagnostic content)
theoretical_knowledge (educational content)
```

---

## 5. Cấu Trúc Project

```
MentalHealth_HybridRAG/
├── backend/                           # FastAPI backend
│   ├── main.py                         # App entry, lifespan (init DB, checkpointer, E5 model)
│   ├── src/
│   │   ├── api/v1/endpoints/
│   │   │   ├── chat.py                 # POST /api/v1/chat (main endpoint)
│   │   │   ├── auth.py                 # Login, register, refresh token
│   │   │   ├── conversations.py        # CRUD conversations
│   │   │   └── health.py               # Health check
│   │   ├── core/
│   │   │   ├── config.py               # Settings (Pydantic BaseSettings)
│   │   │   └── security.py             # JWT, password hashing
│   │   ├── db/
│   │   │   ├── models/                 # SQLAlchemy models (User, Conversation, Message)
│   │   │   ├── repositories/           # Data access (user_repo, conv_repo)
│   │   │   └── session.py              # AsyncSession factory, init_db
│   │   ├── rag/
│   │   │   ├── engine.py               # run_rag_workflow() — ENTRY POINT
│   │   │   ├── config.py               # RAG config
│   │   │   ├── workflow/
│   │   │   │   ├── workflow.py         # build_kg_graph() — 24 nodes + routing
│   │   │   │   ├── state.py            # KGState TypedDict
│   │   │   │   ├── checkpointer.py     # PostgreSQL checkpointer singleton
│   │   │   │   └── graph_nodes/        # 24 node implementations
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
│   │   │   │       ├── crisis_response.py (multi-stage)
│   │   │   │       ├── normal_adjustment_retrieval.py
│   │   │   │       ├── theoretical_retrieval.py
│   │   │   │       └── ...
│   │   │   ├── llm/
│   │   │   │   ├── llm_gemini.py       # Gemini API wrapper
│   │   │   │   └── answer_nodes/       # LLM logic per agent
│   │   │   ├── retrieval/
│   │   │   │   ├── base_retrieval.py   # Base class + RetrievalResult
│   │   │   │   ├── graph_retrieval.py  # GraphRAG pipeline
│   │   │   │   ├── dense_retrieval.py  # Vector-only retrieval
│   │   │   │   └── assessment_retrieval.py
│   │   │   ├── vectors/
│   │   │   │   ├── embeddings.py       # E5 encode_e5(), _average_pool()
│   │   │   │   ├── milvus_client.py    # Milvus search wrapper
│   │   │   │   └── dense_retriever.py  # Milvus collection ops
│   │   │   ├── graph/
│   │   │   │   ├── neo4j_client.py     # Neo4j driver, subgraph queries
│   │   │   │   ├── graph_retriever.py  # build_context(), retrieve_subgraph()
│   │   │   │   └── graph_builder.py
│   │   │   ├── reranker/
│   │   │   │   └── reranker.py         # Cohere rerank API
│   │   │   ├── ingestion/              # Data ingestion pipeline
│   │   │   │   ├── graph/              # Neo4j data loader
│   │   │   │   │   ├── run.py          # run_full_pipeline()
│   │   │   │   │   ├── llm_extractor.py
│   │   │   │   │   ├── nodes_embedder.py
│   │   │   │   │   └── neo4j_writer.py
│   │   │   │   └── vectors/
│   │   │   │       └── index.py        # Milvus batch insert
│   │   │   ├── prompts/
│   │   │   │   └── loader.py           # load_prompts(), format_prompt()
│   │   │   └── utils/
│   │   │       ├── slots.py            # get_default_slots(), has_sufficient_slots()
│   │   │       ├── memory.py            # Buffer/summary formatting
│   │   │       └── disease_translation.py
│   │   ├── schemas/                    # Pydantic models
│   │   └── services/
│   │       ├── chat_service.py          # process_message() — orchestration
│   │       ├── conversation_service.py
│   │       └── auth_service.py
│   ├── data/
│   │   ├── raw/                        # JSONL source data
│   │   │   ├── mental_health_diagnostic_support.jsonl
│   │   │   ├── mental_health_treatment_guidance.jsonl
│   │   │   ├── normal_responses.jsonl
│   │   │   └── theoretical_knowledge.jsonl
│   │   └── processed/                  # Generated embeddings + IDs
│   ├── requirements.txt
│   ├── langgraph.json
│   └── Dockerfile
│
├── frontend/                          # React 19 + TypeScript
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Home.tsx                # Main chat page
│   │   │   ├── Login.tsx
│   │   │   ├── Register.tsx
│   │   │   └── Chat.tsx               # Chat UI component
│   │   ├── components/
│   │   │   ├── Chat.tsx                # Chat UI + message history
│   │   │   └── ui/                     # 50+ Radix UI components
│   │   ├── services/
│   │   │   └── api.ts                  # Axios client, JWT handling
│   │   ├── context/
│   │   │   └── AuthContext.tsx         # Auth state management
│   │   └── routes/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── nginx.conf
│   └── Dockerfile
│
├── nginx/                             # Reverse proxy config
├── docs/images/                        # Demo screenshots
├── docs/
│   └── ARCHITECTURE.md                 # This file
├── docker-compose.yml                  # Production
├── docker-compose-dev.yml              # Development
└── README.md
```

---

## 5. Data Flow Từ Request Đến Response

```
1. USER gửi message (VI/EN)
   ↓
2. FastAPI /api/v1/chat endpoint
   (JWT auth → ChatService.process_message)
   ↓
3. engine.run_rag_workflow(conversation_id, message)
   ↓
4. Load checkpoint từ PostgreSQL (buffer + summary)
   ↓
5. LangGraph ainvoke(initial_state, config)
   ├── checkpoint auto-merged
   └── Node execution begins
       ↓
   [translate_question] → detect VI/EN → translate to EN
       ↓
   [classify_type_query] → follow_up / topic_change / off_topic
       ↓
   [router] → personal / theoretical
       │
       ├─ theoretical ─────────────────────────────┐
       │ [theoretical_retrieval]                  │
       │   → Milvus (theoretical_knowledge)        │
       │ [answer_with_theoretical]                │
       │   → Gemini LLM (EN answer)               │
       │   → translate VI                         │
       └─────────────────────────────────────────┘
       │
       ├─ personal ─────────────────────────────────┐
       │ [safety_check]                            │
       │   → LLM crisis detection                  │
       │   → keywords fallback                     │
       │   ⚠️ HIGH RISK? ──────────────────────┐   │
       │       │                               │   │
       │       │ YES → crisis flow → END       │   │
       │       │ NO ↓                          │   │
       │ [slot_filling]                         │   │
       │   → extract 8 slots (LLM)             │   │
       │   ⚠️ INSUFFICIENT? ──────────────┐   │   │
       │       │                        │   │   │
       │       │ YES → request_more_info  │   │   │
       │       │ NO ↓                    │   │   │
       │ [query_rewriter]                │   │   │
       │   → rewrite(query + slots + buffer) │   │
       │ [assessment]                    │   │   │
       │   → score: normal vs disorder   │   │   │
       │ ┌─ normal/adj ───────────────┐  │   │   │
       │ │ [normal_coping_retrieval / │  │   │   │
       │ │  adjustment_retrieval]     │  │   │   │
       │ │ [answer_with_graph]        │  │   │   │
       │ └────────────────────────────┘  │   │   │
       │ ┌─ possible_disorder ─────────┐  │   │   │
       │ │ [diagnostic_retrieval]     │  │   │   │
       │ │ [disease_conclusion]        │  │   │   │
       │ │ [treatment_retrieval?]      │  │   │   │
       │ │ [answer_with_treatment]     │  │   │   │
       │ └────────────────────────────┘  │   │   │
       │ [graph_retrieval]               │   │   │
       │   → Milvus search (50)           │   │   │
       │   → Cohere rerank (top-3)        │   │   │
       │   → Neo4j 2-hop expand           │   │   │
       │   → build context string         │   │   │
       │ [answer_with_graph]              │   │   │
       │   → Gemini LLM (EN answer)        │   │   │
       │   → translate VI                 │   │   │
       └─────────────────────────────────────┘   │
       ↓
   [conversation_memory]
   → update buffer (last 3 Q&A)
   → update summary (older pairs)
   → merge filled slots
   → checkpoint saved to PostgreSQL
       ↓
6. Return answer + metadata
   (conversation_id, is_high_risk, detected_disease, ...)
   ↓
7. USER nhận response (real-time)
```

---

## 6. Công Nghệ Sử Dụng

| Layer | Technology | Chi tiết |
|-------|-----------|----------|
| **Backend Framework** | FastAPI | Python 3.11+, async |
| **Workflow Engine** | LangGraph | StateGraph, checkpointing |
| **LLM** | Google Gemini 2.0 Flash | API |
| **Embeddings** | E5 Large v2 | 1024-dim, `intfloat/e5-large-v2` |
| **Vector DB** | Milvus | Cloud/Standalone |
| **Graph DB** | Neo4j | Bolt protocol |
| **State Persistence** | PostgreSQL + LangGraph Checkpointer | Async |
| **Reranking** | Cohere Rerank | API |
| **Auth** | JWT Bearer Token | |
| **Frontend** | React 19 + TypeScript | Vite |
| **UI** | Radix UI + Tailwind CSS | |
| **Container** | Docker + Docker Compose | |

---

## 7. Phân Biệt Workflow vs True Agent

### Đây là Workflow, chưa phải True Agent

| | **Workflow (System hiện tại)** | **True Agent** |
|---|---|---|
| **Logic** | Node → edge → node (deterministic) | Tool → reasoning → tool → reasoning (loop) |
| **Decision** | Pre-defined routing functions | **Tự quyết định** next action |
| **Tool use** | Không có tool-calling thực sự | Gọi tools khi cần |
| **Planning** | Flow cố định, định sẵn | **Tự lập kế hoạch** multi-step |
| **Reflection** | Không | Có thể tự đánh giá output rồi điều chỉnh |
| **Loop** | Một chiều (sequential graph) | **ReAct loop**: Act → Observe → Reason → Act |
| **Autonomy** | Thấp | Cao |

### "4 Specialized Agents" — Thực ra là gì?

```
Thực chất chỉ là 4 nhánh retrieval cố định trong graph:

  🎓 Theoretical: theory_retrieval → answer (đường A)
  🔍 Diagnostic: diag_retrieval → conclusion → answer (đường B)
  💊 Treatment: treatment_retrieval → answer (đường C)
  😌 Normal: coping_retrieval → answer (đường D)
```

→ Mỗi "agent" chỉ là **một nhánh cố định**, được chọn bởi router (một hàm `if/else` trong `route_after_*`). Không có agent nào tự quyết định, tự gọi tool, hay tự reflect.

### Ví dụ True Agent (LangGraph ReAct):

```python
# Agent thật sự - có tool-calling + reasoning loop
agent = create_react_agent(llm, tools=[
    milvus_search,
    neo4j_query,
    gemini_generate
])

# Agent tự quyết định: gọi tool nào, bao nhiêu lần, khi nào dừng
result = agent.invoke({
    "messages": [{"role": "user", "content": "..."}]
})
# → LLM suy luận: "Cần tìm triệu chứng trước" → gọi milvus_search
#             → LLM suy luận: "Thiếu thông tin về thời gian" → gọi neo4j_query
#             → LLM suy luận: "Đủ rồi, tạo câu trả lời" → gọi gemini_generate
```

### Muốn thành true agent cần thêm gì?

1. **Tool definitions** — mỗi agent có tools riêng (search, query_kg, generate, ask_user)
2. **ReAct loop** — thay vì graph cố định, LLM quyết định gọi tool nào
3. **Self-reflection** — agent đánh giá answer đã đủ chưa, cần thêm context không
4. **Multi-agent communication** — các agent giao tiếp với nhau (hỏi Diagnostic → chuyển sang Treatment)

---

## 8. Tính Năng Nổi Bật

| Tính năng | Chi tiết |
|-----------|----------|
| **Hybrid RAG** | Graph (Neo4j) + Vector (Milvus) + LLM (Gemini) |
| **4 Retrieval Branches** | Theoretical, Diagnostic, Treatment, Normal/Adjustment |
| **Persistent State** | PostgreSQL LangGraph Checkpointer — survive restart |
| **Crisis Detection** | 4-stage adaptive system (context-aware LLM + keyword fallback) |
| **Slot Filling** | 8 fields, tối thiểu 5/7 required → 2-phase flow |
| **Query Rewriting** | Enhance query với slots + buffer + summary trước retrieval |
| **Reranking** | Cohere rerank + slot bonus (5%) |
| **Bilingual** | Vietnamese ↔ English (translate node) |
| **Multi-turn Memory** | Buffer (3 Q&A pairs) + Summary (older) |
| **Subgraph Expansion** | 2-hop from anchor nodes via Neo4j |
| **Streaming Response** | Real-time streaming qua SSE |

---

## 9. GitNexus Module Clusters

| Cluster | Symbols | Cohesion | Mô tả |
|---------|---------|---------|-------|
| **Ui** | 187 | 92% | React UI (components, pages) |
| **Graph** | 76 | 89% | Neo4j operations + ingestion |
| **Answer_nodes** | 45 | 89% | LLM answer generation per branch |
| **Services** | 44 | 87% | Chat, Auth, Conversation services |
| **Graph_nodes** | 34 | 86% | LangGraph workflow nodes |
| **Vectors** | 28 | 90% | E5 embeddings + Milvus + reranker |
| **Pages** | 20 | 96% | React page components |
| **Components** | 16 | 100% | Shared UI components |
| **Retrieval** | 13 | 77% | Retrieval pipeline (graph, dense) |
| **Repositories** | 10 | 84% | Database access layer |
| **Schemas** | 10 | 100% | Pydantic models |
| **Prompts** | 9 | 76% | Prompt templates & loaders |
| **Db** | 6 | 91% | DB init, session, checkpointer |

---

**⚠️ Disclaimer**: Hệ thống này được thiết kế cho mục đích giáo dục và nghiên cứu. Không thay thế được tư vấn sức khỏe tâm thần chuyên nghiệp. Luôn tham khảo chuyên gia y tế cho tư vấn y khoa.
