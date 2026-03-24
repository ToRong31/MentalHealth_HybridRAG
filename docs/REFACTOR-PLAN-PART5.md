# Mental Health Hybrid RAG — Refactor Plan
## Phần 5: Testing & Deployment — LangSmith, Docker, CI/CD, Integration Tests

> **Testing strategy + LangSmith integration + Docker deployment + CI/CD pipeline**
> Đọc sau: REFACTOR-PLAN-PART1-4.md

---

## 1. Testing Strategy Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TESTING PYRAMID                                   │
│                                                                      │
│                           ▲                                          │
│                          /█\                                          │
│                         / █ \         E2E Tests (Playwright)         │
│                        /  █  \        ~15 tests (critical flows)    │
│                       /   █   \                                      │
│                      /────█────\                                     │
│                     /     █     \     Integration Tests              │
│                    /      █      \    ~50 tests (agent interactions) │
│                   /───────█───────\                                   │
│                  /        █        \  Unit Tests                      │
│                 /─────────█─────────\ ~200 tests (per agent/tools)   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.1 Test Categories

| Level | Scope | Count | Run time | CI/CD |
|-------|-------|-------|---------|-------|
| Unit | Per agent, per tool, per function | ~200 | < 30s | Every PR |
| Integration | Agent ↔ MessageBus, Agent ↔ Agent | ~50 | < 60s | Every PR |
| E2E | Full conversation flows via API | ~15 | < 5min | Nightly |
| Performance | Latency, throughput, cache hit | ~10 | < 2min | Nightly |
| Load | Concurrent users, stress test | ~5 | < 10min | Weekly |

---

## 2. Unit Tests

### 2.1 Test Structure

```
backend/tests/
├── unit/
│   ├── agents/
│   │   ├── supervisor/
│   │   │   ├── test_intent_classification.py
│   │   │   ├── test_routing_rules.py
│   │   │   └── test_agent_manager.py
│   │   ├── crisis/
│   │   │   ├── test_crisis_detection.py
│   │   │   ├── test_crisis_keywords.py
│   │   │   └── test_crisis_interrupt.py
│   │   ├── diagnostic/
│   │   │   ├── test_symptom_extraction.py
│   │   │   ├── test_clinical_reasoning.py
│   │   │   └── test_diagnostic_agent.py
│   │   ├── theory/
│   │   ├── treatment/
│   │   ├── support/
│   │   └── memory/
│   │       ├── test_memory_service.py
│   │       └── test_slot_merge.py
│   │
│   ├── communication/
│   │   ├── test_message_bus.py
│   │   ├── test_event_emitter.py
│   │   └── test_subscriptions.py
│   │
│   ├── cache/
│   │   ├── test_lru_cache.py
│   │   └── test_redis_cache.py
│   │
│   └── services/
│       └── test_chat_service.py
│
├── conftest.py                    # Shared fixtures
├── pytest.ini
└── .coveragerc
```

### 2.2 Unit Test Examples

