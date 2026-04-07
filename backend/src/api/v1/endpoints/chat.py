"""
Chat endpoints — gateway between frontend and SupervisorAgent microservice.

Flow:
  Frontend → Backend /api/v1/chat → SupervisorAgent (HTTP)
  SupervisorAgent routes → calls domain agents → returns response
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from .schemas import ChatRequest, ChatResponse, ErrorResponse
from backend.src.core.deps import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# ─── Supervisor Agent HTTP client ──────────────────────────────────────────────

SUPERVISOR_URL = os.getenv(
    "SUPERVISOR_AGENT_URL",
    os.getenv("AGENT_SUPERVISOR_URL", "http://localhost:8001"),
)
HTTP_TIMEOUT = httpx.Timeout(120.0, connect=10.0)

_httpx_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _httpx_client
    if _httpx_client is None:
        _httpx_client = httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )
    return _httpx_client


async def _close_client() -> None:
    global _httpx_client
    if _httpx_client is not None:
        await _httpx_client.aclose()
        _httpx_client = None


# ─── Turn counter ─────────────────────────────────────────────────────────────

_turn_counter: dict[str, int] = {}


def _next_turn(conversation_id: str) -> int:
    count = _turn_counter.get(conversation_id, 0) + 1
    _turn_counter[conversation_id] = count
    return count


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={500: {"model": ErrorResponse}},
)
async def chat_endpoint(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
) -> ChatResponse:
    """
    Full orchestration: call SupervisorAgent via HTTP.

    The SupervisorAgent handles:
      1. Crisis gate
      2. Intent classification
      3. Routing to domain agent
      4. Returning the final response

    Auth: Bearer JWT required.
    """
    client = _get_client()
    user_id = user.get("user_id", "")

    try:
        payload = {
            "message": request.message,
            "conversation_id": request.conversation_id,
            "user_id": user_id,
            "language": request.language,
            "metadata": request.metadata,
        }

        resp = await client.post(
            f"{SUPERVISOR_URL}/engine/route",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        return ChatResponse(
            response=data.get("response", ""),
            agent_id=data.get("agent_id", "unknown"),
            intent=data.get("intent", "unknown"),
            language=data.get("language", request.language),
            skills_used=data.get("skills_used", []),
            crisis_detected=data.get("crisis_detected", False),
            conversation_id=request.conversation_id,
            turn=_next_turn(request.conversation_id),
        )

    except httpx.HTTPStatusError as e:
        logger.error("[chat] SupervisorAgent HTTP error: %s %s", e.response.status_code, e.response.text)
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"SupervisorAgent error: {e.response.text}",
        )
    except httpx.TransportError as e:
        logger.error("[chat] Cannot connect to SupervisorAgent at %s: %s", SUPERVISOR_URL, e)
        raise HTTPException(
            status_code=503,
            detail=f"Cannot reach SupervisorAgent at {SUPERVISOR_URL}. Is the service running?",
        )
    except Exception as e:
        logger.error("[chat] Unexpected error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """
    SSE streaming — SupervisorAgent returns response, backend streams word-by-word.

    Events:
      event: chunk  → {"content": "..."}
      event: done   → {"agent_id": "...", "intent": "...", "skills_used": [...]}
      event: error  → {"error": "..."}
    """
    async def event_generator() -> AsyncIterator[dict[str, Any]]:
        client = _get_client()
        user_id = user.get("user_id", "")

        try:
            payload = {
                "message": request.message,
                "conversation_id": request.conversation_id,
                "user_id": user_id,
                "language": request.language,
                "metadata": request.metadata,
            }

            resp = await client.post(
                f"{SUPERVISOR_URL}/engine/route",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

            text = data.get("response", "")
            words = text.split()

            for i, word in enumerate(words):
                chunk = " ".join(words[: i + 1])
                yield {
                    "event": "chunk",
                    "data": json.dumps({"event": "chunk", "content": chunk}),
                }
                await asyncio.sleep(0.02)

            yield {
                "event": "done",
                "data": json.dumps({
                    "event": "done",
                    "agent_id": data.get("agent_id", ""),
                    "intent": data.get("intent", ""),
                    "skills_used": data.get("skills_used", []),
                    "crisis_detected": data.get("crisis_detected", False),
                }),
            }

        except httpx.HTTPStatusError as e:
            logger.error("[chat_stream] HTTP error: %s", e)
            yield {"event": "error", "data": json.dumps({"error": f"HTTP {e.response.status_code}"})}
        except httpx.TransportError as e:
            logger.error("[chat_stream] Transport error: %s", e)
            yield {"event": "error", "data": json.dumps({"error": f"Cannot reach SupervisorAgent: {e}"})}
        except Exception as e:
            logger.error("[chat_stream] Unexpected: %s", e)
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Health / Supervision ─────────────────────────────────────────────────────

@router.get("/supervisor/health")
async def supervisor_health() -> dict[str, Any]:
    """Check if SupervisorAgent is reachable."""
    client = _get_client()
    try:
        resp = await client.get(f"{SUPERVISOR_URL}/health", timeout=5.0)
        return {"supervisor": "ok", "status": resp.status_code, "data": resp.json()}
    except Exception as e:
        return {"supervisor": "unreachable", "error": str(e)}
