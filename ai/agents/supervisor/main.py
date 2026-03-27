"""
Supervisor Agent — Standalone FastAPI microservice entry point.
"""
from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ai.agents.supervisor.schemas import (
    SupervisorRequest,
    SupervisorResponse,
    HealthResponse,
)
from ai.shared.agent_based.constants import AgentID
from ai.shared.services.memory_service import MemoryService
from ai.shared.communication.message_bus import MessageBus
from ai.shared.rag import MilvusClient, Neo4jClient, GeminiClient
from ai.agents.supervisor.supervisor_agent import SupervisorAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

# ─── Agent registry ────────────────────────────────────────────────────────────

DOMAIN_AGENT_URLS = {
    AgentID.DIAGNOSTIC: os.getenv("AGENT_DIAGNOSTIC_URL", "http://agent-diagnostic:8101"),
    AgentID.THEORY:     os.getenv("AGENT_THEORY_URL",     "http://agent-theory:8102"),
    AgentID.TREATMENT:  os.getenv("AGENT_TREATMENT_URL",  "http://agent-treatment:8103"),
    AgentID.SUPPORT:     os.getenv("AGENT_SUPPORT_URL",   "http://agent-support:8104"),
    AgentID.CRISIS:     os.getenv("AGENT_CRISIS_URL",     "http://agent-crisis:8105"),
}

HTTP_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


# ─── App factory ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: wire up agent
    app.state.agent = _build_agent()
    app.state.http = httpx.AsyncClient(timeout=HTTP_TIMEOUT)
    logger.info("[Supervisor] Started on port %s", os.getenv("AGENT_PORT", "8001"))
    yield
    # Shutdown
    await app.state.http.aclose()
    logger.info("[Supervisor] Shutdown complete")


app = FastAPI(title="Supervisor Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Agent builder ─────────────────────────────────────────────────────────────

def _build_agent() -> SupervisorAgent:
    redis_url = os.getenv("REDIS_URL", "")
    redis_client = None
    if redis_url:
        import redis
        redis_client = redis.from_url(redis_url, decode_responses=True)

    milvus: MilvusClient | None = None
    milvus_host = os.getenv("MILVUS_HOST", "milvus")
    milvus_port = os.getenv("MILVUS_PORT", "19530")
    try:
        milvus = MilvusClient(uri=f"http://{milvus_host}:{milvus_port}")
    except Exception as e:
        logger.warning("[Supervisor] Milvus unavailable: %s", e)

    neo4j: Neo4jClient | None = None
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")
    if neo4j_password:
        try:
            neo4j = Neo4jClient(
                uri=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
                user=os.getenv("NEO4J_USER", "neo4j"),
                password=neo4j_password,
            )
        except Exception as e:
            logger.warning("[Supervisor] Neo4j unavailable: %s", e)

    llm: GeminiClient | None = None
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        llm = GeminiClient(api_key=gemini_key)

    memory = MemoryService(redis_client=redis_client, max_buffer_size=3, cache_ttl=3600)
    bus = MessageBus()

    agent = SupervisorAgent(
        memory_service=memory,
        llm=llm,
        config={"milvus": milvus, "neo4j": neo4j},
        message_bus=bus,
    )
    agent._domain_agents = DOMAIN_AGENT_URLS  # type: ignore
    return agent


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", agent="supervisor", port=int(os.getenv("AGENT_PORT", "8001")))


@app.post("/engine/route", response_model=SupervisorResponse)
async def route(req: SupervisorRequest):
    """
    Main entry point — routes a user message to the appropriate domain agent.
    The supervisor classifies intent and returns routing info; actual agent call
    is handled by the backend service.
    """
    from ai.shared.agent_based.state import GlobalState

    agent: SupervisorAgent = app.state.agent
    gs: GlobalState = {}  # type: ignore

    try:
        result = await agent.run(
            input={
                "message":          req.message,
                "conversation_id":  req.conversation_id,
                "user_id":          req.user_id,
                "language":         req.language,
                "metadata":         req.metadata,
            },
            gs=gs,
        )

        return SupervisorResponse(
            response=result.get("response", ""),
            agent_id=result.get("target_agent", "supervisor"),
            intent=result.get("intent", "unknown"),
            language=req.language,
            skills_used=result.get("skills_used", []),
            crisis_detected=result.get("crisis_detected", False),
            conversation_id=req.conversation_id,
            turn=result.get("turn", 0),
        )

    except Exception as e:
        logger.error("[Supervisor] route error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/{name}", response_model=SupervisorResponse)
async def call_domain_agent(name: str, req: SupervisorRequest):
    """
    Supervisor delegates to a specific domain agent via HTTP.
    Used when the backend needs the supervisor to fully process a message.
    """
    target_url = DOMAIN_AGENT_URLS.get(f"agent-{name}") or DOMAIN_AGENT_URLS.get(name)
    if not target_url:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {name}")

    try:
        async with app.state.http as client:
            resp = await client.post(
                f"{target_url}/agent/{name}",
                json=req.model_dump(),
                timeout=HTTP_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        logger.error("[Supervisor] domain call error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


# ─── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT", "8001"))
    uvicorn.run("ai.agents.supervisor.main:app", host="0.0.0.0", port=port, reload=False)
