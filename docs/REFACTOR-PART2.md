# Mental Health Hybrid RAG — Refactor Plan
## Phần 2: State Management & Memory Architecture

> **Tách biệt Agent State vs Global State. Giữ nguyên PostgreSQL Checkpointer.**
> Đọc sau: REFACTOR-PLAN-PART1.md

---

## 1. Thiết Kế State Phân Lớp (Layered State)

### 1.1 3 Tầng State

```
┌─────────────────────────────────────────────────────┐
│              GLOBAL STATE (Shared)                   │
│  ┌──────────────┬──────────────┬──────────────┐     │
│  │ Conversation  │ Crisis State │ User Context │     │
│  │ Context       │ (shared by   │ (shared by   │     │
│  │ (shared by    │  all agents) │  all agents) │     │
│  │  all agents)  │              │              │     │
│  └──────────────┴──────────────┴──────────────┘     │
│  Persistence: PostgreSQL (Checkpointer)               │
│  Access: Any agent via get_global_state()           │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────┐
│           AGENT-LOCAL STATE (Private)                │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐     │
│  │ Safety:    │  │ Retrieval: │  │ Memory:    │     │
│  │ _crisis_   │  │ _retrieved │  │ _buffer_   │     │
│  │   history  │  │   _chunks  │  │ _summary_  │     │
│  │ _last_check│  │ _confidence│  │ _slots_    │     │
│  └────────────┘  └────────────┘  └────────────┘     │
│  Persistence: In-memory (ephemeral per agent run)   │
│  Access: Only owner agent                           │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────┐
│              AGENT RESULT STATE                      │
│  Output của mỗi agent sau ReAct loop                 │
│  ┌──────────────────────────────────────────────┐   │
│  │ { agent_id, task_id, result, confidence,      │   │
│  │    artifacts, status, timestamp }            │   │
│  └──────────────────────────────────────────────┘   │
│  Persistence: Short-term (cleared when Domain Agent returns) │
└──────────────────────────────────────────────────────┘
```

### 1.2 GlobalState Schema (TypedDict)

```python
# backend/src/agents/shared/state.py

class GlobalState(TypedDict, total=False):
    # === CONVERSATION CONTEXT ===
    conversation_id: str
    user_id: str
    user_language: str                    # "vi" | "en"
    original_question: str               # Câu hỏi gốc (giữ nguyên ngôn ngữ gốc)
    current_question: str                 # Câu hỏi hiện tại (sau translate)

    # === SAFETY (SafetyAgent + CrisisResponderAgent) ===
    is_high_risk: bool
    crisis_level: str                    # "critical" | "high" | "moderate" | "none"
    crisis_stage: int                    # 1=immediate, 2=follow-up, 3=supportive
    crisis_indicators: List[str]
    crisis_response_count: int
    recent_crisis_detected: bool         # Crisis trong conversation gần đây
    crisis_sensitivity_increased: bool  # Tăng sensitivity sau crisis

    # === QUERY ROUTING ===
    query_type: str                      # "follow_up" | "topic_change" | "off_topic"
    query_nature: str                    # "personal" | "theoretical"
    awaiting_treatment_confirmation: bool
    wants_treatment: bool

    # === SLOT FILLING ===
    slots: Dict[str, Any]                # {emotion, trigger, duration, intensity, ...}
    missing_slots: List[str]
    relevant_missing_slots: List[str]
    has_sufficient_slots: bool           # True nếu đủ 5/7 required slots

    # === RETRIEVAL RESULTS (shared read-only after fill) ===
    retrieval_results: Dict[str, Any]    # {
                                          #   "coping": [...chunks],
                                          #   "adjustment": [...chunks],
                                          #   "diagnostic": [...chunks],
                                          #   "treatment": [...chunks],
                                          #   "theoretical": [...chunks],
                                          #   "graph_context": str
                                          # }

    # === ASSESSMENT ===
    assessment_category: str             # "normal_response" | "adjustment_reaction" | "possible_disorder"
    normal_stress_score: float
    adjustment_reaction_score: float
    diagnostic_chunks: str
    detected_disease: str
    diagnostic_confidence: float

    # === MEMORY (shared across all agents via MemoryService) ===
    conversation_buffer: List            # last 3 Q&A pairs (json string)
    summary_context: str                  # Tóm tắt các cặp cũ

    # === ANSWER GENERATION ===
    answer: str
    answer_metadata: Dict[str, Any]       # {is_high_risk, detected_disease, ...}

    # === AGENT RESULT TRACKING ===
    task_results: Dict[str, "TaskResult"]  # task_id → TaskResult
    pending_tasks: List[str]               # task_ids đang chờ

    # === CONTROL ===
    done: bool
    error: Optional[str]
    error_agent_id: Optional[str]
```

