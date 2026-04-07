# Mental Health Hybrid RAG — Refactor Plan
## Phần 3: Communication Layer — SupervisorAgent & Message Passing

> **SupervisorAgent (Router) + 5 Domain Agents + Message Bus + MemoryService + Module Boundaries**
> Đọc sau: REFACTOR-PLAN-PART1.md, REFACTOR-PLAN-PART2.md

---

## 1. SupervisorAgent — Router Only (Không Orchestrate)

### 1.1 System Prompt

```python
# ai/modules/supervisor/prompts.py

SUPERVISOR_SYSTEM_PROMPT = """Bạn là SupervisorAgent — bộ định tuyến duy nhất của hệ thống Mental Health Hybrid RAG.

## Vai trò của bạn: CHỈ ĐỊNH TUYẾN, KHÔNG ĐIỀU PHỐI
- Bạn là một ROUTER thuần túy, không chạy ReAct loop
- Bạn phân tích intent → gửi message đến đúng Domain Agent
- Bạn KHÔNG chờ từng kết quả từng bước như orchestrator
- Mỗi Domain Agent tự quản lý ReAct loop riêng và gửi response trực tiếp

## ĐIỀU QUAN TRỌNG — KHÔNG NHẦM LẪN:
- SupervisorAgent = ROUTER (đọc intent, gửi đi, done)
- 5 Domain Agents = AGENTS có ReAct loop riêng, tự gửi kết quả về user
- MemoryService = SERVICE, được inject vào agents, KHÔNG gọi qua message bus
- KHÔNG có "OrchestratorAgent" trong kiến trúc này

## 5 Domain Agents bạn có thể gửi message đến:

| Agent | ID | GOAL | Priority |
|-------|-----|------|----------|
| DiagnosticAgent | diagnostic | Chuẩn đoán rối loạn tâm thần | Normal |
| TheoryAgent | theory | Giải thích kiến thức tâm lý | Normal |
| TreatmentAgent | treatment | Phác đồ điều trị | Normal |
| SupportAgent | support | Hỗ trợ sức khỏe tinh thần (non-disorder) | Normal |
| CrisisAgent | crisis | Ứng phó khủng hoảng (CRITICAL interrupt) | CRITICAL (preempt) |

## Skills BÊN TRONG SupervisorAgent (không phải agents riêng):

1. **IntentClassification skill** (inside SupervisorAgent):
   - classify_intent(message) → "diagnostic" | "theory" | "treatment" | "support" | "crisis" | "off_topic"

2. **PreliminaryContext skill** (inside SupervisorAgent):
   - extract_preliminary_slots(message) → thu thập ngữ cảnh ban đầu (tuổi, giới tính, mô tả ngắn)

## Routing Logic:

```
1. Crisis Signal detected by IntentClassification?
   → route_to_agent("crisis", message, context)
   → SupervisorAgent DONE (CrisisAgent emit to MessageBus with CRITICAL priority)
   → CrisisAgent INTERRUPT mọi agent đang chạy

2. Intent = "off_topic"?
   → SupervisorAgent tự generate fallback response
   → DONE

3. Intent = "diagnostic"?
   → route_to_agent("diagnostic", message, context)
   → DONE (DiagnosticAgent gửi response trực tiếp)

4. Intent = "theory"?
   → route_to_agent("theory", message, context)
   → DONE

5. Intent = "treatment"?
   → route_to_agent("treatment", message, context)
   → DONE

6. Intent = "support"?
   → route_to_agent("support", message, context)
   → DONE
```

## Tool Usage Protocol (SupervisorAgent tools):

1. **route_to_agent(agent_id, message, context)**: Gửi message đến Domain Agent. KHÔNG chờ kết quả — agent tự gửi response về user.
2. **classify_intent(message)**: IntentClassification skill → trả về intent string.
3. **extract_preliminary_slots(message)**: PreliminaryContext skill → trả về dict slots sơ bộ.
4. **save_to_buffer(conversation_id, message, role)**: Gọi MemoryService qua shared_memory_tools.
5. **get_context(conversation_id, limit)**: Gọi MemoryService để lấy conversation buffer.

## Safety Protocol:
- IntentClassification chạy ĐẦU TIÊN trước mọi routing
- Nếu intent = "crisis" → gửi ngay đến CrisisAgent (CRITICAL priority)
- CrisisAgent có quyền emit interrupt message (priority=critical, message_type=interrupt) lên MessageBus
- Interrupt đến tất cả agents đang chạy → abort current task

## Output Format:
SupervisorAgent không return "answer" — chỉ:
{
    "status": "routed",
    "routed_to": str,              # "diagnostic" | "theory" | "treatment" | "support" | "crisis"
    "context": dict,               # slots, language, query_type
    "message_id": str
}

CrisisAgent và các Domain Agent gửi response TRỰC TIẾP qua ChatService/websocket.
"""
```

### 1.2 SupervisorAgent Implementation (Router)

