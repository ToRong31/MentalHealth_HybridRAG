"""
PatientGuidance skill — guidance for patients seeking treatment.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


WHAT_TO_EXPECT = {
    "therapy": """**Khi đi khám tâm lý lần đầu, bạn có thể mong đợi:**
1. **Đánh giá**: Bác sĩ/nhà trị liệu sẽ hỏi về triệu chứng, tiền sử, mục tiêu của bạn
2. **Thời gian**: Buổi đầu thường 60-90 phút
3. **Bí mật**: Mọi thông tin bạn chia sẻ đều được bảo mật (trừ nguy hiểm tính mạng)
4. **Không có lời phán xét**: Bạn có thể thoải mái nói về bất cứ điều gì
5. **Kế hoạch**: Cuối buổi, bạn sẽ cùng nhau xây dựng kế hoạch điều trị""",
    "medication": """**Khi được kê thuốc tâm thần:**
1. **Tuân thủ**: Uống đúng liều, đúng giờ như bác sĩ chỉ định
2. **Không tự ý dừng**: Thuốc cần thời gian phát huy (4-6 tuần)
3. **Theo dõi**: Ghi nhận tác dụng phụ để báo lại bác sĩ
4. **Kiên nhẫn**: Nhiều người cần thử 2-3 loại thuốc trước khi tìm được loại phù hợp
5. **Tái khám**: Đi tái khám đúng lịch, không tự ý tăng/giảm liều""",
    "crisis": """**Nếu bạn đang trong khủng hoảng:**
1. Gọi đường dây hỗ trợ: 094 234 99 99 (24/7)
2. Đến phòng cấp cứu tâm thần gần nhất
3. Ở cùng người thân cho đến khi được hỗ trợ chuyên môn
4. KHÔNG tự ý dùng rượu bia hoặc chất kích thích""",
}


class PatientGuidance:
    """Provide guidance for patients about what to expect from treatment."""

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def get_guidance(
        self,
        treatment_types: list[str],
        severity: str = "mild",
        language: str = "vi",
    ) -> str:
        """
        Return guidance for specific treatment types.
        """
        sections = []

        for treatment_type in treatment_types:
            if treatment_type in WHAT_TO_EXPECT:
                sections.append(WHAT_TO_EXPECT[treatment_type])

        # Add crisis guidance if severity is moderate or severe
        if severity in ["moderate", "severe"]:
            sections.append(WHAT_TO_EXPECT["crisis"])

        # Add general first steps
        sections.insert(
            0,
            """**Bước đầu tiên của bạn:**
1. **Gặp bác sĩ tâm thần hoặc nhà tâm lý** — không cần giấy giới thiệu
2. **Chuẩn bị**: Ghi sẵn triệu chứng, thời gian xuất hiện, ảnh hưởng đến cuộc sống
3. **Trung thực**: Càng chia sẻ nhiều, bác sĩ càng giúp bạn tốt hơn""",
        )

        guidance = "\n\n".join(sections)

        # LLM personalize
        if self._llm and language == "vi":
            try:
                prompt = f"""Viết lại lời khuyên cho bệnh nhân sau đây cho dễ hiểu và động viên hơn.
Giữ thông tin y khoa chính xác. Tiếng Việt.

---
{guidance}"""
                polished = (await self._llm.generate(prompt)).strip()
                if polished:
                    guidance = polished
            except Exception as e:
                logger.warning(f"[PatientGuidance] LLM failed: {e}")

        return guidance