```python
# backend/tests/unit/agents/crisis/test_crisis_detection.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from ai.src.agents.crisis.crisis_agent import CrisisAgent
from ai.src.agents.shared.state import GlobalState


@pytest.fixture
def crisis_agent():
    llm = AsyncMock()
    bus = MagicMock()
    return CrisisAgent(llm=llm, message_bus=bus)


@pytest.mark.asyncio
class TestCrisisDetection:

    async def test_detect_crisis_high_risk_keywords(self, crisis_agent):
        """Test: crisis keywords → CrisisAgent (CRITICAL priority)."""
        ...

    async def test_detect_crisis_moderate_concern(self, crisis_agent):
        """Test: borderline language → moderate crisis level."""
        ...

    async def test_detect_crisis_safe_message(self, crisis_agent):
        """Test: normal message → no crisis."""
        ...

    async def test_recent_crisis_increased_sensitivity(self, crisis_agent):
        """Test: recent crisis in buffer → flag all messages."""
        ...

    @pytest.mark.parametrize("keyword,expected_level", [
        ("tự tử", "critical"),
        ("suicide", "critical"),
        ("muốn chết", "high"),
        ("tự gây thương tích", "high"),
        ("không sống nổi", "high"),
        ("mệt mỏi", "none"),
    ])
    async def test_keyword_variations(self, crisis_agent, keyword, expected_level):
        """Test: keyword variations → correct crisis level."""
        ...


# backend/tests/unit/agents/diagnostic/skills/test_diagnostic_retrieval_skill.py

@pytest.mark.asyncio
class TestDiagnosticRetrievalSkill:

    @pytest.fixture
    def mock_milvus(self):
        milvus = AsyncMock()
        milvus.search = AsyncMock(return_value=[
            {"id": "node_1", "text": "Anxiety disorder content", "score": 0.95},
            {"id": "node_2", "text": "Generalized anxiety", "score": 0.90},
        ])
        return milvus

    @pytest.fixture
    def mock_neo4j(self):
        neo4j = AsyncMock()
        neo4j.retrieve_subgraph = AsyncMock(return_value={
            "nodes": [...],
            "rels": [...],
            "context": "Graph context string",
        })
        return neo4j

    @pytest.fixture
    def mock_reranker(self):
        reranker = AsyncMock()
        reranker.rerank_anchors = AsyncMock(return_value=[
            {"id": "node_1", "text": "Anxiety disorder content", "score": 0.98},
            {"id": "node_2", "text": "Generalized anxiety", "score": 0.93},
        ])
        return reranker

    @pytest.fixture
    def skill(self, mock_milvus, mock_neo4j, mock_reranker):
        """DiagnosticRetrievalSkill — retrieval tool cho DiagnosticAgent."""
        from ai.src.rag.retrieval.graph_retrieval import GraphRetrieval
        from ai.src.agents.diagnostic.skills.diagnostic_retrieval import DiagnosticRetrievalSkill

        graph = GraphRetrieval(neo4j_client=mock_neo4j)
        return DiagnosticRetrievalSkill(
            graph_retrieval=graph,
            milvus_client=mock_milvus,
            reranker=mock_reranker,
        )

    async def test_hybrid_search_pipeline(self, tool, mock_milvus, mock_neo4j, mock_reranker):
        """Test: Full hybrid search → Milvus → Rerank → Neo4j."""
        gs = GlobalState(conversation_id="test_conv")

        result = await tool.run({
            "tool": "hybrid_search",
            "args": {
                "query": "anxiety symptoms",
                "collection": "mental_health_diagnostic_support",
                "top_k": 3,
            }
        }, gs)

        # Verify Milvus called
        mock_milvus.search.assert_called_once()

        # Verify Rerank called
        mock_reranker.rerank_anchors.assert_called_once()

        # Verify Neo4j called with reranked anchor IDs
        mock_neo4j.retrieve_subgraph.assert_called_once()

        # Verify result structure
        assert "chunks" in result
        assert "graph_context" in result
        assert len(result["chunks"]) <= 3

    async def test_slot_bonus_applied(self, tool):
        """Test: Slots matching anchor → 5% score bonus."""
        gs = GlobalState(conversation_id="test_conv")
        gs["slots"] = {"emotion": "lo âu", "trigger": "công việc"}

        # Setup mock để return anchors với keywords
        tool.milvus.search = AsyncMock(return_value=[
            {"id": "node_1", "text": "Anxiety at work", "score": 0.80},
            {"id": "node_2", "text": "Depression", "score": 0.90},
        ])

        result = await tool.run({
            "tool": "hybrid_search",
            "args": {
                "query": "emotional distress",
                "collection": "normal_responses",
                "top_k": 2,
                "slots": gs["slots"],
            }
        }, gs)

        # node_1 (anxiety at work) should get bonus due to "lo âu" + "công việc"
        # → score should be higher than node_2 despite lower original
        chunks = result["chunks"]
        anxiety_node = next((c for c in chunks if "Anxiety" in c["text"]), None)
        if anxiety_node:
            assert anxiety_node["score"] > 0.80  # Should have bonus
```

### 2.3 Message Bus Tests

