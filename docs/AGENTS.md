# MentalHealth_HybridRAG — Agent Specifications

> **Generated from implementation** — reflects actual code structure.
> Last updated: 2026-04-07

---

## Architecture Overview

```
User → Backend (FastAPI, port 8000)
         └── HTTP → SupervisorAgent (port 8001) ── HTTP ──→ Domain Agents
                                                              ├── DiagnosticAgent (8101)
                                                              ├── TheoryAgent (8102)
                                                              ├── TreatmentAgent (8103)
                                                              ├── SupportAgent (8104)
                                                              └── CrisisAgent (8105)
```

**Communication:** All agents communicate via HTTP using `AgentHTTPClient`.
**State:** `GlobalState` (shared) + `AgentState` (per-request private).
**Memory:** `MemoryService` — L1 in-memory → L2 Redis async → L3 PostgreSQL.

---

## Agent Registry

| Agent | ID | Port | Microservice Entry |
|-------|----|------|--------------------|
| SupervisorAgent | `supervisor` | 8001 | `ai/agents/supervisor/main.py` |
| DiagnosticAgent | `diagnostic` | 8101 | `ai/agents/diagnostic/main.py` |
| TheoryAgent | `theory` | 8102 | `ai/agents/theory/main.py` |
| TreatmentAgent | `treatment` | 8103 | `ai/agents/treatment/main.py` |
| SupportAgent | `support` | 8104 | `ai/agents/support/main.py` |
| CrisisAgent | `crisis` | 8105 | `ai/agents/crisis/main.py` |

---

## SupervisorAgent

**Type:** Router (no ReAct loop)
**Port:** 8001
**File:** `ai/agents/supervisor/supervisor_agent.py`

### Responsibilities
1. Crisis safety gate (keyword match, O(1), NO LLM cost)
2. Intent classification (keyword + LLM fallback)
3. Extract preliminary context (slots)
4. Route to correct domain agent

### Skills

#### IntentClassification
- Classifies user message into one of: `diagnostic`, `theory`, `treatment`, `support`, `crisis`
- Uses keyword matching + LLM fallback
- Returns `intent` + `confidence` + `reasoning`

#### PreliminaryContext
- Extracts basic slots from message: language, crisis keywords
- Returns `preliminary_slots` dict

### Routing Flow

```
User message
    │
    ▼
┌─────────────────────────┐
│  STEP 1: Crisis Gate    │  ← Keyword match (O(1), NO LLM)
│  "tự tử", "suicide"...  │    If matched → CrisisAgent immediately
└───────────┬─────────────┘
            │ no match
            ▼
┌─────────────────────────┐
│  STEP 2: Intent Classify │  ← Keyword + LLM
│  diagnostic / theory /    │
│  treatment / support     │
└───────────┬─────────────┘
            │
            ▼
      Domain Agent
```

### Output
```python
{
    "target_agent": "support",  # AgentID string
    "context": {
        "original_message": str,
        "translated_message": str,
        "language": "vi",
        "preliminary_slots": dict,
        "intent": str,
        "conv_id": str,
    }
}
```

---

## DiagnosticAgent

**Type:** Domain Agent (self-contained)
**Port:** 8101
**File:** `ai/agents/diagnostic/diagnostic_agent.py`
**Requires:** Milvus, Neo4j, CohereReranker

### Goal
DSM-5 mental health symptom assessment. Outputs binary decision: **có bệnh / không có bệnh**.

### Pipeline
```
1. SymptomExtraction → extract slots from message
2. Check slot sufficiency (≥5/8 required slots)
   → If insufficient: ask user for missing slots (slot filling)
3. DiagnosticRetrieval → retrieve disorder candidates from KB
4. ClinicalReasoning → LLM applies DSM-5 criteria → has_disorder?
5. Return result to SupervisorAgent
```

### Skills

| Skill | Description |
|-------|-------------|
| `SymptomExtraction` | Extracts 8 required slots: emotion, trigger, duration, intensity, impact, stress_level, sleep_quality, appetite_changes. Also extracts 17 optional slots. |
| `DiagnosticRetrieval` | Milvus dense retrieval → Neo4j graph expansion → Cohere reranking → top disorder candidates |
| `ClinicalReasoning` | LLM applies DSM-5 criteria to slots + candidates. Returns `has_disorder`, `diagnosis`, `confidence`, `reasoning`, `differential` |

### Required Slots (≥5 needed)
- `emotion` — specific emotions: anxious, sad, irritable, fearful
- `trigger` — what triggered symptoms
- `duration` — how long: today, few_days, weeks, months
- `intensity` — mild, moderate, severe (or 1-10)
- `impact` — how it affects daily life / functioning
- `stress_level` — perceived stress 1-10
- `sleep_quality` — poor sleep, insomnia, frequent waking, nightmares
- `appetite_changes` — decreased, overeating, no change

