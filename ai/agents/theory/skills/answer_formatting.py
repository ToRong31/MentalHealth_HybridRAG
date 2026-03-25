"""
AnswerFormatting skill for TheoryAgent.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AnswerFormatting:
    """Format TheoryAgent's final response."""

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def format(
        self,
        explanation: str,
        concepts_used: list[str],
        language: str = "vi",
    ) -> dict[str, Any]:
        """
        Format the final theory explanation response.
        """
        sections = ["educational_explanation"]

        response = explanation

        # LLM final polish
        if self._llm and language == "vi":
            try:
                prompt = f"""Format lại đoạn giải thích tâm lý sau cho dễ đọc hơn.
Dùng markdown headers, bullet points.
Không thêm thông tin mới. Giữ chính xác khoa học.
Trả lời bằng tiếng Việt.

---
{explanation[:1500]}"""
                polished = (await self._llm.generate(prompt)).strip()
                if polished:
                    response = polished
            except Exception as e:
                logger.warning(f"[Theory AnswerFormatting] LLM failed: {e}")

        return {
            "response": response,
            "sections": sections,
            "concepts": concepts_used,
        }