```python
# backend/tests/unit/communication/test_message_bus.py

import pytest
import asyncio
from ai.src.communication.message_bus import MessageBus, AgentMessage
from ai.src.communication.events import EventType


@pytest.mark.asyncio
class TestMessageBus:

    async def test_send_and_receive_direct(self):
        """Test: Direct message → correct agent queue."""
        bus = MessageBus()
        bus.register_agent("agent_a")
        bus.register_agent("agent_b")

        msg = AgentMessage(
            id="msg_1",
            from_agent="agent_a",
            to_agent="agent_b",
            message_type="task",
            priority="normal",
            content={"task": "do_something"},
            conversation_id="conv_1",
            timestamp=datetime.utcnow(),
        )

        await bus.send(msg)
        received = await bus.receive("agent_b", timeout=1)

        assert received is not None
        assert received.id == "msg_1"
        assert received.to_agent == "agent_b"
        assert received.content["task"] == "do_something"

    async def test_broadcast_subscription(self):
        """Test: Broadcast → all subscribers receive."""
        bus = MessageBus()
        bus.register_agent("publisher")
        bus.register_agent("subscriber_a")
        bus.register_agent("subscriber_b")
        bus.register_agent("non_subscriber")

        bus.subscribe("subscriber_a", ["event"])
        bus.subscribe("subscriber_b", ["event"])

        msg = AgentMessage(
            id="msg_2",
            from_agent="publisher",
            to_agent=None,
            message_type="event",
            priority="normal",
            content={"event": "something_happened"},
            conversation_id="conv_1",
            timestamp=datetime.utcnow(),
        )

        await bus.send(msg)

        received_a = await bus.receive("subscriber_a", timeout=1)
        received_b = await bus.receive("subscriber_b", timeout=1)
        received_non = await bus.receive("non_subscriber", timeout=0.5)

        assert received_a is not None
        assert received_b is not None
        assert received_non is None  # Not subscribed

    async def test_wait_for_result(self):
        """Test: wait_for_result → returns result for task_id."""
        bus = MessageBus()
        bus.register_agent("supervisor")
        bus.register_agent("diagnostic_agent")

        task_msg = AgentMessage(
            id="task_1",
            from_agent="supervisor",
            to_agent="diagnostic_agent",
            message_type="task",
            priority="normal",
            content={"task": "work"},
            task_id="task_abc",
            conversation_id="conv_1",
            timestamp=datetime.utcnow(),
        )

        result_msg = AgentMessage(
            id="result_1",
            from_agent="diagnostic_agent",
            to_agent="supervisor",
            message_type="result",
            priority="normal",
            content={"output": "done"},
            task_id="task_abc",
            conversation_id="conv_1",
            timestamp=datetime.utcnow(),
        )

        # Diagnostic agent receives task
        await bus.send(task_msg)
        worker_msg = await bus.receive("diagnostic_agent", timeout=1)

        # Diagnostic agent sends result
        await bus.send(result_msg)

        # Supervisor waits for result from Domain Agent
        result = await bus.wait_for_result("task_abc", timeout=2)
        assert result is not None
        assert result.content["output"] == "done"

    async def test_critical_interrupt(self):
        """Test: Critical message → all agents interrupted."""
        bus = MessageBus()
        bus.register_agent("safety")
        bus.register_agent("worker_a")
        bus.register_agent("worker_b")

        interrupt_msg = AgentMessage(
            id="intr_1",
            from_agent="safety",
            to_agent=None,
            message_type="interrupt",
            priority="critical",
            content={"action": "abort", "reason": "crisis_detected"},
            conversation_id="conv_1",
            timestamp=datetime.utcnow(),
        )

        # Set a fake running task in worker
        await bus.send(AgentMessage(
            id="fake_task",
            from_agent="supervisor",
            to_agent="worker_a",
            message_type="task",
            priority="normal",
            content={"task": "long_running"},
            conversation_id="conv_1",
            timestamp=datetime.utcnow(),
        ))

        # Send interrupt
        await bus.send(interrupt_msg)

        # Workers should receive interrupt
        worker_a_intr = await bus.receive("worker_a", timeout=1)
        worker_b_intr = await bus.receive("worker_b", timeout=1)

        assert worker_a_intr is not None
        assert worker_a_intr.message_type == "interrupt"
        assert worker_b_intr is not None
```

---

## 3. Integration Tests

### 3.1 Agent Integration Tests

