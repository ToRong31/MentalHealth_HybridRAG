"""
Theory Agent — Pydantic schemas for HTTP API.
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class TheoryRequest(BaseModel):
    """Request for psychological theory explanation."""
    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: str
    user_id: str
    language: str = "vi"
    context: str = Field(default="")
    metadata: dict[str, Any] = Field(default_factory=dict)


class TheoryResponse(BaseModel):
    """Theory agent response."""
    response: str
    agent_id: str = "theory"
    intent: str = "theory"
    language: str
    skills_used: list[str] = Field(default_factory=list)
    crisis_detected: bool = False
    conversation_id: str
    theories_mentioned: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
    agent: str = "theory"
    port: int = 8102
