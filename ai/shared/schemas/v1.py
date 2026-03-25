"""
Pydantic schemas for API v1 — request/response validation.
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


# ─── Request schemas ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Incoming chat message from user."""
    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: str = Field(..., description="UUID of the conversation")
    user_id: str = Field(..., description="UUID of the authenticated user")
    language: str = Field(default="vi", description="vi | en")
    metadata: dict[str, Any] = Field(default_factory=dict)


class StreamRequest(BaseModel):
    """SSE streaming chat request."""
    message: str = Field(..., min_length=1)
    conversation_id: str
    user_id: str
    language: str = "vi"


# ─── Response schemas ─────────────────────────────────────────────────────────

class MessageContent(BaseModel):
    """A single message in the conversation."""
    role: str  # "user" | "assistant"
    content: str
    timestamp: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from a single agent turn."""
    response: str = Field(..., description="The agent's response text")
    agent_id: str = Field(..., description="Which agent handled this")
    intent: str = Field(..., description="Detected intent")
    language: str
    skills_used: list[str] = Field(default_factory=list)
    crisis_detected: bool = False
    conversation_id: str
    turn: int = 0


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None
    agent_id: Optional[str] = None


# ─── Stream event schemas ─────────────────────────────────────────────────────

class StreamEvent(BaseModel):
    """Server-Sent Event payload for streaming."""
    event: str = Field(..., description="Event type: chunk | done | error")
    agent_id: Optional[str] = None
    content: Optional[str] = None
    intent: Optional[str] = None
    skills_used: list[str] = Field(default_factory=list)
    crisis_detected: bool = False
    error: Optional[str] = None
