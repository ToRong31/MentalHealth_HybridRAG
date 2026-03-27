"""
Crisis Agent — Pydantic schemas for HTTP API.
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class CrisisRequest(BaseModel):
    """Request for crisis intervention."""
    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: str
    user_id: str
    language: str = "vi"
    context: str = Field(default="")
    severity: str = Field(default="unknown", description="low | medium | high | critical")
    metadata: dict[str, Any] = Field(default_factory=dict)


class CrisisResponse(BaseModel):
    """Crisis agent response."""
    response: str
    agent_id: str = "crisis"
    intent: str = "crisis"
    language: str
    skills_used: list[str] = Field(default_factory=list)
    crisis_detected: bool = True
    severity: str
    conversation_id: str
    resources_provided: list[str] = Field(default_factory=list)
    escalation_recommended: bool = False


class HealthResponse(BaseModel):
    status: str = "ok"
    agent: str = "crisis"
    port: int = 8105