```python
# backend/tests/integration/agents/test_retrieval_team_integration.py

@pytest.mark.asyncio
class TestRetrievalTeamIntegration:

    @pytest.fixture
    def real_agents(self):
        """Fixtures: tạo real agents với mock external services."""
        llm = MockLLM()
        milvus = MockMilvusClient()
        neo4j = MockNeo4jClient()
        cohere = MockCohereReranker()
        embed_fn = lambda x: [0.1] * 1024
        bus = MessageBus()
        bus.register_agent("supervisor")
        bus.register_agent("coping_agent")
        bus.register_agent("diagnostic_agent")

        return {
            "supervisor": SupervisorAgent(llm, bus, tools),
            "coping": CopingAgent(llm, tools),
            "diagnostic": DiagnosticAgent(llm, tools),
        }

    async def test_diagnostic_path_full_flow(self, real_agents):
        """
        Test: diagnostic retrieval → DiagnosticAgent skill → aggregated results.
        """
        gs = GlobalState(
            conversation_id="test_conv",
            current_question="I feel anxious all the time and can't sleep",
            slots={
                "emotion": "lo âu",
                "duration": "2 tuần",
                "intensity": "cao",
            },
            has_sufficient_slots=True,
            assessment_category="possible_disorder",
        )

        result = await real_agents["supervisor"].route({
            "task": "retrieve",
            "path": "diagnostic",
            "query": "anxiety symptoms sleep disruption",
        }, gs)

        assert result["status"] == "completed"
        assert "results" in result
        assert "diagnostic" in result["results"]
        assert len(result["results"]["diagnostic"]) > 0

    async def test_normal_path_full_flow(self, real_agents):
        """
        Test: normal coping path → single agent → result.
        """
        gs = GlobalState(
            conversation_id="test_conv",
            current_question="Tôi cảm thấy hơi stress",
            assessment_category="normal_response",
        )

        result = await real_agents["supervisor"].route({
            "task": "retrieve",
            "path": "normal",
            "query": "stress coping",
        }, gs)

        assert result["status"] == "completed"
        assert "coping" in result["results"]


# backend/tests/integration/agents/test_supervisor_integration.py

@pytest.mark.asyncio
class TestSupervisorIntegration:

    @pytest.fixture
    def supervisor(self):
        """Full supervisor với real components (test mode)."""
        llm = MockLLM()
        bus = MessageBus()
        agent_manager = AgentManager(llm, bus)
        checkpointer = MockCheckpointer()
        config = SupervisorConfig()
        return SupervisorAgent(llm, bus, agent_manager, checkpointer, config)

    async def test_safe_personal_query_flow(self, supervisor):
        """
        Test: Safe personal query → intent routing → Domain Agent.
        Full supervisor flow (mocked Domain Agents).
        """
        # Setup mock agents
        supervisor.agent_manager.get_singleton_agent = MagicMock(
            return_value=MockAgent(return_value={"detected_language": "vi", "translated": "..."})
        )

        result = await supervisor.route(
            user_message="Tôi cảm thấy lo âu gần đây",
            conversation_id="test_conv",
        )

        # Should complete without crisis
        assert "answer" in result
        assert result.get("is_high_risk") is False

    async def test_crisis_flow_override(self, supervisor):
        """
        Test: Crisis detected → crisis flow overrides normal flow.
        """
        # Mock CrisisAgent to return crisis
        crisis_agent = MockAgent(return_value={
            "is_crisis": True,
            "level": "high",
            "indicators": ["intent"],
        })
        supervisor.agent_manager.get_singleton_agent = MagicMock(
            side_effect=lambda aid: crisis_agent if aid == "crisis" else MockAgent()
        )

        result = await supervisor.route(
            user_message="Tôi không muốn sống nữa",
            conversation_id="test_conv",
        )

        # Crisis flow should be triggered
        assert result.get("is_high_risk") is True
        assert result.get("crisis_level") == "high"
```

### 3.2 E2E Tests (Playwright)

