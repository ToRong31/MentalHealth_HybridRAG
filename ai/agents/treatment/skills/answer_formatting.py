"""
AnswerFormatting skill for TreatmentAgent.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AnswerFormatting:
    """Format TreatmentAgent's final response."""

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def format(
        self,
        treatments: list[dict[str, Any]],
        patient_guidance: str,
        disclaimer: str,
        language: str = "vi",
    ) -> dict[str, Any]:
        """
        Combine treatments + guidance + disclaimer into final response.
        """
        sections = []

        # Intro
        sections.append(
            "**Lưu ý quan trọng:** Thông tin dưới đây chỉ mang tính chất giáo dục. "
            "Quyết định điều trị phải được đưa ra cùng với bác sĩ hoặc nhà trị liệu chuyên môn."
        )
        sections.append("")

        # Treatment options
        for i, treatment in enumerate(treatments, 1):
            parts = []
            parts.append(f"### {i}. {treatment.get('name', '')}")
            parts.append(
                f"**Mức độ bằng chứng:** {treatment.get('evidence_level', '')}"
            )
            parts.append(f"\n{treatment.get('description', '')}")

            if treatment.get("duration"):
                parts.append(f"\n**Thời gian:** {treatment.get('duration')}")

            if treatment.get("techniques"):
                tech = "\n".join(f"- {t}" for t in treatment["techniques"])
                parts.append(f"\n**Kỹ thuật:**\n{tech}")

            if treatment.get("examples"):
                examples = ", ".join(treatment["examples"])
                parts.append(f"\n**Ví dụ thuốc:** {examples}")

            if treatment.get("side_effects"):
                sfx = "\n".join(f"- {s}" for s in treatment["side_effects"])
                parts.append(f"\n**Tác dụng phụ có thể:**\n{sfx}")
                if treatment.get("note"):
                    parts.append(f"\n⚠️ {treatment['note']}")

            if treatment.get("recommendation"):
                parts.append(f"\n💡 *{treatment['recommendation']}*")

            sections.append("\n".join(parts))

        # Patient guidance
        if patient_guidance:
            sections.append("")
            sections.append("---\n")
            sections.append(patient_guidance)

        # Disclaimer
        sections.append(f"\n---\n{disclaimer}")

        response = "\n\n".join(sections)

        return {
            "response": response,
            "sections": ["disclaimer", "treatments", "guidance", "final_disclaimer"],
            "treatment_count": len(treatments),
        }
