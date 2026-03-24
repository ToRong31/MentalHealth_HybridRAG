# Mental Health Hybrid RAG — Refactor Plan
## Phần 6: Documentation Tổng Hợp & Hướng Dẫn Implementation

> **Tổng hợp toàn bộ kiến trúc + README hướng dẫn implementation từng bước + Migration Guide**
> Đọc trước: REFACTOR-PLAN-PART1-5.md

---

## 1. Consolidated Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    USER LAYER                                           │
│                          React 19 + TypeScript + Tailwind                               │
│                    Radix UI │ Axios │ JWT │ SSE Streaming                               │
└────────────────────────────────┬──────────────────────────────────────────────────────┘
                                 │ HTTP/S (JWT Bearer Token)
                                 ▼
┌────────────────────────────────┬──────────────────────────────────────────────────────┐
│                          FASTAPI BACKEND                                                │
│                                                                                        │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │                     SUPERVISOR AGENT (ROUTER — Entry Point)                    │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────┐ │  │
│  │  │ IntentClassification Skill: classify → route 1 lần đến đúng Domain Agent │ │  │
│  │  │ PreliminaryContext Skill: load context từ MemoryService                  │ │  │
│  │  │                                                                             │ │  │
│  │  │ Routing: crisis → CrisisAgent | support → SupportAgent                     │ │  │
│  │  │           theory → TheoryAgent | treatment → TreatmentAgent               │ │  │
│  │  │           diagnostic → DiagnosticAgent | fallback → SupportAgent           │ │  │
│  │  └──────────────────────────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────┬────────────────────────────────────────────┘  │
│                                       │ Message Bus (async pub/sub)                   │
│  ┌────────────────────────────────────┼────────────────────────────────────────────┐ │
│  │                           MESSAGE BUS                                             │ │
│  │  ┌──────────────────┐  ┌───────────────────┐  ┌────────────────────────────────┐  │ │
│  │  │ Priority: normal  │  │ Priority: high    │  │ Priority: CRITICAL (interrupt) │  │ │
│  │  │ (queued, async)  │  │ (queued, sync)    │  │ (all agents abort immediately) │  │ │
│  │  └──────────────────┘  └───────────────────┘  └────────────────────────────────┘  │ │
│  │  Subscriptions: topic-based │ Result tracking per task_id                          │ │
│  └────────────────────────────────────┬─────────────────────────────────────────────┘  │
│                                       │                                                  │
│     ┌─────────────────────────────────┼────────────────────────────────────────────────┐ │
│     │                    5 DOMAIN AGENTS (self-contained, skills embedded)             │ │
│     │                                                                                    │ │
│     │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐               │ │
│     │  │   CrisisAgent     │  │  SupportAgent    │  │  TheoryAgent     │               │ │
│     │  │  Priority: CRITICAL│  │ Goal: Non-disorder│  │ Goal: Psychology │               │ │
│     │  │  Interrupt capable │  │  coping support   │  │  theory explain  │               │ │
│     │  │ ──────────────── │  │ ──────────────── │  │ ──────────────── │               │ │
│     │  │ Skills:           │  │ Skills:           │  │ Skills:           │               │ │
│     │  │  CrisisDetection  │  │  CopingRetrieval  │  │  ConceptRetrieval │               │ │
│     │  │  ImmediateResponse │  │  EmotionalSupport │  │  EducationalExplain│              │ │
│     │  │  ProfessionalEsc.  │  │  PsychoEducation  │  │  AnswerFormatting │               │ │
│     │  │  FollowUpSupport  │  │  SkillBuilding    │  │                  │               │ │
│     │  │  Documentation    │  │  AnswerFormatting │  │                  │               │ │
│     │  └─────────┬──────────┘  └─────────┬──────────┘  └─────────┬──────────┘               │ │
│     │            │                       │                       │                        │ │
│     │  ┌─────────┴──────────┐  ┌─────────┴──────────┐               │                        │ │
│     │  │ TreatmentAgent     │  │ DiagnosticAgent    │               │                        │ │
│     │  │ Goal: Treatment    │  │ Goal: DSM-5 diag.  │               │                        │ │
│     │  │  plans & guidance  │  │ ──────────────── │               │                        │ │
│     │  │ ──────────────── │  │ Skills:           │               │                        │ │
│     │  │ Skills:           │  │  SymptomExtraction│               │                        │ │
│     │  │  TreatmentRetrieval│  │  DiagnosticRetrieval              │               │                        │ │
│     │  │  TreatmentPlanning │  │  ClinicalReasoning│               │                        │ │
│     │  │  PatientGuidance   │  │  ResponseDrafting  │               │                        │ │
│     │  │  AnswerFormatting  │  │                  │               │                        │ │
│     │  └────────────────────┘  └───────────────────┘               │                        │ │
│     │                                      │                                               │ │
│     │                    ┌─────────────────┴───────────────────────┐                  │ │
│     │                    │          SHARED RETRIEVAL SKILLS         │                  │ │
│     │                    │  ┌──────────────────────────────────────┐ │                  │ │
│     │                    │  │ EmbeddingSkill (E5 encode)          │ │                  │ │
│     │                    │  │ GraphExpansionSkill (Neo4j 2-hop)   │ │                  │ │
│     │                    │  │ RerankingSkill (Cohere)              │ │                  │ │
│     │                    │  │ HybridSearchSkill (Milvus + Graph)   │ │                  │ │
│     │                    │  └──────────────────────────────────────┘ │                  │ │
│     └────────────────────┴───────────────────────────────────────────┘                 │ │
│                                       │                                                  │
│  ┌────────────────────────────────────┴────────────────────────────────────────────┐ │
│  │                         SERVICES LAYER                                            │ │
│  │  ┌────────────────────────────────────────────────────────────────────────────┐  │ │
│  │  │  MemoryService (NOT an Agent — no ReAct loop)                              │  │ │
│  │  │  CRUD: conversation_buffer, summary, slots, retrieval_cache               │  │ │
│  │  │  L2: Redis cache │ L3: PostgreSQL Checkpointer                             │  │ │
│  │  │  Injected into every Domain Agent constructor                              │  │ │
│  │  └────────────────────────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────┬────────────────────────────────────────────┘  │
└────────────────────────────────────────┼─────────────────────────────────────────────┘
                                         │
     ┌───────────────────────────────────┼───────────────────────────────────────┐
     │              INFRASTRUCTURE LAYER  │                                         │
     │  ┌─────────────┐  ┌───────────┐  ┌─────────────┐  ┌────────────────────┐   │
     │  │ PostgreSQL  │  │  Milvus   │  │   Neo4j     │  │  Redis (L2 Cache)  │   │
     │  │ Checkpointer│  │ (Vectors) │  │ (Knowledge  │  │  • Slots cache     │   │
     │  │ • GlobalSt. │  │ • E5 emb  │  │   Graph)    │  │  • Retrieval cache │   │
     │  │ • Buff/Sum  │  │ • 1024-dim│  │ • 2-hop     │  │  • Context cache   │   │
     │  └─────────────┘  └───────────┘  └─────────────┘  └────────────────────┘   │
     │       │                                                   │                   │
     │       └───────────────────────────┬───────────────────────┘                   │
     │                                   ▼                                           │
     │                          ┌─────────────┐                                      │
     │                          │ Gemini API  │ ← LLM Core                          │
     │                          └─────────────┘                                      │
     └─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Bảng So Sánh Toàn Diện: Workflow → Multi-Agent

