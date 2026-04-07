"""
FollowUpSupport skill — generates follow-up guidance and ongoing support.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


FOLLOWUP_GUIDANCE: dict[str, str] = {
    "critical": (
        "**Sau cuộc trò chuyện này, bước tiếp theo của bạn:**\n\n"
        "1. **Gọi ngay**: 094 234 99 99 (24/7)\n"
        "2. **Đến bệnh viện**: Phòng cấp cứu tâm thần gần nhất\n"
        "3. **Nói chuyện**: Với người thân, bạn bè, hoặc ai đó bạn tin tưởng\n\n"
        "Bạn không cần phải đối phó một mình. Có những người được đào tạo chuyên môn "
        "và sẵn sàng giúp bạn vượt qua lúc này."
    ),
    "high": (
        "**Bước tiếp theo dành cho bạn:**\n\n"
        "1. **Gọi đường dây hỗ trợ**: 1800 2020 (24/7)\n"
        "2. **Hẹn gặp chuyên gia**: Bác sĩ tâm thần hoặc nhà tâm lý trị liệu\n"
        "3. **Tự an toàn**: Ở nơi an toàn, tránh ở một mình nếu có thể\n\n"
        "Cảm xúc này sẽ thay đổi. Bạn đã làm đúng khi tìm kiếm sự giúp đỡ."
    ),
    "medium": (
        "**Hướng dẫn theo dõi:**\n\n"
        "1. **Liên hệ chuyên gia**: Hẹn gặp nhà tâm lý hoặc bác sĩ tâm thần\n"
        "2. **Theo dõi cảm xúc**: Ghi nhật ký cảm xúc hàng ngày\n"
        "3. **Tự chăm sóc**: Ăn uống, ngủ đủ, vận động nhẹ\n\n"
        "Nếu cảm xúc trở nên tệ hơn, đừng ngần ngại gọi đường dây hỗ trợ."
    ),
    "low": (
        "**Lời khuyên theo dõi:**\n\n"
        "1. **Tiếp tục chia sẻ**: Nói chuyện với người bạn tin tưởng\n"
        "2. **Tự chăm sóc**: Chú ý giấc ngủ, ăn uống, vận động\n"
        "3. **Theo dõi**: Nếu cảm xúc kéo dài >2 tuần, hãy tìm chuyên gia\n\n"
        "Cảm ơn bạn đã tin tưởng chia sẻ với mình."
    ),
}


class FollowUpSupport:
    """Generate follow-up guidance after crisis intervention."""

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def generate(
        self,
        crisis_level: str,
        language: str = "vi",
    ) -> str:
        """Return follow-up guidance for the crisis level."""
        guidance = FOLLOWUP_GUIDANCE.get(crisis_level, FOLLOWUP_GUIDANCE["low"])

        # LLM personalization
        if self._llm:
            try:
                prompt = f"""Write brief follow-up guidance (3-4 sentences) for someone who just received crisis support.
Be encouraging and hopeful. In Vietnamese (tiếng Việt).

Crisis level: {crisis_level}"""
                enhanced = (await self._llm.generate(prompt)).strip()
                if enhanced and len(enhanced) > 30:
                    guidance = enhanced
            except Exception as e:
                logger.warning(f"[FollowUpSupport] LLM failed: {e}")

        return guidance
