# Mental Health Hybrid RAG — Implementation Plan
## Domain-Centric Multi-Agent System

> Dựa trên kiến trúc đã định nghĩa trong `.claude/CLAUDE.md` và `docs/REFACTOR-PLAN-PART*.md`

---

## Tổng Quan

```
6 tháng → 6 Phase
Phase 1-2: Foundation (backend infrastructure)
Phase 3-4: Agents (6 agents)
Phase 5:   Integration + MemoryService
Phase 6:   Testing + Deployment
```

### Dependency Order (phải theo thứ tự)

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6
   ↑           ↑          ↑         ↑
   └───────────┴──────────┴─────────┘
        (supervisor phụ thuộc shared + services)
```

---

## Phase 1: Foundation — Shared Infrastructure (Tuần 1-3)

**Mục tiêu:** Xây dựng nền tảng shared cho tất cả agents

### 1.1 Shared Modules (`backend/src/agents/shared/`)

```python
# Tạo files theo thứ tự:

1. agents/shared/constants.py
   - Agent IDs: SUPERVISOR, DIAGNOSTIC, THEORY, TREATMENT, SUPPORT, CRISIS
   - Priorities: CRITICAL, HIGH, NORMAL
   - Message types: task, result, error, interrupt

2. agents/shared/message.py
   - AgentMessage dataclass: id, from_agent, to_agent, message_type,
     priority, content, timestamp, task_id

3. agents/shared/state.py
   - GlobalState dict schema (TypedDict)
   - Key fields: conversation_id, user_id, language, slots, crisis_state

4. agents/shared/exceptions.py
   - AgentError, RetryableError, CircuitOpenError,
     CrisisDetectedError, MessageBusError

5. agents/shared/circuit_breaker.py
   - CircuitBreaker class: failures, threshold, state (closed/open),
     _on_success(), _on_failure(), call()

6. agents/shared/base_agent.py          ← PRIORITY NHẤT
   - Abstract BaseAgent class:
       __init__(memory_service: MemoryService, llm, config)
       abstract async def run(input, gs) -> Any
       async def execute_tool(tool_name, params) -> Any
       async def _react_loop(input, gs) -> Any  # template, gọi được override
       local_memory: dict  # agent-private ephemeral state
       shared_memory_tools: dict  # từ memory_service
```

### 1.2 Message Bus (`backend/src/communication/`)

```python
# Tạo files:

1. communication/message_bus.py
   - MessageBus class (singleton):
       queues: Dict[str, asyncio.Queue]
       _broadcast_interrupt(message)  # CrisisAgent gọi cái này
       send(message: AgentMessage) -> str
       receive(agent_id, timeout=30) -> Optional[AgentMessage]
       subscribe(agent_id, event_types)
       wait_for_result(task_id, timeout) -> Optional[AgentMessage]
   - Interrupt mechanism: Event flag per agent

2. communication/events.py
   - Event types: AGENT_STARTED, AGENT_FINISHED, TOOL_CALLED,
     CRISIS_DETECTED, RETRIEVAL_COMPLETED
   - EventEmitter class (LangSmith integration)

3. communication/subscriptions.py
   - SubscriptionManager: subscribe/unsubscribe agents to event types
```

### 1.3 RAG Infrastructure (verify + extend)

```python
# Verify existing files tồn tại và hoạt động:

1. rag/llm/llm_gemini.py
   - LLM class: generate(prompt), batch_generate(prompts) → async

2. rag/vectors/milvus_client.py
   - MilvusClient class: search(collection, query_vector, top_k),
     insert(collection, data), delete(collection, ids)

3. rag/vectors/embeddings.py
   - encode_e5(text) -> List[float]
   - encode_batch(texts) -> List[List[float]]

4. rag/graph/neo4j_client.py
   - Neo4jClient class: run_query(cypher), retrieve_subgraph(node_ids, depth)

5. rag/reranker/cohere_reranker.py
   - CohereReranker class: rerank(query, candidates, top_k) -> ranked list