| Khía cạnh | Workflow (Cũ) | Multi-Agent (Mới) |
|-----------|:---:|:---:|
| **Agent count** | 24 workflow nodes | 5 domain agents + 1 supervisor |
| **Execution** | Sequential nodes | ReAct loops per agent |
| **Decision** | Router if/else | LLM-based reasoning |
| **Tool use** | Hardcoded functions | Dynamic tool calling |
| **Communication** | Implicit state dict | Explicit message passing |
| **Memory** | Global KGState only | GlobalState + Agent-local |
| **Crisis handling** | Node branch | Priority interrupt |
| **Error handling** | Per-node try/catch | Circuit breaker + retry |
| **Caching** | None | 3-level (L1/L2/L3) |
| **Parallelism** | Sequential | Agent-level parallel |
| **Tracing** | Limited | LangSmith per-agent |
| **Scalability** | Add node to graph | Add agent module |
| **Avg latency** | ~3500ms | ~1500ms (-57%) |
| **Streaming** | Full response | Token streaming (SSE) |

---

## 3. Implementation Roadmap — Phase by Phase

### Phase 1: Foundation (Tuần 1-2) — Infrastructure

```
Mục tiêu: Xây dựng nền tảng, không thay đổi behavior hiện tại

Bước 1.1: Thiết lập cấu trúc module mới
  ├── ai/modules/shared/
  │   ├── base_agent.py
  │   ├── message.py
  │   ├── state.py
  │   ├── constants.py
  │   └── exceptions.py
  ├── ai/modules/shared/
  │   ├── message_bus.py
  │   └── events.py
  └── ai/modules/ (empty __init__ + facades)

Bước 1.2: Implement MessageBus + EventSystem
  - Unit tests cho MessageBus (send/receive/broadcast/interrupt)
  - Integration test với 2 dummy agents

Bước 1.3: Implement BaseAgent (Abstract)
  - ReAct loop template
  - Error handling + retry
  - Circuit breaker integration

Bước 1.4: Define GlobalState schema
  - Update từ KGState TypedDict
  - Serializer cho PostgreSQL Checkpointer
  - Backward compatibility với old KGState

Bước 1.5: Implement AgentCache (L1)
  - LRUCache với TTL
  - RedisCache client (L2)

Deliverable: Cơ sở hạ tầng hoàn chỉnh, có thể chạy dummy agents
```

