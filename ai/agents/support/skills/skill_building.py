"""
SkillBuilding skill — guides user through practical mental health skill exercises.
"""

from __future__ import annotations

import logging
from typing import Any

from ai.shared.prompts import load_prompt

logger = logging.getLogger(__name__)

_EXERCISES: dict[str, dict[str, Any]] = {
    "breathing": {
        "name": "Thở bụng 4-7-8",
        "duration": "3 phút",
        "steps": [
            "Hít vào từ từ qua mũi trong 4 giây (bụng phình ra)",
            "Giữ hơi thở trong 7 giây",
            "Thở ra từ từ qua miệng trong 8 giây (bụng xẹp xuống)",
            "Lặp lại 4 chu kỳ",
        ],
        "tip": "Tập mỗi ngày 2 lần, đặc biệt khi thức dậy và trước khi ngủ.",
    },
    "grounding_54321": {
        "name": "5-4-3-2-1 Grounding",
        "duration": "5 phút",
        "steps": [
            "5 thứ bạn THẤY (màu sắc, hình dạng, khoảng cách)",
            "4 thứ bạn CHẠM (bàn, ghế, quần áo — cảm nhận bằng da)",
            "3 thứ bạn NGHE (tiếng quạc, máy tính, điều hòa)",
            "2 thứ bạn NGỬI (cà phê, nước hoa, không khí)",
            "1 thứ bạn NẾM (vị trà, kẹo, hơi thở)",
        ],
        "tip": "Khi lo âu tấn công, giác quan giúp bạn quay về hiện tại.",
    },
    "gratitude": {
        "name": "Viết 3 điều biết ơn",
        "duration": "5 phút mỗi tối",
        "steps": [
            "Viết 3 điều nhỏ trong ngày bạn biết ơn",
            "Viết TẠI SAO bạn biết ơn điều đó",
            "Có thể là thức ăn ngon, một tin nhắn, một khoảnh khắc yên bình",
        ],
        "tip": "Thực hành mỗi ngày giúp não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não não thay đổi cách nhìn.",
    },
    "cbt_thought": {
        "name": "Tước thu nhập (Decatastrophizing)",
        "duration": "10 phút",
        "steps": [
            "Viết ra suy nghĩ tiêu cực đang làm phiền bạn",
            "Hỏi: Điều tệ nhất có thể xảy ra là gì?",
            "Hỏi: Xác suất điều đó xảy ra là bao nhiêu %?",
            "Hỏi: Nếu nó xảy ra, tôi sẽ đối phó thế nào?",
            "Hỏi: Điều tốt nhất có thể xảy ra là gì?",
        ],
        "tip": "Suy nghĩ tiêu cực thường phóng đại. Viết ra giúp nhìn rõ hơn.",
    },
}


class SkillBuilding:
    """Guide user through practical mental health skill exercises."""

    SYSTEM_PROMPT = load_prompt("support.skills.skill_building")

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def execute(
        self,
        context: str,
        gs: Any,
        skill_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return skill exercises to practice.

        Parameters
        ----------
        context : str
            User's message / conversation context.
        gs : GlobalState
            GlobalState.
        skill_type : str | None
            Specific skill type: breathing | grounding | gratitude | cbt
        """
        # Default exercises
        exercise_keys = ["breathing", "grounding_54321"]
        if skill_type and skill_type in _EXERCISES:
            exercise_keys = [skill_type]

        # LLM recommendation if available
        if self._llm:
            try:
                prompt = f"""Based on this message, recommend 1-2 skill exercises from:
- breathing: Thở bụng 4-7-8 (for stress, anxiety)
- grounding_54321: 5-4-3-2-1 grounding (for anxiety, panic)
- gratitude: Viết 3 điều biết ơn (for depression, low mood)
- cbt_thought: Tước thu nhập (for negative thinking)

Message: {context[:200]}
Respond with comma-separated skill names only."""
                response = (await self._llm.generate(prompt)).strip()
                recommended = []
                for key in _EXERCISES:
                    if key in response.lower():
                        recommended.append(key)
                if recommended:
                    exercise_keys = recommended[:2]
            except Exception as e:
                logger.warning(f"[SkillBuilding] LLM failed: {e}")

        exercises = [_EXERCISES[k] for k in exercise_keys if k in _EXERCISES]
        logger.info(f"[SkillBuilding] Returned {len(exercises)} exercises")
        return exercises
