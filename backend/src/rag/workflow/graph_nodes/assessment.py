"""
Assessment Node - Dual Assessment for Routing + Context

This node runs after slot_filling to provide:
1. SEVERITY assessment → routing decision (no premature bypass)
2. DISORDER LIKELIHOOD → context for downstream nodes (query rewriter, LLM)

Why both?
- Severity: Determines urgency and routing (ALL cases screened)
- Disorder likelihood: Provides rich context for retrieval and answer generation
- This maintains retrieval quality while preventing premature routing bypass
"""

import logging
from ..state import KGState
from src.rag.utils.assessment import assess_severity_only, assess_disorder_likelihood, get_assessment_context
from src.rag.utils.normal_response_matcher import match_symptoms_to_database

logger = logging.getLogger(__name__)


async def assessment_node(state: KGState) -> KGState:
    """
    Dual assessment: Severity (for routing) + Disorder likelihood (for context).
    
    This node:
    1. Matches symptoms to normal_responses.jsonl database
    2. Runs assess_severity_only() → routing decision
    3. Runs assess_disorder_likelihood() → context for retrieval/LLM
    4. Updates state with BOTH results
    5. ALL cases then proceed to diagnostic_screening (no premature bypass)
    
    Args:
        state: KGState with slots filled
    
    Returns:
        Updated state with:
        - severity_level, severity_breakdown, severity_confidence (for routing)
        - assessment_category, assessment_explanation, assessment_confidence (for context)
    """

    slots = state.get("slots", {})
    
    logger.info("=" * 80)
    logger.info("[ASSESSMENT NODE] Starting dual assessment (severity + disorder likelihood)")
    logger.info("=" * 80)
    
    # Step 1: Match symptoms to normal_responses.jsonl database
    logger.info("[STEP 1] Matching symptoms to normal_responses database")
    matched_items = match_symptoms_to_database(slots)
    logger.info(f"[MATCHED] {len(matched_items)} items from database")
    
    # Step 2: Severity assessment (for routing decision)
    logger.info("[STEP 2] Running severity assessment (for routing)")
    try:
        severity_level, severity_breakdown, sev_confidence = assess_severity_only(slots, matched_items)
        
        state["severity_level"] = severity_level
        state["severity_breakdown"] = severity_breakdown
        state["severity_confidence"] = sev_confidence
        
        logger.info(f"[SEVERITY RESULT] Level: {severity_level}, Confidence: {sev_confidence:.2f}")
        
    except Exception as e:
        logger.error(f"[SEVERITY ASSESSMENT ERROR] {e}", exc_info=True)
        state["severity_level"] = "moderate"
        state["severity_breakdown"] = {"error": str(e)}
        state["severity_confidence"] = 0.5
    
    # Step 3: Disorder likelihood assessment (for context)
    logger.info("[STEP 3] Running disorder likelihood assessment (for retrieval context)")
    try:
        category, explanation, confidence = assess_disorder_likelihood(slots, matched_items)
        
        # Update state with assessment context (used by query_rewriter, answer generation)
        state["assessment_category"] = category
        state["assessment_explanation"] = explanation
        state["assessment_confidence"] = confidence
        
        logger.info(f"[DISORDER LIKELIHOOD] Category: {category}, Confidence: {confidence:.2f}")
        
        # Generate assessment context for prompt injection
        assessment_ctx = get_assessment_context(slots, matched_items)
        state["assessment_context"] = assessment_ctx
        
    except Exception as e:
        logger.error(f"[DISORDER LIKELIHOOD ERROR] {e}", exc_info=True)
        state["assessment_category"] = "possible_disorder"
        state["assessment_explanation"] = "Không thể đánh giá chính xác. Cần theo dõi triệu chứng."
        state["assessment_confidence"] = 0.5
        state["assessment_context"] = ""
    
    logger.info("=" * 80)
    logger.info(f"[SUMMARY] Severity: {state.get('severity_level')}, Category: {state.get('assessment_category')}")
    logger.info("[NOTE] Routing uses severity_level, but assessment_category provides context for retrieval")
    logger.info("=" * 80)
    
    return state

