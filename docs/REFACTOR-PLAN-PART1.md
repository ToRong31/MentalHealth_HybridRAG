# Mental Health Hybrid RAG — Refactor Plan
## Phần 1: Tổng Quan Kiến Trúc & Định Nghĩa Agents

> **1 Agent = 1 Goal + Nhiều Skills + Nhiều Tools**
> Domain-centric: Mỗi agent sở hữu 1 mục đích người dùng hoàn chỉnh, tự quyết định cách hoàn thành goal.
> Memory là Service + Shared Tools, KHÔNG phải Agent.

---

## 1. Tại Sao Cần Refactor

### Hiện trạng (Workflow-based)
```
24 nodes cố định + conditional edges → deterministic flow
Router là hàm if/else → gọi lần lượt từng node
Không có tool-calling, không ReAct loop
Orchestrator = "god object" điều khiển mọi thứ
```

### Mục tiêu (True Multi-Agent, Domain-Centric)
```
- Mỗi agent sở hữu 1 mục đích người dùng hoàn chỉnh
- Agent tự quyết định dùng skill/tool nào để hoàn thành goal
- Supervisor chỉ ROUTE (đọc intent → gửi đúng agent), không điều khiển từng bước
- Không có "RetrievalAgent" — retrieval chỉ là 1 skill, không phải agent
- Memory là Service, không phải Agent
```

---

## 2. So Sánh Kiến Trúc

| Khía cạnh | Workflow (Cũ) | Multi-Agent (Mới) |
|-----------|:---:|:---:|
| **Execution** | Sequential nodes | Domain agents with ReAct loop |
| **Ownership** | Không ai sở hữu task hoàn chỉnh | Mỗi agent sở hữu 1 intent từ đầu đến cuối |
| **Routing** | Router if/else → gọi nhiều agents lần lượt | Supervisor route 1 lần → agent tự lo từ A→Z |
| **Agent count** | 24 nodes | **5 domain agents + 1 supervisor** |
| **Local Memory** | Không có | **Agent-private ephemeral state (ReAct loop, intermediate results, caches)** |
| **Shared Memory** | Global KGState | **MemoryService (persistent) — buffer, summary, slots, crisis state** |
| **Retrieval** | Node riêng | **Skill** bên trong agent cần nó |
| **Parallelism** | Sequential | Domain agents có thể chạy song song |
| **Avg latency** | ~3500ms | ~1500ms |

---

## 3. Kiến Trúc Tổng Quan — Domain-Centric

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           USER (React Frontend)                          │
│                    Message: "Tôi bị lo âu về công việc"                 │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ HTTP/JWT
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      SupervisorAgent (ROUTER)                             │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │ GOAL: Đọc intent của user → route đến đúng Domain Agent           │   │
│  │ SKILL: IntentRouting                                               │   │
│  │   ├── Tool: classify_intent() → "diagnostic"|"theory"|"treatment"|"support"|"crisis"│
│  │   ├── Tool: detect_language()                                      │   │
│  │   └── Tool: extract_preliminary_slots()                            │   │
│  │ SHARED TOOLS: (Memory)                                            │   │
│  │   ├── Tool: save_to_buffer()                                       │   │
│  │   ├── Tool: get_context()                                          │   │
│  │   └── Tool: merge_slots()                                         │   │
│  └───────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ Route 1 lần → gửi message
                                 ▼
         ┌───────────────────────────────────────────────────────────────┐
         │                    MESSAGE BUS (pub/sub)                       │
         │  Priority: normal | high | CRITICAL (Safety interrupt)        │
         └──────────────────────────┬────────────────────────────────────┘
                                    │
      ┌─────────────┬───────────────┼───────────────┬─────────────┐
      ▼             ▼               ▼               ▼             ▼
┌──────────┐ ┌──────────┐  ┌──────────────┐ ┌──────────┐ ┌──────────┐
│Diagnostic│ │  Theory  │  │  Treatment   │ │  Support │ │  Crisis  │
│  Agent   │ │  Agent  │  │    Agent     │ │   Agent  │ │   Agent  │
│          │ │          │  │              │ │          │ │          │
│ Tự lo   │ │ Tự lo    │  │ Tự lo       │ │ Tự lo    │ │ Ưu tiên  │
│ từ A→Z  │ │ từ A→Z   │  │ từ A→Z      │ │ từ A→Z   │ │ tuyệt đối│
└──────────┘ └──────────┘  └──────────────┘ └──────────┘ └──────────┘

**5 Domain Agents — Mỗi agent tự quyết định:**
- Dùng retrieval hay không? Retrieval thế nào?
- Dùng assessment hay không?
- Dùng drafting skill hay không?
- Gọi shared memory tools khi nào?
- **Mỗi agent có Local Memory riêng + Shared Memory chung**

---

## 4. Memory Architecture — Local + Shared