```python
# ai/modules/supervisor/supervisor_agent.py

class SupervisorAgent(TaskAgent):
    """
    SupervisorAgent — PURE ROUTER, không có ReAct loop.
    Entry point: nhận user message → phân loại intent → gửi đến Domain Agent.
    """

    AGENT_ID = "supervisor"
    TOOLS = [
        "route_to_agent",
        "classify_intent",
        "extract_preliminary_slots",
        "save_to_buffer",
        "get_context",
    ]

    def __init__(
        self,
        llm,
        message_bus: MessageBus,
        config: SupervisorConfig,
        memory_service: MemoryService,
    ):
        super().__init__(llm, name=self.AGENT_ID)
        self.bus = message_bus
        self.config = config
        self.memory = memory_service
        self._setup_tools()
        self._register_skills()

    def _setup_tools(self):
        """Đăng ký router tools."""
        self.tools = {
            "route_to_agent": self._route_to_agent,
            "classify_intent": self._classify_intent,
            "extract_preliminary_slots": self._extract_preliminary_slots,
            "save_to_buffer": self._save_to_buffer,
            "get_context": self._get_context,
        }

    def _register_skills(self):
        """Đăng ký skills — SupervisorAgent sở hữu IntentClassification."""
        self.skills = {
            "intent_classification": IntentClassification(self.llm),
            "preliminary_context": PreliminaryContext(self.llm),
        }

    async def run(self, user_message: str, conversation_id: str) -> dict:
        """
        Pure routing: không có ReAct loop.
        1. classify_intent
        2. extract_preliminary_slots
        3. route_to_agent
        4. DONE
        """
        # Load context from MemoryService
        buffer = await self.memory.get_buffer(conversation_id, limit=10)
        language = self._detect_language(user_message)

        # Step 1: IntentClassification (always first)
        intent = await self.skills["intent_classification"].classify(
            user_message, buffer
        )

        # Step 2: PreliminaryContext
        slots = await self.skills["preliminary_context"].extract(
            user_message, buffer
        )

        # Step 3: Route
        if intent == "crisis":
            # Crisis → emit to MessageBus with CRITICAL priority (interrupt)
            await self._route_crisis(user_message, slots, buffer, language, conversation_id)
            return {
                "status": "routed",
                "routed_to": "crisis",
                "context": {"slots": slots, "language": language, "query_type": "crisis"},
                "message_id": str(uuid.uuid4()),
            }

        if intent == "off_topic":
            # No routing — Supervisor generates fallback directly
            fallback = await self._generate_fallback(user_message)
            return {
                "status": "fallback",
                "answer": fallback,
                "context": {"slots": slots, "language": language},
                "message_id": str(uuid.uuid4()),
            }

        # Step 4: Route to Domain Agent (async, non-blocking)
        context = {
            "slots": slots,
            "language": language,
            "query_type": intent,
            "buffer": buffer,
            "original_message": user_message,
        }

        await self._route_to_domain_agent(intent, user_message, context, conversation_id)

        return {
            "status": "routed",
            "routed_to": intent,
            "context": context,
            "message_id": str(uuid.uuid4()),
        }

    async def _route_crisis(
        self, message: str, slots: dict, buffer: list, language: str, conversation_id: str
    ):
        """
        Route to CrisisAgent with CRITICAL interrupt.
        CrisisAgent will emit to MessageBus with priority=critical → all agents abort.
        """
        await self.bus.send(AgentMessage(
            id=str(uuid.uuid4()),
            from_agent=self.AGENT_ID,
            to_agent="crisis",
            message_type="task",
            priority="critical",  # Crisis = CRITICAL priority
            content={
                "task": "handle_crisis",
                "message": message,
                "slots": slots,
                "buffer": buffer,
                "language": language,
            },
            task_id=f"crisis_{uuid.uuid4().hex[:8]}",
            conversation_id=conversation_id,
            timestamp=datetime.utcnow(),
        ))

    async def _route_to_domain_agent(
        self, intent: str, message: str, context: dict, conversation_id: str
    ):
        """Route to appropriate Domain Agent (non-blocking)."""
        agent_map = {
            "diagnostic": "diagnostic",
            "theory": "theory",
            "treatment": "treatment",
            "support": "support",
        }
        agent_id = agent_map.get(intent, "support")

        await self.bus.send(AgentMessage(
            id=str(uuid.uuid4()),
            from_agent=self.AGENT_ID,
            to_agent=agent_id,
            message_type="task",
            priority="high",
            content={
                "message": message,
                "context": context,
            },
            task_id=f"{agent_id}_{uuid.uuid4().hex[:8]}",
            conversation_id=conversation_id,
            timestamp=datetime.utcnow(),
        ))

    async def _classify_intent(self, message: str) -> str:
        """Skill: IntentClassification."""
        return await self.skills["intent_classification"].classify(message, [])

    async def _extract_preliminary_slots(self, message: str) -> dict:
        """Skill: PreliminaryContext."""
        return await self.skills["preliminary_context"].extract(message, [])

    async def _save_to_buffer(self, conversation_id: str, message: str, role: str):
        """Delegate to MemoryService."""
        return await self.memory.save_to_buffer(conversation_id, message, role)

    async def _get_context(self, conversation_id: str, limit: int = 10):
        """Delegate to MemoryService."""
        return await self.memory.get_buffer(conversation_id, limit=limit)

    async def _generate_fallback(self, message: str) -> str:
        """Generate off-topic fallback response."""
        prompt = f"""
Bạn là một trợ lý tâm lý. Câu hỏi sau không thuộc phạm vi tâm lý:
"{message}"

Trả lời ngắn gọn, lịch sự, và hướng người dùng đến chủ đề sức khỏe tinh thần.
"""
        response = await self.llm.agenerate([prompt])
        return response.text.strip()
```

---

## 2. Message Passing Chi Tiết

### 2.1 Full Message Bus Implementation

