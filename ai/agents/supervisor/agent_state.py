"""
SupervisorAgent state — intent classification result + routing decision.
"""

from __future__ import annotations

from typing import Optional, TypedDict


class IntentClassificationResult(TypedDict, total=False):
    """Result from intent classification skill."""

    intent: str  # "diagnostic" | "theory" | "treatment" | "support" | "crisis"
    confidence: float  # 0.0 – 1.0
    reasoning: str  # Why this intent was chosen
    has_crisis_keywords: bool  # True if crisis gate triggered
    language: str  # "vi" | "en"


class PreliminaryContext(TypedDict, total=False):
    """Context extracted before routing — preliminary slots."""

    language: str
    has_crisis_keywords: bool
    crisis_keywords_found: list[str]
    preliminary_slots: dict[str, str | int | float | None]


class RoutingDecision(TypedDict):
    """Final routing decision made by SupervisorAgent."""

    target_agent: str  # Which agent to dispatch to
    intent: str  # Confirmed intent
    confidence: float
    context: PreliminaryContext
    translated_message: str  # Message in canonical language (vi)


class SupervisorState(TypedDict, total=False):
    """Full SupervisorAgent state for a single turn."""

    original_message: str
    intent_result: IntentClassificationResult
    preliminary_context: PreliminaryContext
    routing_decision: RoutingDecision
    error: Optional[str]
