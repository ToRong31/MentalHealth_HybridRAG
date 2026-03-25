"""
PsychoEducation skill — provides mental health knowledge and psychoeducation.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Basic psychoeducation content (replace with RAG in production)
_EDUCATION_CONTENT: dict[str, str] = {
    "stress": """**Căng thẳng (Stress) là gì?**
Căng thẳng là phản ứng tự nhiên của cơ thể khi đối mặt với thách thức hoặc áp lực.
Có 2 loại:
• Stress tích cực (eustress): Giúp bạn tập trung, năng động
• Stress tiêu cực (distress): Kéo dài, gây hại cho sức khỏe

**Khi nào stress cần được chú ý?**
Nếu stress kéo dài >2 tuần, ảnh hưởng đến giấc ngủ, ăn uống, công việc — hãy tìm kiếm hỗ trợ.""",

    "lo_au": """**Rối loạn lo âu (Anxiety) là gì?**
Lo âu là cảm giác lo lắng, bất an, sợ hãi xảy ra quá mức so với mức độ nguy hiểm thực tế.
Lo âu có thể biểu hiện:
• Lo âu tổng quát (GAD): Lo liên tục về nhiều thứ
• Rối loạn hoảng sợ: Cơn hoảng loạn đột ngột
• Lo âu xã hội: Sợ bị đánh giá

**Tự giúp:**
Thở bụng, thiền định, và liệu pháp nhận thức (CBT) đều được chứng minh hiệu quả.""",

    "buồn": """**Trầm cảm (Depression) là gì?**
Trầm cảm là rối loạn tâm trạng kéo dài, ảnh hưởng đến cảm xúc, suy nghĩ và hành vi.
Triệu chứng cần chú ý kéo dài >2 tuần:
• Buồn liên tục hoặc mất hứng thú
• Thay đổi ngủ, ăn (nhiều hoặc ít)
• Mệt mỏi, thiếu năng lượng
• Cảm giác vô giá trị, tội lỗi

**Lưu ý quan trọng:**
Nếu bạn có ý nghĩ tự hại — xin hãy gọi ngay đường dây hỗ trợ tâm thần.""",

    "default": """**Sức khỏe tâm thần là gì?**
Sức khỏe tâm thần bao gồm cảm xúc, tâm lý và xã hội. Nó ảnh hưởng đến cách chúng ta nghĩ, cảm nhận và hành động.
Giống như thể chất, tâm lý cũng cần được chăm sóc và nuôi dưỡng.

**Dấu hiệu cần chú ý:**
• Thay đổi cân nặng, giấc ngủ bất thường
• Rút khỏi các mối quan hệ
• Khó tập trung, mệt mỏi kéo dài
• Cảm xúc mạnh, khó kiểm soát""",
}


class PsychoEducation:
    """Provide psychoeducation content based on user's concern."""

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def execute(
        self,
        context: str,
        gs: Any,
        topic: str | None = None,
    ) -> str:
        """
        Return psychoeducation content.

        Parameters
        ----------
        context : str
            User's message / conversation context.
        gs : GlobalState
            GlobalState with preliminary_slots.
        topic : str | None
            Specific topic to cover.
        """
        # Determine topic from context
        topic_key = topic or ""
        content = ""

        for key in ["stress", "lo_au", "buồn"]:
            if key in context.lower():
                topic_key = key
                break

        if topic_key in _EDUCATION_CONTENT:
            content = _EDUCATION_CONTENT[topic_key]
        else:
            content = _EDUCATION_CONTENT["default"]

        # LLM enhancement if available
        if self._llm:
            try:
                prompt = f"""Bổ sung kiến thức sau bằng tiếng Việt tự nhiên, ngắn gọn (50-100 từ).
Không bịa thông tin. Dựa trên: {context[:200]}
---
{content}"""
                enhanced = (await self._llm.generate(prompt)).strip()
                if enhanced:
                    content = enhanced
            except Exception as e:
                logger.warning(f"[PsychoEducation] LLM failed: {e}")

        return content