### Phase 2: Domain Agents — CrisisAgent + SupportAgent (Tuần 3-4)

```
Mục tiêu: Implement 2 agents đơn giản nhất trước — domain-centric, tự hoàn thành task

Bước 2.1: Implement CrisisAgent (ưu tiên cao nhất)
  ├── GOAL: Ứng phó khủng hoảng
  ├── Skills: CrisisDetection, ImmediateResponse, ProfessionalEscalation, FollowUpSupport, Documentation
  ├── ReAct loop: detect → response → escalate/follow-up
  ├── Interrupt capability (dừng mọi agent khác)
  ├── Học từ: 4 crisis nodes hiện tại
  └── Tests: unit + integration (crisis flow)

Bước 2.2: Implement SupportAgent
  ├── GOAL: Hỗ trợ sức khỏe tinh thần (non-disorder)
  ├── Skills: CopingRetrieval, EmotionalSupport, PsychoEducation, SkillBuilding, AnswerFormatting
  ├── ReAct loop: assess → retrieve strategies → generate empathetic response
  ├── Học từ: normal_coping_retrieval + answer_with_graph nodes
  └── Tests: unit + integration

Bước 2.3: Test interrupt flow
  ├── CrisisAgent → emit_interrupt → mọi agent dừng
  └── Unit test interrupt propagation

Deliverable: 2 agents hoạt động, có thể handle real conversations
```

### Phase 3: Domain Agents — TheoryAgent + TreatmentAgent (Tuần 5-6)

```
Mục tiêu: Implement 2 agents cho knowledge-heavy tasks

Bước 3.1: Implement TheoryAgent
  ├── GOAL: Giải thích kiến thức tâm lý học
  ├── Skills: ConceptRetrieval, EducationalExplanation, AnswerFormatting
  ├── ReAct loop: understand question → retrieve theory → generate explanation
  ├── KHÔNG cần slot filling (lý thuyết không cần thông tin cá nhân)
  ├── Học từ: theoretical_retrieval + answer_with_theoretical nodes
  └── Tests

Bước 3.2: Implement TreatmentAgent
  ├── GOAL: Cung cấp phác đồ điều trị
  ├── Skills: TreatmentRetrieval, TreatmentPlanning, PatientGuidance, AnswerFormatting
  ├── ReAct loop: understand condition → retrieve treatments → rank by evidence → format guidance
  ├── Học từ: treatment_retrieval + answer_with_treatment nodes
  └── Tests

Bước 3.3: Implement Shared Retrieval Skills
  ├── EmbeddingSkill (encode_e5)
  ├── GraphExpansionSkill (neo4j)
  ├── RerankingSkill (cohere)
  ├── L1 + L2 caching
  └── Benchmark before/after latency

Deliverable: 4 agents hoạt động, cover 80% user intents
```

