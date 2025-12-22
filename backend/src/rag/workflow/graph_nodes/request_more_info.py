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
        # Fallback if no follow-up questions generated
        answer = "Bạn có thể chia sẻ thêm chi tiết về tình huống và cảm xúc của bạn để tôi hiểu rõ hơn và hỗ trợ bạn tốt hơn được không?"
    
    logger.info(f"Requesting more info with {len(follow_up_questions)} REQUIRED questions")
    
    # Update state
    state["answer"] = answer
    state["done"] = True
    state["needs_more_info"] = True  # Flag to indicate this is a request for more info
    
    return state
