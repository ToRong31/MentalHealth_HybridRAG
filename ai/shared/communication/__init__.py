"""
Communication — HTTP client and schemas for inter-agent microservice communication.
"""

from .events import EventEmitter, AgentEvent, emitter
from .http_client import AgentHTTPClient
from .http_schemas import (
    AgentRequest,
    AgentResponse,
    RoutingDecision,
    RoutingRequest,
    RoutingResponse,
    HealthResponse,
)

__all__ = [
    # HTTP (microservice)
    "AgentHTTPClient",
    "AgentRequest",
    "AgentResponse",
    "RoutingDecision",
    "RoutingRequest",
    "RoutingResponse",
    "HealthResponse",
    # Events (still used for observability/logging)
    "EventEmitter",
    "AgentEvent",
    "emitter",
]