### Phase 4: Domain Agent — DiagnosticAgent + SupervisorAgent (Tuần 7-8)

```
Mục tiêu: Implement agent phức tạp nhất (Diagnostic) + routing layer

Bước 4.1: Implement DiagnosticAgent (phức tạp nhất)
  ├── GOAL: Chuẩn đoán rối loạn tâm lý (DSM-5 based)
  ├── Skills: SymptomExtraction, DiagnosticRetrieval, ClinicalReasoning, ResponseDrafting
  ├── ReAct loop: extract slots → if insufficient ask follow-up → retrieve disorders →
  │              apply clinical reasoning → generate conclusion → format answer
  ├── Tự quyết định khi nào cần thêm thông tin
  ├── Tự gọi retrieval + reasoning + drafting (không cần agent trung gian)
  ├── Học từ: slot_filling + assessment + diagnostic_retrieval + disease_conclusion nodes
  └── Tests: comprehensive unit + integration

Bước 4.2: Implement SupervisorAgent
  ├── GOAL: Route intent → đúng Domain Agent (CHỈ routing, không điều khiển từng bước)
  ├── Skills: IntentClassification, PreliminaryContext
  ├── SHARED MEMORY TOOLS: save_to_buffer, get_context, merge_slots
  ├── Routing logic: crisis → Diagnostic → Theory → Treatment → Support → fallback
  ├── MessageBus: emit message to correct agent, KHÔNG gọi lần lượt
  ├── Học từ: translate_question + classify_type_query + router nodes
  └── Tests: routing logic unit tests

Bước 4.3: Implement MemoryService
  ├── KHÔNG phải Agent (không có ReAct loop)
  ├── CRUD operations: buffer, summary, slots
  ├── L2: Redis cache, L3: PostgreSQL checkpoint
  ├── Inject vào constructor của mọi Domain Agent
  ├── Học từ: conversation_memory node
  └── Tests

Bước 4.4: Implement MessageBus Interrupt
  ├── CrisisAgent → priority=critical → broadcast interrupt
  ├── Any agent nhận interrupt → hủy current task
  └── Unit test interrupt propagation

Deliverable: Toàn bộ 5 Domain Agents + Supervisor + MemoryService hoạt động
```

### Phase 5: Integration & Optimization (Tuần 11-12)

```
Mục tiêu: Kết nối tất cả + optimize + LangSmith

Bước 5.1: Integration Tests
  ├── Agent ↔ Agent integration tests
  ├── Full conversation flows
  ├── E2E với Playwright

Bước 5.2: LangSmith Integration
  ├── Setup client + project
  ├── Instrument all agents
  ├── Instrument all tools
  └── Dashboard verification

Bước 5.3: Performance Optimization
  ├── Enable L1/L2 caching
  ├── Verify parallel execution
  ├── Benchmark comparison
  └── Streaming SSE endpoint

Bước 5.4: Docker + CI/CD
  ├── Update Dockerfile
  ├── docker-compose.yml
  ├── GitHub Actions pipeline
  └── Smoke tests

Deliverable: System hoạt động end-to-end, đủ production-ready
```

### Phase 6: Documentation & Polish (Tuần 13)

```
Mục tiêu: Hoàn thiện tài liệu

Bước 6.1: Update ARCHITECTURE.md
  ├── New architecture diagram
  ├── Agent definitions
  ├── Communication patterns
  └── Migration notes

Bước 6.2: API Documentation
  ├── OpenAPI/Swagger
  ├── Endpoint docs
  └── Example requests/responses

Bước 6.3: Agent Developer Guide
  ├── How to add new agent
  ├── How to add new tool
  ├── How to test
  └── Best practices

Bước 6.4: Runbook
  ├── Deployment guide
  ├── Monitoring & alerting
  ├── Troubleshooting
  └── Rollback procedures

Deliverable: Đầy đủ tài liệu cho team vận hành + phát triển
```

---

## 4. Migration Guide — Từ Workflow Sang Multi-Agent

### 4.1 Migration Strategy: Incremental (Không Big Bang)

```
Không refactor tất cả cùng lúc. Thay từng phần, giữ system chạy.

Strategy: "Strangler Fig Pattern"
- Giữ workflow cũ chạy song song
- Thay từng node → agent mới
- Validate kết quả trước khi continue
- Remove workflow node cũ khi agent tương đương stable
```