### Output
```python
{
    "agent_id": "diagnostic",
    "has_disorder": True/False,
    "diagnosis": "GAD" or None,
    "confidence": 0.85,
    "reasoning": "...",
    "basis": [...],          # DSM-5 criteria matched
    "differential": [...],    # Alternative diagnoses considered
    "recommendation": "...",
    "slots_collected": 6,
    "candidates_count": 3,
    "intent": "diagnostic",
}
```

### Slot Filling Response (when insufficient)
```python
{
    "response": "Để mình hỗ trợ bạn tốt hơn, bạn có thể cho mình biết thêm:\n• Bạn đánh giá mức độ nghiêm trọng như thế nào?\n• Triệu chứng này ảnh hưởng đến cuộc sống hàng ngày của bạn như thế nào?",
    "agent_id": "diagnostic",
    "intent": "diagnostic",
    "slot_filling": True,
    "missing_slots": ["intensity", "impact"],
}
```

---

## TheoryAgent

**Type:** Domain Agent (self-contained)
**Port:** 8102
**File:** `ai/agents/theory/theory_agent.py`
**Requires:** Milvus, Neo4j

### Goal
Provide accurate, educational psychological knowledge. **NOT for diagnosis or treatment advice.**

### Pipeline
```
1. ConceptRetrieval → search psychological concepts
2. EducationalExplanation → generate explanation
3. AnswerFormatting → format for user
```

### Skills

| Skill | Description |
|-------|-------------|
| `ConceptRetrieval` | Milvus dense retrieval + Neo4j graph expansion for psychological concepts, disorders, mechanisms |
| `EducationalExplanation` | LLM generates clear, accurate educational explanations with examples |
| `AnswerFormatting` | Formats explanation with structure, sources, Vietnamese language |

### Output
```python
{
    "response": "**Rối loạn lo âu tổng quát (GAD)...**",
    "agent_id": "theory",
    "skills_used": ["ConceptRetrieval", "EducationalExplanation", "AnswerFormatting"],
    "concepts": [{"name": "GAD", "description": "..."}],
    "intent": "theory",
}
```

---

## TreatmentAgent

**Type:** Domain Agent (self-contained)
**Port:** 8103
**File:** `ai/agents/treatment/treatment_agent.py`
**Requires:** Milvus, Neo4j

### Goal
Provide evidence-based treatment options. **Always includes medical disclaimer.**

### Disclaimer (always appended)
> *⚠️ **Tuyên bố miễn trừ trách nhiệm:**
> Thông tin trong cuộc trò chuyện này chỉ mang tính chất giáo dục và KHÔNG phải là lời khuyên y khoa. Mình không phải bác sĩ. Mọi quyết định điều trị phải được thực hiện cùng với bác sĩ hoặc nhà trị liệu có chuyên môn.*

### Pipeline
```
1. TreatmentRetrieval → search treatments
2. TreatmentPlanning → rank by evidence level
3. PatientGuidance → format for patient understanding
4. AnswerFormatting → add disclaimer + format
```

### Skills

| Skill | Description |
|-------|-------------|
| `TreatmentRetrieval` | Milvus + Neo4j retrieval of treatment options for diagnosed/described condition |
| `TreatmentPlanning` | Ranks treatments by evidence level (strong/moderate/weak), checks interactions |
| `PatientGuidance` | Formats treatment information for patient understanding, explains medication/therapy types |
| `AnswerFormatting` | Combines treatment plans + guidance + disclaimer |

### Output
```python
{
    "response": "**Phác đồ điều trị cho GAD:**\n1. **CBT** (Liệu pháp nhận thức hành vi) — strong evidence\n2. **SSRI** (sertraline) — first-line medication...",
    "agent_id": "treatment",
    "skills_used": ["TreatmentRetrieval", "TreatmentPlanning", "PatientGuidance", "AnswerFormatting"],
    "intent": "treatment",
}
```

---

## SupportAgent

**Type:** Domain Agent (self-contained)
**Port:** 8104
**File:** `ai/agents/support/support_agent.py`
**Requires:** Milvus, Neo4j, CohereReranker

### Goal
Provide emotional support, coping strategies, and skill-building for **non-disorder** distress.

### Pipeline
```
1. CopingRetrieval → search coping strategies (parallel with PsychoEducation)
2. PsychoEducation → explain stress response
3. SkillBuilding → recommend mindfulness/breathing/grounding
4. AnswerFormatting → combine into empathetic response
```

### Skills

| Skill | Description |
|-------|-------------|
| `CopingRetrieval` | Milvus + Neo4j retrieval of coping strategies filtered by feasibility |
| `EmotionalSupport` | Generates empathetic, validating responses |
| `PsychoEducation` | Explains stress response mechanism, normalizes experience |
| `SkillBuilding` | Recommends mindfulness, breathing, grounding, lifestyle techniques |
| `AnswerFormatting` | Formats strategies + support into coherent response |