```python
# ai/modules/communication/message_bus.py

class MessageBus:
    """
    Async in-memory pub/sub message bus.
    Thread-safe cho multi-agent communication.
    """

    def __init__(self, max_queue_size: int = 100):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._subscribers: Dict[str, Set[str]] = defaultdict(set)
        self._pending_results: Dict[str, List[AgentMessage]] = defaultdict(list)
        self._interrupt_flags: Dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()
        self._max_queue_size = max_queue_size
        self._message_history: List[AgentMessage] = []
        self._max_history = 1000

    # === Core Send/Receive ===

    async def send(self, message: AgentMessage) -> str:
        """Gửi message. Returns message_id."""
        async with self._lock:
            # Add to history
            self._message_history.append(message)
            if len(self._message_history) > self._max_history:
                self._message_history.pop(0)

            # Route message
            if message.priority == "critical" and message.message_type == "interrupt":
                await self._broadcast_interrupt(message)
            elif message.to_agent:
                await self._queue_message(message.to_agent, message)
            else:
                await self._broadcast_message(message)

            # Track for result waiting
            if message.task_id and message.message_type == "task":
                self._pending_results[message.task_id].append(message)

        return message.id

    async def receive(
        self, agent_id: str, timeout: float = 30
    ) -> Optional[AgentMessage]:
        """Agent nhận message từ queue riêng."""
        if agent_id not in self._queues:
            return None

        try:
            # Check for interrupt first
            if agent_id in self._interrupt_flags:
                intr_event = self._interrupt_flags[agent_id]
                if intr_event.is_set():
                    intr_event.clear()
                    return AgentMessage(
                        id=str(uuid.uuid4()),
                        from_agent="system",
                        to_agent=agent_id,
                        message_type="interrupt",
                        priority="critical",
                        content={"action": "abort"},
                        timestamp=datetime.utcnow(),
                    )

            return await asyncio.wait_for(
                self._queues[agent_id].get(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return None

    # === Subscription ===

    def subscribe(self, agent_id: str, event_types: List[str]):
        """Agent đăng ký nhận message theo event type (broadcast)."""
        for et in event_types:
            self._subscribers[et].add(agent_id)

    def unsubscribe(self, agent_id: str, event_types: List[str]):
        for et in event_types:
            self._subscribers[et].discard(agent_id)

    # === Result Waiting ===

    async def wait_for_result(
        self, task_id: str, timeout: float = 30
    ) -> Optional[AgentMessage]:
        """Chờ result message cho task_id cụ thể."""
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            async with self._lock:
                for msg in self._pending_results[task_id]:
                    if msg.message_type in ["result", "error"]:
                        self._pending_results[task_id].remove(msg)
                        return msg

                if task_id in self._queues:
                    try:
                        msg = self._queues[task_id].get_nowait()
                        if msg.message_type in ["result", "error"]:
                            return msg
                    except asyncio.QueueEmpty:
                        pass

            await asyncio.sleep(0.05)

        return None

    # === Internal Helpers ===

    async def _queue_message(self, agent_id: str, message: AgentMessage):
        if agent_id not in self._queues:
            self._queues[agent_id] = asyncio.Queue(maxsize=self._max_queue_size)
        try:
            self._queues[agent_id].put_nowait(message)
        except asyncio.QueueFull:
            logger.warning(f"Queue full for agent {agent_id}, dropping message")

    async def _broadcast_message(self, message: AgentMessage):
        for agent_id in self._subscribers.get(message.message_type, []):
            if agent_id != message.from_agent:
                await self._queue_message(agent_id, message)

    async def _broadcast_interrupt(self, message: AgentMessage):
        """
        Critical interrupt: CrisisAgent emit → MessageBus broadcast.
        1. Gửi interrupt message đến tất cả agents (trừ CrisisAgent)
        2. Set interrupt flag
        3. Agents nhận interrupt → hủy current task
        """
        for agent_id in self._queues:
            if agent_id != message.from_agent:
                if agent_id not in self._interrupt_flags:
                    self._interrupt_flags[agent_id] = asyncio.Event()
                self._interrupt_flags[agent_id].set()
                await self._queue_message(agent_id, message)

    # === Lifecycle ===

    def register_agent(self, agent_id: str):
        """Đăng ký queue mới cho agent."""
        if agent_id not in self._queues:
            self._queues[agent_id] = asyncio.Queue(maxsize=self._max_queue_size)
            self._interrupt_flags[agent_id] = asyncio.Event()

    def unregister_agent(self, agent_id: str):
        """Dọn queue của agent (khi conversation kết thúc)."""
        if agent_id in self._queues:
            del self._queues[agent_id]
        if agent_id in self._interrupt_flags:
            del self._interrupt_flags[agent_id]

    def get_message_history(
        self, conversation_id: Optional[str] = None, limit: int = 100
    ) -> List[AgentMessage]:
        """Debug: lấy message history."""
        history = self._message_history[-limit:]
        if conversation_id:
            history = [m for m in history if m.conversation_id == conversation_id]
        return history
```

### 2.2 Event System