### 4.2 Migration Mapping: Node → Domain Agent / Service

| Workflow Node (Cũ) | → Thay thế bởi | Migration Step |
|--------------------|-----------------|----------------|
| `translate_question` | **SupervisorAgent** (IntentClassification skill) | Phase 4 |
| `classify_type_query` | **SupervisorAgent** (IntentClassification skill) | Phase 4 |
| `router` + `crisis_router` | **SupervisorAgent** (routing logic, 1 lần duy nhất) | Phase 4 |
| `safety_check` + 4 crisis nodes | **CrisisAgent** (Interrupt capability, Priority: CRITICAL) | Phase 2 |
| `slot_filling` + `request_more_info` | **DiagnosticAgent** (SymptomExtraction skill) | Phase 4 |
| `assessment` | **DiagnosticAgent** (ClinicalReasoning skill) | Phase 4 |
| `diagnostic_retrieval` + `disease_conclusion` | **DiagnosticAgent** (DiagnosticRetrieval skill) | Phase 4 |
| `normal_coping_retrieval` | **SupportAgent** (CopingRetrieval skill) | Phase 2 |
| `adjustment_retrieval` | **SupportAgent** (PsychoEducation skill) | Phase 2 |
| `theoretical_retrieval` + `answer_with_theoretical` | **TheoryAgent** (ConceptRetrieval + AnswerFormatting skills) | Phase 3 |
| `treatment_retrieval` + `answer_with_treatment` | **TreatmentAgent** (TreatmentRetrieval + AnswerFormatting skills) | Phase 3 |
| `answer_with_graph` | **DiagnosticAgent** (ResponseDrafting skill) hoặc domain agent tương ứng | Phase 4 |
| `graph_retrieval` | **Shared Retrieval Skills** (Embedding, GraphExpansion, Reranking, HybridSearch) | Phase 3 |
| `conversation_memory` | **MemoryService** (trong services/, KHÔNG phải Agent) | Phase 4 |
| `not_mental_health` | **SupportAgent** (fallback route) | Phase 2 |

> **Ghi chú:** 24 workflow nodes → **5 Domain Agents + 1 Supervisor + 1 MemoryService**. Skills được nhúng bên trong mỗi Domain Agent — không có agent trung gian.

### 4.3 Backward Compatibility Layer

```python
# ai/engine.py — LEGACY WRAPPER
# Giữ nguyên interface cũ: run_rag_workflow()
# Bên trong: gọi SupervisorAgent (không phải Orchestrator)

async def run_rag_workflow(
    conversation_id: str,
    message: str,
    thread_id: Optional[str] = None,
) -> dict:
    """
    LEGACY ENTRY POINT.
    Wrapper quanh SupervisorAgent.
    Đảm bảo backward compatibility với existing API.
    """
    supervisor = get_supervisor()
    result = await supervisor.run(
        user_message=message,
        conversation_id=conversation_id,
    )
    return result


# ChatService: swap call
# BEFORE:
# async def process_message(...):
#     result = await run_rag_workflow(conv_id, message)

# AFTER:
# async def process_message(...):
#     result = await supervisor.run(conv_id, message)
#     # Same interface, internally uses domain-centric multi-agent
```

---

## 5. Performance Targets & KPIs

### 5.1 Performance KPIs

| Metric | Baseline (Workflow) | Target (Multi-Agent) | Measurement |
|--------|:---:|:---:|---|
| Avg response time | 3.5s | < 2s | p50 API latency |
| p95 response time | 5s | < 3s | p95 |
| Crisis detection | 500ms | < 100ms | CrisisAgent.run() |
| L2 cache hit rate | 0% | > 40% | Redis stats |
| L1 cache hit rate | 0% | > 60% | Per-agent stats |
| Parallel efficiency | 0% | > 80% | vs sequential |
| LangSmith coverage | 0% | 100% | All agents traced |
| Error rate | < 1% | < 0.5% | 5xx errors |
| E2E test pass rate | N/A | > 95% | Nightly run |

### 5.2 Monitoring Dashboard

