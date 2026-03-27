"""
Support Agent — Pydantic schemas for HTTP API.
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class SupportRequest(BaseModel):
    """Request for emotional support and coping strategies."""
    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: str
    user_id: str
    language: str = "vi"
    context: str = Field(default="")
    metadata: dict[str, Any] = Field(default_factory=dict)


class SupportResponse(BaseModel):
    """Support agent response."""
    response: str
    agent_id: str = "support"
    intent: str = "support"
    language: str
    skills_used: list[str] = Field(default_factory=list)
    crisis_detected: bool = False
    conversation_id: str
    coping_strategies: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
    agent: str = "support"
    port: int = 8104
