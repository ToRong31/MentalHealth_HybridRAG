"""
Chat endpoints — synchronous + SSE streaming.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from .schemas import ChatRequest, ChatResponse, ErrorResponse, StreamEvent
from backend.src.core.deps import get_ai_engine, get_current_user, get_db

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Synchronous chat ────────────────────────────────────────────────────────────


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={500: {"model": ErrorResponse}},
)
async def chat_endpoint(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
    engine: Any = Depends(get_ai_engine),
) -> ChatResponse:
    """
    Process a single user message and return the agent's response.

    Pipeline:
      1. SupervisorAgent.route() — intent + crisis gate
      2. Dispatch to domain agent
      3. Return response

    Auth: Bearer JWT required.
    """
    try:
        result = await engine.process_message(
            message=request.message,
            conversation_id=request.conversation_id,
            user_id=user["user_id"],
            language=request.language,
        )

        return ChatResponse(
            response=result.get("response", ""),
            agent_id=str(result.get("agent_id", "unknown")),
            intent=str(result.get("intent", "unknown")),
            language=request.language,
            skills_used=result.get("skills_used", []),
            crisis_detected=result.get("crisis_detected", False),
            conversation_id=request.conversation_id,
            turn=_get_turn(request.conversation_id),
        )

    except Exception as e:
        logger.error(f"[chat_endpoint] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


# ── SSE Streaming chat ──────────────────────────────────────────────────────────


@router.post("/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
    engine: Any = Depends(get_ai_engine),
) -> StreamingResponse:
    """
    SSE streaming endpoint — streams agent response chunks.

    The AI engine processes the message and yields SSE events:
      event: chunk   → {"content": "..."}
      event: done    → {"agent_id": "...", "intent": "...", "skills_used": [...]}
      event: error   → {"error": "..."}
    """
    async def event_generator() -> AsyncIterator[dict[str, Any]]:
        try:
            # Run the full pipeline
            result = await engine.process_message(
                message=request.message,
                conversation_id=request.conversation_id,
                user_id=user["user_id"],
                language=request.language,
            )

            response_text = result.get("response", "")

            # Stream words/chunks
            words = response_text.split()
            for i, word in enumerate(words):
                chunk = " ".join(words[: i + 1])
                yield {
                    "event": "chunk",
                    "data": json.dumps(
                        StreamEvent(
                            event="chunk",
                            content=chunk,
                        ).model_dump(exclude_none=True)
                    ),
                }
                await asyncio.sleep(0.02)  # ~50 words/sec

            # Final done event
            yield {
                "event": "done",
                "data": json.dumps(
                    StreamEvent(
                        event="done",
                        agent_id=str(result.get("agent_id", "")),
                        intent=str(result.get("intent", "")),
                        skills_used=result.get("skills_used", []),
                        crisis_detected=result.get("crisis_detected", False),
                    ).model_dump(exclude_none=True)
                ),
            }

        except Exception as e:
            logger.error(f"[chat_stream] Error: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Conversation history ────────────────────────────────────────────────────────


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    """
    Get conversation message history from memory.

    Returns buffer + summary from MemoryService.
    """
    # TODO: implement with actual DB + MemoryService
    return {
        "conversation_id": conversation_id,
        "messages": [],
        "summary": "",
        "slots": {},
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

_turn_counter: dict[str, int] = {}


def _get_turn(conversation_id: str) -> int:
    """Increment and return turn number for a conversation."""
    count = _turn_counter.get(conversation_id, 0) + 1
    _turn_counter[conversation_id] = count
    return count