```python
# ai/modules/communication/events.py

class EventType(str, Enum):
    # Lifecycle
    AGENT_REGISTERED = "agent_registered"
    AGENT_UNREGISTERED = "agent_unregistered"
    CONVERSATION_STARTED = "conversation_started"
    CONVERSATION_ENDED = "conversation_ended"

    # Tasks
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_TIMEOUT = "task_timeout"

    # Safety / Crisis
    CRISIS_DETECTED = "crisis_detected"
    CRISIS_ESCALATED = "crisis_escalated"
    CRISIS_RESOLVED = "crisis_resolved"

    # Interruption
    AGENT_INTERRUPTED = "agent_interrupted"
    AGENT_RESUMED = "agent_resumed"

    # Results
    RETRIEVAL_COMPLETED = "retrieval_completed"
    ANSWER_GENERATED = "answer_generated"


@dataclass
class AgentEvent:
    event_type: EventType
    source_agent: str
    target_agent: Optional[str]
    conversation_id: str
    payload: Any
    timestamp: datetime
    trace_id: Optional[str]


class EventEmitter:
    """
    Event emitter cho observability.
    Các component có thể subscribe để nhận events.
    """

    def __init__(self):
        self._handlers: Dict[EventType, List[Callable]] = defaultdict(list)

    def on(self, event_type: EventType, handler: Callable):
        self._handlers[event_type].append(handler)

    def off(self, event_type: EventType, handler: Callable):
        self._handlers[event_type].remove(handler)

    async def emit(self, event: AgentEvent):
        for handler in self._handlers.get(event.event_type, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")
```

---

## 3. Agent Communication Patterns

### 3.1 SupervisorAgent → Domain Agent (Router Pattern)

```
SupervisorAgent (Router)                Domain Agent (ReAct Loop)
       │                                        │
       │──── classify_intent() ─────────────────▶│
       │       (inside SupervisorAgent)         │
       │◀─── intent: "diagnostic" ──────────────│
       │                                        │
       │──── route_to_agent("diagnostic") ─────▶│
       │       (message_type=task, non-blocking) │
       │                                        │ [Domain Agent ReAct loop]
       │                                        │ [Domain Agent skills execute]
       │                                        │ [Domain Agent response sent to user]
       │                                        │
       │ DONE (no waiting)                       │
```

```python
# SupervisorAgent side (non-blocking routing)
async def run(self, user_message: str, conversation_id: str) -> dict:
    # IntentClassification skill (inside SupervisorAgent)
    intent = await self.skills["intent_classification"].classify(user_message, buffer)

    # Route non-blocking
    await self.bus.send(AgentMessage(
        from_agent="supervisor",
        to_agent=intent,
        message_type="task",
        priority="high",
        content={"message": user_message, "context": context},
        conversation_id=conversation_id,
        ...
    ))
    return {"status": "routed", "routed_to": intent}

# Domain Agent side (owns its own ReAct loop)
async def run(self, message: str, context: dict) -> dict:
    # Domain Agent receives task from SupervisorAgent
    # Runs its own ReAct loop with its own skills
    # Sends response directly back (via ChatService / websocket)
    result = await self._react_loop(user_message, context)
    await self.chat_service.send_response(conversation_id, result["answer"])
    return result
```

### 3.2 Parallel Routing (Crisis Preemption)

```
SupervisorAgent
    │
    ├──── classify_intent() ────▶ IntentClassification (skill)
    │◀─── intent = "crisis"
    │
    └──── bus.send(priority=CRITICAL) ──▶ CrisisAgent
                                              │
                                              └─▶ bus.emit(priority=critical, type=interrupt)
                                                       │
                               ┌───────────────────────┼───────────────────────┐
                               │                       │                       │
                               ▼                       ▼                       ▼
                          DiagnosticAgent      TheoryAgent           SupportAgent
                          (INTERRUPT abort)    (INTERRUPT abort)     (INTERRUPT abort)
                               │                       │                       │
                               └───────────────────────┴───────────────────────┘
                                              │
                                       CrisisAgent: handle_crisis()
                                              │
                                       Response sent directly to user
```

### 3.3 Domain Agent Internal Communication

```
Domain Agent (e.g., DiagnosticAgent)
    │
    ├─ SymptomExtraction skill (slot_filling equivalent)
    │     └─ extract_symptoms(message) → slots{}
    │
    ├─ DiagnosticRetrieval skill
    │     └─ search_diagnostic_kb() → chunks + graph_context
    │
    ├─ ClinicalReasoning skill
    │     └─ score_symptom_match() → generate_conclusion()
    │
    └─ ResponseDrafting skill (answer_generator equivalent)
          └─ format_diagnostic_answer() → final answer
```

Each Domain Agent owns its skills — no inter-agent calls needed.

### 3.4 Crisis Interrupt Pattern

```
CRISIS DETECTED by IntentClassification (inside SupervisorAgent)

SupervisorAgent (Router)
    │
    └─ bus.send(priority=CRITICAL) ──▶ CrisisAgent

CrisisAgent (REACT LOOP — owns crisis_detection skill)
    │
    ├─ match_crisis_keywords()
    ├─ select_crisis_template()
    ├─ provide_hotline()
    │
    └─ bus.emit(priority=CRITICAL, message_type=interrupt)
            │
            ├─▶ DiagnosticAgent: INTERRUPT (abort current task)
            ├─▶ TheoryAgent: INTERRUPT (abort)
            ├─▶ SupportAgent: INTERRUPT (abort)
            ├─▶ TreatmentAgent: INTERRUPT (abort)
            │
            └─ Response sent directly to user via ChatService
                    (safety plan, hotline, empathetic response)
```

### 3.5 MemoryService — NOT via Message Bus

```
MemoryService SỐNG trong services/, KHÔNG gọi qua Message Bus.
Được inject vào agents qua constructor.

Domain Agent                        MemoryService (injected)
     │                                       │
     ├─ save_to_buffer() ──────────────────▶│ L2: Redis → L3: PostgreSQL
     │                                       │
     ├─ get_buffer() ──────────────────────▶│
     │◀── conversation buffer ─────────────│
     │                                       │
     ├─ save_slots() ──────────────────────▶│
     │◀── confirmed ───────────────────────│
     │                                       │
     └─ get_summary() ──────────────────────▶│
         ◀── conversation summary ──────────│
```