### 1.3 TaskResult Schema

```python
@dataclass
class TaskResult:
    task_id: str
    agent_id: str
    status: str                          # "pending" | "running" | "completed" | "failed"
    result: Optional[Any]
    confidence: Optional[float]
    artifacts: Dict[str, Any]            # Named outputs (e.g., "answer", "disease")
    started_at: datetime
    completed_at: Optional[datetime]
    error: Optional[str]
```

---

## 2. Agent-Local State (Private per Agent)

### 2.1 Mỗi Agent tự quản lý local state

```python
# base_agent.py

class BaseAgent(ABC):
    def __init__(self, agent_id: str, ...):
        self.agent_id = agent_id
        self._local_state: Dict[str, Any] = {}  # Agent-private state
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._result_cache: LRUCache = LRUCache(maxsize=100)

    async def run(self, input: Any, global_state: GlobalState) -> Any:
        """
        Agent ReAct loop:
        1. Reason: analyze input + global state
        2. Act: call tool(s)
        3. Update local state
        4. Check if done → return result
        5. Loop or return
        """
        pass

    def update_local_state(self, updates: dict):
        """Cập nhật agent-local state (private, không ảnh hưởng global)."""
        self._local_state.update(updates)

    def get_local_state(self) -> dict:
        return self._local_state.copy()
```

### 2.2 Agent-Local State cho từng Agent

```python
# SupportAgent._local_state:
{
    "_crisis_keyword_matches": [...],
    "_last_crisis_check_result": dict,
    "_conversation_turns_since_last_check": int,
    "_escalation_history": [...],
    "_crisis_check_cache": {...}          # Cache: message → crisis result
}

# DiagnosticAgent._local_state (SymptomExtraction skill inline):
{
    "_extracted_symptoms": {...},         # SymptomExtraction skill output
    "_missing_symptoms": [...],
    "_symptom_extraction_confidence": float,
    "_follow_up_questions": [...],
}

# TheoryAgent._local_state:
{
    "_retrieved_theories": [...],
    "_theory_confidence": float,
    "_cited_references": [...]
}

# TreatmentAgent._local_state:
{
    "_treatment_options": [...],
    "_treatment_confidence": float,
    "_contraindications_checked": bool
}

# CrisisAgent._local_state:
{
    "_intervention_stage": int,           # 1=immediate, 2=follow-up, 3=supportive
    "_resources_provided": [...],
    "_escalation_triggered": bool
}

# SupervisorAgent._local_state:
{
    "_last_intent": str,
    "_routing_confidence": float,
    "_domain_agent_last_routed": str,
}
```

---

## 3. Message Bus Architecture

### 3.1 Thiết kế Pub/Sub Message Bus