```

### Deliverables Phase 1

| File | Status |
|------|--------|
| `agents/shared/constants.py` | ✅ Tạo mới |
| `agents/shared/message.py` | ✅ Tạo mới |
| `agents/shared/state.py` | ✅ Tạo mới |
| `agents/shared/exceptions.py` | ✅ Tạo mới |
| `agents/shared/circuit_breaker.py` | ✅ Tạo mới |
| `agents/shared/base_agent.py` | ✅ Tạo mới |
| `communication/message_bus.py` | ✅ Tạo mới |
| `communication/events.py` | ✅ Tạo mới |
| `communication/subscriptions.py` | ✅ Tạo mới |

### Verification Phase 1

```bash
# Chạy test cơ bản:
python -c "
from backend.src.agents.shared.base_agent import BaseAgent
from backend.src.communication.message_bus import MessageBus
from backend.src.agents.shared.message import AgentMessage
from backend.src.agents.shared.circuit_breaker import CircuitBreaker
print('Phase 1 imports OK')
"

# Test MessageBus interrupt:
pytest tests/unit/test_message_bus.py -v
pytest tests/unit/test_base_agent.py -v
```

---

## Phase 2: MemoryService + Data Layer (Tuần 4-5)

**Mục tiêu:** Xây dựng MemoryService — persistent memory cho mọi agents

### 2.1 MemoryService (`backend/src/services/memory_service.py`)

```python
# ĐÂY LÀ SERVICE, KHÔNG PHẢI AGENT
# inject vào constructor của mọi agent

class MemoryService:
    """
    Service cho conversation memory.
    KHÔNG bao giờ gọi qua MessageBus — inject trực tiếp.
    """

    def __init__(
        self,
        redis_client: Redis,
        db_session: Callable,
        max_buffer_size: int = 3,
    ):
        self._redis = redis_client
        self._db = db_session
        self._max_buffer = max_buffer_size
        self._cache_ttl = 3600  # 1 hour

    # === Buffer Operations ===
    async def save_buffer(
        self, conv_id: str, role: str, content: str, metadata: dict = None
    ) -> None:
        """Lưu 1 interaction. Tự prune nếu > max_buffer_size."""

    async def get_buffer(self, conv_id: str) -> List[dict]:
        """Đọc last N Q&A pairs."""

    # === Context ===
    async def get_context(self, conv_id: str) -> str:
        """Đọc buffer + summary + slots, format thành string cho LLM."""

    # === Slots ===
    async def get_accumulated_slots(self, conv_id: str) -> dict:
        """Đọc tất cả slots đã collect từ đầu conversation."""

    async def merge_slots(self, conv_id: str, new_slots: dict) -> dict:
        """Merge slots mới vào existing slots. Trả về merged result."""

    async def get_slot_sufficiency(self, conv_id: str) -> dict:
        """Check xem slots đủ chưa (5/7 required cho diagnostic)."""

    # === Summary ===
    async def append_to_summary(self, conv_id: str, summary_text: str) -> None:
        """Append text vào summary (LLM-generated summary)."""

    async def get_summary(self, conv_id: str) -> str:
        """Đọc summary."""

    # === Crisis ===
    async def get_crisis_state(self, conv_id: str) -> dict:
        """Đọc crisis state."""

    async def update_crisis_state(self, conv_id: str, state: dict) -> None:
        """Update crisis state."""

    # === Internal ===
    def _get_redis_key(self, conv_id: str, key_type: str) -> str:
        return f"mental_health:{conv_id}:{key_type}"

    def _cache_with_redis(self, key: str, value: Any) -> None:
        """L2 cache."""

    def _checkpoint_to_postgres(self, conv_id: str, data: dict) -> None:
        """L3 durable storage — gọi khi conversation kết thúc."""
```

### 2.2 Shared Memory Tools Factory

```python
# Tạo: backend/src/agents/shared/memory_tools.py

