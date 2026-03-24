# Mental Health Hybrid RAG — Refactor Plan
## Multi-Agent System Architecture

> **Kế hoạch refactor từ LangGraph StateGraph Workflow → True Multi-Agent System**

---

## 📋 Mục Lục

| Phần | File | Nội dung |
|------|------|----------|
| **Tổng quan & Agent Definitions** | `REFACTOR-PLAN-PART1.md` | Định nghĩa 5 Domain Agents (Supervisor/Diagnostic/Theory/Treatment/Support/Crisis), 1 Service (MemoryService), Skills embedded in agents, module structure |
| **State Management & Memory** | `REFACTOR-PLAN-PART2.md` | GlobalState + Agent-local state, MessageBus, Checkpointer interface, MemoryService (Service, not Agent) |
| **Communication Layer** | `REFACTOR-PLAN-PART3.md` | SupervisorAgent (Router), Message Passing patterns, Domain Agents, Crisis interrupt, Error handling |
| **Performance Optimization** | `REFACTOR-PLAN-PART4.md` | 3-level caching (L1/L2/L3), parallel execution, latency optimization, streaming |
| **Testing & Deployment** | `REFACTOR-PLAN-PART5.md` | Unit/Integration/E2E tests, LangSmith tracing, Docker, CI/CD pipeline |
| **Documentation Tổng Hợp** | `REFACTOR-PLAN-PART6.md` | Architecture diagram, Migration guide, 13-week roadmap, KPIs, Risk register |

---

## 🚀 Đọc Nhanh

### Muốn hiểu nhanh về system mới?
→ Đọc `REFACTOR-PLAN-PART1.md` (Section 1-3) + `REFACTOR-PLAN-PART6.md` (Section 1-2)

### Muốn bắt đầu implementation?
→ Đọc `REFACTOR-PLAN-PART6.md` (Section 3: Implementation Roadmap)

### Muốn debug hoặc thêm agent mới?
→ Đọc `REFACTOR-PLAN-PART3.md` (Section 1-3) + `REFACTOR-PLAN-PART6.md` (Section 7)

### Muốn optimize performance?
→ Đọc `REFACTOR-PLAN-PART4.md`

### Muốn setup CI/CD và deploy?
→ Đọc `REFACTOR-PLAN-PART5.md` (Section 5-7)

---

## 📁 Cấu Trúc Files

```
docs/
├── ARCHITECTURE.md                    # Kiến trúc CŨ (workflow-based)
├── REFACTOR-PLAN-PART1.md             # ✅ Phần 1: Agents & Overview
├── REFACTOR-PLAN-PART2.md             # ✅ Phần 2: State & Memory
├── REFACTOR-PLAN-PART3.md             # ✅ Phần 3: Communication
├── REFACTOR-PLAN-PART4.md             # ✅ Phần 4: Performance
├── REFACTOR-PLAN-PART5.md             # ✅ Phần 5: Testing & Deploy
├── REFACTOR-PLAN-PART6.md             # ✅ Phần 6: Documentation
└── REFACTOR-PLAN-INDEX.md            # ← File này
```

---

## 🔑 Tóm Tắt Key Changes

### 24 Workflow Nodes → 5 Domain Agents + 1 Service + 1 Supervisor

```
THIẾT KẾ MỚI: Domain-Centric
1 Agent = 1 Goal + N Skills + N Tools

CŨ: 24 nodes → Orchestrator gọi lần lượt
MỚI: Supervisor (Router) → 5 Domain Agents (TỰ HOÀN THÀNH task từ A→Z)

1. SupervisorAgent      — Router: đọc intent → gửi đến đúng Domain Agent (1 lần)
2. DiagnosticAgent     — Goal: Chuẩn đoán bệnh (SymptomExtraction + DiagnosticRetrieval + ClinicalReasoning + ResponseDrafting)
3. TheoryAgent        — Goal: Giải thích lý thuyết (ConceptRetrieval + EducationalExplain + AnswerFormatting)
4. TreatmentAgent     — Goal: Phác đồ điều trị (TreatmentRetrieval + Planning + Guidance + Formatting)
5. SupportAgent       — Goal: Hỗ trợ tinh thần (CopingRetrieval + EmotionalSupport + SkillBuilding)
6. CrisisAgent        — Goal: Ứng phó khủng hoảng (Interrupt-capable, Priority=CRITICAL)
+ MemoryService       — Service (NOT Agent): buffer/summary/slots CRUD, L2 Redis, L3 PostgreSQL

Mỗi agent có: Local Memory (ephemeral) + Shared Memory qua MemoryService
```

### State Management

```
CŨ: Global KGState TypedDict (duy nhất)
MỚI: 3-layer state
  - GlobalState: shared across all agents (PostgreSQL persisted)
  - Agent-Local State: private per agent (ephemeral)
  - Agent Result State: task output tracking
```

### Communication

```
CŨ: Implicit state dict passing through nodes
MỚI: Explicit Message Bus (async pub/sub)
  - Priority queues (normal/high/critical)
  - Critical = Safety interrupt (dừng mọi agent khác)
  - Event subscriptions
```

### Performance

```
CŨ: Sequential, no caching, no parallelism
MỚI:
  - 3-level cache: L1 (agent) + L2 (Redis) + L3 (PostgreSQL)
  - Parallel execution: translate+safety, multi-collection retrieval
  - Async non-blocking checkpoint save
  - Streaming SSE response
  - Target: 3.5s → 1.5s (-57%)
```

### Tech Stack (Giữ nguyên)

| Component | Technology | Change? |
|-----------|-----------|---------|
| Backend | FastAPI + Python 3.11 | Minimal |
| Workflow Engine | LangGraph | Replaced by multi-agent |
| LLM | Gemini 2.0 Flash | Same |
| Embedding | E5 Large v2 | Same |
| Vector DB | Milvus | Same |
| Graph DB | Neo4j | Same |
| State DB | PostgreSQL | Extended (checkpointer) |
| Cache | Redis | New (L2) |
| Tracer | LangSmith | New |
| Container | Docker | Updated |

---

## ⏱️ Timeline — Domain-Centric

```
Tuần 1-2:   Phase 1 — Foundation (MessageBus, BaseAgent, State)
Tuần 3-4:   Phase 2 — CrisisAgent + SupportAgent
Tuần 5-6:   Phase 3 — TheoryAgent + TreatmentAgent
Tuần 7-8:   Phase 4 — DiagnosticAgent + SupervisorAgent + MemoryService
Tuần 9-10:  Phase 5 — Integration + LangSmith + Optimization
Tuần 11:    Phase 6 — Documentation
─────────────────────────────────────────
Total: 11 tuần
```

---

## ✅ Definition of Done

- [x] Plan đầy đủ cho tất cả 6 phần
- [x] Architecture diagram tổng hợp
- [x] Agent definitions + tool specifications
- [x] State management design
- [x] Communication patterns
- [x] Caching + performance strategy
- [x] Testing strategy (unit/integration/E2E)
- [x] LangSmith integration plan
- [x] Docker + CI/CD pipeline
- [x] Migration guide (incremental, no big bang)
- [x] Implementation roadmap 13 tuần
- [x] Risk register
- [x] Developer onboarding guide