```python
# backend/src/communication/message_bus.py

@dataclass
class AgentMessage:
    id: str                              # UUID
    from_agent: str                      # Agent gửi
    to_agent: Optional[str]              # None = broadcast
    message_type: str                    # "task" | "result" | "event" | "error"
    priority: str                        # "low" | "normal" | "high" | "critical"
    content: Any                         # Payload
    task_id: Optional[str]               # Link to task
    conversation_id: str
    timestamp: datetime
    reply_to: Optional[str]              # Original message ID

    # === Message Types ===
    # task: Supervisor → Domain Agent (giao việc)
    # result: Domain Agent → Supervisor (kết quả tự hoàn thành A→Z)
    # event: Any → Any (internal events)
    # error: Any → Supervisor (error reporting)
    # interrupt: CrisisAgent → Any (dừng tất cả khi crisis)

class MessageBus:
    """
    In-memory pub/sub message bus cho inter-agent communication.
    Thread-safe, async-first.
    """

    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}  # agent_id → queue
        self._subscribers: Dict[str, Set[str]] = {}  # event_type → {agent_ids}
        self._pending: Dict[str, List[AgentMessage]] = defaultdict(list)  # task_id → messages
        self._lock = asyncio.Lock()

    # === Pub (send) ===
    async def send(self, message: AgentMessage) -> bool:
        """
        Send message:
        - Priority=critical: interrupt receiver (CrisisAgent → all)
        - Direct: put vào agent-specific queue
        - Broadcast: put vào all subscribed queues
        """
        if message.priority == "critical":
            await self._broadcast_interrupt(message)
            return True

        if message.to_agent:
            await self._queues[message.to_agent].put(message)
        else:
            for agent_id in self._subscribers.get(message.message_type, []):
                await self._queues[agent_id].put(message.copy(to_agent=agent_id))

        if message.task_id:
            async with self._lock:
                self._pending[message.task_id].append(message)
        return True

    # === Sub (receive) ===
    async def receive(self, agent_id: str, timeout: float = 30) -> Optional[AgentMessage]:
        """Agent nhận message từ queue riêng."""
        try:
            return await asyncio.wait_for(
                self._queues[agent_id].get(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return None

    # === Subscribe ===
    def subscribe(self, agent_id: str, event_types: List[str]):
        """Agent đăng ký nhận message theo event type."""
        for et in event_types:
            self._subscribers[et].add(agent_id)

    # === Interrupt (Safety) ===
    async def _broadcast_interrupt(self, message: AgentMessage):
        """
        Priority interrupt — CrisisAgent gửi lệnh dừng:
        1. Gửi interrupt message đến tất cả running agents
        2. Agents nhận interrupt → hủy current task, return control
        3. CrisisAgent takes over (priority tuyệt đối)
        """
        for agent_id, queue in self._queues.items():
            if agent_id != "crisis_agent":
                await queue.put(AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent="crisis_agent",
                    to_agent=agent_id,
                    message_type="interrupt",
                    priority="critical",
                    content={"action": "abort", "reason": message.content},
                    timestamp=datetime.utcnow()
                ))

    # === Result waiting ===
    async def wait_for_result(self, task_id: str, timeout: float = 30) -> Optional[AgentMessage]:
        """Domain Agent chạy tự chủ, return khi done. Supervisor chờ result."""
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            async with self._lock:
                for msg in self._pending[task_id]:
                    if msg.message_type == "result":
                        self._pending[task_id].remove(msg)
                        return msg
            await asyncio.sleep(0.1)
        return None

    # === Register agent queue ===
    def register_agent(self, agent_id: str):
        """Đăng ký queue cho agent mới."""
        self._queues[agent_id] = asyncio.Queue()
```

### 3.2 Agent Registration & Message Flow

```python
# backend/src/agents/supervisor/supervisor_agent.py

class SupervisorAgent:
    """
    SupervisorAgent — Router only (no orchestration logic).
    Uses IntentClassification skill for routing decisions.
    """

    def __init__(self, message_bus: MessageBus, checkpointer, ...):
        self.bus = message_bus
        self.intent_classifier = IntentClassificationSkill(llm)  # INLINE skill
        # Register all domain agents
        self._register_agents()

    def _register_agents(self):
        """Đăng ký tất cả domain agents vào message bus."""
        self.bus.register_agent(AGENTS.SUPERVISOR)
        self.bus.register_agent(AGENTS.DIAGNOSTIC)
        self.bus.register_agent(AGENTS.THEORY)
        self.bus.register_agent(AGENTS.TREATMENT)
        self.bus.register_agent(AGENTS.SUPPORT)
        self.bus.register_agent(AGENTS.CRISIS)

        # Subscriptions
        self.bus.subscribe(AGENTS.CRISIS, ["task"])
        self.bus.subscribe(AGENTS.DIAGNOSTIC, ["task"])
        # ... all agents subscribe to "error" events

    async def route(self, user_message: str, conversation_id: str) -> dict:
        """
        Supervisor routing loop:
        1. Classify intent via IntentClassification skill
        2. Check safety flags in global_state
        3. Route to appropriate domain agent(s)
        4. Return response from selected agent(s)
        """
        # Step 1: Intent classification (Supervisor skill)
        intent = await self.intent_classifier.classify(user_message, global_state)

        # Step 2: Safety check (always run in parallel)
        await self.bus.send(AgentMessage(
            from_agent=AGENTS.SUPERVISOR,
            to_agent=AGENTS.SUPPORT,
            message_type="task",
            priority="critical",        # Safety always critical priority
            content={"action": "check", "message": user_message},
            conversation_id=conversation_id
        ))

        # Step 3: Route based on intent
        if intent == "crisis":
            return await self.bus.wait_for_result(task_id="crisis", timeout=5)
        elif intent == "diagnostic":
            await self.bus.send(AgentMessage(
                from_agent=AGENTS.SUPERVISOR,
                to_agent=AGENTS.DIAGNOSTIC,
                message_type="task",
                priority="normal",
                content={"action": "assess", "message": user_message},
                conversation_id=conversation_id
            ))
        # ... route to other agents

        # ... continue flow
```

