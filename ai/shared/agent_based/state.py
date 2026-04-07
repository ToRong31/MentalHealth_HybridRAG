"""
AgentState — per-request private state for an agent instance.

Each agent call gets its own AgentState, isolated from other concurrent calls.
Replaces the unused `local_memory` in BaseAgent.
"""
from __future__ import annotations

from typing import Any
from dataclasses import dataclass, field


@dataclass
class AgentState:
    """
    Per-request private state for an agent.

    Each call to agent.run() receives a fresh AgentState instance.
    This is NOT shared across agents — only the agent that owns it can read/write.
    """
    # Conversation identity
    conversation_id: str = ""
    user_id: str = ""

    # Accumulated tool results (private to this agent)
    tool_results: dict[str, Any] = field(default_factory=dict)

    # LLM context built up during the call
    llm_context: list[dict[str, str]] = field(default_factory=list)

    # Slots collected by this agent
    collected_slots: dict[str, Any] = field(default_factory=dict)

    # Any domain-specific data
    extras: dict[str, Any] = field(default_factory=dict)

    # ── Tool result helpers ────────────────────────────────────────────────

    def add_tool_result(self, tool_name: str, result: Any) -> None:
        """Store a tool call result for later use by this agent."""
        self.tool_results[tool_name] = result

    def get_tool_result(self, tool_name: str) -> Any:
        """Retrieve a previously stored tool result."""
        return self.tool_results.get(tool_name)

    # ── LLM context helpers ────────────────────────────────────────────────

    def add_llm_turn(self, role: str, content: str) -> None:
        """Append a turn to the LLM conversation context."""
        self.llm_context.append({"role": role, "content": content})

    def get_llm_context(self) -> list[dict[str, str]]:
        """Return full LLM context for this agent call."""
        return list(self.llm_context)

    # ── Slot helpers ───────────────────────────────────────────────────────

    def collect_slot(self, key: str, value: Any) -> None:
        """Store a collected slot."""
        self.collected_slots[key] = value

    def get_slot(self, key: str) -> Any:
        """Retrieve a collected slot."""
        return self.collected_slots.get(key)

    # ── Extra helpers ──────────────────────────────────────────────────────

    def set_extra(self, key: str, value: Any) -> None:
        self.extras[key] = value

    def get_extra(self, key: str, default: Any = None) -> Any:
        return self.extras.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        """Export all state as dict (for debugging/logging)."""
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "tool_results": self.tool_results,
            "llm_context_size": len(self.llm_context),
            "collected_slots": self.collected_slots,
            "extras": self.extras,
        }


def create_agent_state(
    conversation_id: str = "",
    user_id: str = "",
) -> AgentState:
    """Factory — create a fresh per-request AgentState."""
    return AgentState(
        conversation_id=conversation_id,
        user_id=user_id,
    )


# ── GlobalState (shared across agents, per request) ─────────────────────────

from typing import Any, Literal, Optional, TypedDict


class GlobalState(TypedDict, total=False):
    """Shared state across all agents in a single request lifecycle."""

    # Conversation context
    conversation_id: str
    user_id: str
    language: Literal["vi", "en", "auto"]

    # User input
    original_message: str
    translated_message: str

    # Routing
    intent: Optional[str]
    target_agent: Optional[str]

    # Slots (DiagnosticAgent)
    accumulated_slots: dict[str, Any]
    missing_slots: list[str]
    slots_sufficient: bool

    # Crisis state
    is_high_risk: bool
    crisis_level: Optional[str]
    crisis_indicators: list[str]
    crisis_detected_at: Optional[str]

    # Memory
    conversation_buffer: list[dict[str, str]]
    summary_context: str

    # Retrieval results
    graph_context: str
    dense_context: str
    reranked_context: str

    # Agent outputs
    response: Optional[str]
    skills_used: list[str]

    # Diagnostic
    detected_disease: Optional[str]
    diagnostic_confidence: Optional[float]
    assessment_category: Optional[str]

    # Error
    error: Optional[str]

    # Streaming
    streaming_enabled: bool
    stream_chunk: Optional[str]


def create_initial_state(
    conversation_id: str,
    user_id: str,
    message: str,
    language: str = "auto",
) -> GlobalState:
    """Create a fresh GlobalState for a new user message."""
    from .constants import Language

    detected_lang = Language.detect(message) if message else "vi"

    return GlobalState(
        conversation_id=conversation_id,
        user_id=user_id,
        language=language if language != "auto" else detected_lang,
        original_message=message,
        translated_message=message,
        intent=None,
        target_agent=None,
        accumulated_slots={},
        missing_slots=[],
        slots_sufficient=False,
        is_high_risk=False,
        crisis_level=None,
        crisis_indicators=[],
        crisis_detected_at=None,
        conversation_buffer=[],
        summary_context="",
        graph_context="",
        dense_context="",
        reranked_context="",
        response=None,
        skills_used=[],
        detected_disease=None,
        diagnostic_confidence=None,
        assessment_category=None,
        error=None,
        streaming_enabled=False,
        stream_chunk=None,
    )