```python
# ai/modules/shared/metrics.py

class AgentMetrics:
    """
    Metrics collector cho agents.
    Exposed qua /metrics endpoint (Prometheus format).
    """

    def __init__(self):
        self._counters: Dict[str, int] = Counter()
        self._histograms: Dict[str, Histogram] = {}
        self._gauges: Dict[str, Gauge] = {}

    def record_agent_call(self, agent_id: str, latency: float, success: bool):
        self._counters["agent_calls_total"].labels(agent_id, "success" if success else "error").inc()
        self._histograms["agent_latency_seconds"].labels(agent_id).observe(latency)

    def record_cache_hit(self, level: str, hit: bool):
        self._counters["cache_hits_total"].labels(level, "hit" if hit else "miss").inc()

    def record_message_bus(self, message_type: str, latency: float):
        self._histograms["message_bus_latency_seconds"].labels(message_type).observe(latency)


# Prometheus metrics endpoint
@router.get("/metrics")
async def metrics():
    return Response(
        content=generate_prometheus_output(metrics_collector),
        media_type="text/plain",
    )
```

---

## 6. Rollback Plan

```
Nếu multi-agent system gặp sự cố trong production:

IMMEDIATE (0-5 phút):
1. Revert Docker image tag về previous version (workflow-based)
   docker tag mhrag/backend:stable mhrag/backend:current
   docker pull mhrag/backend:stable
   kubectl rollout undo deployment/backend

2. Rollback Nginx config nếu cần

3. Verify: check /health endpoint, check error logs

SHORT-TERM (5-30 phút):
4. Analyze crash: LangSmith traces, logs, metrics
5. Identify failing Domain Agent or MemoryService
6. Fix trên branch riêng

MEDIUM-TERM (30 phút - 2 giờ):
7. Unit test + integration test locally
8. Deploy lên staging
9. E2E smoke test
10. Deploy lại production

GIT STRATEGY:
- main: production stable
- develop: integration tested
- feature/refactor-multiagent: development
- Tag stable version trước mỗi deploy
```

---

## 7. Developer Onboarding Guide

### 7.1 Adding a New Agent

```python
# 1. Tạo module mới
# ai/modules/new_agent/

# new_agent/__init__.py
from .new_agent import NewAgent
__all__ = ["NewAgent"]

# new_agent/new_agent.py
from ai.src.agents.shared.base_agent import BaseAgent
from ai.src.agents.shared.message import AgentMessage
from ai.src.agents.shared.state import GlobalState
from typing import Any

class NewAgent(TaskAgent):
    """
    Mô tả ngắn gọn chức năng.
    """

    AGENT_ID = "new_agent"
    TOOLS = ["tool_a", "tool_b"]

    async def _run_impl(self, input: Any, gs: GlobalState) -> Any:
        # Implement ReAct loop logic
        return {"result": "success"}

# 2. Register trong AgentManager
# ai/modules/agent_manager.py
AGENTS = {
    # ... existing
    "new_agent": lambda: NewAgent(llm, ...),
}

# 3. Thêm subscription trong SupervisorAgent
# ai/modules/supervisor/supervisor_agent.py
self.bus.subscribe(AGENTS.NEW_AGENT, ["relevant_event_types"])

# 4. Viết tests
# backend/tests/unit/agents/new_agent/test_new_agent.py
# backend/tests/integration/agents/test_new_agent_integration.py

# 5. Chạy: pytest backend/tests/unit/agents/new_agent/
# 6. Commit + push
```

### 7.2 Adding a New Tool to Existing Agent

```python
# 1. Thêm tool function vào Skill của Domain Agent
class DiagnosticAgent(BaseAgent):
    """DiagnosticAgent — Goal: Chuẩn đoán rối loạn tâm thần (DSM-5 based)"""

    async def _tool_new_diagnostic_tool(self, query: str, filters: dict) -> dict:
        """Tool: advanced diagnostic search with disorder scoring."""
        return {"result": "..."}

# 2. Register tool trong skill
# ai/modules/diagnostic/skills/diagnostic_retrieval.py

# 3. Viết tests
# 4. Update LangSmith tracing
```

### 7.3 Code Style Guide