---

## 4. PostgreSQL Checkpointer — Giữ Nguyên & Mở Rộng

### 4.1 Giữ nguyên infrastructure hiện tại

```python
# backend/src/rag/workflow/checkpointer.py
# Giữ nguyên: AsyncPostgresSaver, connection pool, thread-based isolation
# Chỉ cần cập nhật serialization để hỗ trợ GlobalState mới

class GlobalStateSerializer:
    """Serialize/deserialize GlobalState cho checkpointer."""

    @staticmethod
    def serialize(state: GlobalState) -> dict:
        return {
            "conversation_id": state.get("conversation_id"),
            "slots": json.dumps(state.get("slots", {})),
            "buffer": json.dumps(state.get("conversation_buffer", [])),
            "summary": state.get("summary_context", ""),
            "crisis_state": json.dumps({
                "is_high_risk": state.get("is_high_risk"),
                "crisis_level": state.get("crisis_level"),
                "crisis_stage": state.get("crisis_stage"),
                "crisis_indicators": state.get("crisis_indicators", []),
                "crisis_response_count": state.get("crisis_response_count", 0),
                "recent_crisis_detected": state.get("recent_crisis_detected"),
                "crisis_sensitivity_increased": state.get("crisis_sensitivity_increased"),
            }),
            "retrieval_results": json.dumps(state.get("retrieval_results", {})),
            "assessment": json.dumps({
                "category": state.get("assessment_category"),
                "normal_stress_score": state.get("normal_stress_score"),
                "adjustment_reaction_score": state.get("adjustment_reaction_score"),
                "detected_disease": state.get("detected_disease"),
                "diagnostic_confidence": state.get("diagnostic_confidence"),
            }),
            "metadata": json.dumps(state.get("answer_metadata", {})),
            "updated_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def deserialize(row: dict) -> GlobalState:
        state: GlobalState = {}
        state["conversation_id"] = row["conversation_id"]
        state["slots"] = json.loads(row["slots"])
        state["conversation_buffer"] = json.loads(row["buffer"])
        state["summary_context"] = row["summary"]
        crisis = json.loads(row["crisis_state"])
        state.update(crisis)
        state["retrieval_results"] = json.loads(row["retrieval_results"])
        assessment = json.loads(row["assessment"])
        state.update(assessment)
        state["answer_metadata"] = json.loads(row["metadata"])
        return state
```

### 4.2 Checkpointer Interface cho Agents

```python
# backend/src/agents/memory/checkpointer_interface.py

class CheckpointerInterface:
    """
    Interface cho agents truy cập checkpointer.
    Mỗi conversation_id có checkpoint riêng (thread-based isolation).
    """

    def __init__(self, checkpointer: AsyncPostgresSaver):
        self.checkpointer = checkpointer

    async def load_global_state(self, conversation_id: str) -> GlobalState:
        """Load checkpoint cho conversation. Trả về GlobalState rỗng nếu chưa có."""
        # Sử dụng thread_id = f"conversation_{conversation_id}"
        checkpoint = await self.checkpointer.aget(conversation_id)
        if checkpoint:
            return GlobalStateSerializer.deserialize(checkpoint)
        return GlobalState()

    async def save_global_state(self, conversation_id: str, state: GlobalState):
        """Save checkpoint sau mỗi interaction."""
        serialized = GlobalStateSerializer.serialize(state)
        await self.checkpointer.aput(conversation_id, serialized)

    async def load_buffer(self, conversation_id: str) -> List[dict]:
        """Load conversation buffer (last 3 Q&A)."""
        state = await self.load_global_state(conversation_id)
        return state.get("conversation_buffer", [])

    async def load_summary(self, conversation_id: str) -> str:
        """Load summary context (older pairs)."""
        state = await self.load_global_state(conversation_id)
        return state.get("summary_context", "")

    async def load_slots(self, conversation_id: str) -> Dict[str, Any]:
        """Load accumulated slots."""
        state = await self.load_global_state(conversation_id)
        return state.get("slots", {})
```