### 4.1 Hai Loại Memory

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             MỖI AGENT                                       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ LOCAL MEMORY (Ephemeral — agent-private, không chia sẻ)            │   │
│  │                                                                       │   │
│  │ • ReAct loop state: current step, iteration count                  │   │
│  │ • Intermediate tool results: retrieval hits chưa final           │   │
│  │ • Agent-local cache: embedding cache, rerank cache               │   │
│  │ • Per-turn context: slots extracted trong turn hiện tại           │   │
│  │ • Confidence scores: tạm thời, chưa finalize                       │   │
│  │                                                                       │   │
│  │ ⚠️ Cleared khi ReAct loop kết thúc (end of turn)                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ SHARED MEMORY (Persistent — accessible by ALL agents)             │   │
│  │                                                                       │   │
│  │ • Conversation buffer: last 3 Q&A pairs                           │   │
│  │ • Summary: older turns (LLM-generated)                            │   │
│  │ • Accumulated slots: emotion, trigger, duration, intensity...     │   │
│  │ • Crisis state: is_high_risk, crisis_level, crisis_stage...       │   │
│  │ • Conversation metadata: language, conversation_id, user_id         │   │
│  │                                                                       │   │
│  │ ⚠️ Persisted in PostgreSQL (L3), cached in Redis (L2)            │   │
│  │ ⚠️ Any agent có thể đọc/ghi khi cần                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ MEMORYSERVICE (Service — Centralized CRUD, NOT Agent)              │   │
│  │                                                                       │   │
│  │ Được inject vào mọi agent. Cung cấp:                               │   │
│  │ • Shared memory operations (CRUD)                                 │   │
│  │ • L2: Redis cache                                                  │   │
│  │ • L3: PostgreSQL checkpoint (durable)                              │   │
│  │                                                                       │   │
│  │ Agents gọi MemoryService qua SHARED MEMORY TOOLS:                  │   │
│  │ • save_to_buffer()        • get_context()                         │   │
│  │ • merge_slots()           • get_accumulated_slots()              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Ví Dụ: DiagnosticAgent

```
DiagnosticAgent đang handle user message: "Tôi bị lo âu 2 tuần rồi"

═══════════════ LOCAL MEMORY (Agent-Private) ════════════════
{
    "react_step": 2,                    # Đang ở step 2 của ReAct loop
    "iteration_count": 1,
    "current_skill": "SymptomExtraction",
    "retrieval_candidates": [...],    # Intermediate: retrieval chưa final
    "candidate_disorders": [...],     # Intermediate: disorders đang được score
    "confidence_temp": 0.75,           # Confidence chưa finalize
    "embedding_cache": {...},         # Local cache
}
═══════════════════════════════════════════════════════════════


═══════════════ SHARED MEMORY (All Agents) ═══════════════════
{
    "conversation_buffer": [           # Last 3 turns
        {"role": "user", "content": "Tôi bị lo âu 2 tuần rồi"},
        {"role": "assistant", "content": "Bạn có thể mô tả..."},
    ],
    "summary": "User mentioned work stress, difficulty sleeping...",
    "slots": {                         # Accumulated across turns
        "emotion": "lo âu",
        "duration": "2 tuần",
        "trigger": "công việc",
        "intensity": "cao",           # ← DiagnosticAgent vừa extract được
        # "sleep": ??? (chưa có)
    },
    "crisis_state": {
        "is_high_risk": false,
        "crisis_level": "none",
    },
    "language": "vi",
}
═══════════════════════════════════════════════════════════════

DiagnosticAgent gọi SHARED MEMORY TOOLS:
  • get_accumulated_slots() → đọc slots từ Shared Memory
  • merge_slots({"intensity": "cao"}) → ghi vào Shared Memory
  • get_context() → đọc buffer + summary + slots cùng lúc
  • save_to_buffer() → sau khi trả lời xong

Sau khi ReAct loop kết thúc:
  • LOCAL MEMORY bị cleared
  • SHARED MEMORY được persisted (PostgreSQL + Redis)
```

### 4.3 Memory Tool Definitions (Shared — mọi Agent đều có)

```python
# Mọi Agent đều có quyền gọi các SHARED MEMORY TOOLS này

SHARED_MEMORY_TOOLS = {
    # === Buffer ===
    "save_to_buffer": {
        "args": "(conv_id, role, content, metadata)",
        "desc": "Lưu 1 interaction vào buffer. Tự prune nếu > 3."
    },
    "get_buffer": {
        "args": "(conv_id)",
        "desc": "Đọc last 3 Q&A pairs."
    },

    # === Context ===
    "get_context": {
        "args": "(conv_id)",
        "desc": "Đọc buffer + summary + slots cùng lúc, format thành string."
    },

    # === Slots ===
    "get_accumulated_slots": {
        "args": "(conv_id)",
        "desc": "Đọc tất cả slots đã collect từ đầu conversation."
    },
    "merge_slots": {
        "args": "(conv_id, new_slots)",
        "desc": "Merge slots mới vào existing slots."
    },
    "get_slot_sufficiency": {
        "args": "(conv_id)",
        "desc": "Check xem slots đủ chưa (5/7 required)."
    },

    # === Summary ===
    "append_to_summary": {
        "args": "(conv_id, summary_text)",
        "desc": "Append text vào summary."
    },
    "get_summary": {
        "args": "(conv_id)",
        "desc": "Đọc summary."
    },

    # === Crisis ===
    "get_crisis_state": {
        "args": "(conv_id)",
        "desc": "Đọc crisis state."
    },
    "update_crisis_state": {
        "args": "(conv_id, crisis_state)",
        "desc": "Update crisis state."
    },
}
```

### 4.4 Bảng So Sánh: Local vs Shared Memory

| Khía cạnh | Local Memory | Shared Memory |
|-----------|:---:|:---:|
| **Scope** | Agent-private | All agents |
| **Lifetime** | 1 ReAct loop (end of turn) | Full conversation |
| **Persistence** | KHÔNG (ephemeral) | PostgreSQL (L3) + Redis (L2) |
| **Access** | Chỉ agent sở hữu | Mọi agent đều đọc/ghi |
| **Use case** | ReAct state, intermediate results, caches | Buffer, summary, slots, crisis state |
| **Cleared** | Khi ReAct loop kết thúc | Khi conversation kết thúc |
| **Conflict risk** | KHÔNG (private) | Có — cần semaphore khi ghi |

