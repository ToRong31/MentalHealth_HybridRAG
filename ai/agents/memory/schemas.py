"""
Memory Agent — Pydantic schemas for HTTP API.
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class BufferRequest(BaseModel):
    """Save a message to the conversation buffer."""
    conversation_id: str
    role: str = Field(..., description="user | assistant")
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextRequest(BaseModel):
    """Get accumulated context for a conversation."""
    conversation_id: str
    max_turns: int = Field(default=5, ge=1, le=20)


class SlotsRequest(BaseModel):
    """Merge or get accumulated slots (user profile/treatment data)."""
    conversation_id: str
    new_slots: Optional[dict[str, Any]] = None


class CrisisStateRequest(BaseModel):
    """Get or update crisis state for a conversation."""
    conversation_id: str
    state: Optional[dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    agent: str = "memory"
    port: int = 8002


class BufferResponse(BaseModel):
    saved: bool = True
    conversation_id: str


class ContextResponse(BaseModel):
    conversation_id: str
    context: str


class SlotsResponse(BaseModel):
    conversation_id: str
    slots: dict[str, Any]


class CrisisStateResponse(BaseModel):
    conversation_id: str
    state: dict[str, Any]
