"""
Memory Agent — Standalone FastAPI microservice entry point.
Provides conversation memory as an HTTP service.
"""
from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ai.agents.memory.schemas import (
    BufferRequest,
    BufferResponse,
    ContextRequest,
    ContextResponse,
    SlotsRequest,
    SlotsResponse,
    CrisisStateRequest,
    CrisisStateResponse,
    HealthResponse,
)
from ai.shared.services.memory_service import MemoryService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_url = os.getenv("REDIS_URL", "")
    redis_client = None
    if redis_url:
        import redis
        redis_client = redis.from_url(redis_url, decode_responses=True)

    app.state.memory = MemoryService(
        redis_client=redis_client,
        max_buffer_size=int(os.getenv("MAX_BUFFER_SIZE", "3")),
        cache_ttl=int(os.getenv("CACHE_TTL", "3600")),
    )
    logger.info("[Memory] Started — redis=%s", "yes" if redis_client else "no")
    yield
    logger.info("[Memory] Shutdown complete")


app = FastAPI(title="Memory Agent", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", agent="memory", port=int(os.getenv("AGENT_PORT", "8002")))


@app.post("/memory/buffer", response_model=BufferResponse)
async def save_buffer(req: BufferRequest):
    try:
        await app.state.memory.save_buffer(req.conversation_id, req.role, req.content, req.metadata)
        return BufferResponse(saved=True, conversation_id=req.conversation_id)
    except Exception as e:
        logger.error("[Memory] save_buffer error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/context", response_model=ContextResponse)
async def get_context(req: ContextRequest):
    try:
        ctx = await app.state.memory.get_context(req.conversation_id, max_turns=req.max_turns)
        return ContextResponse(conversation_id=req.conversation_id, context=ctx)
    except Exception as e:
        logger.error("[Memory] get_context error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/slots/merge", response_model=SlotsResponse)
async def merge_slots(req: SlotsRequest):
    try:
        if req.new_slots:
            merged = await app.state.memory.merge_slots(req.conversation_id, req.new_slots)
        else:
            merged = await app.state.memory.get_accumulated_slots(req.conversation_id)
        return SlotsResponse(conversation_id=req.conversation_id, slots=merged)
    except Exception as e:
        logger.error("[Memory] merge_slots error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/slots", response_model=SlotsResponse)
async def get_slots(req: SlotsRequest):
    try:
        slots = await app.state.memory.get_accumulated_slots(req.conversation_id)
        return SlotsResponse(conversation_id=req.conversation_id, slots=slots)
    except Exception as e:
        logger.error("[Memory] get_slots error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/crisis", response_model=CrisisStateResponse)
async def crisis_state(req: CrisisStateRequest):
    try:
        if req.state is not None:
            await app.state.memory.update_crisis_state(req.conversation_id, req.state)
        state = await app.state.memory.get_crisis_state(req.conversation_id)
        return CrisisStateResponse(conversation_id=req.conversation_id, state=state)
    except Exception as e:
        logger.error("[Memory] crisis_state error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT", "8002"))
    uvicorn.run("ai.agents.memory.main:app", host="0.0.0.0", port=port, reload=False)
