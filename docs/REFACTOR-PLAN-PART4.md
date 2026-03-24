# Mental Health Hybrid RAG — Refactor Plan
## Phần 4: Performance Optimization — Caching & Parallel Processing

> **Caching Strategy + Parallel Agent Execution + Latency Optimization**
> Đọc sau: REFACTOR-PLAN-PART1.md, REFACTOR-PLAN-PART2.md, REFACTOR-PLAN-PART3.md

---

## 1. Caching Strategy — 3-Level Cache

### 1.1 Cache Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 L1: In-Memory LRU Cache                  │
│  (per-process, per-agent, ephemeral)                     │
│  Cache entry: {embedding, retrieval_result, LLM_response}│
│  TTL: Agent run duration (~30s)                         │
│  Size: 100-500 entries per agent                        │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              L2: Redis Distributed Cache                 │
│  (shared across processes/workers)                      │
│  Cache entry: {user_context, slot_state, retrieval_cache}│
│  TTL: Conversation duration (~30 min)                   │
│  Size: ~10MB per conversation                            │
│  Connection pool: 10 connections                         │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│               L3: PostgreSQL Checkpoint                  │
│  (persistent, durable)                                   │
│  Cache entry: {global_state, buffer, summary, slots}    │
│  TTL: Conversation lifetime (~30 days retention)         │
│  Load: On conversation resume                           │
└─────────────────────────────────────────────────────────┘
```

### 1.2 L1 In-Memory Cache (Per-Agent)

```python
# ai/modules/shared/cache.py

from functools import lru_cache
from collections import OrderedDict
import hashlib
import asyncio

class LRUCache:
    """Thread-safe LRU cache với TTL."""

    def __init__(self, maxsize: int = 128, ttl: float = 30.0):
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    def _make_key(self, *args, **kwargs) -> str:
        """Tạo cache key từ args."""
        key_data = f"{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._cache:
                return None

            # Check TTL
            if time.time() - self._timestamps.get(key, 0) > self.ttl:
                del self._cache[key]
                del self._timestamps[key]
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return self._cache[key]

    async def set(self, key: str, value: Any):
        async with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self.maxsize:
                    # Evict LRU
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
                    del self._timestamps[oldest_key]

                self._cache[key] = value
            self._timestamps[key] = time.time()

    async def delete(self, key: str):
        async with self._lock:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)

    async def clear(self):
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()


