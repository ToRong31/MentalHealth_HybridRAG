"""
Chat API schemas — request/response validation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat message from user."""

    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: str = Field(..., description="UUID of the conversation")
    language: str = Field(default="vi", description="vi | en")
    metadata: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Response from a single agent turn."""

    response: str
    agent_id: str
    intent: str
    language: str
    skills_used: list[str] = Field(default_factory=list)
    crisis_detected: bool = False
    conversation_id: str
    turn: int = 0


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: str | None = None


class StreamEvent(BaseModel):
    """SSE streaming event."""

    event: str = Field(..., description="chunk | done | error")
    agent_id: str | None = None
    content: str | None = None
    intent: str | None = None
    skills_used: list[str] = Field(default_factory=list)
    crisis_detected: bool = False
    error: str | None = None
