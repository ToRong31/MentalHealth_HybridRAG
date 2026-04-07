"""
ProfessionalEscalation skill — provides hotline numbers and professional resources.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Vietnam hotlines
VIETNAM_HOTLINES: list[dict[str, str]] = [
    {
        "name": "Đường dây nóng Tâm lý - Tổ chức Y tế Thế giới (WHO)",
        "phone": "094 234 99 99",
        "hours": "24/7",
        "description": "Hỗ trợ tâm lý khẩn cấp",
    },
    {
        "name": "Đường dây nóng Tâm thần Việt Nam",
        "phone": "1800 2020",
        "hours": "24/7",
        "description": "Tư vấn sức khỏe tâm thần",
    },
    {
        "name": "Tổng đài Sức khỏe Gia đình Việt Nam",
        "phone": "1900 1900",
        "hours": "24/7",
        "description": "Hỗ trợ tâm lý, tư vấn gia đình",
    },
]

# International hotlines
INTERNATIONAL_HOTLINES: list[dict[str, str]] = [
    {
        "name": "International Association for Suicide Prevention",
        "phone": "https://www.iasp.info/resources/Crisis_Centres/",
        "hours": "24/7",
        "description": "Danh sách đường dây nóng tự sát toàn cầu",
    },
    {
        "name": "Befrienders Worldwide",
        "phone": "https://www.befrienders.org/",
        "hours": "24/7",
        "description": "Hỗ trợ tâm lý toàn cầu",
    },
]


class ProfessionalEscalation:
    """Provide professional mental health resources and hotlines."""

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def escalate(
        self,
        crisis_level: str,
        language: str = "vi",
    ) -> dict[str, Any]:
        """
        Return escalation information including hotlines.

        Returns
        -------
        {
            "hotlines": list[dict],
            "professional_help_needed": bool,
            "recommended_action": str,
        }
        """
        requires_professional = crisis_level in ["critical", "high", "medium"]

        hotlines = VIETNAM_HOTLINES if language == "vi" else INTERNATIONAL_HOTLINES

        if requires_professional:
            recommended_action = (
                "**Hành động được khuyến nghị:**\n"
                "1. Gọi ngay đường dây hỗ trợ tâm lý\n"
                "2. Đến phòng cấp cứu gần nhất\n"
                "3. Ở cùng người thân cho đến khi được hỗ trợ chuyên môn"
            )
        else:
            recommended_action = (
                "**Lời khuyên:**\n"
                "Hãy liên hệ với chuyên gia tâm lý để được tư vấn thêm. "
                "Bạn có thể gọi đường dây nóng bất cứ lúc nào."
            )

        return {
            "hotlines": hotlines,
            "professional_help_needed": requires_professional,
            "recommended_action": recommended_action,
        }
