"""
Request More Info Node
Return follow-up questions when insufficient REQUIRED slots are filled
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def request_more_info_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Handle insufficient REQUIRED slots by returning follow-up questions.
    Questions have been filtered to only ask about REQUIRED_SLOTS.
    
    Args:
        state: State dict with follow_up_questions (already filtered for REQUIRED), required_missing_slots
    
    Returns:
        Updated state with answer containing follow-up questions and done=True
    """
    follow_up_questions = state.get("follow_up_questions", [])
    required_missing = state.get("required_missing_slots", [])
    
    logger.info(f"Insufficient REQUIRED slots filled. Requesting more information.")
    logger.info(f"Missing REQUIRED slots: {required_missing}")
    
    # Build response with follow-up questions (already filtered to REQUIRED only)
    if follow_up_questions:
        # Natural Vietnamese response
        response_parts = [
            "Để tôi có thể hỗ trợ bạn tốt hơn, bạn có thể chia sẻ thêm một chút về tình huống của mình được không?"
        ]
        
        # Add questions naturally
        for question in follow_up_questions:
            response_parts.append(f"\n{question}")
        
        answer = "\n".join(response_parts)
    else:
        # Fallback if no follow-up questions generated - ask specific REQUIRED slots
        logger.warning(f"⚠️ No follow_up_questions generated! Missing REQUIRED: {required_missing}")
        
        # Build specific questions based on missing REQUIRED slots
        slot_questions = []
        slot_map = {
            "emotion": "Bạn đang cảm thấy thế nào? (ví dụ: lo lắng, buồn, căng thẳng, tức giận...)",
            "primary_mood": "Tâm trạng chủ đạo của bạn là gì?",
            "intensity": "Cảm giác này mạnh đến mức nào? (nhẹ, trung bình, hay nghiêm trọng?)",
            "trigger": "Có điều gì đặc biệt khiến bạn cảm thấy như vậy không? (công việc, mối quan hệ, sự kiện...)",
            "duration": "Tình trạng này kéo dài bao lâu rồi? (vài ngày, vài tuần, hay lâu hơn?)",
            "specific_duration": "Bạn có thể cho biết cụ thể hơn về thời gian không? (ví dụ: 1 tuần, 2 tháng...)",
            "impact": "Nó ảnh hưởng đến cuộc sống hàng ngày của bạn như thế nào?",
            "recent_life_events": "Gần đây có biến cố hoặc thay đổi lớn nào trong cuộc sống của bạn không?",
            "functional_impairment": "Các triệu chứng này có ảnh hưởng đến công việc/học tập hoặc sinh hoạt hàng ngày của bạn không?",
            "medical_exclusion": "Bạn có tiền sử bệnh lý (tim mạch, tuyến giáp...) hoặc đang dùng thuốc/chất kích thích nào không?",
            "need": "Bạn cần tôi hỗ trợ điều gì? (lắng nghe, tư vấn, hay thông tin cụ thể?)",
            "stress_level": "Bạn đánh giá mức độ stress hiện tại của mình ra sao?"
        }
        
        for slot in required_missing[:3]:  # Ask max 3 questions
            if slot in slot_map:
                slot_questions.append(slot_map[slot])
        
        if slot_questions:
            answer = "Để tôi hiểu rõ hơn, bạn có thể cho tôi biết:\n\n" + "\n".join(f"• {q}" for q in slot_questions)
        else:
            # Ultimate fallback
            answer = "Bạn có thể chia sẻ thêm về cảm xúc và tình huống bạn đang gặp phải được không?"
    
    logger.info(f"Requesting more info with {len(follow_up_questions)} REQUIRED questions")
    
    # Update state
    state["answer"] = answer
    state["done"] = True
    state["needs_more_info"] = True  # Flag to indicate this is a request for more info
    
    return state
