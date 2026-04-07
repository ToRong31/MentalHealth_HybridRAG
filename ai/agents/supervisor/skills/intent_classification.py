"""
IntentClassification skill — classifies user message into one of 5 intents.
Uses keyword heuristics + LLM as fallback.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from ai.agents.supervisor.agent_state import IntentClassificationResult
from ai.shared.agent_based.constants import Intent

logger = logging.getLogger(__name__)

# Keyword maps for fast heuristic classification
_INTENT_KEYWORDS: dict[str, list[str]] = {
    Intent.DIAGNOSTIC: [
        # Vietnamese
        "bệnh", "triệu chứng", "chẩn đoán", "mắc gì", "có phải bệnh",
        "cảm thấy", "đau", "khó chịu", "rối loạn", "biểu hiện",
        # English
        "disease", "symptom", "diagnostic", "disorder", "condition",
        "am i", "do i have", "what's wrong with me",
    ],
    Intent.TREATMENT: [
        # Vietnamese
        "điều trị", "thuốc", "uống thuốc", "liệu pháp", "chữa trị",
        "biện pháp", "cách chữa", "tôi nên làm gì", "phác đồ",
        # English
        "treatment", "therapy", "medication", "medicine", "how to treat",
        "cure", "prescription", "should i take",
    ],
    Intent.THEORY: [
        # Vietnamese
        "tại sao", "vì sao", "giải thích", "là gì", "nghĩa là gì",
        "tâm lý", "cơ chế", "nguyên nhân", "tại sao lại", "học thuyết",
        # English
        "why", "what is", "how does", "explain", "theory", "psychology",
        "mechanism", "cause", "reason",
    ],
    Intent.SUPPORT: [
        # Vietnamese
        "buồn", "stress", "lo âu", "sợ", "khó chịu", "mệt mỏi",
        "cần giúp", "cần ai đó", "tôi không ổn", "giã tôi",
        "đau lòng", "thất vọng", "cô đơn", "bế tắc",
        # English
        "sad", "anxious", "stressed", "depressed", "lonely",
        "hopeless", "overwhelmed", "i need help", "i'm not okay",
    ],
}


def _score_intent(message: str, intent: str) -> float:
    """Count keyword matches for an intent. Returns score 0.0–1.0."""
    lower = message.lower()
    keywords = _INTENT_KEYWORDS.get(intent, [])
    matches = sum(1 for kw in keywords if kw in lower)
    return min(matches / 3.0, 1.0)  # Normalize: 3+ matches = 1.0


class IntentClassification:
    """
    Classifies user intent using keyword scoring + LLM fallback.

    Intents: diagnostic | theory | treatment | support | crisis
    """

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def classify(self, message: str, language: str = "vi") -> IntentClassificationResult:
        """
        Classify message intent.

        Pipeline:
        1. Fast keyword scoring
        2. If tied or unclear → LLM fallback (if llm provided)
        3. Always check crisis keywords separately
        """
        from ai.agents.supervisor.router import check_crisis_gate

        # Crisis gate first
        has_crisis, crisis_keywords = check_crisis_gate(message)
        if has_crisis:
            return IntentClassificationResult(
                intent=Intent.CRISIS,
                confidence=1.0,
                reasoning=f"Crisis keyword detected: {crisis_keywords}",
                has_crisis_keywords=True,
                language=language,
            )

        # Keyword scoring
        scores = {
            intent: _score_intent(message, intent)
            for intent in [Intent.DIAGNOSTIC, Intent.TREATMENT, Intent.THEORY, Intent.SUPPORT]
        }

        # Pick highest score
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        # If no keywords matched → default to support
        if best_score == 0.0:
            return IntentClassificationResult(
                intent=Intent.SUPPORT,
                confidence=0.5,
                reasoning="No intent keywords detected — defaulting to support",
                has_crisis_keywords=False,
                language=language,
            )

        # LLM refinement if available and score is medium
        if self._llm is not None and best_score < 0.8:
            refined = await self._llm_refine(message, best_intent, scores)
            if refined:
                return refined

        reasoning = (
            "Keyword scoring: "
            + ", ".join(f"{k}={v:.2f}" for k, v in scores.items())
            + f" → {best_intent}"
        )

        return IntentClassificationResult(
            intent=best_intent,
            confidence=best_score,
            reasoning=reasoning,
            has_crisis_keywords=has_crisis,
            language=language,
        )

    async def _llm_refine(
        self,
        message: str,
        best_intent: str,
        scores: dict[str, float],
    ) -> Optional[IntentClassificationResult]:
        """Optional LLM fallback for ambiguous cases."""
        if self._llm is None:
            return None

        prompt = f"""Classify this mental health message into ONE of these intents:
- diagnostic: user wants to understand their symptoms or possible disorder
- theory: user asks for psychological knowledge/explanation
- treatment: user asks about treatment options
- support: user needs emotional/coping support

Message: {message}

Respond with only the intent name."""

        try:
            response = await self._llm.generate(prompt)
            response = response.strip().lower()

            for intent in [Intent.DIAGNOSTIC, Intent.THEORY, Intent.TREATMENT, Intent.SUPPORT]:
                if intent in response:
                    return IntentClassificationResult(
                        intent=intent,
                        confidence=0.85,
                        reasoning=f"LLM refinement: keyword={best_intent}, llm={intent}",
                        has_crisis_keywords=False,
                        language="auto",
                    )
        except Exception as e:
            logger.warning(f"[IntentClassification] LLM refine failed: {e}")

        return None