### 4.5 SupervisorAgent SHARED MEMORY TOOLS

```
SupervisorAgent
├── SHARED MEMORY TOOLS (đặc biệt quan trọng cho Supervisor):
│   ├── Tool: save_to_buffer()        → Lưu user message + assistant response
│   ├── Tool: get_context()           → Đọc buffer + summary + slots
│   ├── Tool: merge_slots()           → Merge preliminary slots
│   ├── Tool: get_accumulated_slots() → Đọc slots đã có
│   └── Tool: get_crisis_state()     → Check crisis trước khi route
│
├── LOCAL MEMORY:
│   ├── "preliminary_slots": {}       → Slots extract trước khi route
│   ├── "routing_confidence": 0.0    → Confidence của routing decision
│   └── "route_history": []          → Lịch sử routing (debugging)
│
└── KHÔNG tự persist checkpoint — MemoryService làm việc đó
```

---

## 5. Định Nghĩa Chi Tiết Từng Agent

### 4.1 SupervisorAgent

```
┌──────────────────────────────────────────────────────────────────┐
│ SupervisorAgent                                                     │
│ GOAL: Đọc intent người dùng → route đến Domain Agent đúng        │
│       (chỉ routing, KHÔNG điều khiển từng bước)                  │
├──────────────────────────────────────────────────────────────────┤
│ ROUTING FLOW (3 bước):                                             │
│   Step 1: Crisis Safety Gate → keyword match (O(1), NO LLM)      │
│           Nếu matched → CrisisAgent (CRITICAL, done)              │
│   Step 2: LLM Intent Classify → confidence, reasoning             │
│           theory | treatment | personal | off_topic               │
│   Step 3: Personal → LLM sub-classify → Diagnostic | Support    │
├──────────────────────────────────────────────────────────────────┤
│ SKILLS:                                                              │
│   Skill: IntentRouting                                               │
│     ├── Tool: crisis_safety_gate() → bool (keyword match, fast)   │
│     ├── Tool: classify_intent() → LLM → intent + confidence       │
│     ├── Tool: subclassify_personal() → LLM → diagnostic|support  │
│     ├── Tool: detect_language() → "vi"|"en"                       │
│     └── Tool: detect_crisis_urgency() → bool (parallel w/ step 1) │
│                                                                     │
│   Skill: PreliminaryContext                                         │
│     ├── Tool: extract_immediate_slots() → basic slots từ message │
│     ├── Tool: get_conversation_history() → recent turns            │
│     └── Tool: check_recent_crisis() → bool                        │
├──────────────────────────────────────────────────────────────────┤
│ SHARED TOOLS (Memory):                                              │
│   ├── Tool: save_to_buffer(conv_id, role, content, metadata)        │
│   ├── Tool: get_context(conv_id) → full context for LLM            │
│   ├── Tool: merge_slots(conv_id, new_slots) → merge into state    │
│   └── Tool: get_accumulated_slots(conv_id) → all slots so far     │
├──────────────────────────────────────────────────────────────────┤
│ OUTPUT: Một message gửi đến đúng Domain Agent với:                │
│   - original_message, translated_message, language, preliminary_slots│
│   - conversation_context                                           │
│   - routing_reasoning (LLM reasoning output)                      │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 DiagnosticAgent

```
┌──────────────────────────────────────────────────────────────────┐
│ DiagnosticAgent                                                     │
│ GOAL: Chuẩn đoán rối loạn tâm thần dựa trên triệu chứng          │
│       người dùng cung cấp (DSM-5 based)                            │
├──────────────────────────────────────────────────────────────────┤
│ SKILLS:                                                              │
│   Skill: SymptomExtraction                                          │
│     ├── Tool: extract_emotion() → emotion slot                    │
│     ├── Tool: extract_trigger() → trigger slot                    │
│     ├── Tool: extract_duration() → duration slot                   │
│     ├── Tool: extract_intensity() → intensity slot                 │
│     ├── Tool: extract_impact() → impact slot                       │
│     ├── Tool: extract_stress_level() → stress level               │
│     └── Tool: extract_optional_symptoms() → sleep/appetite/etc   │
│                                                                     │
│   Skill: DiagnosticRetrieval                                        │
│     ├── Tool: search_diagnostic_kb(query) → milvus search         │
│     ├── Tool: expand_related_disorders(anchors) → neo4j 2-hop     │
│     ├── Tool: rerank_disorders(query, candidates) → cohere rerank │
│     └── Tool: get_dsm_criteria(disorder_id) → criteria text       │
│                                                                     │
│   Skill: ClinicalReasoning                                          │
│     ├── Tool: score_symptom_match(symptoms, disorder) → 0-100     │
│     ├── Tool: apply_differential_diagnosis() → ranked disorders   │
│     ├── Tool: generate_diagnostic_conclusion() → final diagnosis  │
│     └── Tool: assess_confidence_level() → confidence score         │
│                                                                     │
│   Skill: ResponseDrafting                                           │
│     ├── Tool: format_diagnostic_answer(diagnosis, confidence)     │
│     ├── Tool: translate_to_vietnamese()                            │
│     └── Tool: format_suggestion_prompt() → ask for more info       │
├──────────────────────────────────────────────────────────────────┤
│ REACT LOOP (internal):                                              │
│   1. Extract slots từ user message                                │
│   2. Nếu thiếu slots → generate follow-up questions → return       │
│   3. Retrieve disorders từ knowledge base                          │
│   4. Apply clinical reasoning                                      │
│   5. Generate diagnostic answer                                     │
│   6. Return result (tự hoàn thành task, KHÔNG cần Supervisor)      │
└──────────────────────────────────────────────────────────────────┘
```

### 4.3 TheoryAgent

```
┌──────────────────────────────────────────────────────────────────┐
│ TheoryAgent                                                        │
│ GOAL: Giải thích kiến thức tâm lý học (khái niệm, rối loạn,     │
│       cơ chế, triệu chứng) cho mục đích học tập/hiểu biết       │
├──────────────────────────────────────────────────────────────────┤
│ SKILLS:                                                              │
│   Skill: ConceptRetrieval                                          │
│     ├── Tool: search_theory_kb(query) → milvus search             │
│     ├── Tool: expand_concept_graph(anchors) → neo4j relationships │
│     ├── Tool: rerank_concepts(query, candidates) → cohere rerank  │
│     └── Tool: get_related_concepts(concept_id) → linked topics    │
│                                                                     │
│   Skill: EducationalExplanation                                    │
│     ├── Tool: generate_concept_explanation(context) → LLM draft    │
│     ├── Tool: simplify_for_user(complex_text) → simplify           │
│     ├── Tool: add_examples(concept) → real-world examples          │
│     └── Tool: cite_sources(references) → source citations         │
│                                                                     │
│   Skill: AnswerFormatting                                          │
│     ├── Tool: format_theoretical_answer(concept, explanation)      │
│     ├── Tool: translate_to_vietnamese()                            │
│     └── Tool: preserve_scientific_accuracy() → don't oversimplify │
├──────────────────────────────────────────────────────────────────┤
│ REACT LOOP:                                                         │
│   1. Understand theoretical question                                │
│   2. Retrieve relevant knowledge                                   │
│   3. Generate educational explanation                              │
│   4. Return answer                                                 │
│   (KHÔNG cần slot filling — câu hỏi lý thuyết không cần thông tin cá nhân)│
└──────────────────────────────────────────────────────────────────┘
```

### 4.4 TreatmentAgent

```
┌──────────────────────────────────────────────────────────────────┐
│ TreatmentAgent                                                      │
│ GOAL: Cung cấp phác đồ điều trị, tư vấn phương pháp chữa trị    │
│       dựa trên chuẩn đoán hoặc triệu chứng                       │
├──────────────────────────────────────────────────────────────────┤
│ SKILLS:                                                              │
│   Skill: TreatmentRetrieval                                         │
│     ├── Tool: search_treatment_kb(condition) → milvus search      │
│     ├── Tool: expand_treatment_graph(anchors) → neo4j relationships│
│     ├── Tool: rerank_treatments(query, candidates) → cohere       │
│     └── Tool: get_evidence_level(treatment_id) → strong/moderate/weak│
│                                                                     │
│   Skill: TreatmentPlanning                                          │
│     ├── Tool: match_treatment_to_diagnosis(diagnosis, treatments) │
│     ├── Tool: rank_by_evidence(treatments) → evidence-based order  │
│     ├── Tool: filter_by_availability(treatments) → practical       │
│     └── Tool: assess_interactions(treatments) → warnings          │
│                                                                     │
│   Skill: PatientGuidance                                           │
│     ├── Tool: format_treatment_plan(treatments)                   │
│     ├── Tool: explain_medication(medication)                       │
│     ├── Tool: explain_therapy_type(therapy)                         │
│     ├── Tool: estimate_timeline(treatment)                         │
│     └── Tool: format_when_to_seek_help() → escalation criteria    │
│                                                                     │
│   Skill: AnswerFormatting                                          │
│     ├── Tool: translate_to_vietnamese()                            │
│     └── Tool: add_important_disclaimers() → "consult professional" │
├──────────────────────────────────────────────────────────────────┤
│ REACT LOOP:                                                         │
│   1. Nhận diagnosis từ user (hoặc infer từ symptoms)             │
│   2. Retrieve treatment options                                    │
│   3. Rank and filter by evidence                                   │
│   4. Generate treatment guidance                                   │
│   5. Return answer với disclaimer                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 4.5 SupportAgent

