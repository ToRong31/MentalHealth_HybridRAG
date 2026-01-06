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