```python
# backend/tests/e2e/test_chat_flow.py

from playwright.async_api import async_playwright, expect

@pytest.mark.asyncio
class TestChatE2E:

    @pytest.fixture
    async def browser(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            yield browser
            await browser.close()

    @pytest.fixture
    async def page(self, browser):
        page = await browser.new_page()
        await page.goto("http://localhost:3000/login")
        # Login
        await page.fill('[data-testid="email"]', "test@example.com")
        await page.fill('[data-testid="password"]', "testpass123")
        await page.click('[data-testid="login-btn"]')
        await page.wait_for_url("**/home")
        yield page

    async def test_safe_conversation_flow(self, page):
        """Test: Safe conversation → answer → memory saved."""
        await page.goto("http://localhost:3000/home")

        # Send message
        await page.fill('[data-testid="chat-input"]', "Tôi cảm thấy stress với công việc")
        await page.click('[data-testid="send-btn"]')

        # Wait for response
        await page.wait_for_selector('[data-testid="assistant-message"]', timeout=10000)
        response = await page.text_content('[data-testid="assistant-message"]')

        assert len(response) > 10
        assert "stress" in response.lower() or "căng thẳng" in response.lower()

        # Check no crisis indicator
        crisis_banner = await page.query_selector('[data-testid="crisis-banner"]')
        assert crisis_banner is None

    async def test_crisis_detection_e2e(self, page):
        """Test: Crisis keywords → immediate crisis response."""
        await page.goto("http://localhost:3000/home")

        # Send crisis message
        await page.fill('[data-testid="chat-input"]', "Tôi muốn tự tử")
        await page.click('[data-testid="send-btn"]')

        # Crisis banner should appear immediately
        await page.wait_for_selector('[data-testid="crisis-banner"]', timeout=5000)
        banner = await page.text_content('[data-testid="crisis-banner"]')

        assert any(keyword in banner for keyword in ["hỗ trợ", "khủng hoảng", "quan trọng", "emergency"])

        # Hotline should be visible
        hotline = await page.text_content('[data-testid="crisis-hotline"]')
        assert "1800" in hotline or "113" in hotline

    async def test_multi_turn_memory(self, page):
        """Test: Multi-turn conversation → memory persists."""
        await page.goto("http://localhost:3000/home")

        # Turn 1
        await page.fill('[data-testid="chat-input"]', "Tôi bị lo âu về công việc")
        await page.click('[data-testid="send-btn"]')
        await page.wait_for_selector('[data-testid="assistant-message"]', timeout=10000)

        # Turn 2 (follow-up)
        await page.fill('[data-testid="chat-input"]', "Điều đó kéo dài 2 tuần rồi")
        await page.click('[data-testid="send-btn"]')
        await page.wait_for_selector('[data-testid="assistant-message"]', timeout=10000)

        # Response should reference previous context
        response = await page.text_content('[data-testid="assistant-message"]')
        # (May or may not reference previous depending on slot filling progress)
        assert len(response) > 10
```

---

## 4. LangSmith Integration

### 4.1 LangSmith Setup

```bash
# Install
pip install langsmith

# Environment
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=your_api_key
export LANGCHAIN_PROJECT=mhrag-agents  # or per-environment
```

### 4.2 LangSmith Client Setup

```python
# ai/modules/shared/langsmith_tracer.py

from langsmith.run_trees import traceable
from langsmith.run_handlers import LangChainHandler
from langchain_core.tracers.langchain import LangChainTracer
from contextvars import ContextVar
import uuid

# Per-conversation trace ID
_current_trace_id: ContextVar[str] = ContextVar("trace_id", default="")

class LangSmithTracer:
    """
    LangSmith tracer cho multi-agent system.
    - Traces each agent run as a top-level span
    - Traces each tool call as a child span
    - Correlates all spans via conversation trace_id
    """

    def __init__(self, project_name: str = "mhrag-agents"):
        self.project_name = project_name
        self._handlers: List[LangChainTracer] = []

    def setup(self):
        """Initialize LangSmith handlers."""
        handler = LangChainTracer(
            project_name=self.project_name,
            tags=["production", "multi-agent"],
        )
        self._handlers.append(handler)
        return handler

    def get_trace_id(self) -> str:
        return _current_trace_id.get()

    def start_trace(self, conversation_id: str) -> str:
        """Start new trace for conversation."""
        trace_id = f"conv_{conversation_id}_{uuid.uuid4().hex[:8]}"
        _current_trace_id.set(trace_id)
        return trace_id

    def end_trace(self):
        _current_trace_id.set("")

    @property
    def current_trace_id(self) -> str:
        return _current_trace_id.get()
```

### 4.3 Instrument Agents with LangSmith

