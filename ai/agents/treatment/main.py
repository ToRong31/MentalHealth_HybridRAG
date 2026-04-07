"""
Treatment Agent — Standalone FastAPI microservice.
"""
from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ai.shared.agent_based.constants import AgentID
from ai.shared.agent_based.state import GlobalState
from ai.shared.services.memory_service import MemoryService
from ai.shared.rag import MilvusClient, Neo4jClient, OpenAIClient, CohereReranker
from ai.shared.communication import AgentRequest, AgentResponse, HealthResponse
from ai.agents.treatment.treatment_agent import TreatmentAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def _build_llm():
    if api_key := os.getenv("NVIDIA_API_KEY"):
        try:
            return OpenAIClient(
                base_url=os.getenv("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1"),
                api_key=api_key,
                model=os.getenv("OPENAI_MODEL", "openai/gpt-oss-120b"),
            )
        except Exception as e:
            logger.warning("[Treatment] OpenAI LLM init failed: %s", e)

    if api_key := os.getenv("GEMINI_API_KEY"):
        try:
            from ai.shared.rag import GeminiClient
            return GeminiClient(api_key=api_key, model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
        except Exception as e:
            logger.warning("[Treatment] Gemini init failed: %s", e)

    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
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
        logger.warning("[Treatment] Milvus unavailable: %s", e)

    neo4j: Neo4jClient | None = None
    if pwd := os.getenv("NEO4J_PASSWORD"):
        try:
            neo4j = Neo4jClient(
                uri=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
                user=os.getenv("NEO4J_USER", "neo4j"),
                password=pwd,
            )
        except Exception as e:
            logger.warning("[Treatment] Neo4j unavailable: %s", e)

    reranker: CohereReranker | None = None
    if api_key := os.getenv("COHERE_API_KEY"):
        try:
            reranker = CohereReranker(api_key=api_key)
        except Exception as e:
            logger.warning("[Treatment] Reranker unavailable: %s", e)

    memory = MemoryService(redis_client=redis_client, max_buffer_size=3, cache_ttl=3600)
    app.state.agent = TreatmentAgent(
        memory_service=memory,
        llm=_build_llm(),
        config={"milvus": milvus, "neo4j": neo4j, "reranker": reranker},
    )
    logger.info("[Treatment] Started on port %s", os.getenv("AGENT_PORT", "8103"))
    yield
    logger.info("[Treatment] Shutdown complete")


app = FastAPI(title="Treatment Agent", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", agent="treatment", port=int(os.getenv("AGENT_PORT", "8103")))


@app.post("/agent/treatment", response_model=AgentResponse)
async def run_treatment(req: AgentRequest):
    agent: TreatmentAgent = app.state.agent
    gs: GlobalState = {}
    try:
        result = await agent.run(
            input={
                "message":          req.message,
                "conversation_id":  req.conversation_id,
                "user_id":          req.user_id,
                "language":         req.language,
                "context":          req.context,
                "metadata":         req.metadata,
            },
            gs=gs,
        )
        return AgentResponse(
            response=result.get("response", ""),
            agent_id=AgentID.TREATMENT,
            intent="treatment",
            language=req.language,
            skills_used=result.get("skills_used", []),
            crisis_detected=result.get("crisis_detected", False),
            conversation_id=req.conversation_id,
            metadata=result.get("metadata", {}),
        )
    except Exception as e:
        logger.error("[Treatment] error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT", "8103"))
    uvicorn.run("ai.agents.treatment.main:app", host="0.0.0.0", port=port, reload=False)
