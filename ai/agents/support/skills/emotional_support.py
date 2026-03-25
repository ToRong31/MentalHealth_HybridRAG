"""
EmotionalSupport skill — generates empathetic, validating responses.
"""
from __future__ import annotations

import logging
from typing import Any

from ai.shared.prompts import load_prompt

logger = logging.getLogger(__name__)


_EMOTION_RESPONSES: dict[str, str] = {
    "buồn": "Mình hiểu bạn đang cảm thấy buồn. Điều đó hoàn toàn bình thường khi chúng ta trải qua những lúc khó khăn. Cảm xúc buồn không phải là điều gì đáng xấu hổ.",
    "stress": "Bạn đang chịu nhiều áp lực, và điều đó có thể khiến bạn cảm thấy quá tải. Hãy nhớ rằng bạn có thể tạm dừng và hít thở.",
    "lo âu": "Mình hiểu bạn đang lo lắng về điều gì đó. Lo âu có thể rất mệt mỏi. Điều bạn đang làm là đã rất dũng cảm khi chia sẻ điều này.",
    "cô đơn": "Cảm giác cô đơn thực sự rất đau. Bạn không đơn độc — có những người quan tâm đến bạn, dù bạn có thể không cảm nhận được ngay lúc này.",
    "bế tắc": "Khi mọi thứ dường như không có lối thoát, cảm giác đó rất nặng nề. Nhưng ngay cả trong bế tắc, thường vẫn có những bước nhỏ có thể thử.",
}


class EmotionalSupport:
    """Generate validating, empathetic responses based on detected emotion."""

    SYSTEM_PROMPT = load_prompt("support.skills.emotional_support")

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def execute(
        self,
        context: str,
        gs: Any,
        emotion_hint: str | None = None,
    ) -> str:
        """
        Return an empathetic validation response.
        """
        # Get emotion from slot
        emotion = emotion_hint or ""
        emotion_lower = emotion.lower()

        # Find matching emotion response
        response = ""
        for key, val in _EMOTION_RESPONSES.items():
            if key in emotion_lower:
                response = val
                break

        # LLM enhancement
        if not response and self._llm:
            prompt = f"""Bạn là một người bạn đồng hành tâm lý, EMPATHETIC và VALIDATING.
Không đưa ra lời khuyên. Không phân tích. Chỉ validate cảm xúc.

User đang chia sẻ: {context[:300]}

Viết 1-2 câu empathetic response bằng tiếng Việt:"""
            try:
                response = (await self._llm.generate(prompt)).strip()
            except Exception as e:
                logger.warning(f"[EmotionalSupport] LLM failed: {e}")

        if not response:
            response = "Mình hiểu bạn đang trải qua điều gì đó khó khăn. Cảm ơn bạn đã chia sẻ với mình. Bạn muốn nói thêm về điều này không?"

        return response