```python
# ai/modules/shared/base_agent.py

from ai.src.agents.shared.langsmith_tracer import LangSmithTracer

class BaseAgent(ABC):
    def __init__(self, llm, name: str):
        self.agent_id = name
        self.llm = llm
        self.tracer = LangSmithTracer()

    async def run(self, input: Any, gs: GlobalState) -> Any:
        """Wrapper với LangSmith tracing."""
        trace_id = self.tracer.current_trace_id
        tags = [
            f"agent:{self.agent_id}",
            f"conv:{gs.get('conversation_id', 'unknown')}",
            f"language:{gs.get('user_language', 'unknown')}",
        ]

        if gs.get("is_high_risk"):
            tags.append("crisis:true")

        # Create LangSmith run
        with tracer.start_span(
            name=f"agent:{self.agent_id}",
            tags=tags,
            metadata={
                "input_preview": str(input)[:500],
                "conversation_id": gs.get("conversation_id"),
                "crisis_level": gs.get("crisis_level"),
            },
        ) as span:
            try:
                result = await self._run_impl(input, gs)

                span.add_event(
                    "result",
                    {
                        "status": "success",
                        "output_preview": str(result)[:500],
                    }
                )
                return result

            except Exception as e:
                span.add_event(
                    "error",
                    {"error": str(e), "type": type(e).__name__}
                )
                raise

    async def _call_llm(self, prompt: str, **kwargs) -> str:
        """LLM call với tracing."""
        with tracer.start_span(
            name=f"llm:{self.agent_id}",
            tags=[f"agent:{self.agent_id}"],
            metadata={"model": kwargs.get("model", "gemini-2.0-flash")},
        ) as span:
            result = await self.llm.agenerate([prompt], **kwargs)
            span.add_event(
                "tokens",
                {
                    "output_tokens": len(str(result)),
                    "model": kwargs.get("model"),
                }
            )
            return result


# ai/modules/diagnostic/skills/diagnostic_retrieval.py

class DiagnosticRetrievalSkill:
    """Skill — retrieval cho DiagnosticAgent, gọi rag/retrieval/ tools."""

    def __init__(self, graph_retrieval, milvus_client, reranker):
        self.graph = graph_retrieval
        self.milvus = milvus_client
        self.reranker = reranker

    async def search_diagnostic_kb(
        self, query: str, slots: dict, top_k: int = 5
    ) -> dict:
        """Tool: search diagnostic KB + graph expansion + rerank."""
        with tracer.start_span("tool:diagnostic_retrieval", tags=["skill", "domain:diagnostic"]):
            # Milvus
            milvus_results = await self.milvus.search(
                collection="diagnostic",
                query=query,
                top_k=top_k * 2,
            )

            # Graph expand
            disorder_ids = [r["id"] for r in milvus_results if "disorder" in r.get("type", "")]
            graph_context = await self.graph.expand_subgraph(
                anchor_ids=disorder_ids,
                depth=2,
            )

            # Rerank
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

### 4.4 LangSmith Dashboard Queries

```python
# backend/tests/integration/test_langsmith_queries.py

import pytest
from langsmith import Client

class TestLangSmithDashboard:
    """
    Verify LangSmith traces đúng cách.
    """

    @pytest.fixture
    def ls_client(self):
        return Client()

    def test_trace_per_conversation(self, ls_client):
        """Verify: mỗi conversation có 1 trace root."""
        project_name = "mhrag-agents"

        runs = ls_client.list_runs(
            project_name=project_name,
            filter='and(eq(tags, "supervisor"))',
            limit=10,
        )

        for run in runs:
            assert run.trace_id is not None
            # All child spans should share same trace_id
            child_spans = ls_client.list_runs(
                trace_id=run.trace_id,
                limit=100,
            )
            trace_ids = {s.trace_id for s in child_spans}
            assert len(trace_ids) == 1  # All same trace_id

    def test_critical_crisis_traced(self, ls_client):
        """Verify: crisis conversations được tag đúng."""
        runs = ls_client.list_runs(
            project_name=project_name,
            filter='and(eq(tags, "crisis:true"))',
            limit=10,
        )

        for run in runs:
            assert any("crisis" in str(r.tags) for r in [run])
            # Should have CrisisAgent trace
            children = ls_client.list_runs(trace_id=run.trace_id)
            agent_names = {s.name for s in children}
            assert any("crisis" in name for name in agent_names)

    def test_tool_call_traces(self, ls_client):
        """Verify: mỗi tool call có span."""
        runs = ls_client.list_runs(
            project_name=project_name,
            filter='eq(name, "agent:supervisor")',
            limit=5,
        )

        for run in runs:
            children = ls_client.list_runs(trace_id=run.trace_id)
            tool_spans = [s for s in children if "tool:" in s.name]
            assert len(tool_spans) > 0  # At least hybrid_search tool called