```python
# MemoryService called via dependency injection, NOT message bus
class DiagnosticAgent(TaskAgent):
    def __init__(
        self,
        llm,
        memory_service: MemoryService,  # Injected, not via message bus
        message_bus: MessageBus,
        tools: {
            "graph_retrieval": GraphRetrieval(...),
            "milvus": MilvusClient(...),
            "reranker": CohereReranker(...),
        },  # rag/retrieval/ modules, injected into Domain Agents
        config: DiagnosticConfig,
    ):
        super().__init__(llm, name=self.AGENT_ID)
        self.memory = memory_service  # Direct call, not bus.send
        self.bus = message_bus
        self.tools = tools
        self._setup_skills()

    async def _react_loop(self, user_message: str, context: dict) -> dict:
        # Inside the agent: direct call to MemoryService
        buffer = await self.memory.get_buffer(context["conversation_id"])

        # Agent ReAct loop runs its skills...
        slots = await self.skills["symptom_extraction"].extract(user_message, buffer)

        # Save slots directly
        await self.memory.save_slots(context["conversation_id"], slots)

        # Retrieval via tools (not via message bus)
        chunks = await self.tools.hybrid_search(...)
        ...
```

---

## 4. Retrieval — Shared Skills, Not a Separate Agent

> **Nguyên tắc:** Retrieval KHÔNG phải agent riêng. Mỗi Domain Agent gọi retrieval tools qua Skill của mình.

### 4.1 Vị trí retrieval tools trong kiến trúc mới

```
ai/modules/shared/rag/retrieval/
├── graph_retrieval.py        # Graph retrieval logic (Neo4j 2-hop expansion)
├── hybrid_search.py          # Milvus + reranking logic
├── cohere_reranker.py        # Cohere reranking
└── encode_e5.py               # E5 embedding

ai/modules/[domain]/
├── [domain]_agent.py         # Agent sử dụng skills
└── skills/
    └── [domain]_retrieval.py  # Skill gọi rag/retrieval/ tools
```

### 4.2 Mỗi Domain Agent gọi retrieval như tool bên trong skill

```python
# ai/modules/diagnostic/skills/diagnostic_retrieval.py

class DiagnosticRetrievalSkill:
    """Skill — gọi retrieval tools từ rag/retrieval/"""

    def __init__(self, graph_retrieval, milvus_client, reranker):
        self.graph = graph_retrieval
        self.milvus = milvus_client
        self.reranker = reranker

    async def search_diagnostic_kb(
        self, query: str, slots: dict, top_k: int = 5
    ) -> dict:
        """Tool: search diagnostic knowledge base."""
        # 1. Hybrid search (vector + keyword)
        milvus_results = await self.milvus.search(
            collection="diagnostic",
            query=query,
            top_k=top_k * 2,  # get more for reranking
        )

        # 2. Expand via graph (2-hop from disorders found)
        disorder_ids = [r["id"] for r in milvus_results]
        graph_context = await self.graph.expand_subgraph(
            anchor_ids=disorder_ids,
            depth=2,
        )

        # 3. Rerank
        reranked = await self.reranker.rerank(
            query=query,
            documents=milvus_results + graph_context,
            top_k=top_k,
        )

        return {
            "chunks": reranked,
            "graph_context": graph_context,
            "confidence": reranked[0]["score"] if reranked else 0.0,
        }
```

### 4.3 Shared retrieval tools (dùng chung bởi mọi Domain Agent)

```python
# ai/modules/shared/rag/retrieval/graph_retrieval.py
# (Giữ nguyên logic hiện tại, KHÔNG bọc trong ToolAgent)

class GraphRetrieval:
    def __init__(self, neo4j_client: Neo4jClient):
        self.neo4j = neo4j_client

    async def expand_subgraph(
        self, anchor_ids: List[str], depth: int = 2
    ) -> List[dict]:
        """Expand disorder graph from anchor nodes (2-hop)."""
        ...

    async def get_related_disorders(self, disorder_id: str) -> List[str]:
        """Get comorbid disorders."""
        ...
```

### 4.4 Pattern cho mọi Domain Agent

| Agent | Retrieval Skill | Collection |
|-------|----------------|------------|
| DiagnosticAgent | `DiagnosticRetrievalSkill` | `diagnostic`, `dsm5` |
| TheoryAgent | `ConceptRetrievalSkill` | `theory`, `psychology` |
| TreatmentAgent | `TreatmentRetrievalSkill` | `treatment`, `therapy` |
| SupportAgent | `CopingRetrievalSkill` | `coping`, `self_help` |
| CrisisAgent | (không cần retrieval) | — |

---

## 5. Module Boundaries & Dependency Rules

### 5.1 Dependency Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                     frontend/ (React)                        │
└────────────────────────────┬─────────────────────────────────┘
                             │ HTTP/JWT
