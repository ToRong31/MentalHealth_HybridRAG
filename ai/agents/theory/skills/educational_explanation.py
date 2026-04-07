"""
EducationalExplanation skill — generates clear, educational explanations.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class EducationalExplanation:
    """Generate educational explanations for psychological concepts."""

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def explain(
        self,
        concept: dict[str, Any],
        question: str,
        language: str = "vi",
    ) -> str:
        """
        Generate a clear, educational explanation of a concept.

        Parameters
        ----------
        concept : dict
            Retrieved concept from ConceptRetrieval.
        question : str
            User's original question.
        language : str
            Output language.
        """
        parts = []

        # Title
        name = concept.get("name", "")
        parts.append(f"## {name}\n")

        # Definition
        definition = concept.get("definition", "")
        if definition:
            parts.append(f"**Định nghĩa:** {definition}\n")

        # Key figures
        if "key_figures" in concept:
            figures = ", ".join(concept["key_figures"])
            parts.append(f"**Nhân vật chính:** {figures}\n")

        # Symptoms / Concepts / Mechanisms
        for section_key in ["symptoms", "concepts", "mechanisms", "stages", "theories"]:
            if section_key in concept:
                items = concept[section_key]
                if isinstance(items, list) and items:
                    items_text = "\n".join(f"- {item}" for item in items)
                    label = section_key.replace("_", " ").title()
                    parts.append(f"**{label}:**\n{items_text}\n")

        explanation = "\n".join(parts)

        # LLM polish
        if self._llm and language == "vi":
            try:
                prompt = f"""Viết lại đoạn giải thích tâm lý sau đây cho dễ hiểu hơn với người không chuyên.
Giữ thông tin khoa học chính xác. Dùng ngôn ngữ đơn giản, thân thiện.
Trả lời bằng tiếng Việt.

Câu hỏi gốc: {question}
---
{explanation}"""
                polished = (await self._llm.generate(prompt)).strip()
                if polished and len(polished) > 50:
                    explanation = polished
            except Exception as e:
                logger.warning(f"[EducationalExplanation] LLM failed: {e}")

        return explanation

    async def explain_multiple(
        self,
        concepts: list[dict[str, Any]],
        question: str,
        language: str = "vi",
    ) -> str:
        """Explain multiple concepts, combining them coherently."""
        explanations = []
        for concept in concepts:
            exp = await self.explain(concept, question, language)
            explanations.append(exp)

        if len(explanations) > 1:
            combined = "\n\n---\n\n".join(explanations)
        else:
            combined = explanations[0] if explanations else ""

        # Add disclaimer
        disclaimer = (
            "\n\n---\n"
            "*Đây là kiến thức tâm lý học tổng quát, không phải chuẩn đoán y khoa. "
            "Nếu bạn có lo lắng về sức khỏe tâm thần, hãy tham khảo chuyên gia.*"
        )

        return combined + disclaimer
