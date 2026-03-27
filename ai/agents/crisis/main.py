"""
Crisis Agent — Standalone FastAPI microservice entry point.
"""
from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ai.agents.crisis.schemas import CrisisRequest, CrisisResponse, HealthResponse
from ai.shared.agent_based.constants import AgentID
from ai.shared.agent_based.state import GlobalState
from ai.shared.services.memory_service import MemoryService
from ai.shared.communication.message_bus import MessageBus
from ai.shared.rag import MilvusClient, Neo4jClient, GeminiClient
from ai.agents.crisis.crisis_agent import CrisisAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_url = os.getenv("REDIS_URL", "")
    redis_client = None
    if redis_url:
        import redis
        redis_client = redis.from_url(redis_url, decode_responses=True)

    milvus: MilvusClient | None = None
    try:
        milvus = MilvusClient(uri=f"http://{os.getenv('MILVUS_HOST','milvus')}:{os.getenv('MILVUS_PORT','19530')}")
    except Exception as e:
        logger.warning("[Crisis] Milvus unavailable: %s", e)

    neo4j: Neo4jClient | None = None
    pwd = os.getenv("NEO4J_PASSWORD", "")
    if pwd:
        try:
            neo4j = Neo4jClient(uri=os.getenv("NEO4J_URI","bolt://neo4j:7687"),
                                user=os.getenv("NEO4J_USER","neo4j"), password=pwd)
        except Exception as e:
            logger.warning("[Crisis] Neo4j unavailable: %s", e)

    llm: GeminiClient | None = None
    if os.getenv("GEMINI_API_KEY"):
        llm = GeminiClient(api_key=os.getenv("GEMINI_API_KEY",""))

    memory = MemoryService(redis_client=redis_client, max_buffer_size=3, cache_ttl=3600)
    bus = MessageBus()

    app.state.agent = CrisisAgent(
        memory_service=memory, llm=llm,
        config={"milvus": milvus, "neo4j": neo4j},
        message_bus=bus,
    )
    logger.info("[Crisis] Started on port %s", os.getenv("AGENT_PORT","8105"))
    yield
    logger.info("[Crisis] Shutdown complete")


app = FastAPI(title="Crisis Agent", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", agent="crisis", port=int(os.getenv("AGENT_PORT","8105")))


@app.post("/agent/crisis", response_model=CrisisResponse)
async def run_crisis(req: CrisisRequest):
    agent: CrisisAgent = app.state.agent
    gs: GlobalState = {}
    try:
        result = await agent.run(
            input={
                "message":          req.message,
                "conversation_id":  req.conversation_id,
                "user_id":          req.user_id,
                "language":         req.language,
                "context":          req.context,
                "severity":         req.severity,
                "metadata":         req.metadata,
            },
            gs=gs,
        )
        return CrisisResponse(
            response=result.get("response",""),
            agent_id=AgentID.CRISIS,
            intent="crisis",
            language=req.language,
            skills_used=result.get("skills_used",[]),
            crisis_detected=True,
            severity=result.get("severity", req.severity),
            conversation_id=req.conversation_id,
            resources_provided=result.get("resources_provided",[]),
            escalation_recommended=result.get("escalation_recommended", False),
        )
    except Exception as e:
        logger.error("[Crisis] error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT","8105"))
    uvicorn.run("ai.agents.crisis.main:app", host="0.0.0.0", port=port, reload=False)
