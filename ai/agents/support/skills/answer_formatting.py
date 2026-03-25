"""
AnswerFormatting skill — combines skill outputs into final response.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AnswerFormatting:
    """Format final response combining all skill outputs."""

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def format(
        self,
        emotional_response: str,
        coping_strategies: list[dict[str, str]],
        exercises: list[dict[str, Any]],
        psychoeducation: str,
        language: str = "vi",
    ) -> dict[str, Any]:
        """
        Combine all skill outputs into a formatted response.

        Returns
        -------
        {"response": str, "sections": list[str]}
        """
        sections = []

        # 1. Emotional validation
        if emotional_response:
            sections.append(emotional_response)

        # 2. Psychoeducation (if provided)
        if psychoeducation:
            sections.append(psychoeducation)

        # 3. Coping strategies
        if coping_strategies:
            strategies_text = "**Một số cách bạn có thể thử:**\n"
            for i, s in enumerate(coping_strategies, 1):
                strategies_text += f"\n{i}. **{s.get('name', '')}**"
                strategies_text += f"\n   {s.get('description', '')}"
                if s.get('duration'):
                    strategies_text += f"\n   Thời gian: {s.get('duration')}"
            sections.append(strategies_text)

        # 4. Exercises
        if exercises:
            exercises_text = "**Bài tập thực hành:**\n"
            for i, ex in enumerate(exercises, 1):
                steps_text = "\n".join(
                    f"   {j+1}. {step}" for j, step in enumerate(ex.get("steps", []))
                )
                exercises_text += f"\n{i}. **{ex.get('name', '')}** ({ex.get('duration', '')})"
                exercises_text += f"\n{steps_text}"
                if ex.get("tip"):
                    exercises_text += f"\n   💡 {ex.get('tip')}"
            sections.append(exercises_text)

        # 5. Closing
        closing = (
            "Bạn không đơn độc trong hành trình này. "
            "Nếu những cảm xúc này kéo dài và ảnh hưởng đến cuộc sống hàng ngày, "
            "mình khuyên bạn nên tìm đến chuyên gia tâm lý để được hỗ trợ thêm nhé."
        )
        sections.append(closing)

        response = "\n\n".join(sections)

        # LLM polish if available
        if self._llm and language == "vi":
            try:
                prompt = f"""Polish this mental health support response to be more natural, warm, and concise.
Keep all medical/psychology information accurate. Don't add false information.
Keep Vietnamese language.

Response:
{response[:1000]}"""
                polished = (await self._llm.generate(prompt)).strip()
                if polished:
                    response = polished
            except Exception as e:
                logger.warning(f"[AnswerFormatting] LLM polish failed: {e}")

        return {
            "response": response,
            "sections": ["emotional_support", "psychoeducation", "coping", "exercises", "closing"],
        }
