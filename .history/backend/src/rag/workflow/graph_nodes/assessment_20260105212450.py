"""
Assessment Node - Classify Normal vs Disorder

This node runs after slot_filling to determine whether symptoms indicate:
- normal_response: Normal stress, no disorder
- adjustment_reaction: Adjustment to life event
- possible_disorder: Some indicators, needs monitoring
- likely_disorder: Meets disorder criteria, refer to professional
"""

import logging
from ..state import KGState

logger = logging.getLogger(__name__)


async def assessment_node(state: KGState) -> KGState:
    """
    Assess whether symptoms indicate normal response or disorder.
    
    This node:
    1. Checks if is_diagnosis_ready() = True (prerequisite)
    2. Matches symptoms to normal_responses.jsonl database
    3. Runs assess_disorder_likelihood() to classify into 4 categories
    4. Updates state with assessment results
    
    Args:
        state: KGState with slots filled
    
    Returns:
        Updated state with assessment_category, assessment_explanation, assessment_confidence
    """
    from src.rag.utils.assessment import assess_disorder_likelihood, get_assessment_context
    from src.rag.utils.normal_response_matcher import match_symptoms_to_database
    
    slots = state.get("slots", {})
    
    logger.info("=" * 80)
    logger.info("[ASSESSMENT NODE] Starting disorder likelihood assessment")
    logger.info("=" * 80)
    
    # Step 1: Match symptoms to normal_responses.jsonl database
    logger.info("[STEP 1] Matching symptoms to normal_responses database")
    matched_items = match_symptoms_to_database(slots)
    logger.info(f"[MATCHED] {len(matched_items)} items from database")
    
    # Always run assessment - don't check is_diagnosis_ready() first
    # The assessment function itself will determine if it's normal vs disorder
    logger.info("[STEP 2] Running disorder likelihood assessment on slots")
    
    # Run assessment
    try:
        category, explanation, confidence = assess_disorder_likelihood(slots, matched_items)
        
        # Update state
        state["assessment_category"] = category
        state["assessment_explanation"] = explanation
        state["assessment_confidence"] = confidence
        
        logger.info(f"[ASSESSMENT RESULT] Category: {category}")
        logger.info(f"[ASSESSMENT RESULT] Confidence: {confidence:.2f}")
        logger.info(f"[ASSESSMENT RESULT] Explanation: {explanation}")
        
        # Generate assessment context for prompt
        assessment_ctx = get_assessment_context(slots)
        logger.debug(f"[ASSESSMENT CONTEXT]\n{assessment_ctx}")
        
        # Log for monitoring over-diagnosis
        _log_assessment_decision(state, category, slots)
        
    except Exception as e:
        logger.error(f"[ASSESSMENT ERROR] {e}", exc_info=True)
        # Fallback to possible_disorder (safer)
        state["assessment_category"] = "possible_disorder"
        state["assessment_explanation"] = "Không thể đánh giá chính xác. Khuyến nghị theo dõi triệu chứng và tham khảo chuyên gia nếu không cải thiện."
        state["assessment_confidence"] = 0.5
    
    logger.info("=" * 80)
    return state


def _log_assessment_decision(state: KGState, category: str, slots: dict):
    """
    Log assessment decision for monitoring over-diagnosis.
    
    Warnings logged if:
    - Category is "normal_response" but diagnostic_diseases present (should not happen)
    - Category is "likely_disorder" but has clear trigger + short duration (potential over-diagnosis)
    """
    conversation_id = state.get("conversation_id", "unknown")
    duration = slots.get("duration", "")
    recent_events = slots.get("recent_life_events", "")
    daily_functioning = slots.get("daily_functioning", "")
    
    # Warning: Normal response but somehow diagnostic diseases present
    diagnostic_diseases = state.get("diagnostic_diseases", [])
    if category == "normal_response" and diagnostic_diseases:
        logger.warning(
            f"[OVER-DIAGNOSIS WARNING] Conversation {conversation_id}: "
            f"Assessment = 'normal_response' but diagnostic_diseases present: {diagnostic_diseases}. "
            f"This should NOT happen - routing logic should prevent disorder retrieval."
        )
    
    # Warning: Likely disorder but short duration + clear trigger (potential over-diagnosis)
    if category == "likely_disorder":
        duration_lower = duration.lower() if duration else ""
        short_indicators = ["ngày", "day", "tuần", "week", "1 tháng", "2 tháng"]
        has_short_duration = any(ind in duration_lower for ind in short_indicators)
        has_clear_trigger = bool(recent_events and len(recent_events) > 5)
        
        if has_short_duration and has_clear_trigger:
            logger.warning(
                f"[POTENTIAL OVER-DIAGNOSIS] Conversation {conversation_id}: "
                f"Assessment = 'likely_disorder' but duration = '{duration}' and trigger = '{recent_events}'. "
                f"Review: Should this be 'adjustment_reaction' instead?"
            )
    
    # Info log for analytics
    logger.info(
        f"[ASSESSMENT LOG] Conversation: {conversation_id} | "
        f"Category: {category} | "
        f"Duration: {duration} | "
        f"Trigger: {recent_events} | "
        f"Functioning: {daily_functioning}"
    )