```
┌──────────────────────────────────────────────────────────────────┐
│ SupportAgent                                                        │
│ GOAL: Cung cấp hỗ trợ sức khỏe tinh thần, chiến lược ứng phó,  │
│       kỹ năng quản lý cảm xúc — cho người KHÔNG có rối loạn    │
├──────────────────────────────────────────────────────────────────┤
│ SKILLS:                                                              │
│   Skill: CopingRetrieval                                           │
│     ├── Tool: search_coping_kb(stress_type) → milvus search       │
│     ├── Tool: expand_coping_graph(anchors) → neo4j strategies      │
│     ├── Tool: rerank_coping_strategies(query, strategies)         │
│     └── Tool: filter_by_feasibility(strategies) → user resources  │
│                                                                     │
│   Skill: EmotionalSupport                                          │
│     ├── Tool: generate_empathetic_response() → empathetic language │
│     ├── Tool: validate_user_feelings() → "cảm xúc của bạn hợp lý"│
│     ├── Tool: normalize_experience() → "nhiều người cũng vậy"    │
│     └── Tool: provide_hope() → "có cách cải thiện"                │
│                                                                     │
│   Skill: PsychoEducation                                          │
│     ├── Tool: explain_stress_response() → why they feel this     │
│     ├── Tool: explain_emotion_mechanism() → how emotions work      │
│     └── Tool: provide_self_assessment_tools() → stress scales     │
│                                                                     │
│   Skill: SkillBuilding                                             │
│     ├── Tool: recommend_mindfulness_techniques()                   │
│     ├── Tool: recommend_breathing_exercises()                      │
│     ├── Tool: recommend_grounding_techniques()                     │
│     └── Tool: recommend_lifestyle_changes() → sleep/exercise/etc  │
│                                                                     │
│   Skill: AnswerFormatting                                          │
│     ├── Tool: format_coping_answer(strategies, support)           │
│     └── Tool: translate_to_vietnamese()                            │
├──────────────────────────────────────────────────────────────────┤
│ REACT LOOP:                                                         │
│   1. Assess mức độ stress (slot extraction)                       │
│   2. Retrieve appropriate coping strategies                        │
│   3. Generate empathetic response + strategies                     │
│   4. Return answer                                                 │
│   (Self-contained: KHÔNG cần DiagnosisAgent hay TreatmentAgent)   │
└──────────────────────────────────────────────────────────────────┘
```