### Output
```python
{
    "response": "**Mình hiểu bạn đang trải qua...**\n\nMột số cách bạn có thể thử...\n- **Kỹ thuật thở...**",
    "agent_id": "support",
    "skills_used": ["CopingRetrieval", "EmotionalSupport", "PsychoEducation", "SkillBuilding", "AnswerFormatting"],
    "intent": "support",
}
```

---

## CrisisAgent

**Type:** Domain Agent (CRITICAL priority)
**Port:** 8105
**File:** `ai/agents/crisis/crisis_agent.py`
**Priority:** CRITICAL — can interrupt all other agents

### Goal
Psychological crisis intervention for suicide/self-harm ideation. **Priority over everything.**

### Crisis Keywords (Vietnamese + English)
```
VI: tự tử, tự sát, buốc tử, từ tử, muốn chết, mong muốn được chết,
    giết chết mình, tự hại mình, overdose, uống thuốc nhiều, treo cổ,
    nhảy lầu, nhảy cầu, không còn muốn sống, chán đời muốn chết
EN: suicide, kill myself, want to die, end my life, take my own life,
    self-harm, overdose, hang myself, jump off, don't want to live anymore
```

### Pipeline
```
1. CrisisDetection → determine crisis level
2. ImmediateResponse → respond immediately with empathy
3. ProfessionalEscalation → provide hotlines
4. FollowUpSupport → next steps guidance
5. Documentation → log event
```

### Skills

| Skill | Description |
|-------|-------------|
| `CrisisDetection` | Determines crisis level (critical/high/moderate/low) from keywords + message + context |
| `ImmediateResponse` | Generates immediate empathetic crisis response |
| `ProfessionalEscalation` | Provides crisis hotlines and professional resources |
| `FollowUpSupport` | Generates follow-up support guidance |
| `Documentation` | Logs crisis event for safety records |

### Output
```python
{
    "response": "**Mình rất lo cho bạn.**\n\nBạn có thể gọi ngay: **094 234 99 99**...",
    "agent_id": "crisis",
    "crisis_level": "high",
    "crisis_detected": True,
    "hotlines": [
        {"name": "Vietnam Suicide Prevention", "phone": "094 234 99 99", "hours": "24/7"},
    ],
    "skills_used": ["CrisisDetection", "ImmediateResponse", "ProfessionalEscalation", "FollowUpSupport", "Documentation"],
    "intent": "crisis",
}
```

---

## Shared Components

### MemoryService

Injected into every agent. Manages conversation memory across 3 layers.

| Method | Description |
|--------|-------------|
| `save_buffer(conv_id, role, content)` | Save Q&A to L1 + L2 |
| `get_buffer(conv_id)` | Get last 3 Q&A pairs |
| `get_context(conv_id)` | Full context string for LLM |
| `merge_slots(conv_id, new_slots)` | Merge new slots into accumulated |
| `get_accumulated_slots(conv_id)` | Get all collected slots |
| `get_slot_sufficiency(conv_id)` | Check if ≥5/8 required slots filled |
| `get_crisis_state(conv_id)` | Get crisis state |
| `update_crisis_state(conv_id, state)` | Update crisis state |
| `checkpoint_to_postgres(conv_id)` | Persist to PostgreSQL L3 |
| `load_from_postgres(conv_id)` | Resume conversation from L3 |

### EventEmitter

LangSmith tracing integration. Emits structured events.

| Event | When |
|-------|------|
| `agent_started` | Agent begins processing |
| `agent_finished` | Agent completes |
| `agent_error` | Agent throws exception |
| `crisis_detected` | Crisis keywords found |
| `routing_decided` | Supervisor routes to agent |
| `retrieval_completed` | Retrieval finishes |

### CircuitBreaker

Per-tool circuit breaker in `BaseAgent`. Prevents cascading failures.
- `threshold`: 5 failures triggers open
- `timeout`: 30s before half-open retry

---

## Intent → Agent Routing

| Intent | Agent | Rationale |
|--------|-------|-----------|
| `crisis` | CrisisAgent | Safety first — never route elsewhere |
| `theory` | TheoryAgent | "Rối loạn lo âu là gì?" |
| `treatment` | TreatmentAgent | "Làm sao điều trị GAD?" |
| `diagnostic` | DiagnosticAgent | "Tôi bị lo âu 2 tuần, sợ work" |
| `support` | SupportAgent | "Tôi buồn và stress" (non-disorder) |

---

## How to Add a New Agent

1. Create `ai/agents/new_agent/` directory
2. Create `new_agent.py` (extends `BaseAgent`)
3. Create `skills/` subdirectory with skill classes
4. Create `main.py` (FastAPI microservice entry point)
5. Add to `AgentManager.register_domain_agents()`
6. Add URL to `AgentHTTPClient.DEFAULT_AGENT_URLS`
7. Add to `docker-compose.yml`
8. Add to `run_agents.py`
9. Write unit + integration tests
