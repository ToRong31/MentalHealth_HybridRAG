"""
TreatmentPlanning skill — creates personalized treatment plans.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


_EVIDENCE_HIERARCHY = {
    "A": "Được chứng minh bởi nhiều thử nghiệm ngẫu nhiên có đối chứng (RCTs)",
    "B": "Được hỗ trợ bởi các nghiên cứu lớn nhưng cần thêm bằng chứng",
    "C": "Dựa trên nghiên cứu nhỏ hoặc kinh nghiệm lâm sàng",
}


class TreatmentPlanning:
    """Rank and plan treatments by evidence level and patient fit."""

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def plan(
        self,
        treatments: list[dict[str, Any]],
        severity: str = "mild",
        patient_preferences: dict | None = None,
    ) -> list[dict[str, Any]]:
        """
        Rank treatments and create a personalized plan.
        """
        plans = []

        for treatment in treatments:
            evidence = treatment.get("evidence_level", "C")
            evidence_letter = evidence[-2] if evidence.endswith(")") else "C"
            evidence_desc = _EVIDENCE_HIERARCHY.get(evidence_letter, "")

            suitable_for = treatment.get("suitable_for", [])

            entry = {
                "name": treatment.get("name", ""),
                "description": treatment.get("description", ""),
                "evidence_level": evidence,
                "evidence_description": evidence_desc,
                "duration": treatment.get("duration", ""),
                "techniques": treatment.get("techniques", []),
                "suitable_for": suitable_for,
                "priority": self._rank_priority(evidence_letter, severity, suitable_for),
            }

            if "examples" in treatment:
                entry["examples"] = treatment["examples"]
            if "side_effects" in treatment:
                entry["side_effects"] = treatment["side_effects"]
                entry["note"] = treatment.get("note", "")

            plans.append(entry)

        plans.sort(key=lambda x: x["priority"])

        if self._llm and plans:
            try:
                prompt = (
                    f"Tạo lời khuyên phác đồ điều trị cá nhân hóa.\n"
                    f"Severity: {severity}\n"
                    f"Treatments: {str(plans[:2])[:500]}\n"
                    f"Viết 2-3 câu tiếng Việt khuyến nghị."
                )
                recommendation = (await self._llm.generate(prompt)).strip()
                if recommendation:
                    plans[0]["recommendation"] = recommendation
            except Exception as e:
                logger.warning(f"[TreatmentPlanning] LLM failed: {e}")

        logger.info(f"[TreatmentPlanning] Created plan with {len(plans)} options")
        return plans

    def _rank_priority(
        self,
        evidence_letter: str,
        severity: str,
        suitable_for: list[str],
    ) -> int:
        score = 0
        evidence_score = {"A": 1, "B": 2, "C": 3}.get(evidence_letter, 4)
        score += evidence_score * 10
        if severity == "severe" and "medication" in str(suitable_for).lower():
            score -= 5
        if severity == "mild" and "therapy" in str(suitable_for).lower():
            score -= 3
        return score