### 4.6 CrisisAgent

```
┌──────────────────────────────────────────────────────────────────┐
│ CrisisAgent                                                        │
│ GOAL: Phát hiện và ứng phó nguy cơ khủng hoảng tâm lý           │
│       (tự tử/tự gây thương tích) — ƯU TIÊN TUYỆT ĐỐI            │
│       Có quyền interrupt mọi agent khác                          │
├──────────────────────────────────────────────────────────────────┤
│ SKILLS:                                                              │
│   Skill: CrisisDetection                                           │
│     ├── Tool: match_crisis_keywords() → list matched keywords     │
│     ├── Tool: detect_suicidal_ideation() → plan/means/intent       │
│     ├── Tool: assess_immediate_danger() → "critical"|"high"       │
│     ├── Tool: detect_recent_crisis_context() → conversation hist  │
│     └── Tool: increase_sensitivity_mode() → flag all messages     │
│                                                                     │
│   Skill: ImmediateResponse                                         │
│     ├── Tool: select_crisis_template(level) → response text        │
│     ├── Tool: validate_user_safety() → check if they're safe now │
│     ├── Tool: ask_about_means() → "Bạn có kế hoạch cụ thể?"      │
│     └── Tool: express_caring() → empathetic, non-judgmental       │
│                                                                     │
│   Skill: ProfessionalEscalation                                   │
│     ├── Tool: provide_crisis_hotline() → hotline numbers           │
│     ├── Tool: suggest_immediate_resources() → ER, therapist       │
│     ├── Tool: encourage_professional_help()                       │
│     └── Tool: create_safety_plan_template() → coping plan          │
│                                                                     │
│   Skill: FollowUpSupport                                           │
│     ├── Tool: classify_user_response() → "seeking_help"|"declining"│
│     ├── Tool: gentle_persistence() → continue offering support     │
│     ├── Tool: assess_deescalation() → "bạn có ổn không?"         │
│     └── Tool: transition_to_domain_agent() → khi an toàn          │
│                                                                     │
│   Skill: Documentation                                            │
│     ├── Tool: log_crisis_event() → for safety records             │
│     └── Tool: alert_moderators() → flag conversation              │
├──────────────────────────────────────────────────────────────────┤
│ PRIORITY: CRITICAL — KHÔNG cần Supervisor route                     │
│   Supervisor gọi CrisisAgent TRƯỚC bất kỳ domain agent nào      │
│   Nếu detected → emit_interrupt → mọi agent khác dừng            │
│   Kết quả → Supervisor → trả về cho user → done                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. Memory — Service, Không Phải Agent

### 5.1 Tại Sao Memory Không Phải Agent

```
MemoryAgent (như thiết kế sai trước):
┌─────────────────────────────────────────────┐
│ Agent with ReAct loop                      │
│ Gọi qua message bus                      │
│ Làm nhiều thứ hơn CRUD thông thường?     │
└─────────────────────────────────────────────┘
     ↓ Sai — Memory operations KHÔNG cần cái đó
```

**Memory operations thực sự cần gì:**
- Đọc/ghi buffer (Q&A pairs)
- Đọc/ghi summary
- Merge slots
- Save/load checkpoint
- **KHÔNG cần LLM reasoning**
- **KHÔNG cần "quyết định"**
- **KHÔNG cần ReAct loop**
- **CHỈ cần CRUD trên persistent storage**

### 5.2 MemoryService

```python
# ai/modules/shared/services/memory_service.py

