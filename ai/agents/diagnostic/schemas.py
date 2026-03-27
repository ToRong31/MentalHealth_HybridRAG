"""
Diagnostic Agent — Pydantic schemas for HTTP API.
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class DiagnosticRequest(BaseModel):
    """Request for diagnostic analysis."""
    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: str
    user_id: str
    language: str = "vi"
    context: str = Field(default="", description="Previous conversation context")
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiagnosticResponse(BaseModel):
    """Diagnostic agent response."""
    response: str
    agent_id: str = "diagnostic"
    intent: str = "diagnostic"
    language: str
    skills_used: list[str] = Field(default_factory=list)
    crisis_detected: bool = False
    conversation_id: str
    symptoms_found: list[str] = Field(default_factory=list)
    preliminary_assessment: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    agent: str = "diagnostic"
    port: int = 8101