┌────────────────────────────┼─────────────────────────────────┐
│          ai/modules/     │                                  │
│  ┌─────────────────────────┼──────────────────────────────┐  │
│  │ api/v1/endpoints/       │ ← Chỉ gọi ChatService          │  │
│  └──────────┬──────────────┴───────────────────────────────┘  │
│             │                                                 │
│  ┌──────────▼──────────────┐                                  │
│  │ services/               │ ← Gọi SupervisorAgent            │
│  │ ChatService             │    + MemoryService                │
│  │ MemoryService           │    (Service, NOT Agent)           │
│  └──────────┬──────────────┘                                  │
│             │                                                 │
│  ┌──────────▼──────────────┐                                  │
│  │ agents/                  │ ← Đỉnh cao nhất của backend       │
│  │ SupervisorAgent (Router) │    KHÔNG gọi ChatService          │
│  │ CrisisAgent (interrupt) │    KHÔNG gọi MemoryService trực tiếp│
│  │ DiagnosticAgent          │    (inject MemoryService)         │
│  │ TheoryAgent              │                                  │
│  │ TreatmentAgent           │                                  │
│  │ SupportAgent             │                                  │
│  │ shared/                  │                                  │
│  │ communication/           │ ← MessageBus cho inter-agent     │
│  └──────────┬───────────────┘                                  │
│             │                                                  │
│  ┌──────────▼──────────────┐                                  │
│  │ rag/                    │ ← Infrastructure layer            │
│  │ retrieval/             │    Shared retrieval modules       │
│  │   graph_retrieval.py    │    (GraphRetrieval, HybridSearch) │
│  │   hybrid_search.py      │                                  │
│  │   cohere_reranker.py    │    Skills trong agents/ gọi     │
│  │ vectors/                │    rag/retrieval/                │
│  │ graph/                  │                                  │
│  └──────────┬──────────────┘                                  │
│             │                                                  │
│  ┌──────────▼──────────────┐                                  │
│  │ db/                    │ ← Data layer                       │
│  │ LangGraph checkpointer │    Được gọi bởi MemoryService      │
│  └─────────────────────────┘                                  │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 Import Rules (Modular Monolithic)

```python
# ✅ ĐƯỢC PHÉP
from ai.src.agents.shared.base_agent import BaseAgent
from ai.src.agents.shared.message import AgentMessage
from ai.src.agents.shared.state import GlobalState
from ai.src.communication.message_bus import MessageBus
from ai.src.services.memory_service import MemoryService  # Service, NOT Agent
from ai.src.rag.retrieval.graph_retrieval import GraphRetrieval
from ai.src.rag.vectors.milvus_client import MilvusClient
from ai.src.rag.llm.llm_gemini import GeminiLLM
from ai.src.db.session import get_session

# ❌ KHÔNG ĐƯỢC PHÉP
# Agents không được import services (ngược chiều)
# from ai.src.services.chat_service import ChatService  # SAI — circular

# Agent A không được import module mà import Agent B (agents độc lập)
# from ai.src.agents.diagnostic import DiagnosticAgent  # SAI

# KHÔNG được phép circular import giữa agents
```

### 5.3 Module Facade Pattern

```python
# ai/modules/supervisor/__init__.py

"""
Supervisor Module Facade.
Cung cấp unified interface cho SupervisorAgent.
"""

from .supervisor_agent import SupervisorAgent
from .skills.intent_classification import IntentClassification
from .skills.preliminary_context import PreliminaryContext

__all__ = [
    "SupervisorAgent",
    "IntentClassification",
    "PreliminaryContext",
]
```

---

## 6. Error Handling & Resilience

### 6.1 Per-Agent Error Handling

```python
# ai/modules/shared/base_agent.py

class BaseAgent(ABC):
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds

    async def run(self, input: Any, gs: GlobalState) -> Any:
        """Wrapper với retry + error handling."""
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                result = await self._run_impl(input, gs)
                return result

            except RetryableError as e:
                last_error = e
                logger.warning(
                    f"Agent {self.agent_id} retry {attempt+1}/{self.MAX_RETRIES}: {e}"
                )
                await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))

            except NonRetryableError as e:
                logger.error(f"Agent {self.agent_id} non-retryable error: {e}")
                return {"error": str(e), "retryable": False}

            except Exception as e:
                logger.error(f"Agent {self.agent_id} unexpected error: {e}")
                return {"error": str(e), "retryable": False}

        return {
            "error": str(last_error),
            "retryable": False,
            "attempts": self.MAX_RETRIES,
        }

    @abstractmethod
    async def _run_impl(self, input: Any, gs: GlobalState) -> Any:
        """Implement agent logic here."""
        pass
```

### 6.2 Error Propagation

```python
# Domain Agent handles its own errors — SupervisorAgent does NOT manage intermediate steps

async def _handle_agent_error(
    self, error: dict, gs: GlobalState
) -> str:
    """
    Domain Agent xử lý error nội bộ.
    SupervisorAgent không chờ kết quả nên không cần error propagation upstream.
    """
    if error.get("retryable") and error.get("attempts", 0) < 3:
        result = await self._run_impl(gs["original_input"], gs)
        if "error" not in result:
            return result

    return self._fallback_answer(gs)
```

### 6.3 Circuit Breaker

```python
# ai/modules/shared/circuit_breaker.py

class CircuitBreaker:
    """
    Circuit breaker cho external calls (API calls, DB queries).
    Prevent cascading failures.
    """

    def __init__(self, name: str, failure_threshold: int = 5, timeout: float = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed | open | half_open

    async def call(self, fn: Callable, *args, **kwargs):
        if self.state == "open":
            if time_since(self.last_failure_time) > self.timeout:
                self.state = "half_open"
            else:
                raise CircuitOpenError(f"Circuit {self.name} is open")

        try:
            result = await fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        self.failures = 0
        self.state = "closed"

    def _on_failure(self):
        self.failures += 1
        self.last_failure_time = datetime.utcnow()
        if self.failures >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit {self.name} opened after {self.failures} failures")
```

