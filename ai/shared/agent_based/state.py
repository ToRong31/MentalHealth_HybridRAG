"""
Global state schema for the multi-agent system.
"""
from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict

from .constants import Language


class GlobalState(TypedDict, total=False):
    """Shared state across all agents in a single request lifecycle."""

    # ── Conversation context ───────────────────────────────────────────────
    conversation_id: str
    user_id: str
    language: Literal["vi", "en", "auto"]

    # ── User input ───────────────────────────────────────────────────────
    original_message: str
    translated_message: str

    # ── Routing ───────────────────────────────────────────────────────────
    intent: Optional[str]
    target_agent: Optional[str]

    # ── Slots (DiagnosticAgent) ────────────────────────────────────────────
    accumulated_slots: dict[str, Any]
    missing_slots: list[str]
    slots_sufficient: bool

    # ── Crisis state ──────────────────────────────────────────────────────
    is_high_risk: bool
    crisis_level: Optional[str]
    crisis_indicators: list[str]
    crisis_detected_at: Optional[str]

    # ── Memory ────────────────────────────────────────────────────────────
    conversation_buffer: list[dict[str, str]]
    summary_context: str

    # ── Retrieval results ─────────────────────────────────────────────────
    graph_context: str
    dense_context: str
    reranked_context: str

    # ── Agent outputs ──────────────────────────────────────────────────────
    response: Optional[str]
    skills_used: list[str]

    # ── Diagnostic ───────────────────────────────────────────────────────
    detected_disease: Optional[str]
    diagnostic_confidence: Optional[float]
    assessment_category: Optional[str]

    # ── Error ─────────────────────────────────────────────────────────────
    error: Optional[str]

    # ── Streaming ─────────────────────────────────────────────────────────
    streaming_enabled: bool
    stream_chunk: Optional[str]


def create_initial_state(
    conversation_id: str,
    user_id: str,
    message: str,
    language: str = "auto",
) -> GlobalState:
    """Create a fresh GlobalState for a new user message."""
    detected_lang = Language.detect(message)

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
