"""
CopingRetrieval skill — find relevant coping strategies for user's emotional state.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# In-memory coping strategy KB (replace with RAG retrieval in production)
_COPING_BY_EMOTION: dict[str, list[dict[str, str]]] = {
    "buồn": [
        {
            "name": "Di chuyển - Nhảy dây hoặc tập thể dục nhẹ",
            "description": "Vận động giúp cơ thể giải phóng endorphin, cải thiện tâm trạng tự nhiên.",
            "duration": "15-30 phút",
        },
        {
            "name": "Viết nhật ký cảm xúc",
            "description": "Viết ra những gì bạn đang cảm thấy giúp giải tỏa cảm xúc và nhìn nhận rõ hơn.",
            "duration": "10-20 phút",
        },
        {
            "name": "Gọi điện cho người thân",
            "description": "Kết nối xã hội là liều thuốc tự nhiên giảm đau.",
            "duration": "Tùy ý",
        },
    ],
    "stress": [
        {
            "name": "Thở bụng 4-7-8",
            "description": "Hít vào 4 giây, giữ 7 giây, thở ra 8 giây. Kích hoạt hệ thần kinh parasympathetic.",
            "duration": "2-3 phút",
        },
        {
            "name": "5-4-3-2-1 Grounding",
            "description": "Nhận diện 5 thứ bạn thấy, 4 thứ bạn chạm, 3 thứ bạn nghe, 2 thứ bạn ngửi, 1 thứ bạn nếm. Giúp quay về hiện tại.",
            "duration": "3-5 phút",
        },
    ],
    "lo âu": [
        {
            "name": "Hướng dẫn thư giãn cơ tiến progressive",
            "description": "Căng và thả từng nhóm cơ từ chân đến đầu. Giảm lo âu hiệu quả.",
            "duration": "10-15 phút",
        },
        {
            "name": "Tước thu nhập (Decatastrophizing)",
            "description": "Hỏi: Điều tệ nhất có thể xảy ra là gì? Xác suất? Tôi sẽ đối phó thế nào?",
            "duration": "5 phút",
        },
    ],
    "cô đơn": [
        {
            "name": "Tham gia cộng đồng trực tuyến",
            "description": "Tham gia nhóm hỗ trợ tâm lý trực tuyến, câu lạc bộ sở thích.",
            "duration": "Tùy ý",
        },
    ],
    "bế tắc": [
        {
            "name": " chia nhỏ vấn đề",
            "description": "Viết ra tất cả vấn đề, chọn 1 việc nhỏ nhất có thể làm trong 5 phút. Bắt đầu ngay.",
            "duration": "5-10 phút",
        },
    ],
}


class CopingRetrieval:
    """Retrieve coping strategies based on detected emotion and context."""

    def __init__(self, llm: Any = None):
        self._llm = llm

    async def execute(
        self,
        context: str,
        gs: Any,
        emotion_hint: str | None = None,
    ) -> list[dict[str, str]]:
        """
        Return relevant coping strategies.

        Parameters
        ----------
        context : str
            Full conversation context.
        gs : GlobalState
            GlobalState with accumulated_slots.
        emotion_hint : str | None
            Detected emotion from preliminary context.
        """
        # Try emotion hint first
        strategies = []
        if emotion_hint:
            strategies = _COPING_BY_EMOTION.get(emotion_hint.lower(), [])

        # If no match, use LLM to determine emotion and retrieve
        if not strategies and self._llm:
            try:
                # Extract emotion with LLM
                emotion_prompt = f"""Extract the primary emotion from this message.
Respond with only ONE word in Vietnamese (e.g. buồn, stress, lo âu, cô đơn, bế tắc).
Message: {context[:200]}"""
                emotion = (await self._llm.generate(emotion_prompt)).strip().lower()
                strategies = _COPING_BY_EMOTION.get(emotion, [])

                if strategies:
                    logger.debug(f"[CopingRetrieval] LLM emotion={emotion}, found {len(strategies)} strategies")
            except Exception as e:
                logger.warning(f"[CopingRetrieval] LLM failed: {e}")

        # Fallback: return general strategies
        if not strategies:
            strategies = _COPING_BY_EMOTION.get("stress", [])

        logger.info(f"[CopingRetrieval] Returned {len(strategies)} strategies")
        return strategies
