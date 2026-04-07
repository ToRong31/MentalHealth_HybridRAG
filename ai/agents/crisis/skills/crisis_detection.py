"""
CrisisDetection skill — confirms crisis and determines crisis level.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Crisis level indicators
CRISIS_LEVELS: dict[str, dict[str, Any]] = {
    "critical": {
        "keywords": [
            "tự tử",
            "tự sát",
            "kill myself",
            "end my life",
            "overdose",
            "hang myself",
            "poison",
        ],
        "description": "Nguy cơ tự hại nghiêm trọng, cần can thiệp ngay",
    },
    "high": {
        "keywords": [
            "muốn chết",
            "muốn tự tử",
            "no reason to live",
            "don't want to live",
            "nhảy cầu",
        ],
        "description": "Nguy cơ cao, cần theo dõi sát và hỗ trợ chuyên môn",
    },
    "medium": {
        "keywords": ["tự hại mình", "cut myself", "hurt myself", "self-harm"],
        "description": "Có dấu hiệu tự hại, cần quan tâm và theo dõi",
    },
    "low": {
        "keywords": ["chán đời", "không còn muốn sống", "hết cách rồi"],
        "description": "Biểu hiện tuyệt vọng nhẹ, cần empathetic response",
    },
}


class CrisisDetection:
    """Detect crisis level based on message content and keywords."""

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def detect(
        self,
        message: str,
        matched_keywords: list[str],
        context: str = "",
    ) -> dict[str, Any]:
        """
        Determine crisis level from message and keywords.

        Returns
        -------
        {
            "level": "critical" | "high" | "medium" | "low",
            "description": str,
            "requires_immediate": bool,
            "requires_professional": bool,
            "indicators": list[str],
        }
        """
        # Normalize message
        msg_lower = message.lower()

        # Check against crisis levels
        level = "low"
        indicators: list[str] = list(matched_keywords)

        for lvl, data in CRISIS_LEVELS.items():
            for kw in data["keywords"]:
                if kw.lower() in msg_lower:
                    # Use the most severe level found
                    level_order = ["critical", "high", "medium", "low"]
                    if level_order.index(lvl) < level_order.index(level):
                        level = lvl
                    indicators.extend(matched_keywords + [kw])

        # Deduplicate
        indicators = list(set(indicators))

        level_data = CRISIS_LEVELS.get(level, CRISIS_LEVELS["low"])

        requires_immediate = level in ["critical", "high"]
        requires_professional = level in ["critical", "high", "medium"]

        # LLM refinement if available
        if self._llm and level != "critical":
            try:
                prompt = f"""Assess the crisis level of this message.
Respond with ONLY one of: critical, high, medium, low

Message: {message}
Context: {context[:200] if context else 'none'}"""
                response = (await self._llm.generate(prompt)).strip().lower()
                for lvl in ["critical", "high", "medium", "low"]:
                    if lvl in response:
                        level = lvl
                        break
            except Exception as e:
                logger.warning(f"[CrisisDetection] LLM failed: {e}")

        logger.warning(f"[CrisisDetection] Level={level} indicators={indicators}")

        return {
            "level": level,
            "description": level_data["description"],
            "requires_immediate": requires_immediate,
            "requires_professional": requires_professional,
            "indicators": indicators,
        }