```

---

## 5. Docker Deployment

### 5.1 Dockerfile (Backend Multi-Stage)

```dockerfile
# backend/Dockerfile

# === Stage 1: Builder ===
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# === Stage 2: Production ===
FROM python:3.11-slim AS production

WORKDIR /app

# Security: non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Install runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy app code
COPY --chown=appuser:appgroup backend/src ./src

# Install app deps (exclude dev)
RUN pip install --no-cache-dir --user \
    fastapi uvicorn[standard] \
    langgraph langchain-google-genai \
    pymilvus neo4j asyncpg \
    redis \
    python-jose passlib \
    pydantic pydantic-settings \
    python-multipart \
    langsmith

# Set PATH
ENV PATH=/home/appuser/.local/bin:$PATH
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 5.2 Docker Compose (Production)

```yaml
# docker-compose.yml

version: "3.9"

services:

  # === Backend ===
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: mhrag-backend
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/mhrag
      - REDIS_URL=redis://redis:6379/0
      - MILVUS_URI=http://milvus:19530
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - COHERE_API_KEY=${COHERE_API_KEY}
      - LANGCHAIN_TRACING_V2=${LANGCHAIN_TRACING_V2}
      - LANGCHAIN_API_KEY=${LANGCHAIN_API_KEY}
      - LANGCHAIN_PROJECT=${LANGCHAIN_PROJECT:-mhrag-production}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 4G
        reservations:
          cpus: "1"
          memory: 2G
    restart: unless-stopped

  # === Frontend ===
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: mhrag-frontend
    environment:
      - VITE_API_URL=http://backend:8000/api/v1
    depends_on:
      - backend
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  # === PostgreSQL ===
  postgres:
    image: postgres:16-alpine
    container_name: mhrag-postgres
    environment:
      - POSTGRES_DB=mhrag
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # === Redis ===
  redis:
    image: redis:7-alpine
    container_name: mhrag-redis
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # === Milvus (Standalone) ===
  milvus:
    image: milvusdb/milvus:v2.3.3
    container_name: mhrag-milvus
    environment:
      - ETCD_ENDPOINTS=milvus-etcd:2379
      - MINIO_ADDRESS=milvus-minio:9000
    depends_on:
      - milvus-etcd
      - milvus-minio
    volumes:
      - milvus_data:/var/lib/milvus
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9091/healthz"]
      interval: 30s
      timeout: 10s
      retries: 5
    restart: unless-stopped

  milvus-etcd:
    image: quay.io/coreos/etcd:v3.5.5
    container_name: mhrag-milvus-etcd
    environment:
      - ETCD_AUTO_COMPACTION_MODE=revision
      - ETCD_AUTO_COMPACTION_RETENTION=1000
      - ETCD_QUOTA_BACKEND_BYTES=4294967296
    volumes:
      - milvus_etcd:/etcd
    command: etcd -auto-compaction-retention=1000

  milvus-minio:
    image: minio/minio:RELEASE.2023-03-20T20-16-18Z
    container_name: mhrag-milvus-minio
    environment:
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
    volumes:
      - milvus_minio:/minio_data
    command: minio server /minio_data

  # === Neo4j ===
  neo4j:
    image: neo4j:5.14-community
    container_name: mhrag-neo4j
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_PLUGINS=["apoc"]
      - NEO4J_dbms_memory_heap_initial__size=512m
      - NEO4J_dbms_memory_heap_max__size=2G
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7474"]
      interval: 30s
      timeout: 10s
      retries: 5
    restart: unless-stopped

  # === Nginx ===
  nginx:
    image: nginx:alpine
    container_name: mhrag-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - backend
      - frontend
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  milvus_data:
  milvus_etcd:
  milvus_minio:
  neo4j_data:
  neo4j_logs:
```

### 5.3 Nginx Configuration