class AgentCache:
    """
    Per-agent cache manager.
    Mỗi agent có 1 instance riêng.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.embedding_cache = LRUCache(maxsize=500, ttl=60)
        self.retrieval_cache = LRUCache(maxsize=200, ttl=120)
        self.llm_response_cache = LRUCache(maxsize=100, ttl=30)
        self.llm_call_semaphore = asyncio.Semaphore(5)  # Max 5 concurrent LLM calls

    async def cached_embedding(self, text: str, embed_fn) -> list[float]:
        """Cache E5 embedding."""
        cache_key = hashlib.md5(text.lower().strip().encode()).hexdigest()
        cached = await self.embedding_cache.get(cache_key)
        if cached is not None:
            return cached

        result = await embed_fn(text)
        await self.embedding_cache.set(cache_key, result)
        return result

    async def cached_retrieval(
        self, query: str, collection: str, top_k: int, retrieval_fn
    ) -> dict:
        """Cache retrieval results."""
        cache_key = hashlib.md5(
            f"{query}:{collection}:{top_k}".encode()
        ).hexdigest()
        cached = await self.retrieval_cache.get(cache_key)
        if cached is not None:
            return cached

        result = await retrieval_fn(query, collection, top_k)
        await self.retrieval_cache.set(cache_key, result)
        return result

    async def cached_llm(
        self, prompt_hash: str, llm_fn, *args, **kwargs
    ) -> Any:
        """
        Cache LLM responses.
        prompt_hash = hash của input prompt (bao gồm slots, buffer, ...)
        """
        async with self.llm_call_semaphore:
            cached = await self.llm_response_cache.get(prompt_hash)
            if cached is not None:
                return cached

            result = await llm_fn(*args, **kwargs)
            await self.llm_response_cache.set(prompt_hash, result)
            return result
```

### 1.3 L2 Redis Cache (Distributed, Shared)

```python
# ai/modules/shared/redis_cache.py

import redis.asyncio as redis
import json
from typing import Optional, Any
import hashlib

class RedisCache:
    """
    L2 distributed cache — shared across all workers.
    TTL: 30 min per conversation.
    """

    KEY_PREFIX = "mhrag:cache:"
    DEFAULT_TTL = 1800  # 30 minutes

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )

    def _key(self, namespace: str, conv_id: str, *parts) -> str:
        parts_str = ":".join(str(p) for p in parts)
        hash_part = hashlib.md5(parts_str.encode()).hexdigest()[:16]
        return f"{self.KEY_PREFIX}{namespace}:{conv_id}:{hash_part}"

    # === Slot Cache ===
    async def get_slots(self, conv_id: str) -> Optional[dict]:
        key = self._key("slots", conv_id)
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def set_slots(self, conv_id: str, slots: dict, ttl: int = DEFAULT_TTL):
        key = self._key("slots", conv_id)
        await self.redis.setex(key, ttl, json.dumps(slots))

    # === Retrieval Cache ===
    async def get_retrieval(
        self, conv_id: str, query: str, collection: str
    ) -> Optional[dict]:
        query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
        key = self._key("retrieval", conv_id, collection, query_hash)
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def set_retrieval(
        self, conv_id: str, query: str, collection: str,
        result: dict, ttl: int = DEFAULT_TTL
    ):
        query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
        key = self._key("retrieval", conv_id, collection, query_hash)
        await self.redis.setex(key, ttl, json.dumps(result))

    # === Context Cache ===
    async def get_conversation_context(self, conv_id: str) -> Optional[dict]:
        key = self._key("context", conv_id)
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def set_conversation_context(
        self, conv_id: str, context: dict, ttl: int = DEFAULT_TTL
    ):
        key = self._key("context", conv_id)
        await self.redis.setex(key, ttl, json.dumps(context))

    # === Warm-up ===
    async def warm_from_checkpointer(self, conv_id: str, checkpointer):
        """
        Load data từ PostgreSQL → Redis khi conversation resume.
        Tránh phải query DB mỗi lần.
        """
        gs = await checkpointer.load_global_state(conv_id)
        if gs:
            if gs.get("slots"):
                await self.set_slots(conv_id, gs["slots"])
            if gs.get("conversation_buffer"):
                await self.set_conversation_context(conv_id, {
                    "buffer": gs["conversation_buffer"],
                    "summary": gs.get("summary_context", ""),
                    "slots": gs.get("slots", {}),
                })

    # === Cleanup ===
    async def invalidate_conversation(self, conv_id: str):
        """Xóa tất cả cache entries cho 1 conversation."""
        pattern = f"{self.KEY_PREFIX}*:{conv_id}:*"
        async for key in self.redis.scan_iter(match=pattern):
            await self.redis.delete(key)

    async def close(self):
        await self.redis.close()
```

### 1.4 Cache Coordination

```python
# Sử dụng trong Retrieval Skills bên trong Domain Agent

class RetrievalSkillMixin:
    """Mixin — cung cấp 3-level caching cho retrieval methods."""

    def __init__(self, redis_cache: RedisCache, ...):
        self.redis = redis_cache
        self._retrieval_cache = RetrievalCache()

    async def _tool_hybrid_search(
        self, query: str, collection: str, top_k: int = 3, slots: dict = None
    ) -> dict:
        conv_id = self._get_conversation_id()
        cache_key_parts = (query, collection, top_k)

        # L2 cache check (Redis)
        cached = await self.redis.get_retrieval(conv_id, query, collection)
        if cached:
            logger.debug(f"Cache HIT (L2) for {collection}:{query[:50]}")
            return cached

        # L1 cache check (in-memory)
        cache_key = hashlib.md5(f"{query}:{collection}:{top_k}".encode()).hexdigest()
        cached_l1 = await self.agent_cache.retrieval_cache.get(cache_key)
        if cached_l1:
            logger.debug(f"Cache HIT (L1) for {collection}:{query[:50]}")
            return cached_l1

        # Execute retrieval
        result = await self._execute_hybrid_search(query, collection, top_k, slots)

        # Store in both caches
        await self.redis.set_retrieval(conv_id, query, collection, result)
        await self.agent_cache.retrieval_cache.set(cache_key, result)

        return result
```

---

## 2. Parallel Processing — Agent Execution

### 2.1 Parallel Execution Patterns

```python
# ai/modules/shared/parallel_execution.py

class ParallelExecutor:
    """
    Quản lý parallel execution của multiple agents.
    """

    @staticmethod
    async def run_parallel(
        agents: List[Tuple[BaseAgent, dict]],
        gs: GlobalState,
        timeout: float = 30,
    ) -> Dict[str, Any]:
        """
        Chạy nhiều agents song song.
        agents: [(agent, input_dict), ...]
        Returns: {agent_id: result, ...}
        """
        tasks = []
        agent_ids = []

        for agent, input_dict in agents:
            agent_ids.append(agent.agent_id)
            task = asyncio.create_task(agent.run(input_dict, gs))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for agent_id, result in zip(agent_ids, results):
            if isinstance(result, Exception):
                output[agent_id] = {"error": str(result), "status": "failed"}
            else:
                output[agent_id] = result

        return output

    @staticmethod
    async def run_sequential(
        steps: List[Tuple[BaseAgent, dict]],
        gs: GlobalState,
        stop_on_error: bool = False,
    ) -> List[Any]:
        """
        Chạy agents tuần tự, mỗi step có thể update gs.
        """
        results = []
        for agent, input_dict in steps:
            try:
                result = await agent.run(input_dict, gs)
                results.append(result)
                if stop_on_error and result.get("error"):
                    break
            except Exception as e:
                results.append({"error": str(e), "status": "failed"})
                if stop_on_error:
                    break
        return results

    @staticmethod
    async def run_pipeline(
        stages: List[List[Tuple[BaseAgent, dict]]],
        gs: GlobalState,
    ) -> GlobalState:
        """
        Pipeline: stage 1 chạy parallel → results merge vào gs →
        stage 2 chạy parallel → ...

        Stages: [[agent1, agent2], [agent3], [agent4, agent5]]
        """
        for stage_idx, stage in enumerate(stages):
            logger.debug(f"Pipeline stage {stage_idx}: {[a.agent_id for a, _ in stage]}")

            # Run stage in parallel
            results = await ParallelExecutor.run_parallel(stage, gs)

            # Merge results into global state
            for agent_id, result in results.items():
                if "error" not in result:
                    gs[f"_{agent_id}_result"] = result

            # Early exit if any critical result is an error
            if all(r.get("error") for r in results.values()):
                logger.warning(f"Pipeline stage {stage_idx}: all agents failed")
                break

        return gs
```

### 2.2 Parallel Retrieval — Domain Agent Internal

```python
# ai/modules/shared/parallel_retrieval.py

class ParallelRetrievalExecutor:
    """
    Shared parallel retrieval skill embedded inside each Domain Agent.
    Executes multi-collection retrieval in parallel within a single domain agent context.
    NOT a standalone agent — a skill mixin used by Domain Agents.
    """

    # Collection map for each retrieval path
    COLLECTION_MAP = {
        "diagnostic": "mental_health_diagnostic_support",
        "theory": "theory_grounding",
        "treatment": "treatment_protocols",
        "support": "community_support",
        "crisis": "crisis_resources",
    }

    async def _parallel_retrieve(
        self,
        query: str,
        path: str,
        gs: GlobalState,
        top_k: int = 5,
    ) -> dict:
        """
        Run parallel retrieval across multiple collections for a given path.
        Called internally by Domain Agents (DiagnosticAgent, TheoryAgent, etc.)
        """
        slots = gs.get("slots", {})
        collection = self.COLLECTION_MAP.get(path, "mental_health_diagnostic_support")

        # === PARALLEL: Hybrid search + Graph retrieval ===
        if path == "diagnostic":
            # DiagnosticAgent calls 3 skill methods in parallel
            results = await asyncio.gather(
                self._skill_hybrid_search(
                    query=query,
                    collection="mental_health_diagnostic_support",
                    top_k=top_k,
                    slots=slots,
                ),
                self._skill_hybrid_search(
                    query=query,
                    collection="normal_responses",
                    top_k=top_k,
                    slots=slots,
                ),
                self._skill_graph_subgraph(
                    query=query,
                    depth=2,
                    slots=slots,
                ),
                return_exceptions=True,
            )

            # Aggregate results
            hybrid_results = results[0] if not isinstance(results[0], Exception) else {}
            normal_results = results[1] if not isinstance(results[1], Exception) else {}
            graph_results = results[2] if not isinstance(results[2], Exception) else {}

            aggregated = self._aggregate_multi_results(
                diagnostic_chunks=hybrid_results.get("chunks", []),
                normal_chunks=normal_results.get("chunks", []),
                graph_context=graph_results.get("subgraph_text", ""),
            )

        else:
            # Single collection retrieval for other paths
            result = await self._skill_hybrid_search(
                query=query,
                collection=collection,
                top_k=top_k,
                slots=slots,
            )
            aggregated = {"primary": result}

        gs["retrieval_results"] = aggregated
        return aggregated

    def _aggregate_multi_results(
        self,
        diagnostic_chunks: list,
        normal_chunks: list,
        graph_context: str,
    ) -> dict:
        """Gộp kết quả từ multiple retrieval skill calls."""
        # Rank diagnostic chunks by score
        diagnostic_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        normal_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)

        return {
            "diagnostic_chunks": diagnostic_chunks[:5],
            "normal_chunks": normal_chunks[:3],
            "graph_context": graph_context,
            "combined": (diagnostic_chunks + normal_chunks)[:5],
        }
```

### 2.3 SupervisorAgent — Parallel Translation + Crisis Safety Gate

```python
# ai/modules/supervisor/supervisor_agent.py

async def route(self, user_message: str, conversation_id: str) -> dict:
    gs = await self.checkpointer.load_global_state(conversation_id)
    gs["conversation_id"] = conversation_id
    gs["original_question"] = user_message

    # === PARALLEL: Crisis Safety Gate (keyword, no LLM) + LLM Intent Classification ===
    # Crisis check is synchronous keyword-based — no LLM needed, runs instantly.
    # Intent classification uses LLM but is fast; both run in parallel.
    parallel_results = await ParallelExecutor.run_parallel([
        (
            None,  # No agent — crisis_safety_gate is a plain async function
            {"fn": crisis_safety_gate, "text": user_message}
        ),
        (
            self.llm,
            {
                "task": "classify_intent",
                "text": user_message,
                "conversation_context": self._get_context_snippet(gs),
            }
        ),
    ], gs, timeout=10)  # 10s timeout

    crisis_result = parallel_results.get(0, {})
    intent_result = parallel_results.get(1, {})

    # Update global state
    gs["user_language"] = intent_result.get("detected_language", "vi")
    gs["current_question"] = intent_result.get("translated", user_message)
    gs["intent"] = intent_result.get("intent", "unknown")
    gs["is_high_risk"] = crisis_result.get("is_crisis", False)
    gs["crisis_level"] = crisis_result.get("level", "none")
    gs["crisis_indicators"] = crisis_result.get("indicators", [])

    # === Route based on crisis check (highest priority) ===
    if gs["is_high_risk"]:
        return await self._route_to_crisis_agent(gs)
    else:
        return await self._route_to_domain_agent(gs["intent"], gs)
```

### 2.4 ResponseDrafting — Domain Agent Skill

```python
# ai/modules/shared/skills/response_drafting.py

class ResponseDraftingSkill:
    """
    ResponseDrafting skill embedded inside each Domain Agent.
    MemoryService is injected via constructor (NOT a singleton agent).
    """

    def __init__(self, memory_service: MemoryService, llm, ...):
        self.memory_service = memory_service  # Injected, not retrieved via agent_manager
        self.llm = llm

    async def run(self, input: dict, gs: GlobalState) -> dict:
        """
        Response drafting with parallel context preparation.
        MemoryService is called directly as a service method.
        """
        # Parallel: build context from retrieval results + conversation memory
        context_task = asyncio.create_task(self._build_retrieval_context(gs))
        memory_task = asyncio.create_task(
            self.memory_service.get_context(gs)  # Direct service call, NOT agent_manager
        )

        retrieval_context, memory_context = await asyncio.gather(
            context_task, memory_task
        )

        # Combine contexts
        full_context = {
            **retrieval_context,
            "conversation_memory": memory_context.get("formatted", ""),
            "slots": gs.get("slots", {}),
        }

        # Generate answer (LLM call — main bottleneck, no parallelism here)
        answer = await self._generate_with_llm(
            query=gs["current_question"],
            context=full_context,
            language=gs.get("user_language", "vi"),
        )

        # Translate if needed
        if gs.get("user_language") == "vi":
            answer = await self._translate_to_vietnamese(answer)

        gs["answer"] = answer
        return {"status": "completed", "answer": answer}

    async def _build_retrieval_context(self, gs: GlobalState) -> dict:
        """Build retrieval context từ retrieval results (ResponseDrafting skill)."""
        rr = gs.get("retrieval_results", {})

        graph_context = ""
        chunks = []

        # Combine all retrieval results
        for key, value in rr.items():
            if isinstance(value, str) and key == "graph_context":
                graph_context += value + "\n\n"
            elif isinstance(value, list):
                chunks.extend(value)

        # Sort by score
        chunks.sort(key=lambda x: x.get("score", 0), reverse=True)

        return {
            "graph_context": graph_context,
            "top_chunks": chunks[:5],
            "context_text": self._chunks_to_text(chunks[:5]) + "\n\n" + graph_context,
        }
```

---

## 3. Latency Optimization

### 3.1 Bottleneck Analysis

```
Current average latency breakdown (workflow cũ):
────────────────────────────────────────────────────────────
1. Translation (LLM call)        ~300ms
2. Safety check (LLM call)       ~400ms
3. Slot filling (LLM call)       ~500ms
4. Assessment (LLM call)         ~400ms
5. Retrieval (Milvus + Rerank)   ~600ms
6. Neo4j subgraph                ~200ms
7. Answer generation (LLM)       ~800ms
8. Translation (VI output)       ~200ms
9. Memory save                   ~100ms
────────────────────────────────────────────────────────────
TOTAL SEQUENTIAL:                ~3500ms (~3.5s)

Optimization potential:
- Step 1+2 parallel:             -300ms  (parallel translation + safety)
- L2 cache hit (retrieval):     -500ms  (Redis cache)
- L1 cache hit (embedding):      -50ms  (per embedding)
- Parallel retrieval:           -200ms  (multi-collection)
- Lazy assessment:              -400ms  (skip if slots insufficient → request_info first)
────────────────────────────────────────────────────────────
ESTIMATED NEW TOTAL:             ~1850ms (~1.8s)
```

### 3.2 Optimizations Checklist

```python
# ai/modules/supervisor/optimizations.py

class OptimizerConfig:
    """Cấu hình optimization strategies."""

    # Parallel execution
    PARALLEL_TRANSLATE_SAFETY = True      # Default: True
    PARALLEL_RETRIEVAL = True             # Default: True
    PARALLEL_CONTEXT_BUILDING = True       # Default: True

    # Caching
    ENABLE_L1_CACHE = True                # Default: True
    ENABLE_L2_CACHE = True                # Default: True
    CACHE_TTL_L1_EMBEDDING = 60            # seconds
    CACHE_TTL_L1_RETRIEVAL = 120           # seconds
    CACHE_TTL_L1_LLM = 30                  # seconds
    CACHE_TTL_L2_CONVERSATION = 1800       # 30 minutes

    # LLM optimization
    STREAM_LLM = True                      # Stream tokens (frontend)
    LLM_TIMEOUT = 30                       # seconds
    EMBEDDING_BATCH_SIZE = 10              # Batch multiple embeddings

    # Retrieval optimization
    RETRIEVAL_TOP_K_MILVUS = 50            # Candidates for reranking
    RETRIEVAL_TOP_K_RERANK = 3             # Final chunks
    SKIP_RERANK_IF_CACHED = True           # Skip Cohere call if cache hit

    # Memory optimization
    SKIP_MEMORY_SAVE_IF_NO_CHANGE = True   # Don't write if no state change
    BATCH_DB_WRITES = True                 # Batch multiple writes
    ASYNC_CHECKPOINT = True                # Non-blocking checkpoint save
```

### 3.3 Streaming Response (Frontend Real-time)

```python
# backend/src/api/v1/endpoints/streaming.py

async def generate_streaming_answer(
    query: str,
    context: dict,
    llm,
    conversation_id: str,
):
    """
    Streaming answer generation — real-time display on frontend.
    Uses SSE (Server-Sent Events) via FastAPI.
    """
    from fastapi.responses import StreamingResponse

    async def event_generator():
        full_answer = ""

        # Stream from LLM
        async for chunk in llm.astream_generate(
            prompt=build_prompt(query, context),
            model="gemini-2.0-flash",
        ):
            full_answer += chunk
            yield f"data: {json.dumps({'token': chunk, 'done': False})}\n\n"

        yield f"data: {json.dumps({'token': '', 'done': True, 'full': full_answer})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# backend/src/api/v1/endpoints/chat.py

@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    current_user = Depends(get_current_user),
):
    """SSE endpoint for streaming chat."""
    supervisor = get_supervisor()

    # Route message to domain agent (non-blocking)
    result = await supervisor.route(
        user_message=request.message,
        conversation_id=request.conversation_id,
    )

    # Stream answer
    return await generate_streaming_answer(
        query=result["answer"],
        context={},
        llm=get_llm(),
        conversation_id=request.conversation_id,
    )
```

### 3.4 Async Checkpoint (Non-blocking Save)

```python
# ai/modules/shared/rag/workflow/checkpointer.py

class AsyncCheckpointerInterface:
    """
    Non-blocking checkpointer — không block agent execution.
    """

    def __init__(self, checkpointer: AsyncPostgresSaver, redis_cache: RedisCache):
        self.checkpointer = checkpointer
        self.redis = redis_cache
        self._pending_save: asyncio.Event = asyncio.Event()
        self._save_task: Optional[asyncio.Task] = None
        self._dirty = False

    async def save_global_state(self, conversation_id: str, state: GlobalState):
        """Non-blocking save: update L2 cache immediately, L3 async."""
        # L2: Redis (fast, non-blocking)
        if state.get("slots"):
            await self.redis.set_slots(conversation_id, state["slots"])

        await self.redis.set_conversation_context(conversation_id, {
            "buffer": state.get("conversation_buffer", []),
            "summary": state.get("summary_context", ""),
            "slots": state.get("slots", {}),
        })

        # L3: PostgreSQL (slower, background)
        self._dirty = True
        if self._save_task is None or self._save_task.done():
            self._save_task = asyncio.create_task(
                self._flush_to_postgres(conversation_id, state)
            )

    async def _flush_to_postgres(self, conv_id: str, state: GlobalState):
        """Background task: flush to PostgreSQL."""
        await asyncio.sleep(0.5)  # Batch: wait 500ms for more changes
        serialized = GlobalStateSerializer.serialize(state)
        await self.checkpointer.aput(conv_id, serialized)
        self._dirty = False

    async def load_global_state(self, conversation_id: str) -> GlobalState:
        """Load: check L2 first (Redis), fallback to L3 (PostgreSQL)."""
        # L2: Redis
        cached = await self.redis.get_conversation_context(conversation_id)
        if cached:
            return self._context_to_global_state(cached)

        # L3: PostgreSQL
        checkpoint = await self.checkpointer.aget(conversation_id)
        if checkpoint:
            state = GlobalStateSerializer.deserialize(checkpoint)
            # Warm L2 cache
            await self.redis.set_conversation_context(conversation_id, {
                "buffer": state.get("conversation_buffer", []),
                "summary": state.get("summary_context", ""),
                "slots": state.get("slots", {}),
            })
            return state

        return GlobalState()
```

---

## 4. Concurrency Limits

```python
# ai/modules/shared/concurrency.py

class ConcurrencyManager:
    """
    Quản lý concurrency limits cho external resources.
    """

    def __init__(self):
        # Semaphores per resource type
        self.milvus_semaphore = asyncio.Semaphore(20)    # Max 20 parallel Milvus queries
        self.neo4j_semaphore = asyncio.Semaphore(10)     # Max 10 parallel Neo4j queries
        self.llm_semaphore = asyncio.Semaphore(15)       # Max 15 parallel LLM calls
        self.cohere_semaphore = asyncio.Semaphore(10)   # Max 10 parallel rerank calls
        self.redis_semaphore = asyncio.Semaphore(50)    # Max 50 parallel Redis ops

        # Per-conversation concurrency limit
        self.conv_semaphore: Dict[str, asyncio.Semaphore] = {}
        self.MAX_CONCURRENT_PER_CONV = 5

    def get_conv_semaphore(self, conv_id: str) -> asyncio.Semaphore:
        if conv_id not in self.conv_semaphore:
            self.conv_semaphore[conv_id] = asyncio.Semaphore(self.MAX_CONCURRENT_PER_CONV)
        return self.conv_semaphore[conv_id]

    async def cleanup_conv(self, conv_id: str):
        if conv_id in self.conv_semaphore:
            del self.conv_semaphore[conv_id]


# Usage in tools
class RetrievalSkillMixin:
    """Mixin — cung cấp concurrency limits cho retrieval methods."""
    def __init__(self, concurrency: ConcurrencyManager, ...):
        self.concurrency = concurrency

    async def milvus_search(self, query: str, collection: str, top_k: int):
        async with self.concurrency.milvus_semaphore:
            return await self._do_milvus_search(query, collection, top_k)

    async def neo4j_subgraph(self, anchor_ids: list, depth: int):
        async with self.concurrency.neo4j_semaphore:
            return await self._do_neo4j_subgraph(anchor_ids, depth)

    async def hybrid_search(self, ...):
        # Milvus + Neo4j in parallel within this skill
        async with self.concurrency.milvus_semaphore:
            milvus_task = self._do_milvus_search(...)
        async with self.concurrency.neo4j_semaphore:
            neo4j_task = self._do_neo4j_subgraph(...)

        milvus_result, neo4j_result = await asyncio.gather(milvus_task, neo4j_task)
        return self._merge(milvus_result, neo4j_result)
```

---

## 5. Memory Efficiency

```python
#ai/modules/shared/memory_efficiency.py

class MemoryOptimizedAgent(BaseAgent):
    """
    Base class với memory optimization.
    """

    MAX_BUFFER_SIZE = 3        # Q&A pairs
    MAX_SUMMARY_LENGTH = 1000  # Characters
    MAX_SLOTS_JSON_SIZE = 5000  # Characters

    def _compact_state(self, gs: GlobalState) -> GlobalState:
        """
        Compact global state trước khi lưu/checkpoint.
        Giảm memory footprint.
        """
        compacted = gs.copy()

        # Compact buffer
        buffer = compacted.get("conversation_buffer", [])
        if len(buffer) > self.MAX_BUFFER_SIZE:
            compacted["conversation_buffer"] = buffer[-self.MAX_BUFFER_SIZE:]

        # Compact summary
        summary = compacted.get("summary_context", "")
        if len(summary) > self.MAX_SUMMARY_LENGTH:
            compacted["summary_context"] = summary[-self.MAX_SUMMARY_LENGTH:]

        # Truncate large string fields
        for key in ["diagnostic_chunks", "graph_context"]:
            if compacted.get(key) and len(str(compacted[key])) > 10000:
                compacted[key] = str(compacted[key])[:10000] + "...[truncated]"

        return compacted

    def _lazy_checkpoint(self, gs: GlobalState) -> bool:
        """
        Chỉ checkpoint nếu có thay đổi thực sự.
        """
        if not hasattr(self, "_last_checkpoint"):
            self._last_checkpoint = {}
            return True

        # Compare only important fields
        important_keys = ["slots", "conversation_buffer", "summary_context",
                         "crisis_level", "assessment_category"]
        for key in important_keys:
            if gs.get(key) != self._last_checkpoint.get(key):
                self._last_checkpoint = {k: gs.get(k) for k in important_keys}
                return True
        return False
```

---

## 6. Performance Comparison

| Optimization | Before | After | Improvement |
|-------------|--------|-------|-------------|
| Translate + Safety parallel | 700ms sequential | 400ms parallel | 43% faster |
| L2 cache hit (retrieval) | 600ms fresh | 50ms cached | 92% faster |
| L1 cache hit (embedding) | 100ms fresh | 10ms cached | 90% faster |
| Parallel retrieval (3 collections) | 1800ms sequential | 700ms parallel | 61% faster |
| Async checkpoint save | 100ms blocking | 5ms non-blocking | 95% faster |
| **Overall avg latency** | **3500ms** | **~1500ms** | **~57% faster** |
| Crisis detection (priority) | 500ms | 100ms (interrupt) | 80% faster |
| Streaming response | N/A (full response) | First token ~500ms | UX +50% |

---

*Lưu ý: File này là Part 4 — Performance Optimization. Tiếp theo: Part 5 — Testing & Deployment (LangSmith + Docker).*
