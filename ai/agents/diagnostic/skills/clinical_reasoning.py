"""
ClinicalReasoning skill — score symptom match, generate diagnostic conclusion.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ClinicalReasoning:
    """
    Apply clinical reasoning rules to diagnose based on slots + candidate disorders.
    """

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def reason(
        self,
        slots: dict[str, Any],
        candidates: list[dict[str, Any]],
        context: str = "",
    ) -> dict[str, Any]:
        """
        Generate clinical reasoning and diagnostic conclusion.

        Parameters
        ----------
        slots : dict
            Accumulated diagnostic slots.
        candidates : list[dict]
            Ranked disorder candidates from DiagnosticRetrieval.
        context : str
            Full conversation context.

        Returns
        -------
        {
            "diagnosis": str | None,
            "confidence": float (0-1),
            "reasoning": str,
            "missing_criteria": list[str],
            "differential": list[str],
            "recommendation": str,
        }
        """
        if not candidates:
            return self._no_candidates_result(slots)

        top = candidates[0]
        top_score = top["score"]

        # Score-based confidence
        if top_score >= 4:
            confidence = 0.85
        elif top_score >= 3:
            confidence = 0.70
        elif top_score >= 2:
            confidence = 0.55
        else:
            confidence = 0.40

        # Check must-have criteria
        must_have = top.get("must_have", [])
        emotion = slots.get("emotion", "")
        matched_must = [c for c in must_have if c in emotion.lower()]

        if must_have and not matched_must:
            confidence *= 0.7  # Penalty for missing must-have

        # Check slot sufficiency
        filled_count = sum(1 for v in slots.values() if v is not None and v != "")
        if filled_count < 4:
            confidence *= 0.8  # Penalty for insufficient data

        # Build reasoning
        reasoning_parts = [
            f"Candidate: {top['disorder_vi']} ({top['disorder']})",
            f"Match score: {top_score}",
            f"Filled slots ({filled_count}): {list(slots.keys())}",
        ]
        if matched_must:
            reasoning_parts.append(f"Must-have criteria matched: {matched_must}")
        if must_have and not matched_must:
            reasoning_parts.append(f"⚠️ Missing must-have: {[c for c in must_have if c not in matched_must]}")

        reasoning = "\n".join(reasoning_parts)

        # Missing criteria
        missing = [c for c in top.get("criteria", [])[:3]]  # Top 3 criteria to check

        # Differential (next best candidates)
        differential = [
            {"disorder": c["disorder"], "disorder_vi": c["disorder_vi"], "score": c["score"]}
            for c in candidates[1:3]
        ]

        # Recommendation
        if confidence >= 0.7:
            recommendation = (
                "Các triệu chứng của bạn có đặc điểm phù hợp với rối loạn này. "
                "**Khuyến nghị:** Gặp bác sĩ tâm thần để được chuẩn đoán chính xác."
            )
        elif confidence >= 0.5:
            recommendation = (
                "Có một số đặc điểm liên quan nhưng chưa đủ để chuẩn đoán. "
                "**Khuyến nghị:** Theo dõi thêm và tìm kiếm ý kiến chuyên gia."
            )
        else:
            recommendation = (
                "Chưa đủ thông tin để đưa ra chuẩn đoán. "
                "**Khuyến nghị:** Chia sẻ thêm về triệu chứng của bạn để mình hỗ trợ tốt hơn."
            )

        # LLM refinement
        if self._llm and confidence >= 0.5:
            try:
                prompt = (
                    f"Based on these diagnostic slots and candidate disorder, "
                    f"provide a brief clinical reasoning in Vietnamese.\n"
                    f"Slots: {slots}\n"
                    f"Disorder: {top['disorder_vi']}\n"
                    f"Confidence: {confidence:.0%}\n"
                    f"Write 2-3 sentences max."
                )
                llm_reasoning = (await self._llm.generate(prompt)).strip()
                if llm_reasoning:
                    reasoning = llm_reasoning
            except Exception as e:
                logger.warning(f"[ClinicalReasoning] LLM failed: {e}")

        return {
            "diagnosis": top["disorder_vi"],
            "disorder_en": top["disorder"],
            "confidence": confidence,
            "reasoning": reasoning,
            "missing_criteria": missing,
            "differential": differential,
            "recommendation": recommendation,
            "score": top_score,
        }

    def _no_candidates_result(self, slots: dict) -> dict[str, Any]:
        filled = sum(1 for v in slots.values() if v)
        return {
            "diagnosis": None,
            "confidence": 0.0,
            "reasoning": f"No matching disorder found. Filled slots: {filled}/8",
            "missing_criteria": [],
            "differential": [],
            "recommendation": (
                "Mình chưa tìm được rối loạn phù hợp với thông tin hiện tại. "
                "Bạn có thể chia sẻ thêm về triệu chứng, thời gian kéo dài, và ảnh hưởng đến cuộc sống không?"
            ),
            "score": 0,
        }