```nginx
# nginx/nginx.conf

worker_processes auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 4096;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';
    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log warn;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml application/json application/javascript application/rss+xml application/atom+xml image/svg+xml;

    upstream backend {
        least_conn;
        server backend:8000 max_fails=3 fail_timeout=30s;
        keepalive 32;
    }

    upstream frontend {
        server frontend:3000;
    }

    server {
        listen 80;
        server_name localhost;

        # Redirect to HTTPS (in production)
        # return 301 https://$server_name$request_uri;

        # === Frontend ===
        location / {
            proxy_pass http://frontend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_cache_bypass $http_upgrade;
        }

        # === API ===
        location /api/v1 {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Timeout
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # === SSE Streaming ===
        location /api/v1/chat/stream {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_buffering off;
            proxy_cache off;
            proxy_flush on;
            proxy_buffers 4 64k;
            chunked_transfer_encoding on;
            tcp_nodelay on;
        }

        health_check uri=/api/v1/health interval=10s fails=3 passes=2;
    }
}
```

---

## 6. CI/CD Pipeline

```yaml
# .github/workflows/ci-cd.yml

name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "3.11"
  NODE_VERSION: "20"

jobs:
  # === LINT & TYPE CHECK ===
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Python setup
        uses: actions/setup-python@v5
        with: {python-version: ${{ env.PYTHON_VERSION }}}

      - name: Install linters
        run: pip install ruff mypy black

      - name: Run ruff
        run: ruff check ai/

      - name: Run mypy
        run: mypy ai/ --ignore-missing-imports

      - name: Run black
        run: black --check ai/

  # === UNIT TESTS ===
  unit-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: mhrag_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s

    steps:
      - uses: actions/checkout@v4

      - name: Python setup
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r backend/requirements.txt pytest pytest-asyncio pytest-cov

      - name: Unit tests
        run: |
          pytest backend/tests/unit/ \
            --asyncio-mode=auto \
            --cov=src.agents \
            --cov-report=xml \
            --cov-fail-under=80

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml

  # === INTEGRATION TESTS ===
  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: mhrag_test
      redis:
        image: redis:7
      # Note: Integration tests use mocks for Milvus/Neo4j/Cohere
      # Real infra tested in E2E

    steps:
      - uses: actions/checkout@v4

      - name: Python setup
        uses: actions/setup-python@v5
        with: {python-version: ${{ env.PYTHON_VERSION }}}

      - name: Integration tests
        run: |
          pytest backend/tests/integration/ \
            --asyncio-mode=auto

  # === E2E TESTS (Nightly) ===
  e2e-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule' && github.event.schedule == '0 2 * * *'
    steps:
      - uses: actions/checkout@v4

      - name: Build & Start infra
        run: docker compose -f docker-compose-dev.yml up -d

      - name: Wait for services
        run: sleep 30

      - name: Install Playwright
        run: |
          npm ci
          npx playwright install chromium

      - name: Run E2E tests
        run: npx playwright test

      - name: Stop infra
        run: docker compose -f docker-compose-dev.yml down

  # === DOCKER BUILD ===
  docker-build:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    needs: [lint, unit-tests, integration-tests]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      - name: Build & Push backend
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: mhrag/backend:latest,mhrag/backend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build & Push frontend
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: true
          tags: mhrag/frontend:latest,mhrag/frontend:${{ github.sha }}

  # === DEPLOY (Production) ===
  deploy:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    needs: [docker-build]
    environment: production
    steps:
      - name: Deploy to production
        run: |
          # SSH to production server
          # docker compose pull
          # docker compose up -d
          echo "Deployment triggered"
```

---

## 7. Environment Config

```bash
# .env.example

# === API Keys ===
GEMINI_API_KEY=your_gemini_api_key
COHERE_API_KEY=your_cohere_api_key
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=mhrag-production

# === Databases ===
POSTGRES_PASSWORD=secure_password_here
POSTGRES_DB=mhrag
DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}

REDIS_PASSWORD=
REDIS_URL=redis://redis:6379/0

# === Neo4j ===
NEO4J_PASSWORD=secure_neo4j_password

# === Milvus ===
MILVUS_URI=http://milvus:19530
MILVUS_TOKEN=

# === Security ===
SECRET_KEY=your_jwt_secret_key_min_32_chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# === LangSmith ===
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

---

*Lưu ý: File này là Part 5 — Testing & Deployment. Tiếp theo: Part 6 — Documentation (Tổng hợp kiến trúc đầy đủ).*
