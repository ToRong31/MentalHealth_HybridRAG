"""
Assessment Node - Classify Normal vs Disorder

This node runs after slot_filling to determine whether symptoms indicate:
- normal_stress: Normal stress, no disorder
- adjustment_reaction: Adjustment to life event
- possible_disorder: Some indicators, needs monitoring
- likely_disorder: Meets disorder criteria, refer to professional

REVERTED: Back to old binary classification for backward compatibility.
"""

import logging
from ..state import KGState

logger = logging.getLogger(__name__)


async def assessment_node(state: KGState) -> KGState:
    """
    Assess whether symptoms indicate normal response or disorder.
    
    REVERTED to old logic for backward compatibility with existing workflow.
    
    This node:
    1. Matches symptoms to normal_responses.jsonl database
    2. Runs assess_disorder_likelihood() to classify into 4 categories
    3. Updates state with assessment_category, assessment_explanation, assessment_confidence
    
    Args:
        state: KGState with slots filled
    
    Returns:
        Updated state with assessment_category, assessment_explanation, assessment_confidence
    """
    from src.rag.utils.assessment import assess_disorder_likelihood, get_assessment_context
    from src.rag.utils.normal_response_matcher import match_symptoms_to_database
    
    slots = state.get("slots", {})
    
    logger.info("=" * 80)
    logger.info("[ASSESSMENT NODE] Starting disorder likelihood assessment (REVERTED)")
    logger.info("=" * 80)
    
    # Step 1: Match symptoms to normal_responses.jsonl database
    logger.info("[STEP 1] Matching symptoms to normal_responses database")
    matched_items = match_symptoms_to_database(slots)
    logger.info(f"[MATCHED] {len(matched_items)} items from database")
    
    # Step 2: Run assessment (OLD logic restored)
    logger.info("[STEP 2] Running disorder likelihood assessment")
    
    try:
        category, explanation, confidence = assess_disorder_likelihood(slots, matched_items)
        
        # Update state with OLD format for compatibility
        state["assessment_category"] = category
        state["assessment_explanation"] = explanation
        state["assessment_confidence"] = confidence
        
        logger.info(f"[ASSESSMENT RESULT] Category: {category}")
        logger.info(f"[ASSESSMENT RESULT] Confidence: {confidence:.2f}")
        logger.info(f"[ASSESSMENT RESULT] Explanation: {explanation}")
        
        # Generate assessment context for prompt
        assessment_ctx = get_assessment_context(slots, matched_items)
        logger.debug(f"[ASSESSMENT CONTEXT]\n{assessment_ctx}")
        
    except Exception as e:
        logger.error(f"[ASSESSMENT ERROR] {e}", exc_info=True)
        # Fallback to possible_disorder (safer, backward compatible)
        state["assessment_category"] = "possible_disorder"
        state["assessment_explanation"] = "Không thể đánh giá chính xác. Khuyến nghị theo dõi triệu chứng và tham khảo chuyên gia nếu không cải thiện."
        state["assessment_confidence"] = 0.5
    
    logger.info("=" * 80)
    return state