class MemoryService:
    """
    Singleton service — KHÔNG phải Agent.
    Quản lý conversation memory (buffer, summary, slots).
    Inject vào constructor của agents cần dùng.
    """

    def __init__(
        self,
        redis_cache: RedisCache,          # L2: distributed cache
        checkpointer: AsyncPostgresSaver,  # L3: persistent storage
    ):
        self.redis = redis_cache
        self.checkpointer = checkpointer

    # === Buffer (last 3 Q&A pairs) ===
    async def save_interaction(
        self, conv_id: str, role: str, content: str, metadata: dict
    ):
        """Lưu 1 interaction vào buffer. Tự prune nếu > 3."""
        buffer = await self.get_buffer(conv_id)
        buffer.append({
            "role": role,
            "content": content,
            "metadata": metadata,
            "timestamp": datetime.utcnow().isoformat(),
        })
        # Keep last 3
        if len(buffer) > 3:
            buffer = buffer[-3:]
        await self.redis.set(f"buffer:{conv_id}", json.dumps(buffer))

    async def get_buffer(self, conv_id: str) -> List[dict]:
        data = await self.redis.get(f"buffer:{conv_id}")
        return json.loads(data) if data else []

    # === Summary (older Q&A pairs) ===
    async def append_to_summary(self, conv_id: str, new_summary: str):
        existing = await self.get_summary(conv_id)
        combined = f"{existing}\n{new_summary}" if existing else new_summary
        await self.redis.set(f"summary:{conv_id}", combined[:5000])  # Max 5k chars

    async def get_summary(self, conv_id: str) -> str:
        return await self.redis.get(f"summary:{conv_id}") or ""

    # === Slots (accumulated structured info) ===
    async def merge_slots(self, conv_id: str, new_slots: dict) -> dict:
        """Merge new slots vào existing slots. Return merged."""
        existing = await self.get_slots(conv_id)
        merged = {**existing, **new_slots}
        await self.redis.set(f"slots:{conv_id}", json.dumps(merged))
        return merged

    async def get_slots(self, conv_id: str) -> dict:
        data = await self.redis.get(f"slots:{conv_id}")
        return json.loads(data) if data else {}

    async def get_sufficiency(self, conv_id: str) -> dict:
        """Check if slots are sufficient (5/7 required)."""
        slots = await self.get_slots(conv_id)
        required = ["emotion", "trigger", "duration", "intensity",
                    "impact", "need", "stress_level"]
        filled = [k for k in required if slots.get(k)]
        missing = [k for k in required if not slots.get(k)]
        return {
            "filled": filled,
            "missing": missing,
            "count": len(filled),
            "sufficient": len(filled) >= 5,
        }

    # === Full Context (for LLM prompt) ===
    async def get_full_context(self, conv_id: str) -> str:
        """Build full conversation context string."""
        buffer = await self.get_buffer(conv_id)
        summary = await self.get_summary(conv_id)
        slots = await self.get_slots(conv_id)

        lines = ["=== Conversation Context ==="]

        if buffer:
            for i, pair in enumerate(buffer, 1):
                lines.append(f"--- Turn {i} ---")
                lines.append(f"User: {pair['content']}")
                lines.append(f"Assistant: {pair.get('assistant_content', '')}")

        if slots:
            lines.append("\n=== Structured Information ===")
            for k, v in slots.items():
                lines.append(f"  - {k}: {v}")

        if summary:
            lines.append(f"\n=== Previous Summary ===\n{summary}")

        return "\n".join(lines)

    # === Persistence ===
    async def save_checkpoint(self, conv_id: str):
        """Flush Redis → PostgreSQL (L3)."""
        data = {
            "buffer": await self.get_buffer(conv_id),
            "summary": await self.get_summary(conv_id),
            "slots": await self.get_slots(conv_id),
            "updated_at": datetime.utcnow().isoformat(),
        }
        await self.checkpointer.aput(conv_id, data)

    async def load_checkpoint(self, conv_id: str) -> dict:
        """Load from PostgreSQL, warm Redis cache."""
        data = await self.checkpointer.aget(conv_id)
        if data:
            await self.redis.set(f"buffer:{conv_id}", json.dumps(data.get("buffer", [])))
            await self.redis.set(f"summary:{conv_id}", data.get("summary", ""))
            await self.redis.set(f"slots:{conv_id}", json.dumps(data.get("slots", {})))
        return data or {}

    # === Cleanup ===
    async def invalidate(self, conv_id: str):
        """Xóa memory khi conversation kết thúc."""
        await self.redis.delete(f"buffer:{conv_id}")
        await self.redis.delete(f"summary:{conv_id}")
        await self.redis.delete(f"slots:{conv_id}")
```

### 5.3 Memory như Shared Tools

```
MemoryService không phải Agent → không có ReAct loop
→ Tools được inject vào agents dưới dạng shared utilities

SupervisorAgent
├── SHARED MEMORY TOOLS:
│   ├── save_to_buffer()
│   ├── get_context()
│   ├── merge_slots()
│   └── get_accumulated_slots()

Mọi Domain Agent cũng có quyền gọi MemoryService trực tiếp
(không qua message bus → synchronous, nhanh)
```

---

## 6. Bảng Tổng Hợp: 5 Agents + 1 Service

| Agent/Service | Goal | Skills | Tools Count |
|--------------|------|--------|:---:|
| **SupervisorAgent** | Route intent → đúng domain agent | IntentClassification, PreliminaryContext | ~8 |
| **DiagnosticAgent** | Chuẩn đoán rối loạn tâm thần | SymptomExtraction, DiagnosticRetrieval, ClinicalReasoning, ResponseDrafting | ~14 |
| **TheoryAgent** | Giải thích kiến thức tâm lý | ConceptRetrieval, EducationalExplanation, AnswerFormatting | ~10 |
| **TreatmentAgent** | Phác đồ điều trị | TreatmentRetrieval, TreatmentPlanning, PatientGuidance, AnswerFormatting | ~13 |
| **SupportAgent** | Hỗ trợ sức khỏe tinh thần (non-disorder) | CopingRetrieval, EmotionalSupport, PsychoEducation, SkillBuilding, AnswerFormatting | ~15 |
| **CrisisAgent** | Ứng phó khủng hoảng (priority) | CrisisDetection, ImmediateResponse, ProfessionalEscalation, FollowUpSupport, Documentation | ~12 |
| **MemoryService** | Quản lý memory đa turn | (Service, không phải Agent) | ~10 |

**Tổng: 5 Agents + 1 Service, 72+ Tools across all agents**

---

## 7. So Sánh: Domain-Centric vs Chức Năng-Kỹ-Thuật

```
THIẾT KẾ SAI (theo chức năng kỹ thuật):
┌─────────────────────────────────────────────────────────┐
│ Supervisor → RetrievalAgent → AssessmentAgent →       │
│           → AnswerGeneratorAgent → MemoryAgent         │
│                                                         │
│ User: "Tôi bị lo âu"                                   │
│   Supervisor: "là personal, gọi RetrievalAgent"         │
│   RetrievalAgent: "lấy dữ liệu xong, gọi AssessmentAgent"│
│   AssessmentAgent: "đánh giá xong, gọi AnswerGenerator" │
│   AnswerGenerator: "tạo câu trả lời xong"             │
│   MemoryAgent: "lưu memory"                           │
│                                                         │
│ → 5 agents gọi nhau lần lượt                          │
│ → Không ai sở hữu task hoàn chỉnh                     │
│ → Supervisor trở thành "god object"                    │
└─────────────────────────────────────────────────────────┘

