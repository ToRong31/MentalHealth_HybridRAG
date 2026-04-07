"""
PreliminaryContext skill — extracts basic context from user message BEFORE routing.
Language detection, crisis keywords, and preliminary slot hints.
"""
from __future__ import annotations

import logging
from typing import Any

from ai.agents.supervisor.agent_state import PreliminaryContext
from ai.shared.agent_based.constants import Language

logger = logging.getLogger(__name__)

# ─── Intensity words ───────────────────────────────────────────────────────────

INTENSITY_HINTS: dict[str, int] = {
    "rất": 7, "cực kỳ": 9, "vô cùng": 9,
    "hơi": 3, "hơi hơi": 2, "ít": 2,
    "không": 0, "hoàn toàn không": 0,
    "rõ rệt": 7, "đáng kể": 6,
    "nhẹ": 3, "vừa": 5, "nặng": 8,
    "mạnh": 7, "yếu": 2,
}

DURATION_HINTS: dict[str, str] = {
    "hôm nay": "today", "hôm qua": "yesterday", "mấy ngày": "few_days",
    "tuần": "week", "tháng": "month", "năm": "year",
    "lâu rồi": "long_time", "từ lâu": "long_time",
    "vừa mới": "recent", "mới": "recent",
    "thường xuyên": "frequent", "luôn luôn": "always",
}

TRIGGER_HINTS: list[str] = [
    "vì", "do", "bởi vì", "khi", "sau khi",
    "mỗi khi", "bắt đầu từ", "từ khi",
    "because", "due to", "after", "when", "since",
]

EMOTION_WORDS: list[str] = [
    "buồn", "vui", "sợ", "lo", "giận", "tức", "chán",
    "mệt", "mệt mỏi", "cô đơn", "bế tắc", "hoảng",
    "lo âu", "trầm cảm", " căng thẳng", "stress",
    "sad", "happy", "angry", "anxious", "scared", "depressed",
    "stressed", "lonely", "hopeless", "frustrated",
]


def _extract_language(message: str) -> str:
    """Detect language using heuristic."""
    detected = Language.detect(message)
    logger.debug(f"[PreliminaryContext] Language detected: {detected}")
    return detected


def _extract_intensity(message: str) -> int | None:
    """Extract intensity hint from message (returns 1–10 or None)."""
    lower = message.lower()
    for phrase, value in INTENSITY_HINTS.items():
        if phrase in lower:
            return value
    return None


def _extract_duration(message: str) -> str | None:
    """Extract duration hint from message."""
    lower = message.lower()
    for phrase, value in DURATION_HINTS.items():
        if phrase in lower:
            return value
    return None


def _extract_emotion(message: str) -> str | None:
    """Extract primary emotion word from message."""
    lower = message.lower()
    for emotion in EMOTION_WORDS:
        if emotion in lower:
            return emotion
    return None


def _extract_trigger_hint(message: str) -> str | None:
    """Extract trigger hint from message."""
    lower = message.lower()
    for trigger in TRIGGER_HINTS:
        if trigger in lower:
            idx = lower.find(trigger)
            # Grab surrounding context
            start = max(0, idx - 10)
            end = min(len(message), idx + len(trigger) + 20)
            snippet = message[start:end].strip()
            return snippet
    return None


class PreliminaryContextSkill:
    """
    Extracts basic context from user message BEFORE routing.
    Lightweight — NO LLM call needed for most extractions.
    """

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def extract(self, message: str) -> PreliminaryContext:
        """
        Extract preliminary context from user message.

        Returns dict with:
        - language: detected language
        - has_crisis_keywords: bool
        - crisis_keywords_found: list[str]
        - preliminary_slots: hints for DiagnosticAgent slots
        """
        from ai.agents.supervisor.router import check_crisis_gate

        # Language
        language = _extract_language(message)

        # Crisis gate
        has_crisis, crisis_keywords = check_crisis_gate(message)

        # Slot hints (preliminary)
        preliminary_slots: dict[str, str | int | float | None] = {
            "emotion": _extract_emotion(message),
            "intensity": _extract_intensity(message),
            "duration": _extract_duration(message),
            "trigger": _extract_trigger_hint(message),
        }

        result = PreliminaryContext(
            language=language,
            has_crisis_keywords=has_crisis,
            crisis_keywords_found=crisis_keywords,
            preliminary_slots={k: v for k, v in preliminary_slots.items() if v is not None},
        )

        logger.debug(
            f"[PreliminaryContext] lang={language} crisis={has_crisis} "
            f"slots={[k for k,v in result.get('preliminary_slots',{}).items() if v]}"
        )

        return result
