"""
ImmediateResponse skill — generates immediate crisis response.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

IMMEDIATE_RESPONSES: dict[str, str] = {
    "critical": (
        "**Bạn ơi, mình rất lo lắng cho bạn.**\n\n"
        "Mình nghe bạn đang nghĩ đến những điều rất đau đớn. "
        "Điều đó có nghĩa là bạn đang chịu đựng rất nhiều.\n\n"
        "**Mình muốn bạn biết:** Bạn không đơn độc. Cảm xúc này không định nghĩa con người bạn.\n\n"
        "Trước tiên, bạn có thể **gọi ngay** đường dây hỗ trợ tâm thần không?"
    ),
    "high": (
        "**Mình rất quan tâm đến bạn và điều bạn đang trải qua.**\n\n"
        "Nghe có vẻ như bạn đang cảm thấy rất tuyệt vọng ngay lúc này. "
        "Mình muốn bạn biết rằng những cảm xúc này, dù rất thật với bạn, "
        "nhưng chúng có thể thay đổi.\n\n"
        "Bạn có thể chia sẻ thêm với mình không? Và bạn có an toàn ngay lúc này?"
    ),
    "medium": (
        "**Mình hiểu bạn đang trải qua điều rất khó khăn.**\n\n"
        "Cảm ơn bạn đã chia sẻ điều này với mình. "
        "Việc bạn nói ra cho thấy bạn đang tìm kiếm sự giúp đỡ — đó là một bước rất dũng cảm.\n\n"
        "Bạn có muốn kể thêm về những gì đang xảy ra không? Mình ở đây để lắng nghe."
    ),
    "low": (
        "**Mình rất vui vì bạn đã chia sẻ điều này.**\n\n"
        "Nghe có vẻ như bạn đang cảm thấy rất mệt mỏi và bế tắc. "
        "Những cảm xúc đó hoàn toàn hợp lý khi chúng ta đối mặt với khó khăn.\n\n"
        "Bạn có muốn nói thêm về những gì đang xảy ra không?"
    ),
}


class ImmediateResponse:
    """Generate immediate crisis response based on detected crisis level."""

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def respond(
        self,
        crisis_level: str,
        message: str,
        language: str = "vi",
    ) -> str:
        """
        Return immediate empathetic response for the crisis level.
        """
        response = IMMEDIATE_RESPONSES.get(crisis_level, IMMEDIATE_RESPONSES["low"])

        # LLM enhancement for more personalized response
        if self._llm:
            try:
                prompt = f"""Generate a brief, warm, empathetic immediate response for someone in crisis.
The response should:
- Validate their pain and feelings
- Express genuine concern
- Encourage them to reach out for professional help
- Be in Vietnamese (tiếng Việt)
- Be 3-5 sentences maximum
- NOT give advice, just listen and validate
- NOT minimize their feelings

Crisis level: {crisis_level}
Their message: {message[:300]}"""
                enhanced = (await self._llm.generate(prompt)).strip()
                if enhanced and len(enhanced) > 20:
                    response = enhanced
            except Exception as e:
                logger.warning(f"[ImmediateResponse] LLM failed: {e}")

        return response
