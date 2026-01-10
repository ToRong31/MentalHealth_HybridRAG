"""
Request More Info Node
Return follow-up questions when insufficient REQUIRED slots are filled
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


# Mapping: slot -> Vietnamese question
SLOT_QUESTIONS = {
    # Stage 1: Initial Assessment (emotional_issue)
    "emotion": "Bạn đang cảm thấy cảm xúc nào chủ yếu? (ví dụ: buồn, lo lắng, tức giận...)",
    "frequency": "Tình trạng này diễn ra với tần suất như thế nào? (mỗi ngày, vài lần/tuần, thỉnh thoảng...)",
    "intensity": "Mức độ nghiêm trọng của cảm xúc này thế nào? (nhẹ, trung bình, nặng...)",
    
    # Stage 2: Symptom Details (symptom_pattern)
    "duration": "Tình trạng này kéo dài bao lâu rồi? (vài ngày, vài tuần, vài tháng...)",
    "onset": "Nó bắt đầu từ khi nào? Có điều gì xảy ra trước đó không?",
    "trigger": "Có sự kiện hoặc tình huống nào khiến bạn cảm thấy như vậy không?",
    
    # Stage 3: Impact Assessment (functional_impact) 
    "sleep_pattern": "Giấc ngủ của bạn có bị ảnh hưởng không? (khó ngủ, ngủ nhiều, thức giấc...)",
    "appetite_change": "Khẩu vị ăn uống của bạn có thay đổi không? (ăn ít hơn, ăn nhiều hơn...)",
    "work_school_impact": "Tình trạng này có ảnh hưởng đến công việc/học tập không?",
    "social_withdrawal": "Bạn có tránh gặp gỡ bạn bè hoặc người thân không?",
    
    # Stage 4: Risk Assessment (risk_factors)
    "self_harm_thoughts": "Bạn có nghĩ đến việc tự làm hại bản thân không?",
    "suicide_ideation": "Bạn có nghĩ đến việc tự tử không?",
}


def generate_questions_from_slots(missing_slots: List[str]) -> List[str]:
    """
    Generate natural follow-up questions from missing REQUIRED slots.
    Fallback when LLM doesn't generate questions.
    
    Args:
        missing_slots: List of missing required slot names
    
    Returns:
        List of Vietnamese questions to ask
    """
    questions = []
    for slot in missing_slots[:3]:  # Ask max 3 at a time
        if slot in SLOT_QUESTIONS:
            questions.append(SLOT_QUESTIONS[slot])
    
    return questions


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
    
    # BACKUP: If LLM didn't generate questions, generate from missing slots
    if not follow_up_questions and required_missing:
        follow_up_questions = generate_questions_from_slots(required_missing)
        logger.warning(f"⚠️ LLM didn't generate questions. Auto-generated {len(follow_up_questions)} from missing slots")
    
    # Build response with follow-up questions (already filtered to REQUIRED only)
    if follow_up_questions:
        # Natural Vietnamese response
        response_parts = [
            "Để tôi có thể hỗ trợ bạn tốt hơn, bạn có thể chia sẻ thêm về:"
        ]
        
        # Add questions naturally
        for i, question in enumerate(follow_up_questions, 1):
            response_parts.append(f"{i}. {question}")
        
        answer = "\n".join(response_parts)
    else:
        # Final fallback if even auto-generation fails
        answer = "Bạn có thể chia sẻ thêm chi tiết về tình huống và cảm xúc của bạn để tôi hiểu rõ hơn và hỗ trợ bạn tốt hơn được không?"
    
    logger.info(f"Requesting more info with {len(follow_up_questions)} REQUIRED questions")
    
    # Update state
    state["answer"] = answer
    state["done"] = True
    state["needs_more_info"] = True  # Flag to indicate this is a request for more info
    
    return state