```python
# ai/modules/shared/constants.py

# Agent IDs — 5 Domain Agents + 1 Supervisor
AGENTS = {
    "supervisor": "supervisor",          # Router — entry point
    "crisis": "crisis",                  # Crisis response (interrupt-capable)
    "support": "support",               # Non-disorder coping + emotional support
    "theory": "theory",                 # Psychology theory explanations
    "treatment": "treatment",           # Treatment plans & guidance
    "diagnostic": "diagnostic",         # DSM-5 diagnosis + symptom extraction
}

# MemoryService lives in services/, NOT an agent
MEMORY_SERVICE_ID = "memory_service"

# Priority levels
class Priority:
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"  # Safety interrupt

# Message types
class MessageType:
    TASK = "task"
    RESULT = "result"
    EVENT = "event"
    ERROR = "error"
    INTERRUPT = "interrupt"

# Naming conventions
# - Agent classes: PascalCase (SupervisorAgent, CrisisAgent, DiagnosticAgent, ...)
# - Tool methods: _tool_<name> (_tool_hybrid_search)
# - Agent IDs: snake_case ("supervisor", "diagnostic_agent", "crisis_agent", ...)
# - State keys: snake_case (conversation_buffer, crisis_level)
# - Test files: test_<module>.py
```

---

## 8. Risk Register

| Risk | Impact | Probability | Mitigation |
|------|--------|:---:|---|
| LLM-based Supervisor routing unreliable | HIGH | MEDIUM | Fallback rules, guardrails, extensive testing |
| Message bus bottleneck under high load | MEDIUM | LOW | Redis-based bus (future), concurrency limits |
| Agent state leaks between conversations | CRITICAL | LOW | Thread isolation + per-conv agent instances |
| Circular dependencies in agent calls | HIGH | LOW | Modular architecture + import rules |
| LangSmith cost explosion (too many traces) | MEDIUM | MEDIUM | Sampling, filter by agent type |
| Redis cache inconsistency | MEDIUM | LOW | PostgreSQL as source of truth, async sync |
| Neo4j/Milvus downtime | HIGH | LOW | Circuit breaker, graceful degradation |
| LLM provider (Gemini) rate limit | HIGH | MEDIUM | Rate limiter, retry with backoff, queue |
| Migration breaks existing API contract | HIGH | LOW | Backward compatibility wrapper, E2E tests |

---

## 9. Checklist Hoàn Thành Refactor

```
□ Phase 1: Foundation
  □ MessageBus với unit tests
  □ BaseAgent abstract class
  □ GlobalState schema
  □ AgentCache (L1 + L2)
  □ Event emitter

□ Phase 2: CrisisAgent + SupportAgent
  □ CrisisAgent + tests (Detection, Response, Escalation, FollowUp)
  □ SupportAgent + tests (Coping, EmotionalSupport, SkillBuilding)
  □ Interrupt flow working
  □ Shared Retrieval Skills (Embedding, Graph, Reranking)

□ Phase 3: TheoryAgent + TreatmentAgent
  □ TheoryAgent + tests (ConceptRetrieval, EducationalExplain)
  □ TreatmentAgent + tests (TreatmentRetrieval, Planning, Guidance)
  □ Shared Retrieval Skills benchmarked

□ Phase 4: DiagnosticAgent + SupervisorAgent + MemoryService
  □ DiagnosticAgent + tests (SymptomExtraction, ClinicalReasoning)
  □ SupervisorAgent + tests (IntentClassification, Routing)
  □ MemoryService + tests (buffer, summary, slots, Redis, PostgreSQL)
  □ MessageBus interrupt working
  □ AgentManager + tests

□ Phase 5: Integration + Optimization
  □ LangSmith tracing all 5 agents
  □ Performance benchmark (3.5s → 1.5s)
  □ L2 cache hit rate > 40%
  □ Streaming SSE working
  □ Full conversation flows (E2E)
  □ Docker + CI/CD pipeline green

□ Phase 6: Documentation
  □ ARCHITECTURE.md updated (domain-centric)
  □ API docs complete
  □ Developer onboarding guide
  □ Runbook + rollback plan

□ Pre-Production
  □ Load test (100 concurrent users)
  □ Security audit (JWT, rate limiting)
  □ Penetration test (safety system)
  □ Staging full smoke test
```

---

*Lưu �u: File này là Part 6 — Documentation Tổng Hợp. Hoàn thành!*
