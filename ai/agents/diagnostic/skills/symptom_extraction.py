"""
SymptomExtraction skill — extracts 8 diagnostic slots from user messages.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

from ai.shared.agent_based.constants import REQUIRED_SLOTS, OPTIONAL_SLOTS, ALL_SLOTS

logger = logging.getLogger(__name__)

# ─── Extraction patterns ────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(c) != "Mn"
    )


_EMOTION_PATTERNS: list[tuple[str, str]] = [
    # Vietnamese
    ("buồn", "sad"),
    ("vui", "happy"),
    ("sợ", "fear"),
    ("lo âu", "anxiety"),
    ("giận", "anger"),
    ("tức", "anger"),
    ("chán", "bored"),
    ("mệt", "fatigue"),
    ("cô đơn", "lonely"),
    ("bế tắc", "hopeless"),
    ("hoảng", "panic"),
    ("căng thẳng", "stressed"),
    ("trầm cảm", "depressed"),
    # English
    ("sad", "sad"),
    ("angry", "anger"),
    ("anxious", "anxiety"),
    ("stressed", "stressed"),
    ("depressed", "depressed"),
    ("lonely", "lonely"),
    ("hopeless", "hopeless"),
    ("overwhelmed", "overwhelmed"),
    ("panic", "panic"),
]


_INTENSITY_MAP: dict[str, int] = {
    "một chút": 2,
    "hơi": 3,
    "hơi hơi": 2,
    "vừa": 5,
    "khá": 6,
    "rất": 7,
    "cực kỳ": 9,
    "vô cùng": 9,
    "hoàn toàn": 10,
    "nhẹ": 3,
    "nặng": 8,
    "mạnh": 7,
    "yếu": 2,
    "slightly": 2,
    "a bit": 2,
    "very": 7,
    "extremely": 9,
    "mild": 3,
    "moderate": 5,
    "severe": 8,
}


_DURATION_MAP: dict[str, str] = {
    "hôm nay": "today",
    "hôm qua": "yesterday",
    "mấy ngày": "few_days",
    "vài ngày": "few_days",
    "1 tuần": "1_week",
    "tuần này": "this_week",
    "2 tuần": "2_weeks",
    "tháng": "1_month",
    "năm": "1_year",
    "lâu rồi": "long_time",
    "từ lâu": "long_time",
    "vĩnh viễn": "always",
    "luôn": "always",
    "vừa mới": "recent",
    "mới": "recent",
    "today": "today",
    "yesterday": "yesterday",
    "few days": "few_days",
    "a week": "1_week",
    "month": "1_month",
    "long time": "long_time",
    "always": "always",
    "recently": "recent",
}


_IMPACT_WORDS: list[str] = [
    "ảnh hưởng", "work", "học", "ngủ", "giấc ngủ", "ăn", "uống",
    "quan hệ", "giao tiếp", "tập trung", "quyết định",
    "can't sleep", "can't work", "can't eat", "relationship",
]


class SymptomExtraction:
    """Extract 8 diagnostic slots from user message text."""

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def extract(
        self,
        message: str,
        existing_slots: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Extract diagnostic slots from message.

        Parameters
        ----------
        message : str
            User's current message.
        existing_slots : dict | None
            Already collected slots (from memory) to avoid overwriting.

        Returns
        -------
        dict[str, Any] — extracted slots
        """
        existing = existing_slots or {}
        extracted = {}
        msg_lower = _norm(message)

        # ── Emotion ──────────────────────────────────────────────────────────
        if "emotion" not in existing:
            for vi, en in _EMOTION_PATTERNS:
                if _norm(vi) in msg_lower or en in msg_lower:
                    extracted["emotion"] = en
                    break

        # ── Intensity ───────────────────────────────────────────────────────
        if "intensity" not in existing:
            for phrase, value in _INTENSITY_MAP.items():
                if _norm(phrase) in msg_lower:
                    extracted["intensity"] = value
                    break

        # ── Duration ────────────────────────────────────────────────────────
        if "duration" not in existing:
            for phrase, value in _DURATION_MAP.items():
                if _norm(phrase) in msg_lower:
                    extracted["duration"] = value
                    break

        # ── Trigger ────────────────────────────────────────────────────────
        if "trigger" not in existing:
            trigger_indicators = [
                "vì", "do", "bởi", "khi", "sau khi", "mỗi khi",
                "bắt đầu từ", "từ khi",
                "because", "due to", "after", "when", "since",
            ]
            for indicator in trigger_indicators:
                if _norm(indicator) in msg_lower:
                    idx = msg_lower.find(_norm(indicator))
                    # Extract surrounding context
                    start = max(0, idx - 10)
                    end = min(len(message), idx + len(indicator) + 30)
                    snippet = message[start:end].strip()
                    extracted["trigger"] = snippet
                    break

        # ── Impact ─────────────────────────────────────────────────────────
        if "impact" not in existing:
            for word in _IMPACT_WORDS:
                if _norm(word) in msg_lower:
                    extracted["impact"] = word
                    break

        # ── Sleep ──────────────────────────────────────────────────────────
        if "sleep" not in existing:
            sleep_patterns = [
                "mất ngủ", "không ngủ", "ngủ ít", "ngủ nhiều",
                "insomnia", "can't sleep", "sleep", "sleepless",
            ]
            for p in sleep_patterns:
                if _norm(p) in msg_lower:
                    extracted["sleep"] = p
                    break

        # ── Appetite ───────────────────────────────────────────────────────
        if "appetite" not in existing:
            appetite_patterns = [
                "không ăn", "ăn ít", "ăn nhiều", "chán ăn",
                "no appetite", "lost appetite", "overeating",
            ]
            for p in appetite_patterns:
                if _norm(p) in msg_lower:
                    extracted["appetite"] = p
                    break

        # ── Stress level ───────────────────────────────────────────────────
        if "stress_level" not in existing:
            if "stress" in msg_lower or _norm("căng thẳng") in msg_lower:
                extracted["stress_level"] = 5  # default moderate
                # Try to extract specific level
                for phrase, value in _INTENSITY_MAP.items():
                    if _norm(phrase) in msg_lower:
                        extracted["stress_level"] = value
                        break

        # ── LLM enhancement if still missing slots ──────────────────────────
        missing = [k for k in REQUIRED_SLOTS if k not in existing and k not in extracted]
        if missing and self._llm and len(missing) > 0:
            llm_extracted = await self._llm_extract(message, missing)
            extracted.update(llm_extracted)

        logger.info(f"[SymptomExtraction] Extracted: {list(extracted.keys())}")
        return extracted

    async def _llm_extract(
        self,
        message: str,
        missing_slots: list[str],
    ) -> dict[str, Any]:
        """Use LLM to extract slots that regex couldn't find."""
        try:
            prompt = (
                f"Extract these diagnostic slots from the message. "
                f"Reply as JSON dict with keys: {missing_slots}\n"
                f"Message: {message[:300]}\n"
                f"Reply ONLY JSON, no explanation."
            )
            response = await self._llm.generate(prompt)
            import json
            data = json.loads(response)
            return {k: v for k, v in data.items() if k in missing_slots and v}
        except Exception as e:
            logger.warning(f"[SymptomExtraction] LLM failed: {e}")
            return {}