THIẾT KẾ ĐÚNG (domain-centric):
┌─────────────────────────────────────────────────────────┐
│ Supervisor: "User nói gì? → DiagnosticAgent"           │
│                                                         │
│ User: "Tôi bị lo âu về công việc"                      │
│                                                         │
│ Supervisor: intent=diagnostic → emit to DiagnosticAgent│
│   └── Done, không cần làm gì thêm                       │
│                                                         │
│ DiagnosticAgent (tự lo từ A→Z):                       │
│   1. Extract slots                                     │
│   2. Nếu thiếu → ask follow-up (tự quyết định)        │
│   3. Retrieve diagnostic knowledge (tự gọi skill)      │
│   4. Apply clinical reasoning (tự gọi skill)          │
│   5. Generate answer (tự gọi skill)                    │
│   6. Save to memory (gọi MemoryService)                │
│   7. Return result                                     │
│                                                         │
│ → Chỉ 1 agent gọi, tự hoàn thành                      │
│ → Supervisor = simple router, không phức tạp           │
│ → Debug dễ: 1 intent = 1 agent = 1 trace              │
└─────────────────────────────────────────────────────────┘
```

### Lợi ích Domain-Centric:

| Criteria | Chức năng-Kỹ-Thuật | Domain-Centric |
|----------|:---:|:---:|
| Agent count | 8 | **5** |
| Supervisor complexity | Cao (god object) | **Thấp (chỉ route)** |
| Ownership | Mỗi task qua nhiều agents | **1 agent sở hữu hoàn toàn** |
| Intent clarity | Mờ | **Rõ ràng theo user need** |
| Debugging | Trace qua nhiều agents | **1 trace per intent** |
| Scalability | Thêm agent = thêm routing | **Thêm route mới** |
| Parallelism | Hạn chế (sequential) | **Domain agents có thể song song** |

---

## 8. Routing Logic (SupervisorAgent)

### 8.1 Routing Flow

```
User message
    │
    ▼
┌─────────────────────────────────┐
│  STEP 1: Crisis Safety Gate    │  ← String/regex match (O(1), no LLM cost)
│  "tự tử", "suicide", ...       │    Keyword matched → CrisisAgent (CRITICAL)
└──────────────┬──────────────────┘
               │ no match
               ▼
┌─────────────────────────────────┐
│  STEP 2: LLM Intent Classify   │  ← LLM reasoning + context + slots
│  theory / treatment /          │    confidence + reasoning output
│  personal / off_topic          │
└──────────────┬──────────────────┘
               │
    ┌──────────┼──────────────────┬───────────────┐
    ▼          ▼                  ▼               ▼
Theory   Treatment          Diagnostic      Support
Agent    Agent               Agent           Agent
                             (slots → ask
                              follow-up
                              if needed)
```

### 8.2 Routing Rules

```python
# SupervisorAgent — Intent routing rules
# Keyword → CrisisAgent | Non-crisis → LLM decides