---

## 5. MemoryService — Service (Không Phải Agent)

### 5.1 Thiết kế MemoryService

```python
# backend/src/services/memory_service.py

class MemoryService:
    """
    MemoryService quản lý conversation memory (SERVICE, not Agent).
    Được inject vào các domain agents.
    - Buffer: last 3 Q&A pairs (full text)
    - Summary: older pairs (LLM-generated summary)
    - Slots: structured patient information (accumulated)
    """

    def __init__(self, checkpointer_interface: CheckpointerInterface, llm=None):
        self.checkpointer = checkpointer_interface
        self.llm = llm
        self._pending_save: List[dict] = []  # Local buffer (not agent-local state)
        self._buffer_flush_needed: bool = False
        self._summary_regenerate_needed: bool = False

    # === PUBLIC API ===

    async def save_interaction(
        self,
        conv_id: str,
        question: str,
        answer: str,
        global_state: GlobalState,
        **extra: str
    ) -> dict:
        """Lưu 1 Q&A pair vào buffer. Tự động flush summary nếu buffer đầy."""
        qa_pair = {
            "question": question,
            "answer": answer,
            "slots": global_state.get("slots", {}),
            "assessment": global_state.get("assessment_category"),
            "disease": global_state.get("detected_disease"),
            "timestamp": datetime.utcnow().isoformat(),
            **extra
        }

        # Load current buffer
        buffer: List[dict] = global_state.get("conversation_buffer", [])
        buffer.append(qa_pair)

        # Keep only last 3
        if len(buffer) > 3:
            older_pairs = buffer[:-3]
            buffer = buffer[-3:]

            # Update summary (append older to existing summary)
            existing_summary = global_state.get("summary_context", "")
            summary_update = await self._generate_summary_text(older_pairs)
            new_summary = f"{existing_summary}\n{summary_update}" if existing_summary else summary_update
            global_state["summary_context"] = new_summary

        global_state["conversation_buffer"] = buffer

        # Save to PostgreSQL
        await self.checkpointer.save_global_state(conv_id, global_state)

        return {"status": "saved", "buffer_size": len(buffer)}

    async def get_context(self, global_state: GlobalState) -> dict:
        """
        Trả về full context cho agent sử dụng.
        Context = slots + buffer + summary, formatted cho LLM.
        """
        buffer = global_state.get("conversation_buffer", [])
        summary = global_state.get("summary_context", "")
        slots = global_state.get("slots", {})

        return {
            "buffer": self._format_buffer(buffer),
            "summary": summary,
            "slots": self._format_slots(slots),
            "formatted": self._format_full_context(buffer, summary, slots)
        }

    async def merge_slots(self, conv_id: str, new_slots: Dict[str, Any], global_state: GlobalState) -> dict:
        """Merge slots mới vào existing slots. Được gọi từ DiagnosticAgent."""
        existing_slots = global_state.get("slots", {})

        # Merge: new slots override existing
        merged = {**existing_slots, **new_slots}

        # Validate required slots
        required = ["emotion", "trigger", "duration", "intensity", "impact", "need", "stress_level"]
        missing = [k for k in required if k not in merged or not merged[k]]
        sufficient = len(missing) <= 2  # Allow 2 missing

        global_state["slots"] = merged
        global_state["missing_slots"] = missing
        global_state["relevant_missing_slots"] = self._filter_relevant_missing(missing)
        global_state["has_sufficient_slots"] = sufficient

        await self.checkpointer.save_global_state(conv_id, global_state)

        return {"slots": merged, "missing": missing, "sufficient": sufficient}

    # === INTERNAL HELPERS ===

    async def _generate_summary_text(self, older_pairs: List[dict]) -> str:
        """Generate LLM summary for older Q&A pairs."""
        if not self.llm:
            return str(older_pairs)
        # TODO: call LLM to summarize
        return str(older_pairs)

    def _format_buffer(self, buffer: List[dict]) -> str:
        if not buffer:
            return ""
        lines = []
        for i, pair in enumerate(buffer, 1):
            lines.append(f"--- Turn {i} ---")
            lines.append(f"User: {pair['question']}")
            lines.append(f"Assistant: {pair['answer']}")
        return "\n".join(lines)

    def _format_slots(self, slots: Dict[str, Any]) -> str:
        if not slots:
            return "No structured information collected yet."
        lines = ["Structured information:"]
        for key, value in slots.items():
            lines.append(f"  - {key}: {value}")
        return "\n".join(lines)

    def _format_full_context(self, buffer, summary, slots) -> str:
        return f"""Conversation Context:
{self._format_buffer(buffer)}

{self._format_slots(slots)}

Previous Summary:
{summary or "No previous conversation."}"""

    def _filter_relevant_missing(self, missing: List[str]) -> List[str]:
        """Filter to only return clinically relevant missing slots."""
        return missing  # TODO: implement relevance scoring
```

