"""
Event emitter with LangSmith integration.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentEvent:
    """Structured event emitted by agents during execution."""

    event_type: str
    agent_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "error": self.error,
            **self.data,
            **self.metadata,
        }


# LangSmith integration
_LANGSMITH_ENABLED: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
_LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "mental-health-hybrid-rag")
_LANGSMITH_API_KEY: Optional[str] = os.getenv("LANGSMITH_API_KEY")


def _should_trace() -> bool:
    return _LANGSMITH_ENABLED and _LANGSMITH_API_KEY is not None


class EventEmitter:
    """
    Emits structured events with optional LangSmith tracing.

    Usage:
        emitter = EventEmitter()
        with emitter.span("symptom_extraction", agent_id="diagnostic") as span:
            result = await extract(...)
            span.set_data("slots_extracted", len(result))
    """

    def __init__(self, enable_langsmith: bool = True):
        self.enable_langsmith = enable_langsmith and _should_trace()
        self._subscribers: list[Callable[[AgentEvent], None]] = []

        if self.enable_langsmith:
            try:
                from langsmith.run_helpers import traceable

                self._traceable = traceable
                logger.info(
                    f"[EventEmitter] LangSmith enabled (project={_LANGSMITH_PROJECT})"
                )
            except ImportError:
                logger.warning("[EventEmitter] langsmith not installed")
                self.enable_langsmith = False

    def span(
        self,
        name: str,
        agent_id: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Span:
        return Span(
            name=name,
            agent_id=agent_id,
            metadata=metadata or {},
            emitter=self,
        )

    def emit(
        self,
        event_type: str,
        agent_id: str,
        data: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        event = AgentEvent(
            event_type=event_type,
            agent_id=agent_id,
            data=data or {},
            metadata=metadata or {},
        )
        self._notify(event)

    def emit_agent_started(self, agent_id: str, input_summary: str = "") -> None:
        self.emit("agent_started", agent_id, {"input_summary": input_summary})

    def emit_agent_finished(
        self,
        agent_id: str,
        output_summary: str = "",
        duration_ms: Optional[float] = None,
    ) -> None:
        self.emit(
            "agent_finished",
            agent_id,
            {
                "output_summary": output_summary,
                "duration_ms": duration_ms,
            },
        )

    def emit_agent_error(
        self,
        agent_id: str,
        error: str,
        duration_ms: Optional[float] = None,
    ) -> None:
        self.emit("agent_error", agent_id, {"error": error, "duration_ms": duration_ms})

    def emit_tool_called(
        self,
        agent_id: str,
        tool_name: str,
        params: Optional[dict[str, Any]] = None,
    ) -> None:
        self.emit("tool_called", agent_id, {"tool_name": tool_name, "params": params})

    def emit_crisis_detected(
        self,
        agent_id: str,
        crisis_level: str,
        indicators: list[str],
    ) -> None:
        self.emit(
            "crisis_detected",
            agent_id,
            {
                "crisis_level": crisis_level,
                "indicators": indicators,
            },
        )

    def emit_routing_decided(
        self,
        agent_id: str,
        intent: str,
        target_agent: str,
    ) -> None:
        self.emit(
            "routing_decided",
            agent_id,
            {
                "intent": intent,
                "target_agent": target_agent,
            },
        )

    def emit_retrieval_completed(
        self,
        agent_id: str,
        collection: str,
        result_count: int,
        duration_ms: Optional[float] = None,
    ) -> None:
        self.emit(
            "retrieval_completed",
            agent_id,
            {
                "collection": collection,
                "result_count": result_count,
                "duration_ms": duration_ms,
            },
        )

    def subscribe(self, callback: Callable[[AgentEvent], None]) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[AgentEvent], None]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def _notify(self, event: AgentEvent) -> None:
        logger.debug(
            f"[Event] {event.agent_id}:{event.event_type} "
            f"({event.duration_ms}ms) error={event.error}"
        )
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"[EventEmitter] Subscriber error: {e}")


class Span:
    """
    Context manager for timing a block of code and emitting events.

    Usage:
        with emitter.span("symptom_extraction", agent_id="diagnostic") as span:
            result = await extract(...)
            span.set_data("slots_extracted", len(result))
    """

    def __init__(
        self,
        name: str,
        agent_id: str,
        metadata: dict[str, Any],
        emitter: EventEmitter,
    ):
        self.name = name
        self.agent_id = agent_id
        self.metadata = metadata
        self.emitter = emitter
        self._start_time: float = 0.0
        self._data: dict[str, Any] = {}
        self._error: Optional[str] = None

    def set_data(self, key: str, value: Any) -> None:
        self._data[key] = value

    def set_error(self, error: str) -> None:
        self._error = error

    def __enter__(self) -> Span:
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration_ms = (time.perf_counter() - self._start_time) * 1000
        if exc_type is not None:
            self._error = str(exc_val)
            self.emitter.emit_agent_error(
                self.agent_id, self._error or "unknown", duration_ms
            )
        else:
            self.emitter.emit(
                self.name,
                self.agent_id,
                data={**self.metadata, **self._data, "duration_ms": duration_ms},
            )


emitter = EventEmitter()
