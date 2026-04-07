"""
Shared Pydantic schemas for inter-agent HTTP communication.

All agent services use these schemas to talk to each other over HTTP.
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


# ─── Common ──────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Standard health check response for all agent services."""
    status: str = "ok"
    agent: str
    port: int


# ─── Request ─────────────────────────────────────────────────────────────────

class AgentRequest(BaseModel):
    """
    Unified request schema for all domain agents.

    Sent by: SupervisorAgent → DomainAgent
    """
    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: str
    user_id: str
    language: str = "vi"
    # Routing context from supervisor
    intent: str = "support"
    context: dict[str, Any] = Field(default_factory=dict)
    # Optional overrides
    metadata: dict[str, Any] = Field(default_factory=dict)
    # For domain-specific agents
    severity: Optional[str] = None
    # Crisis-specific
    crisis_detected: bool = False


# ─── Response ────────────────────────────────────────────────────────────────

class AgentResponse(BaseModel):
    """
    Unified response schema for all domain agents.

    Returned by: DomainAgent → SupervisorAgent / Backend
    """
    response: str = ""
    agent_id: str
    intent: str = "unknown"
    language: str = "vi"
    skills_used: list[str] = Field(default_factory=list)
    crisis_detected: bool = False
    conversation_id: str
    turn: int = 0
    # Domain-specific fields (optional, pass through)
    error: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─── Routing ─────────────────────────────────────────────────────────────────

class RoutingDecision(BaseModel):
    """
    Routing decision returned by SupervisorAgent.

    Sent by: SupervisorAgent → Backend / ChatService
    """
    target_agent: str
    intent: str
    confidence: float = 0.5
    context: dict[str, Any] = Field(default_factory=dict)
    language: str = "vi"
    crisis_detected: bool = False


class RoutingRequest(BaseModel):
    """Request for supervisor to classify and route a message."""
    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: str
    user_id: str
    language: str = "vi"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoutingResponse(BaseModel):
    """Response from supervisor routing endpoint."""
    target_agent: str
    intent: str
    confidence: float
    crisis_detected: bool = False
    context: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str
    language: str = "vi"
