"""
SupervisorAgent routing logic — maps intent → domain agent.
"""
from __future__ import annotations

import logging
from typing import Optional

from ai.shared.agent_based.constants import (
    AgentID,
    INTENT_TO_AGENT,
    CRISIS_KEYWORDS,
)
from .agent_state import (
    IntentClassificationResult,
    RoutingDecision,
    SupervisorState,
)

logger = logging.getLogger(__name__)


import unicodedata
import re


def _remove_diacritics(text: str) -> str:
    """Remove Vietnamese diacritics for fuzzy matching."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _normalize_text(text: str) -> list[str]:
    """
    Split text into words, normalize each word (lowercase + no diacritics).
    Example: "Tôi muốn TỰ TỬ" -> ["toi", "muon", "tu", "tu"]
    """
    words = re.findall(r"\w+", text.lower())
    return [_remove_diacritics(w) for w in words]


def check_crisis_gate(message: str) -> tuple[bool, list[str]]:
    """
    O(1) keyword match for crisis safety gate.
    Handles Vietnamese diacritics via word-level fuzzy matching.

    Returns
    -------
    (has_crisis, matched_keywords)
    """
    msg_words = _normalize_text(message)
    matched = []

    for kw in CRISIS_KEYWORDS:
        kw_words = _normalize_text(kw)
        # All words in keyword must be present in message
        if all(kw_w in msg_words for kw_w in kw_words):
            matched.append(kw)

    return len(matched) > 0, matched


def classify_intent(message: str, language: str = "vi") -> IntentClassificationResult:
    """
    Intent classification — returns top intent + confidence + reasoning.

    This is a placeholder. Replace with actual LLM call in implementation.
    The real implementation should call IntentClassification skill.
    """
    # TODO: Replace with LLM-based classification skill
    lower = message.lower()

    # Simple keyword-based fallback (replace with skill)
    if any(kw in lower for kw in ["bệnh", "triệu chứng", "chẩn đoán", "mắc gì", "có phải", "disease", "symptom", "diagnostic"]):
        intent = "diagnostic"
    elif any(kw in lower for kw in ["điều trị", "thuốc", "liệu pháp", "uống", "treatment", "therapy", "medication"]):
        intent = "treatment"
    elif any(kw in lower for kw in ["tại sao", "vì sao", "giải thích", "là gì", "what is", "why", "theory", "psychology"]):
        intent = "theory"
    elif any(kw in lower for kw in ["buồn", "stress", "lo âu", "sợ", "khó chịu", "sad", "anxious", "stressed", "help", "cần", "cần giúp"]):
        intent = "support"
    else:
        intent = "support"  # fallback

    has_crisis, _ = check_crisis_gate(message)

    return IntentClassificationResult(
        intent="crisis" if has_crisis else intent,
        confidence=0.8,
        reasoning=f"Keyword-based classification: {intent}",
        has_crisis_keywords=has_crisis,
        language=language,
    )


def route_intent(intent_result: IntentClassificationResult) -> str:
    """
    Map classified intent to target agent ID.

    Returns agent ID string from INTENT_TO_AGENT mapping.
    """
    intent = intent_result["intent"]
    agent = INTENT_TO_AGENT.get(intent, AgentID.SUPPORT)
    logger.debug(f"[Router] intent={intent} -> agent={agent}")
    return agent


def make_routing_decision(
    message: str,
    language: str,
) -> RoutingDecision:
    """
    Full routing pipeline: crisis gate -> intent classify -> route.

    Returns a RoutingDecision dict ready to pass to the domain agent.
    """
    # 1. Crisis safety gate
    has_crisis, matched_keywords = check_crisis_gate(message)
    if has_crisis:
        logger.warning(f"[Router] CRISIS GATE triggered: {matched_keywords}")
        return RoutingDecision(
            target_agent=AgentID.CRISIS,
            intent="crisis",
            confidence=1.0,
            context={
                "language": language,
                "has_crisis_keywords": True,
                "crisis_keywords_found": matched_keywords,
                "preliminary_slots": {},
            },
            translated_message=message,
        )

    # 2. Intent classification
    intent_result = classify_intent(message, language)

    # 3. Route
    target = route_intent(intent_result)

    return RoutingDecision(
        target_agent=target,
        intent=intent_result["intent"],
        confidence=intent_result["confidence"],
        context={
            "language": language,
            "has_crisis_keywords": intent_result["has_crisis_keywords"],
            "crisis_keywords_found": [],
            "preliminary_slots": {},
        },
        translated_message=message,
    )