---

## 6. Concurrency & Isolation

### 6.1 Per-Conversation Thread Isolation

```python
# Giữ nguyên từ checkpointer hiện tại:
# thread_id = f"conversation_{conversation_id}"
# Đảm bảo 2 conversations chạy song song không conflict state

# Mapping:
# Conversation A → thread_pool_A → agent instances A1, A2, ...
# Conversation B → thread_pool_B → agent instances B1, B2, ...
```

### 6.2 Agent Instance Management

```python
# backend/src/agents/agent_manager.py

class AgentManager:
    """
    Quản lý lifecycle của 5 Domain Agents + MemoryService.

    Agents (5):
      - SupervisorAgent  (ROUTER — IntentClassification skill inline)
      - DiagnosticAgent  (SymptomExtraction skill inline)
      - TheoryAgent      (ResponseDrafting skill inline)
      - TreatmentAgent   (ResponseDrafting skill inline)
      - SupportAgent     (ResponseDrafting skill inline)
      - CrisisAgent      (ResponseDrafting skill inline)

    Service (1):
      - MemoryService    (injected into all agents)

    NO MemoryAgent, NO OrchestratorAgent, NO SlotFillingAgent,
    NO TranslatorAgent, NO AnswerGeneratorAgent.
    """

    def __init__(self, llm, checkpointer, message_bus, ...):
        self.llm = llm
        self.checkpointer = checkpointer
        self.bus = message_bus
        self._instances: Dict[str, BaseAgent] = {}
        self._conv_agents: Dict[str, Dict[str, BaseAgent]] = {}  # conv_id → {agent_id → instance}

        # MemoryService — singleton, injected into all agents
        self._memory_service = MemoryService(
            CheckpointerInterface(checkpointer),
            llm=llm
        )

    def get_singleton_agent(self, agent_id: str) -> BaseAgent:
        """Shared stateless agent instances."""
        if agent_id not in self._instances:
            self._instances[agent_id] = self._create_agent(agent_id)
        return self._instances[agent_id]

    def get_conversation_agent(self, conv_id: str, agent_id: str) -> BaseAgent:
        """Per-conversation stateful agent. Mỗi conv có instance riêng."""
        if conv_id not in self._conv_agents:
            self._conv_agents[conv_id] = {}
        if agent_id not in self._conv_agents[conv_id]:
            self._conv_agents[conv_id][agent_id] = self._create_agent(agent_id)
        return self._conv_agents[conv_id][agent_id]

    def get_memory_service(self) -> MemoryService:
        """Returns the shared MemoryService instance."""
        return self._memory_service

    def cleanup_conversation(self, conv_id: str):
        """Dọn agents sau khi conversation kết thúc."""
        if conv_id in self._conv_agents:
            del self._conv_agents[conv_id]

    def _create_agent(self, agent_id: str) -> BaseAgent:
        """Factory method để tạo agent instance. MemoryService injected."""
        agents = {
            AGENTS.SUPERVISOR: lambda: SupervisorAgent(self.llm, self.bus, self._memory_service, ...),
            AGENTS.DIAGNOSTIC: lambda: DiagnosticAgent(self.llm, self._memory_service, ...),
            AGENTS.THEORY:     lambda: TheoryAgent(self.llm, self._memory_service, ...),
            AGENTS.TREATMENT:  lambda: TreatmentAgent(self.llm, self._memory_service, ...),
            AGENTS.SUPPORT:    lambda: SupportAgent(self.llm, self._memory_service, ...),
            AGENTS.CRISIS:     lambda: CrisisAgent(self.llm, self.bus, self._memory_service, ...),
        }
        return agents[agent_id]()
```

