"""
Supervisor Agent — Standalone FastAPI microservice.

Responsibilities:
  1. Route user message → domain agent (HTTP call to that agent)
  2. Return final response to backend

Communication:
  - Incoming: Backend → POST /engine/route
  - Outgoing: Supervisor → POST /agent/{name} (domain agents via HTTP)
"""

from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ai.shared.agent_based.constants import AgentID
from ai.shared.agent_based.state import GlobalState
from ai.shared.services.memory_service import MemoryService
from ai.shared.rag import MilvusClient, Neo4jClient, OpenAIClient
from ai.shared.communication import (
    AgentHTTPClient,
    AgentRequest,
    AgentResponse,
    HealthResponse,
)
from ai.agents.supervisor.supervisor_agent import SupervisorAgent

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger(__name__)

# ─── Defaults ─────────────────────────────────────────────────────────────────

HTTP_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


# ─── App factory ───────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build and inject agent
    app.state.agent = _build_agent()
    # HTTP client for calling domain agents
    app.state.http_client = AgentHTTPClient(
        timeout=60.0,
        connect_timeout=10.0,
        max_retries=2,
    )
    logger.info("[Supervisor] Started on port %s", os.getenv("AGENT_PORT", "8001"))
    yield
    await app.state.http_client.close()
    logger.info("[Supervisor] Shutdown complete")


def _build_agent() -> SupervisorAgent:
    redis_client = None
    if redis_url := os.getenv("REDIS_URL"):
        import redis.asyncio as redis_async

        redis_client = redis_async.from_url(redis_url, decode_responses=True)

    milvus: MilvusClient | None = None
    try:
        milvus = MilvusClient(
            uri=f"http://{os.getenv('MILVUS_HOST','milvus')}:{os.getenv('MILVUS_PORT','19530')}"
        )
    except Exception as e:
        logger.warning("[Supervisor] Milvus unavailable: %s", e)

    neo4j: Neo4jClient | None = None
    if pwd := os.getenv("NEO4J_PASSWORD"):
        try:
            neo4j = Neo4jClient(
                uri=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
                user=os.getenv("NEO4J_USER", "neo4j"),
                password=pwd,
            )
        except Exception as e:
            logger.warning("[Supervisor] Neo4j unavailable: %s", e)

    llm = _build_llm()

    memory = MemoryService(redis_client=redis_client, max_buffer_size=3, cache_ttl=3600)

    agent = SupervisorAgent(
        memory_service=memory,
        llm=llm,
        config={"milvus": milvus, "neo4j": neo4j},
    )
    return agent


def _build_llm():
    """Build LLM client — prefers NVIDIA API (OpenAI-compatible), falls back to Gemini."""
    import os

    # 1. OpenAI-compatible (NVIDIA API)
    if api_key := os.getenv("NVIDIA_API_KEY"):
        base_url = os.getenv("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")
        model = os.getenv("OPENAI_MODEL", "openai/gpt-oss-120b")
        try:
            return OpenAIClient(
                base_url=base_url,
                api_key=api_key,
                model=model,
                default_temperature=0.7,
                default_max_tokens=1024,
            )
        except Exception as e:
            logger.warning("[Supervisor] OpenAI LLM init failed: %s", e)

    # 2. Gemini fallback
    if api_key := os.getenv("GEMINI_API_KEY"):
        try:
            from ai.shared.rag import GeminiClient

            return GeminiClient(
                api_key=api_key, model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            )
        except Exception as e:
            logger.warning("[Supervisor] Gemini init failed: %s", e)

    logger.warning("[Supervisor] No LLM configured")
    return None


app = FastAPI(title="Supervisor Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Routes ───────────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok", agent="supervisor", port=int(os.getenv("AGENT_PORT", "8001"))
    )


@app.post("/engine/route", response_model=AgentResponse)
async def route_and_dispatch(req: AgentRequest):
    """
    Full orchestration endpoint:
      1. SupervisorAgent.route() → target domain agent
      2. Call that domain agent via HTTP
      3. Return final response

    This is the main entry point called by the backend FastAPI service.
    """
    agent: SupervisorAgent = app.state.agent
    http_client: AgentHTTPClient = app.state.http_client
    gs: GlobalState = {}

    try:
        # Step 1: Supervisor classifies and routes
        routing = await agent.run(
            input={
                "message": req.message,
                "conv_id": req.conversation_id,
                "user_id": req.user_id,
                "language": req.language,
                "metadata": req.metadata,
            },
            gs=gs,
        )

        target_agent: str = routing["target_agent"]  # e.g. "agent-support"
        context: dict = routing.get("context", {})

        # Step 2: Build request for domain agent
        domain_req = AgentRequest(
            message=req.message,
            conversation_id=req.conversation_id,
            user_id=req.user_id,
            language=req.language,
            intent=context.get("intent", req.intent),
            context={
                "original_message": req.message,
                "translated_message": context.get("translated_message", req.message),
                "preliminary_slots": context.get("preliminary_slots", {}),
                "language": req.language,
            },
            metadata=req.metadata,
            crisis_detected=(target_agent == AgentID.CRISIS),
        )

        # Step 3: Call domain agent via HTTP
        if target_agent == AgentID.CRISIS:
            domain_resp = await http_client.call_crisis_emergency(domain_req)
        else:
            domain_resp = await http_client.call_agent(target_agent, domain_req)

        # Step 4: Return combined response
        return AgentResponse(
            response=domain_resp.response,
            agent_id=domain_resp.agent_id,
            intent=domain_resp.intent,
            language=domain_resp.language,
            skills_used=domain_resp.skills_used,
            crisis_detected=domain_resp.crisis_detected,
            conversation_id=domain_resp.conversation_id,
            turn=domain_resp.turn + 1,
            metadata={
                "routed_to": target_agent,
                "supervisor_intent": context.get("intent", ""),
            },
        )

    except httpx.HTTPStatusError as e:
        logger.error("[Supervisor] Domain agent HTTP error: %s", e)
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        logger.error("[Supervisor] route_and_dispatch error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/engine/classify", response_model=AgentResponse)
async def classify_only(req: AgentRequest):
    """
    Lightweight endpoint — only classify intent, no domain agent call.
    Useful for debugging, analytics, or backend wanting to handle dispatch itself.
    """
    agent: SupervisorAgent = app.state.agent
    gs: GlobalState = {}

    try:
        routing = await agent.run(
            input={
                "message": req.message,
                "conv_id": req.conversation_id,
                "user_id": req.user_id,
                "language": req.language,
                "metadata": req.metadata,
            },
            gs=gs,
        )

        context = routing.get("context", {})
        return AgentResponse(
            response="",
            agent_id=routing["target_agent"],
            intent=context.get("intent", "unknown"),
            language=req.language,
            crisis_detected=(routing["target_agent"] == AgentID.CRISIS),
            conversation_id=req.conversation_id,
            metadata={
                "routing_context": context,
            },
        )

    except Exception as e:
        logger.error("[Supervisor] classify_only error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/{name}")
async def call_domain_agent(name: str, req: AgentRequest):
    """
    Direct passthrough — call a specific domain agent by name.
    Used by backend for custom orchestration flows.
    """
    agent_id = f"agent-{name}"
    http_client: AgentHTTPClient = app.state.http_client

    try:
        resp = await http_client.call_agent(agent_id, req)
        return resp
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        logger.error("[Supervisor] call_domain_agent error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


# ─── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT", "8001"))
    uvicorn.run(
        "ai.agents.supervisor.main:app", host="0.0.0.0", port=port, reload=False
    )
