"""
Custom exceptions for the multi-agent system.
"""
from __future__ import annotations


# =============================================================================
# Base Exception
# =============================================================================

class AgentError(Exception):
    """Base exception for all agent-related errors."""

    def __init__(self, message: str, agent_id: str = "", context: dict | None = None):
        super().__init__(message)
        self.agent_id = agent_id
        self.context = context or {}


# =============================================================================
# Execution Errors
# =============================================================================

class RetryableError(AgentError):
    """
    Error that can be retried.
    Raised when a transient failure occurs (network, timeout, rate limit).
    """

    def __init__(
        self,
        message: str,
        agent_id: str = "",
        retry_count: int = 0,
        max_retries: int = 3,
        context: dict | None = None,
    ):
        super().__init__(message, agent_id, context)
        self.retry_count = retry_count
        self.max_retries = max_retries

    @property
    def should_retry(self) -> bool:
        return self.retry_count < self.max_retries


class CircuitOpenError(AgentError):
    """Raised when a circuit breaker is in OPEN state."""

    def __init__(
        self,
        message: str = "Circuit breaker is open",
        agent_id: str = "",
        context: dict | None = None,
    ):
        super().__init__(message, agent_id, context)


class TimeoutError(AgentError):
    """Raised when an agent operation times out."""

    def __init__(
        self,
        message: str,
        agent_id: str = "",
        timeout_seconds: float = 60.0,
        context: dict | None = None,
    ):
        super().__init__(message, agent_id, context)
        self.timeout_seconds = timeout_seconds


# =============================================================================
# Crisis
# =============================================================================

class CrisisDetectedError(AgentError):
    """
    Raised when a crisis is detected in user message.
    This triggers immediate interrupt of all agents.
    """

    def __init__(
        self,
        message: str = "Crisis detected",
        agent_id: str = "",
        crisis_level: str = "high",
        indicators: list[str] | None = None,
        context: dict | None = None,
    ):
        super().__init__(message, agent_id, context)
        self.crisis_level = crisis_level
        self.indicators = indicators or []


# =============================================================================
# Communication
# =============================================================================

class MessageBusError(AgentError):
    """Raised when MessageBus operations fail."""

    def __init__(
        self,
        message: str,
        agent_id: str = "",
        operation: str = "",
        context: dict | None = None,
    ):
        super().__init__(message, agent_id, context)
        self.operation = operation


class AgentNotFoundError(MessageBusError):
    """Raised when trying to send to a non-existent agent."""

    def __init__(self, agent_id: str, operation: str = "send"):
        super().__init__(
            message=f"Agent not found: {agent_id}",
            operation=operation,
        )
        self.agent_id = agent_id


class QueueFullError(MessageBusError):
    """Raised when a message queue is full."""

    def __init__(self, agent_id: str, queue_size: int = 0):
        super().__init__(
            message=f"Queue full for agent: {agent_id}",
            operation="enqueue",
        )
        self.queue_size = queue_size


# =============================================================================
# Routing
# =============================================================================

class RoutingError(AgentError):
    """Raised when routing fails."""

    def __init__(
        self,
        message: str,
        agent_id: str = "",
        intent: str | None = None,
        context: dict | None = None,
    ):
        super().__init__(message, agent_id, context)
        self.intent = intent


class UnknownIntentError(RoutingError):
    """Raised when intent cannot be classified."""

    def __init__(self, message: str = "Unknown intent", intent: str | None = None):
        super().__init__(message, intent=intent)


# =============================================================================
# Memory
# =============================================================================

class MemoryError(AgentError):
    """Base exception for memory operations."""

    def __init__(
        self,
        message: str,
        agent_id: str = "",
        operation: str = "",
        context: dict | None = None,
    ):
        super().__init__(message, agent_id, context)
        self.operation = operation


class SlotError(AgentError):
    """Raised when slot operations fail."""

    def __init__(
        self,
        message: str,
        agent_id: str = "",
        slot_name: str | None = None,
        context: dict | None = None,
    ):
        super().__init__(message, agent_id, context)
        self.slot_name = slot_name


class SlotInsufficientError(SlotError):
    """Raised when not enough slots are collected for diagnostic."""

    def __init__(
        self,
        missing_slots: list[str],
        current_count: int = 0,
        required_count: int = 5,
    ):
        super().__init__(
            message=f"Insufficient slots: {current_count}/{required_count}. Missing: {missing_slots}",
        )
        self.missing_slots = missing_slots
        self.current_count = current_count
        self.required_count = required_count
