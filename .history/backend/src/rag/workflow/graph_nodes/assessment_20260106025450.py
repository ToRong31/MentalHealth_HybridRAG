"""
Assessment Node - Severity Assessment Only (No Binary Classification)

This node runs after slot_filling to determine SEVERITY ONLY:
- mild: Low impact, short duration
- moderate: Some impact, moderate duration
- severe: Significant impact, longer duration
- crisis: Emergency level, immediate intervention needed

NO LONGER classifies as normal vs disorder (that's premature).
ALL cases proceed to diagnostic_screening after this node.
"""

import logging
from ..state import KGState

logger = logging.getLogger(__name__)


async def assessment_node(state: KGState) -> KGState:
    """
    Assess ONLY severity level - NO binary classification.
    
    This node:
    1. Matches symptoms to normal_responses.jsonl database
    2. Runs assess_severity_only() to get severity level (mild/moderate/severe/crisis)
    3. Updates state with severity_level, severity_breakdown
    4. ALL cases then proceed to diagnostic_screening (no premature bypass)
    
    Args:
        state: KGState with slots filled
    
    Returns:
        Updated state with severity_level, severity_breakdown, severity_confidence
    """
    from src.rag.utils.assessment import assess_severity_only
    from src.rag.utils.normal_response_matcher import match_symptoms_to_database
    
    slots = state.get("slots", {})
    
    logger.info("=" * 80)
    logger.info("[ASSESSMENT NODE] Starting severity assessment (no binary classification)")
    logger.info("=" * 80)
    
    # Step 1: Match symptoms to normal_responses.jsonl database
    logger.info("[STEP 1] Matching symptoms to normal_responses database")
    matched_items = match_symptoms_to_database(slots)
    logger.info(f"[MATCHED] {len(matched_items)} items from database")
    
    # Step 2: Run severity assessment (NOT binary classification)
    logger.info("[STEP 2] Running severity-only assessment")
    
    try:
        severity_level, severity_breakdown, confidence = assess_severity_only(slots, matched_items)
        
        # Update state
        state["severity_level"] = severity_level
        state["severity_breakdown"] = severity_breakdown
        state["severity_confidence"] = confidence
        
        logger.info(f"[SEVERITY RESULT] Level: {severity_level}")
        logger.info(f"[SEVERITY RESULT] Confidence: {confidence:.2f}")
        logger.info(f"[SEVERITY RESULT] Breakdown: {severity_breakdown}")
        
        # Log for monitoring
        logger.info(f"[ASSESSMENT] Severity={severity_level}, Total Score={severity_breakdown.get('total_score', 0)}")
        
    except Exception as e:
        logger.error(f"[ASSESSMENT ERROR] {e}", exc_info=True)
        # Fallback to moderate (safer)
        state["severity_level"] = "moderate"
        state["severity_breakdown"] = {"error": str(e)}
        state["severity_confidence"] = 0.5
    
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
