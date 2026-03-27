"""
Supervisor Agent — Pydantic schemas for HTTP API.
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class SupervisorRequest(BaseModel):
    """Incoming routing request from backend."""
    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: str
    user_id: str
    language: str = "vi"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SupervisorResponse(BaseModel):
    """Response after supervisor routes and orchestrates agents."""
    response: str
    agent_id: str
    intent: str
    language: str
    skills_used: list[str] = Field(default_factory=list)
    crisis_detected: bool = False
    conversation_id: str
    turn: int = 0


class HealthResponse(BaseModel):
    status: str = "ok"
    agent: str = "supervisor"
    port: int = 8001
