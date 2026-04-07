"""
ResponseDrafting skill — format diagnostic response with translation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ResponseDrafting:
    """Format DiagnosticAgent's final response."""

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def format(
        self,
        diagnosis: dict[str, Any],
        slots: dict[str, Any],
        language: str = "vi",
    ) -> dict[str, Any]:
        """
        Format diagnostic response.

        Parameters
        ----------
        diagnosis : dict
            Result from ClinicalReasoning.
        slots : dict
            Accumulated diagnostic slots.
        language : str
            Output language.
        """
        parts = []

        # Header
        if diagnosis.get("diagnosis"):
            parts.append(f"## {diagnosis['diagnosis']}")
            if diagnosis.get("disorder_en"):
                parts.append(f"*({diagnosis['disorder_en']})*\n")
            parts.append(f"**Độ tin cậy:** {diagnosis['confidence']:.0%}\n")
        else:
            parts.append("## Chưa có chuẩn đoán cụ thể")

        # Reasoning
        if diagnosis.get("reasoning"):
            parts.append(f"\n**Phân tích lâm sàng:**\n{diagnosis['reasoning']}\n")

        # Filled slots summary
        filled = {k: v for k, v in slots.items() if v is not None and v != ""}
        if filled:
            slot_lines = "\n".join(f"- **{k}**: {v}" for k, v in filled.items())
            parts.append(f"\n**Triệu chứng đã xác định:**\n{slot_lines}\n")

        # Differential
        differential = diagnosis.get("differential", [])
        if differential:
            diff_lines = "\n".join(
                f"- {d['disorder_vi']} ({d['disorder']}) — score={d['score']}"
                for d in differential
            )
            parts.append(f"\n**Chuẩn đoán phân biệt:**\n{diff_lines}\n")

        # Missing info
        missing = diagnosis.get("missing_criteria", [])
        if missing:
            missing_text = "\n".join(f"- {m}" for m in missing[:3])
            parts.append(f"\n**Thông tin cần bổ sung:**\n{missing_text}\n")

        # Recommendation
        if diagnosis.get("recommendation"):
            parts.append(f"\n**Khuyến nghị:**\n{diagnosis['recommendation']}\n")

        # Disclaimer
        disclaimer = (
            "\n---\n"
            "*⚠️ **Tuyên bố miễn trừ trách nhiệm:**\n"
            "Đây là chuẩn đoán sơ bộ dựa trên thông tin bạn cung cấp, "
            "KHÔNG phải là chuẩn đoán y khoa chính thức. "
            "Chỉ bác sĩ tâm thần mới có thể chuẩn đoán chính xác. "
            "Nếu bạn đang có ý nghĩ tự hại, xin gọi ngay: **094 234 99 99**.*"
        )
        parts.append(disclaimer)

        response = "\n".join(parts)

        # LLM polish
        if self._llm and language == "vi":
            try:
                prompt = (
                    f"Format lại phản hồi chuẩn đoán tâm lý sau đây cho dễ đọc hơn.\n"
                    f"Dùng markdown headers, bullet points.\n"
                    f"Giữ thông tin khoa học chính xác.\n"
                    f"Tiếng Việt.\n\n{response[:2000]}"
                )
                polished = (await self._llm.generate(prompt)).strip()
                if polished:
                    response = polished
            except Exception as e:
                logger.warning(f"[ResponseDrafting] LLM failed: {e}")

        return {
            "response": response,
            "diagnosis": diagnosis.get("diagnosis"),
            "confidence": diagnosis.get("confidence", 0.0),
            "disorder_en": diagnosis.get("disorder_en"),
            "sections": [
                "diagnosis",
                "reasoning",
                "slots",
                "differential",
                "recommendation",
                "disclaimer",
            ],
        }