---

## 7. Cấu Trúc File Cuối Cùng (Domain-Centric)

```
ai/
├── agents/                                  # 5 Domain Agents + SupervisorAgent
│   ├── __init__.py
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── base_agent.py                   # Abstract base (ReAct loop template)
│   │   ├── state.py                       # GlobalState schema
│   │   ├── message.py                     # AgentMessage dataclass
│   │   ├── exceptions.py                   # Custom exceptions
│   │   ├── constants.py                   # Agent IDs, priorities
│   │   └── circuit_breaker.py             # Circuit breaker
│   │
│   ├── supervisor/                         # SupervisorAgent (ROUTER)
│   │   ├── __init__.py
│   │   ├── supervisor_agent.py            # CHỈ route, không ReAct loop
│   │   ├── prompts.py                     # SUPERVISOR_SYSTEM_PROMPT
│   │   ├── skills/
│   │   │   ├── __init__.py
│   │   │   ├── intent_classification.py   # Skill: classify_intent()
│   │   │   └── preliminary_context.py     # Skill: extract_preliminary_slots()
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── routing_tools.py          # Tool: route_to_agent()
│   │       └── shared_memory_tools.py    # Tool: save_to_buffer, get_context, merge_slots
│   │
│   ├── diagnostic/                        # DiagnosticAgent (1 Goal + N Skills)
│   │   ├── __init__.py
│   │   ├── diagnostic_agent.py            # GOAL: Chuẩn đoán rối loạn tâm thần
│   │   ├── skills/
│   │   │   ├── __init__.py
│   │   │   ├── symptom_extraction.py      # Skill: extract_* slots (8 tools)
│   │   │   │                                  (equivalent to old SlotFillingAgent)
│   │   │   ├── diagnostic_retrieval.py   # Skill: search_diagnostic_kb()
│   │   │   ├── clinical_reasoning.py     # Skill: score_symptom_match()
│   │   │   └── response_drafting.py      # Skill: format_diagnostic_answer()
│   │   │                                     (equivalent to old AnswerGeneratorAgent)
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── retrieval_tools.py        # milvus, neo4j, cohere
│   │       └── shared_memory_tools.py
│   │
│   ├── theory/                            # TheoryAgent (1 Goal + N Skills)
│   │   ├── __init__.py
│   │   ├── theory_agent.py               # GOAL: Giải thích kiến thức tâm lý
│   │   ├── skills/
│   │   │   ├── __init__.py
│   │   │   ├── concept_retrieval.py       # Skill: search_theory_kb()
│   │   │   ├── educational_explanation.py # Skill: generate_explanation()
│   │   │   └── answer_formatting.py       # Skill: format_theoretical_answer()
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── retrieval_tools.py
│   │       └── shared_memory_tools.py
│   │
│   ├── treatment/                        # TreatmentAgent (1 Goal + N Skills)
│   │   ├── __init__.py
│   │   ├── treatment_agent.py           # GOAL: Phác đồ điều trị
│   │   ├── skills/
│   │   │   ├── __init__.py
│   │   │   ├── treatment_retrieval.py    # Skill: search_treatment_kb()
│   │   │   ├── treatment_planning.py      # Skill: match_treatment()
│   │   │   ├── patient_guidance.py        # Skill: format_treatment_plan()
│   │   │   └── answer_formatting.py       # Skill: add_disclaimers()
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── retrieval_tools.py
│   │       └── shared_memory_tools.py
│   │
│   ├── support/                          # SupportAgent (1 Goal + N Skills)
│   │   ├── __init__.py
│   │   ├── support_agent.py              # GOAL: Hỗ trợ sức khỏe tinh thần (non-disorder)
│   │   ├── skills/
│   │   │   ├── __init__.py
│   │   │   ├── coping_retrieval.py        # Skill: search_coping_kb()
│   │   │   ├── emotional_support.py       # Skill: generate_empathetic()
│   │   │   ├── psycho_education.py        # Skill: explain_stress_response()
│   │   │   ├── skill_building.py          # Skill: recommend_mindfulness()
│   │   │   └── answer_formatting.py
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── retrieval_tools.py
│   │       └── shared_memory_tools.py
│   │
│   └── crisis/                            # CrisisAgent (1 Goal + N Skills, CRITICAL)
│       ├── __init__.py
│       ├── crisis_agent.py                # GOAL: Ứng phó khủng hoảng
│       │                                      Interrupt capability via MessageBus
│       ├── skills/
│       │   ├── __init__.py
│       │   ├── crisis_detection.py         # Skill: match_crisis_keywords()
│       │   ├── immediate_response.py      # Skill: select_crisis_template()
│       │   ├── professional_escalation.py  # Skill: provide_hotline()
│       │   ├── follow_up_support.py       # Skill: classify_user_response()
│       │   └── documentation.py           # Skill: log_crisis_event()
│       └── tools/
│           ├── __init__.py
│           └── shared_memory_tools.py
│
├── services/                              # Business logic layer
│   ├── __init__.py
│   ├── chat_service.py                  # Entry: gọi SupervisorAgent
│   ├── auth_service.py                  # Giữ nguyên
│   ├── conversation_service.py           # Giữ nguyên
│   └── memory_service.py                 # MemoryService (Service, NOT Agent)
│                                         # - buffer CRUD + summary CRUD + slots CRUD
│                                         # - L2: Redis cache + L3: PostgreSQL checkpoint
│                                         # - Injected vào agents, KHÔNG qua MessageBus
│
├── communication/                          # Inter-agent communication
│   ├── __init__.py
│   ├── message_bus.py                    # Pub/sub async message bus
│   ├── events.py                         # Event types + emitter (LangSmith)
│   └── subscriptions.py                  # Subscription manager
│
├── rag/                                    # RAG infrastructure (giữ nguyên)
│   ├── llm/
│   │   ├── llm_gemini.py                # Gemini API wrapper
│   │   └── prompts/                       # Prompt templates
│   ├── vectors/
│   │   ├── embeddings.py                # E5 encode functions
│   │   ├── milvus_client.py            # Milvus wrapper
│   │   └── dense_retriever.py          # Milvus collection operations
│   ├── graph/
│   │   ├── neo4j_client.py             # Neo4j driver
│   │   ├── graph_retriever.py           # build_context(), retrieve_subgraph()
│   │   └── graph_builder.py            # Data ingestion
│   ├── reranker/
│   │   └── cohere_reranker.py          # Cohere rerank API
│   └── ingestion/                         # Data pipeline
│
├── db/                                     # Data layer (giữ nguyên)
│   ├── repositories/
│   ├── models/
│   └── session.py
│
├── api/v1/endpoints/                    # API layer (giữ nguyên)
│   ├── chat.py                           # POST /api/v1/chat
│   ├── auth.py
│   ├── conversations.py
│   └── health.py
│
├── engine.py                              # Legacy wrapper
│                                          # run_rag_workflow() -> SupervisorAgent
│
└── main.py                                # App entry: init agents, services
```