INTENT_RULES = {
    # ── Step 1: Crisis Safety Gate (keyword only, NO LLM) ──────────────────
    # Priority tuyệt đối — chạy trước bất kỳ logic nào khác.
    # Dùng case-insensitive regex match, O(1), không tốn LLM cost.
    "safety_gate": {
        "type": "keyword_match",
        "keywords": [
            "tự tử", "tự sát", "suicide", "kill myself",
            "end my life", "muốn chết", "không sống nổi",
            "tự gây thương tích", "self-harm", "self harm",
        ],
        "action": "route → CrisisAgent (CRITICAL priority)",
    },

    # ── Step 2: LLM Intent Classification ──────────────────────────────────
    # Tất cả non-crisis message → LLM tự suy luận intent.
    # Keyword matching KHÔNG dùng ở bước này.
    "intent_classification": {
        "type": "llm",
        "confidence_threshold": 0.7,  # confidence < 0.7 → SupportAgent (safe fallback)

        "classification_prompt": """
Bạn là Supervisor của hệ thống sức khỏe tâm thần.
Đọc message và context, sau đó classify vào ĐÚNG 1 intent:

- "theory": User hỏi kiến thức, khái niệm, cơ chế tâm lý.
  Ví dụ: "Rối loạn lo âu tổng quát là gì?", "Cơ chế của trầm cảm"
  → Route: TheoryAgent

- "treatment": User hỏi về phác đồ, thuốc, therapy cho bệnh ĐÃ BIẾT/ĐƯỢC CHẨN ĐOÁN.
  Ví dụ: "Tôi bị GAD, có cách nào điều trị?", "SSRI có tác dụng gì?"
  → Route: TreatmentAgent

- "personal": User chia sẻ triệu chứng, cảm xúc, khó khăn cá nhân.
  Ví dụ: "Tôi lo âu về công việc 2 tuần nay", "Khó ngủ, mệt mỏi"
  → Route: DiagnosticAgent hoặc SupportAgent (tùy severity — see Step 3)

- "off_topic": Không liên quan sức khỏe tâm thần.
  Ví dụ: "Thời tiết hôm nay thế nào?", "Công thức nấu ăn"
  → Route: fallback message

Trả về JSON:
{{"intent": "...", "confidence": 0.0-1.0, "reasoning": "..."}}
""",
    },

    # ── Step 3: Personal → Sub-classify (LLM) ───────────────────────────────
    # Khi Step 2 trả về "personal" → LLM quyết định tiếp.
    "personal_subclassify": {
        "type": "llm",
        "subclassify_prompt": """
User message: "{message}"
Accumulated slots: {slots}

Sub-classify "personal" intent:
- "diagnostic": Triệu chứng nghiêm trọng, kéo dài, ảnh hưởng đời sống,
  hoặc user hỏi về "bệnh gì" / triệu chứng lạ.
  → Route: DiagnosticAgent (sẽ tự ask follow-up nếu thiếu slots)

- "support": Căng thẳng thông thường, stress مؤقت, không phải disorder,
  hoặc user cần emotional support / coping strategies.
  → Route: SupportAgent

Trả về JSON:
{{"sub_intent": "diagnostic|support", "confidence": 0.0-1.0, "reasoning": "..."}}
""",
    },

    # ── Fallback ────────────────────────────────────────────────────────────
    "fallback": {
        "llm_confidence_too_low": "SupportAgent",   # confidence < 0.7
        "off_topic": "return_fallback_message",
    },
}
```

### 8.3 Routing Decision Table

| Step | Trigger | Method | Output |
|------|---------|--------|--------|
| **Step 1** | Mọi message (đồng thời với Step 2) | `keyword_match` | `CrisisAgent` (nếu matched) |
| **Step 2** | Non-crisis message | `llm` | `TheoryAgent`, `TreatmentAgent`, `personal`, `off_topic` |
| **Step 3** | Step 2 = `personal` | `llm` | `DiagnosticAgent` hoặc `SupportAgent` |

### 8.4 Tại Sao Keyword + LLM Hybrid

| | Keyword-only | LLM-only | **Hybrid (Keyword + LLM)** |
|--|:---:|:---:|:---:|
| Crisis detection | ✅ Nhanh, rẻ | ⚠️ Có thể miss | ✅ **An toàn + nhanh** |
| Theory/Treatment phân biệt | ⚠️ Miss nuance | ✅ Reasoning | ✅ **Đúng cả hai** |
| Personal sub-classify | ❌ Không đủ | ✅ Context-aware | ✅ **Đọc được slots** |
| Off-topic reject | ⚠️ Keyword explosion | ✅ Hiểu ngữ cảnh | ✅ **Chính xác** |
| LLM call cost | Thấp | Cao | **Trung bình (1 call/message)** |

---

## 9. Ánh Xạ: 24 Nodes → Domain Agents

| Node Cũ | → Domain Agent | → Skills Used |
|---------|---------------|---------------|
| translate_question | SupervisorAgent | IntentClassification |
| classify_type_query | SupervisorAgent | IntentClassification |
| router | SupervisorAgent | IntentClassification |
| safety_check | **CrisisAgent** | CrisisDetection |
| slot_filling | **DiagnosticAgent** (tự gọi) | SymptomExtraction |
| request_more_info | **DiagnosticAgent** (tự gọi) | SymptomExtraction |
| query_rewriter | **DiagnosticAgent** (tự gọi) | SymptomExtraction |
| assessment | **DiagnosticAgent** (tự gọi) | ClinicalReasoning |
| normal_coping_retrieval | **SupportAgent** | CopingRetrieval |
| adjustment_retrieval | **SupportAgent** | CopingRetrieval |
| diagnostic_retrieval | **DiagnosticAgent** | DiagnosticRetrieval |
| disease_conclusion | **DiagnosticAgent** | ClinicalReasoning |
| treatment_retrieval | **TreatmentAgent** | TreatmentRetrieval |
| theoretical_retrieval | **TheoryAgent** | ConceptRetrieval |
| graph_retrieval | (shared) | DiagnosticRetrieval, CopingRetrieval, etc. |
| answer_with_graph | **DiagnosticAgent** | ResponseDrafting |
| answer_with_theoretical | **TheoryAgent** | AnswerFormatting |
| answer_with_treatment | **TreatmentAgent** | AnswerFormatting |
| conversation_memory | **MemoryService** | (Service, không phải agent) |
| not_mental_health | SupervisorAgent | (fallback) |
| crisis_immediate_response | **CrisisAgent** | ImmediateResponse |
| crisis_follow_up_classifier | **CrisisAgent** | FollowUpSupport |
| crisis_escalation | **CrisisAgent** | ProfessionalEscalation |
| crisis_contextual_support | **CrisisAgent** | ImmediateResponse, FollowUpSupport |

---

*Lưu ý: File này là Part 1 đã sửa — Domain-Centric, 5 Agents + 1 MemoryService*