---

## 7. State Flow: User Message → Domain Agents

```
User sends: "Tôi cảm thấy rất lo âu gần đây..."

STEP 1: SupervisorAgent.init(conversation_id)
  → Load checkpoint (PostgreSQL)
  → global_state = GlobalState(conversation_id=conv_id, ...)
  → agent_manager = AgentManager()   # includes MemoryService

STEP 2: SupervisorAgent.route() ReAct Loop
  │
  ├─ REASON: "IntentClassification skill → classify intent"
  ├─ ACT: IntentClassificationSkill.classify(user_message, global_state)
  │        → intent = "personal" (not crisis)
  │
  ├─ ACT: bus.send(to=SupportAgent, task="check", priority=critical)
  │        (SupportAgent runs crisis check)
  │
  ├─ OBSERVE: SupportAgent → {is_crisis: False, level: "none"}
  │            global_state.update(...)
  │
  ├─ REASON: "Safe + personal → route to DiagnosticAgent"
  ├─ ACT: bus.send(to=DiagnosticAgent, task="assess", context={...})
  │
  ├─ OBSERVE: DiagnosticAgent (SymptomExtraction skill)
  │            → {slots: {emotion: "lo âu", ...}, sufficient: False}
  │            global_state.update(slots, has_sufficient_slots)
  │
  ├─ REASON: "Missing slots → DiagnosticAgent requests more info"
  │            (DiagnosticAgent uses ResponseDrafting skill to ask)
  │
  └─ OBSERVE: Return "request more info" question to user
             → WAIT for user response
             → Loop back to STEP 2 with new message

STEP 3: (Sau khi đủ slots)
  ├─ REASON: "Sufficient slots → DiagnosticAgent completes assessment"
  ├─ ACT: DiagnosticAgent → {category: "adjustment_reaction", score: 55}
  │
  ├─ OBSERVE: Assessment → global_state.update(assessment_category, ...)
  │
  ├─ REASON: "adjustment_reaction → route to TheoryAgent"
  ├─ ACT: bus.send(to=TheoryAgent, task="retrieve_theory", slots={...})
  │            TheoryAgent → GraphRetrievalTool → Milvus → Neo4j → Cohere
  │
  ├─ OBSERVE: TheoryAgent → {theory_context: "...", confidence: 0.82}
  │            global_state.update(retrieval_results)
  │
  ├─ REASON: "Theory retrieved → ResponseDrafting skill generates answer"
  │            TheoryAgent.ResponseDraftingSkill.draft(global_state, theory_context)
  │            → answer (VI, empathetic, with references)
  │
  └─ OBSERVE: Final answer (VI)
             → Return {answer, metadata} to user

STEP 4: SupervisorAgent.done
  ├─ ACT: MemoryService.save_interaction(conv_id, question, answer, global_state)
  │        (Service, NOT agent — injected into SupervisorAgent)
  ├─ OBSERVE: Memory saved to buffer + PostgreSQL checkpoint
  └─ Return {answer, metadata} to user
```

---

## 8. So Sánh State Management Cũ vs Mới

| Khía cạnh | KGState (Cũ) | GlobalState + LocalState (Mới) |
|-----------|-------------|-------------------------------|
| Scope | 1 global TypedDict | 2 levels: global + agent-local |
| Updates | Overwritten at each node | Agents update own portion only |
| Thread safety | Thread ID isolation | Thread isolation + agent-local private state |
| Persistence | Full state checkpoint | Selective: slots, buffer, summary, crisis |
| Debugging | Hard to trace updates | Clear: which agent modified what |
| Caching | None | Agent-local LRU cache for repeated calls |
| Memory usage | Single large dict | Distributed: each agent only holds what it needs |
| Checkpoint size | Full KGState | Compact: only persistent fields saved |

---

*Lưu ý: File này là Part 2 — State Management & Memory. Tiếp theo: Part 3 — Communication Layer (Supervisor + Domain Agents + Message Passing).*