### 7.1 Old Agents → New Architecture Mapping

| Old Agent (ĐÃ XÓA) | New Location | Notes |
|---|---|---|
| OrchestratorAgent | **SupervisorAgent** | Nhưng chỉ là Router, không ReAct loop |
| TranslatorAgent | IntentClassification skill | Inside SupervisorAgent |
| SlotFillingAgent | SymptomExtraction skill | Inside DiagnosticAgent |
| AnswerGeneratorAgent | ResponseDrafting skill | Inside each Domain Agent |
| SafetyAgent | CrisisAgent | Crisis detection skill + interrupt |
| MemoryAgent | **MemoryService** | Trong services/, injected, NOT via bus |
| RetrievalOrchestrator | **SupervisorAgent route_to_agent** | Routing only |

### 7.2 Shared Tools vs Agent-Specific Skills

```
SHARED TOOLS (reuse bởi nhiều agents):
  retrieval_tools.py       — MỌI agent dùng: encode_e5, milvus_search, expand_subgraph, cohere_rerank
  shared_memory_tools.py   — MỌI agent dùng: save_to_buffer, get_context, merge_slots
                              (delegates to injected MemoryService)

AGENT-SPECIFIC SKILLS (chỉ agent đó sở hữu):
  symptom_extraction         — CHỈ DiagnosticAgent
  clinical_reasoning         — CHỈ DiagnosticAgent
  crisis_detection           — CHỈ CrisisAgent
  intent_classification      — CHỈ SupervisorAgent (ROUTER SKILL)
  preliminary_context        — CHỈ SupervisorAgent (ROUTER SKILL)
  coping_retrieval           — CHỈ SupportAgent
  concept_retrieval           — CHỈ TheoryAgent
  treatment_planning         — CHỈ TreatmentAgent
  educational_explanation     — CHỈ TheoryAgent
  emotional_support          — CHỈ SupportAgent
```

### 7.3 Module Dependency Rules

```
Dependency Flow:
api/endpoints -> services -> SupervisorAgent -> Domain Agents
                     |                  |
                     |           MessageBus (inter-agent)
                     |                  |
               MemoryService      Retrieval Skills
               (injected)          (in agents/[domain]/skills/)
                                  rag/retrieval/ modules
                                   Milvus + Neo4j + Cohere

DA ĐƯỢC PHÉP:
  from ai.src.agents.shared.base_agent import BaseAgent
  from ai.src.services.memory_service import MemoryService  # Inject vào agents
  from ai.src.communication.message_bus import MessageBus
  from ai.src.rag.vectors.milvus_client import MilvusClient

KHÔNG ĐƯỢC PHÉP:
  Agent A import Agent B  (agents độc lập, giao tiếp qua MessageBus)
  Agents import services.chat_service (circular)
  MemoryService gọi qua MessageBus (nó là Service, không phải Agent)
```

### 7.4 MemoryService Location & Access Pattern

```
MemoryService SỐNG trong services/, KHÔNG trong agents/
  services/memory_service.py

Truy cập: Dependency Injection (constructor)
  class DiagnosticAgent:
      def __init__(self, ..., memory_service: MemoryService, ...):
          self.memory = memory_service  # Direct call, no bus

  class SupportAgent:
      def __init__(self, ..., memory_service: MemoryService, ...):
          self.memory = memory_service  # Direct call, no bus

Shared Memory Tools (tools/shared_memory_tools.py) = wrapper:
  def create_shared_memory_tools(memory_service: MemoryService):
      return {
          "save_to_buffer": memory_service.save_to_buffer,
          "get_context": memory_service.get_buffer,
          "merge_slots": memory_service.merge_slots,
          "save_slots": memory_service.save_slots,
      }
```

---

*Lưu ý: File này là Part 3 — Communication Layer. Tiếp theo: Part 4 — Performance Optimization (Caching + Parallel Processing).*