def create_shared_memory_tools(memory_service: MemoryService) -> dict:
    """
    Factory: tạo tools dict từ MemoryService instance.
    Mỗi agent gọi cái này trong __init__.
    """
    return {
        "save_to_buffer": {
            "description": "Lưu 1 interaction vào conversation buffer",
            "parameters": {
                "type": "object",
                "properties": {
                    "conv_id": {"type": "string"},
                    "role": {"type": "string", "enum": ["user", "assistant"]},
                    "content": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["conv_id", "role", "content"],
            },
            "handler": lambda ctx: memory_service.save_buffer(**ctx),
        },
        "get_context": {
            "description": "Đọc buffer + summary + slots, format thành string",
            "parameters": {
                "type": "object",
                "properties": {"conv_id": {"type": "string"}},
                "required": ["conv_id"],
            },
            "handler": lambda ctx: memory_service.get_context(**ctx),
        },
        "get_accumulated_slots": {
            "description": "Đọc tất cả slots đã collect",
            "parameters": {
                "type": "object",
                "properties": {"conv_id": {"type": "string"}},
                "required": ["conv_id"],
            },
            "handler": lambda ctx: memory_service.get_accumulated_slots(**ctx),
        },
        "merge_slots": {
            "description": "Merge slots mới vào existing slots",
            "parameters": {
                "type": "object",
                "properties": {
                    "conv_id": {"type": "string"},
                    "new_slots": {"type": "object"},
                },
                "required": ["conv_id", "new_slots"],
            },
            "handler": lambda ctx: memory_service.merge_slots(**ctx),
        },
        "get_crisis_state": {
            "description": "Đọc crisis state",
            "parameters": {
                "type": "object",
                "properties": {"conv_id": {"type": "string"}},
                "required": ["conv_id"],
            },
            "handler": lambda ctx: memory_service.get_crisis_state(**ctx),
        },
        "update_crisis_state": {
            "description": "Update crisis state",
            "parameters": {
                "type": "object",
                "properties": {
                    "conv_id": {"type": "string"},
                    "state": {"type": "object"},
                },
                "required": ["conv_id", "state"],
            },
            "handler": lambda ctx: memory_service.update_crisis_state(**ctx),
        },
    }
```

### 2.3 Database Models

```python
# Tạo/extend: backend/src/db/models/conversation.py

# Thêm:
class ConversationMemory(Base):
    __tablename__ = "conversation_memories"

    id: UUID
    conversation_id: UUID
    buffer: JSON          # [{"role": "user", "content": "..."}]
    summary: Text         # LLM-generated summary
    slots: JSON           # accumulated slots
    crisis_state: JSON    # {"is_high_risk": bool, "crisis_level": str}
    created_at: DateTime
    updated_at: DateTime
```

### Deliverables Phase 2

| File | Status |
|------|--------|
| `services/memory_service.py` | ✅ Tạo mới |
| `agents/shared/memory_tools.py` | ✅ Tạo mới |
| `db/models/conversation.py` | ✅ Extend |

### Verification Phase 2

```bash
pytest tests/unit/test_memory_service.py -v
pytest tests/unit/test_memory_tools.py -v
```

---

## Phase 3: SupervisorAgent (Tuần 6-7)

**Mục tiêu:** SupervisorAgent — Router thuần túy, không ReAct loop

### 3.1 SupervisorAgent

```python
# Tạo: backend/src/agents/supervisor/supervisor_agent.py

class SupervisorAgent(BaseAgent):
    """
    CHỈ CÓ 1 NHIỆM VỤ:
    1. Đọc user message
    2. Classify intent (IntentClassification skill)
    3. Extract preliminary context (PreliminaryContext skill)
    4. Route đến đúng Domain Agent

    KHÔNG điều khiển từng bước. KHÔNG có ReAct loop.
    """

    def __init__(
        self,
        memory_service: MemoryService,
        llm,
        message_bus: MessageBus,
        domain_agents: Dict[str, BaseAgent],
        config: dict,
    ):
        super().__init__(memory_service=memory_service, llm=llm, config=config)
        self._bus = message_bus
        self._domain_agents = domain_agents
        self._skills = self._register_skills()

    def _register_skills(self) -> dict:
        return {
            "IntentClassification": IntentClassification(self._llm),
            "PreliminaryContext": PreliminaryContext(self._llm),
        }

    async def run(self, input: dict, gs: GlobalState) -> dict:
        """
        Input: {"message": "user message text", "conv_id": "...", ...}
        Output: {"agent": "diagnostic", "context": {...}, "message": translated}
        """
        user_message = input["message"]
        conv_id = input["conv_id"]

        # 1. Classify intent
        intent = await self._skills["IntentClassification"].classify(user_message)

        # 2. Extract preliminary context
        preliminary_slots = await self._skills["PreliminaryContext"].extract(
            user_message
        )

        # 3. Save user message to buffer
        await self.memory_service.save_buffer(conv_id, "user", user_message)

        # 4. Route to domain agent
        target_agent = self._route(intent)

        # 5. Build routing context
        routing_context = {
            "original_message": user_message,
            "translated_message": user_message,  # IntentClassification handles language
            "language": preliminary_slots.get("language", "vi"),
            "preliminary_slots": preliminary_slots,
            "intent": intent,
            "conv_id": conv_id,
        }

        return {
            "target_agent": target_agent,
            "context": routing_context,
        }
```

### 3.2 Supervisor Skills

```python
# Tạo: backend/src/agents/supervisor/skills/intent_classification.py

class IntentClassification:
    """
    Classify user message intent vào 1 trong 5 domains.
    """

    INTENTS = [
        "diagnostic",    # Hỏi triệu chứng, muốn biết mình có bệnh gì
        "theory",        # Hỏi kiến thức tâm lý
        "treatment",     # Hỏi về điều trị
        "support",       # Cần hỗ trợ tinh thần (không phải bệnh)
        "crisis",        # Đang trong khủng hoảng
    ]

    async def classify(self, message: str) -> str:
        """Trả về 1 trong 5 intent."""

# Tạo: backend/src/agents/supervisor/skills/preliminary_context.py

class PreliminaryContext:
    """
    Extract basic context từ user message TRƯỚC KHI route.
    """

    async def extract(self, message: str) -> dict:
        """Trả về: {language, has_crisis_keywords, preliminary_slots}"""
```

### 3.3 Supervisor Tools

```python
# Tạo: backend/src/agents/supervisor/tools/routing_tools.py

def route_to_agent(intent: str, domain_agents: dict) -> str:
    """Map intent → agent_id."""
    mapping = {
        "diagnostic": "diagnostic",
        "theory": "theory",
        "treatment": "treatment",
        "support": "support",
        "crisis": "crisis",
    }
    return mapping.get(intent, "support")  # fallback to support
```

### Deliverables Phase 3

| File | Status |
|------|--------|
| `agents/supervisor/supervisor_agent.py` | ✅ Tạo mới |
| `agents/supervisor/__init__.py` | ✅ Tạo mới |
| `agents/supervisor/skills/intent_classification.py` | ✅ Tạo mới |
| `agents/supervisor/skills/preliminary_context.py` | ✅ Tạo mới |
| `agents/supervisor/skills/__init__.py` | ✅ Tạo mới |
| `agents/supervisor/tools/routing_tools.py` | ✅ Tạo mới |
| `agents/supervisor/tools/__init__.py` | ✅ Tạo mới |

### Verification Phase 3

```bash
# Test SupervisorAgent routing
pytest tests/unit/test_supervisor_agent.py -v
pytest tests/integration/test_supervisor_routing.py -v
```

---

## Phase 4: Domain Agents (Tuần 8-14)

> **3 tuần cho mỗi 2 agents: Support + Crisis → Theory + Treatment → Diagnostic**

### Phase 4A: SupportAgent + CrisisAgent (Tuần 8-10)

#### 4A.1 SupportAgent (`agents/support/support_agent.py`)

```python
# Tạo: backend/src/agents/support/support_agent.py

class SupportAgent(BaseAgent):
    """
    GOAL: Hỗ trợ sức khỏe tinh thần (non-disorder cases)
    Mỗi agent TỰ HOÀN THÀNH task từ A→Z
    """

    def __init__(self, memory_service: MemoryService, llm, config: dict):
        super().__init__(memory_service=memory_service, llm=llm, config=config)
        self._skills = {
            "CopingRetrieval": CopingRetrieval(llm),
            "EmotionalSupport": EmotionalSupport(llm),
            "PsychoEducation": PsychoEducation(llm),
            "SkillBuilding": SkillBuilding(llm),
            "AnswerFormatting": AnswerFormatting(llm),
        }
        self._shared_tools = create_shared_memory_tools(memory_service)
        # Retrieval tools (shared)
        self._retrieval_tools = create_retrieval_tools(...)

    async def run(self, input: dict, gs: GlobalState) -> dict:
        """
        1. Extract slots (từ context đã có từ Supervisor)
        2. Retrieval (nếu cần)
        3. Generate response (skills)
        4. Format answer
        5. Save to buffer
        """
        context = input["context"]
        conv_id = context["conv_id"]

        # Get accumulated context
        full_context = await self.memory_service.get_context(conv_id)

        # Determine which skills to use
        skills_to_use = self._select_skills(context)

        # Execute skills (sequential hoặc parallel tùy loại)
        results = []
        for skill_name in skills_to_use:
            result = await self._skills[skill_name].execute(
                context=full_context, gs=gs
            )
            results.append(result)

        # Combine results
        combined = self._skills["AnswerFormatting"].format(results)

        # Save to buffer
        await self.memory_service.save_buffer(
            conv_id, "assistant", combined["response"]
        )

        return {"response": combined["response"], "skills_used": skills_to_use}
```

#### 4A.2 SupportAgent Skills

```python
# Tạo files:
agents/support/skills/coping_retrieval.py
agents/support/skills/emotional_support.py
agents/support/skills/psycho_education.py
agents/support/skills/skill_building.py
agents/support/skills/answer_formatting.py
```

#### 4A.3 CrisisAgent (`agents/crisis/crisis_agent.py`)

```python
# Tạo: backend/src/agents/crisis/crisis_agent.py

class CrisisAgent(BaseAgent):
    """
    GOAL: Ứng phó khủng hoảng tâm lý
    Priority: CRITICAL — interrupt mọi agent đang chạy
    """

    async def handle_crisis(self, input: dict, gs: GlobalState) -> dict:
        """
        1. CrisisDetection — check keywords + LLM
        2. ImmediateResponse — respond immediately
        3. ProfessionalEscalation — provide hotline
        4. FollowUpSupport — monitor response
        5. Documentation — log event
        """
        conv_id = input["context"]["conv_id"]

        # Update crisis state
        await self.memory_service.update_crisis_state(conv_id, {
            "is_high_risk": True,
            "crisis_level": "active",
            "detected_at": datetime.utcnow().isoformat(),
        })

        # Emit interrupt to MessageBus (CRITICAL priority)
        # Tất cả agents khác sẽ abort
        await self._bus.emit_interrupt(
            from_agent="crisis",
            content={"action": "abort", "reason": "crisis_detected"}
        )

        # Immediate response
        response = await self._skills["ImmediateResponse"].respond(gs)

        # Escalation
        hotline_info = await self._skills["ProfessionalEscalation"].escalate(gs)

        return {
            "response": response,
            "hotline": hotline_info,
            "crisis_state": "active",
        }
```

#### 4A.4 CrisisAgent Skills

```python
# Tạo files:
agents/crisis/skills/crisis_detection.py
agents/crisis/skills/immediate_response.py
agents/crisis/skills/professional_escalation.py
agents/crisis/skills/follow_up_support.py
agents/crisis/skills/documentation.py
```

### Phase 4B: TheoryAgent + TreatmentAgent (Tuần 11-13)

#### 4B.1 TheoryAgent

```python
# Tạo: backend/src/agents/theory/theory_agent.py

class TheoryAgent(BaseAgent):
    """
    GOAL: Giải thích kiến thức tâm lý học
    Skills: ConceptRetrieval, EducationalExplanation, AnswerFormatting
    """
    # Tương tự SupportAgent structure
    # 1. Retrieval từ theory KB
    # 2. Generate explanation
    # 3. Format answer
    # 4. Save to buffer
```

```python
# Skills:
agents/theory/skills/concept_retrieval.py
agents/theory/skills/educational_explanation.py
agents/theory/skills/answer_formatting.py
```

#### 4B.2 TreatmentAgent

```python
# Tạo: backend/src/agents/treatment/treatment_agent.py

class TreatmentAgent(BaseAgent):
    """
    GOAL: Phác đồ điều trị dựa trên bằng chứng
    Skills: TreatmentRetrieval, TreatmentPlanning, PatientGuidance, AnswerFormatting
    """
    # Tương tự structure
    # 1. Retrieval từ treatment KB
    # 2. Rank treatments by evidence level
    # 3. Generate treatment plan
    # 4. Format answer với disclaimers
```

```python
# Skills:
agents/treatment/skills/treatment_retrieval.py
agents/treatment/skills/treatment_planning.py
agents/treatment/skills/patient_guidance.py
agents/treatment/skills/answer_formatting.py
```

### Phase 4C: DiagnosticAgent (Tuần 14-16)

#### 4C.1 DiagnosticAgent

```python
# Tạo: backend/src/agents/diagnostic/diagnostic_agent.py

class DiagnosticAgent(BaseAgent):
    """
    GOAL: Chuẩn đoán rối loạn tâm thần (DSM-5 based)
    Skills:
      - SymptomExtraction: extract 8 slots
      - DiagnosticRetrieval: hybrid search diagnostic KB
      - ClinicalReasoning: score symptom match, generate conclusion
      - ResponseDrafting: format answer + translate
    """

    REQUIRED_SLOTS = [
        "emotion",      # Primary emotion
        "trigger",       # What triggered it
        "duration",      # How long
        "intensity",     # Severity (1-10)
        "impact",        # Impact on life
        "stress_level",  # Stress level
        # Optional:
        "sleep",         # Sleep patterns
        "appetite",      # Appetite changes
    ]

    async def run(self, input: dict, gs: GlobalState) -> dict:
        conv_id = input["context"]["conv_id"]

        # 1. Get accumulated slots (từ Shared Memory)
        existing_slots = await self.memory_service.get_accumulated_slots(conv_id)

        # 2. Extract NEW slots từ message
        new_slots = await self._skills["SymptomExtraction"].extract(
            input["context"]["message"]
        )

        # 3. Merge slots
        merged_slots = await self.memory_service.merge_slots(conv_id, new_slots)

        # 4. Check if sufficient
        sufficiency = await self.memory_service.get_slot_sufficiency(conv_id)
        if not sufficiency["is_sufficient"]:
            # Ask for more info
            return await self._ask_for_slots(conv_id, sufficiency["missing"])

        # 5. Diagnostic retrieval (hybrid search)
        candidates = await self._skills["DiagnosticRetrieval"].search(
            query=input["context"]["message"],
            slots=merged_slots,
            collection="mental_health_diagnostic",
        )

        # 6. Clinical reasoning
        diagnosis = await self._skills["ClinicalReasoning"].reason(
            slots=merged_slots,
            candidates=candidates,
        )

        # 7. Response drafting
        response = await self._skills["ResponseDrafting"].format(
            diagnosis=diagnosis,
            slots=merged_slots,
            language=input["context"]["language"],
        )

        # 8. Save to buffer
        await self.memory_service.save_buffer(conv_id, "assistant", response)

        return {"response": response, "diagnosis": diagnosis}
```

```python
# Skills:
agents/diagnostic/skills/symptom_extraction.py  # 8 extractors
agents/diagnostic/skills/diagnostic_retrieval.py
agents/diagnostic/skills/clinical_reasoning.py
agents/diagnostic/skills/response_drafting.py
```

### Deliverables Phase 4

| Agent | Files |
|-------|-------|
| SupportAgent | `support_agent.py` + 5 skills + tools |
| CrisisAgent | `crisis_agent.py` + 5 skills + tools |
| TheoryAgent | `theory_agent.py` + 3 skills + tools |
| TreatmentAgent | `treatment_agent.py` + 4 skills + tools |
| DiagnosticAgent | `diagnostic_agent.py` + 4 skills + tools |

### Verification Phase 4

```bash
pytest tests/unit/test_support_agent.py -v
pytest tests/unit/test_crisis_agent.py -v
pytest tests/unit/test_theory_agent.py -v
pytest tests/unit/test_treatment_agent.py -v
pytest tests/unit/test_diagnostic_agent.py -v
pytest tests/integration/test_domain_agents.py -v
```

---

## Phase 5: Integration — ChatService + Entry Point (Tuần 17-18)

**Mục tiêu:** Kết nối tất cả lại — ChatService gọi SupervisorAgent

### 5.1 ChatService (`backend/src/services/chat_service.py`)

```python
# Tạo: backend/src/services/chat_service.py

class ChatService:
    """
    Entry point của toàn bộ hệ thống.
    API endpoint gọi ChatService.process_message()
    """

    def __init__(
        self,
        supervisor_agent: SupervisorAgent,
        crisis_agent: CrisisAgent,
        memory_service: MemoryService,
    ):
        self._supervisor = supervisor_agent
        self._crisis = crisis_agent
        self._memory = memory_service

    async def process_message(
        self, user_id: str, conversation_id: str, message: str, language: str = "vi"
    ) -> dict:
        """
        1. SupervisorAgent.route() → target_domain_agent
        2. Gọi domain_agent.run()
        3. Trả response
        """
        # Check crisis FIRST (nếu Supervisor chưa detect)
        crisis_state = await self._memory.get_crisis_state(conversation_id)
        if crisis_state.get("is_high_risk"):
            return await self._crisis.handle_crisis(
                {"context": {"conv_id": conversation_id, "message": message}},
                GlobalState(),
            )

        # Supervisor routes
        routing = await self._supervisor.run(
            {
                "message": message,
                "conv_id": conversation_id,
                "user_id": user_id,
                "language": language,
            },
            GlobalState(),
        )

        # Dispatch to domain agent
        target = routing["target_agent"]
        domain_agent = self._supervisor._domain_agents[target]

        result = await domain_agent.run(
            {"context": routing["context"]},
            GlobalState(),
        )

        return result
```

### 5.2 API Endpoint (`backend/src/api/v1/endpoints/chat.py`)

```python
# Update: backend/src/api/v1/endpoints/chat.py

@router.post("/chat")
async def chat(request: ChatRequest):
    result = await chat_service.process_message(
        user_id=request.user_id,
        conversation_id=request.conversation_id,
        message=request.message,
        language=request.language,
    )
    return {"data": result}
```

### 5.3 App Factory (`backend/src/main.py`)

```python
# Update: backend/src/main.py

async def create_app() -> FastAPI:
    app = FastAPI()

    # Initialize MemoryService
    memory_service = MemoryService(
        redis_client=redis,
        db_session=get_db_session,
    )

    # Initialize LLM
    llm = GeminiLLM(config)

    # Initialize MessageBus
    message_bus = MessageBus()

    # Initialize Domain Agents
    support_agent = SupportAgent(memory_service, llm, config)
    theory_agent = TheoryAgent(memory_service, llm, config)
    treatment_agent = TreatmentAgent(memory_service, llm, config)
    diagnostic_agent = DiagnosticAgent(memory_service, llm, config)
    crisis_agent = CrisisAgent(memory_service, llm, config, message_bus)

    domain_agents = {
        "support": support_agent,
        "theory": theory_agent,
        "treatment": treatment_agent,
        "diagnostic": diagnostic_agent,
        "crisis": crisis_agent,
    }

    # Initialize SupervisorAgent
    supervisor = SupervisorAgent(
        memory_service=memory_service,
        llm=llm,
        message_bus=message_bus,
        domain_agents=domain_agents,
        config=config,
    )

    # Initialize ChatService
    chat_service = ChatService(
        supervisor_agent=supervisor,
        crisis_agent=crisis_agent,
        memory_service=memory_service,
    )

    app.state.chat_service = chat_service
    return app
```

### Deliverables Phase 5

| File | Status |
|------|--------|
| `services/chat_service.py` | ✅ Tạo mới |
| `api/v1/endpoints/chat.py` | ✅ Update |
| `main.py` | ✅ Update |

### Verification Phase 5

```bash
pytest tests/integration/test_chat_flow.py -v
pytest tests/integration/test_supervisor_to_domain.py -v
```

---

## Phase 6: Testing + Deployment (Tuần 19-20)

### 6.1 Test Suite

```python
# Unit tests
tests/unit/
├── test_base_agent.py
├── test_message_bus.py
├── test_memory_service.py
├── test_memory_tools.py
├── test_supervisor_agent.py
├── test_support_agent.py
├── test_crisis_agent.py
├── test_theory_agent.py
├── test_treatment_agent.py
└── test_diagnostic_agent.py

# Integration tests
tests/integration/
├── test_supervisor_routing.py
├── test_chat_flow.py
├── test_crisis_interrupt.py
├── test_memory_persistence.py
└── test_domain_agents.py

# E2E tests
tests/e2e/
├── test_full_conversation.py
└── test_crisis_flow.py
```

### 6.2 Docker

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim
COPY backend/src /app/src
RUN pip install -r /app/src/requirements.txt
CMD ["uvicorn", "src.main:create_app", "--factory"]
```

### 6.3 LangSmith Tracing

```python
# Cấu hình LangSmith trong config:
config.langsmith = {
    "tracing": True,
    "project": "mental-health-hybrid-rag",
    "api_key": os.getenv("LANGSMITH_API_KEY"),
}

# Wrap agents với LangSmith:
from langsmith.run_helpers import traceable

@traceable(project_name="mental-health-hybrid-rag")
async def run(self, input, gs):
    return await super().run(input, gs)
```

---

## Checklist Trước Khi Commit

```python
# Tự động check trước mỗi commit:

1. gitnexus_impact() đã chạy cho tất cả symbols được modify
2. No HIGH/CRITICAL risk warnings được ignore
3. gitnexus_detect_changes() confirm changes match expected scope
4. Tất cả d=1 (WILL BREAK) dependents đã được update
5. Không có old agent names (OrchestratorAgent, MemoryAgent, etc.)
6. Tất cả agents inherit từ BaseAgent
7. MemoryService inject qua constructor (không import trong agent)
8. Tests pass: pytest tests/
```

---

## File Structure Cuối Cùng

```
backend/src/
├── agents/
│   ├── __init__.py
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── base_agent.py              # ✅ Phase 1
│   │   ├── state.py                   # ✅ Phase 1
│   │   ├── message.py                 # ✅ Phase 1
│   │   ├── constants.py               # ✅ Phase 1
│   │   ├── exceptions.py             # ✅ Phase 1
│   │   ├── circuit_breaker.py        # ✅ Phase 1
│   │   └── memory_tools.py           # ✅ Phase 2
│   ├── supervisor/                     # ✅ Phase 3
│   │   ├── __init__.py
│   │   ├── supervisor_agent.py
│   │   ├── skills/
│   │   │   ├── intent_classification.py
│   │   │   └── preliminary_context.py
│   │   └── tools/
│   │       └── routing_tools.py
│   ├── diagnostic/                    # ✅ Phase 4C
│   │   ├── __init__.py
│   │   ├── diagnostic_agent.py
│   │   ├── skills/
│   │   │   ├── symptom_extraction.py
│   │   │   ├── diagnostic_retrieval.py
│   │   │   ├── clinical_reasoning.py
│   │   │   └── response_drafting.py
│   │   └── tools/
│   ├── theory/                        # ✅ Phase 4B
│   │   ├── __init__.py
│   │   ├── theory_agent.py
│   │   └── skills/
│   ├── treatment/                     # ✅ Phase 4B
│   │   ├── __init__.py
│   │   ├── treatment_agent.py
│   │   └── skills/
│   ├── support/                       # ✅ Phase 4A
│   │   ├── __init__.py
│   │   ├── support_agent.py
│   │   └── skills/
│   └── crisis/                        # ✅ Phase 4A
│       ├── __init__.py
│       ├── crisis_agent.py
│       └── skills/
├── services/
│   ├── __init__.py
│   ├── chat_service.py               # ✅ Phase 5
│   ├── memory_service.py             # ✅ Phase 2
│   ├── auth_service.py
│   └── conversation_service.py
├── communication/
│   ├── __init__.py
│   ├── message_bus.py                # ✅ Phase 1
│   ├── events.py                     # ✅ Phase 1
│   └── subscriptions.py              # ✅ Phase 1
├── rag/
│   ├── llm/
│   ├── vectors/
│   ├── graph/
│   └── reranker/
├── db/
│   ├── models/
│   │   └── conversation.py           # ✅ Phase 2
│   └── session.py
├── api/v1/endpoints/
│   ├── chat.py                       # ✅ Phase 5
│   └── ...
└── main.py                           # ✅ Phase 5
```

---

## Timeline Tổng Hợp

```
Tuần  1-3:  Phase 1 — Foundation
             Shared modules + MessageBus + RAG verify

Tuần  4-5:  Phase 2 — MemoryService
             MemoryService + Shared Memory Tools + DB models

Tuần  6-7:  Phase 3 — SupervisorAgent
             SupervisorAgent + IntentClassification + PreliminaryContext

Tuần  8-10: Phase 4A — SupportAgent + CrisisAgent
Tuần 11-13: Phase 4B — TheoryAgent + TreatmentAgent
Tuần 14-16: Phase 4C — DiagnosticAgent

Tuần 17-18: Phase 5 — Integration
             ChatService + API Endpoint + App Factory

Tuần 19-20: Phase 6 — Testing + Deployment
             Unit/Integration/E2E tests + Docker + LangSmith

─────────────────────────────────────────
Total: 20 tuần (~5 tháng)
```
