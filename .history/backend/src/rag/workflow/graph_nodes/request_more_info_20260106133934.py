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
    If REQUIRED slots are filled but RELEVANT optional slots are missing,
    ask about those instead of generic questions.
    
    Args:
        state: State dict with follow_up_questions (filtered for REQUIRED), 
               optional_follow_up_questions (for RELEVANT optional slots),
               required_missing_slots, relevant_missing_slots
    
    Returns:
        Updated state with answer containing follow-up questions and done=True
    """
    follow_up_questions = state.get("follow_up_questions", [])
    optional_follow_up_questions = state.get("optional_follow_up_questions", [])
    required_missing = state.get("required_missing_slots", [])
    relevant_missing_slots = state.get("relevant_missing_slots", [])
    
    # Determine which questions to ask
    if follow_up_questions:
        # Have REQUIRED questions → Ask them
        questions_to_ask = follow_up_questions
        logger.info(f"Insufficient REQUIRED slots. Requesting {len(questions_to_ask)} REQUIRED questions")
        logger.info(f"Missing REQUIRED slots: {required_missing}")
    elif optional_follow_up_questions:
        # REQUIRED filled but have RELEVANT optional questions → Ask them
        questions_to_ask = optional_follow_up_questions
        logger.info(f"REQUIRED slots filled. Requesting {len(questions_to_ask)} RELEVANT optional questions")
        logger.info(f"Relevant optional slots: {[s for s in relevant_missing_slots if s not in required_missing]}")
    else:
        questions_to_ask = []
    
    # Build response with follow-up questions
    if questions_to_ask:
        # Dynamic intro based on what we're asking
        if follow_up_questions:
            # Asking REQUIRED slots - more urgent tone
            intro = "Để tôi có thể đánh giá và hỗ trợ bạn tốt hơn, bạn có thể chia sẻ thêm về:"
        else:
            # Asking optional slots - softer tone  
            intro = "Cảm ơn bạn đã chia sẻ. Để tôi hiểu rõ hơn tình huống của bạn, bạn có thể cho biết thêm:"
        
        # Format questions as bullet points
        questions_formatted = "\n".join([f"• {q}" for q in questions_to_ask])
        answer = f"{intro}\n\n{questions_formatted}"
    else:
        # Fallback if no follow-up questions generated - ask specific slots
        logger.warning(f"⚠️ No follow_up_questions generated! Missing REQUIRED: {required_missing}")
        
        # Build specific questions based on missing slots
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
            "functional_impairment": "Các triệu chứng này có ảnh hưởng đến công việc/học tập hoặc sinh hoạt hàng ngày của bạn không? (không ảnh hưởng, ảnh hưởng nhẹ, ảnh hưởng vừa, ảnh hưởng nặng)",
            "medical_history": "Bạn có tiền sử bệnh lý (tim mạch, tuyến giáp, tiểu đường...) hoặc đang dùng thuốc điều trị nào không?",
            "substance_use": "Bạn có sử dụng chất kích thích (cà phê, rượu, thuốc lá...) hoặc thuốc không kê đơn nào không?",
            "medical_exclusion": "Bạn có tiền sử bệnh lý hoặc đang dùng thuốc/chất kích thích nào không?",
            "need": "Bạn cần tôi hỗ trợ điều gì? (lắng nghe, tư vấn, hay thông tin cụ thể?)",
            "stress_level": "Bạn đánh giá mức độ stress hiện tại của mình ra sao?",
            "physical_symptoms": "Bạn có triệu chứng vật lý nào không? (đau đầu, mất ngủ, tim đập nhanh...)",
            "sleep_quality": "Giấc ngủ của bạn thế nào? (ngủ ngon, khó ngủ, hay thức giấc nhiều?)",
            "coping_mechanisms": "Bạn đang làm gì để đối phó với tình trạng này?",
            "support_system": "Bạn có người thân/bạn bè hỗ trợ không?"
        }
        
        # Prioritize REQUIRED first, then relevant optional
        slots_to_ask = required_missing[:3] if required_missing else []
        if len(slots_to_ask) < 3:
            # Add relevant optional to fill up to 3
            relevant_optional = [s for s in relevant_missing_slots if s not in required_missing]
            slots_to_ask.extend(relevant_optional[:(3 - len(slots_to_ask))])
        
        for slot in slots_to_ask:
            if slot in slot_map:
                slot_questions.append(slot_map[slot])
        
        if slot_questions:
            answer = "Để tôi hiểu rõ hơn, bạn có thể cho tôi biết:\n\n" + "\n".join(f"• {q}" for q in slot_questions)
        else:
            # Ultimate fallback only if no slots to ask at all
            logger.warning("⚠️ No slots to ask - using ultimate fallback")
            answer = "Bạn có thể chia sẻ thêm về cảm xúc và tình huống bạn đang gặp phải được không?"
    
    logger.info(f"Requesting more info with {len(questions_to_ask) if questions_to_ask else 0} questions")
    
    # Update state
    state["answer"] = answer
    state["done"] = True
    state["needs_more_info"] = True  # Flag to indicate this is a request for more info
    
    return state