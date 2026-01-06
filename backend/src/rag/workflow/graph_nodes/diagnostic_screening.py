"""
Diagnostic Screening Node - Universal disorder screening for all cases

This node implements the new universal diagnostic flow:
- ALL cases go through this node (no premature bypass)
- Screens for potential disorders using symptom patterns
- Prevents false negatives by evaluating all symptom presentations
- Routes to appropriate support based on screening results

Screening Process:
1. Check severity level (from severity assessment)
2. Screen for potential disorders (symptom pattern matching)
3. Apply clinical thresholds (≥7/10 items for clinical level)
4. Check exclusion criteria (prevents false positives)
5. Route to: disorder_diagnostic / coping / adjustment
"""

import logging
from typing import Dict, Any
from ..state import KGState

logger = logging.getLogger(__name__)


async def diagnostic_screening_node(state: KGState) -> KGState:
    """
    Universal diagnostic screening node - evaluates ALL cases for potential disorders.
    
    This node:
    1. Gets severity level from severity assessment
    2. Screens symptoms against disorder patterns (generic, not disorder-specific)
    3. Applies clinical thresholds to prevent false positives
    4. Determines screening result: disorder_suspected / subclinical / non_clinical
    5. Updates state with screening results for routing
    
    Args:
        state: KGState with severity_level and slots
    
    Returns:
        Updated state with screening_result, screening_confidence, screening_details
    """
    slots = state.get("slots", {})
    severity_level = state.get("severity_level", "moderate")
    severity_breakdown = state.get("severity_breakdown", {})
    
    logger.info("=" * 80)
    logger.info("[DIAGNOSTIC SCREENING] Starting universal screening")
    logger.info(f"[INPUT] Severity level: {severity_level}")
    logger.info("=" * 80)
    
    try:
        # Step 1: Quick triage based on severity
        if severity_level == "crisis":
            logger.critical("[SCREENING] CRISIS level detected - immediate routing to diagnostic")
            state["screening_result"] = "disorder_suspected"
            state["screening_confidence"] = 0.95
            state["screening_details"] = {
                "reason": "crisis_level",
                "message": "Mức độ nghiêm trọng cần được đánh giá ngay lập tức"
            }
            return state
        
        # Step 2: Run generic disorder screening (symptom pattern analysis)
        # TODO: Replace with actual disorder_screeners.py module when implemented
        screening_score = _calculate_screening_score(slots, severity_breakdown)
        
        # Step 3: Apply clinical thresholds
        screening_result, confidence = _apply_clinical_thresholds(
            screening_score, 
            severity_level,
            slots
        )
        
        # Step 4: Update state
        state["screening_result"] = screening_result
        state["screening_confidence"] = confidence
        state["screening_details"] = {
            "screening_score": screening_score,
            "severity_level": severity_level,
            "message": _get_screening_message(screening_result, screening_score)
        }
        
        logger.info(f"[SCREENING RESULT] {screening_result} (confidence: {confidence:.2f})")
        logger.info(f"[SCREENING SCORE] {screening_score}/10")
        
    except Exception as e:
        logger.error(f"[SCREENING ERROR] {e}", exc_info=True)
        # Fallback: route to diagnostic flow (safer than dismissing)
        state["screening_result"] = "disorder_suspected"
        state["screening_confidence"] = 0.6
        state["screening_details"] = {
            "reason": "error_fallback",
            "message": "Không thể đánh giá chính xác, cần đánh giá thêm"
        }
    
    logger.info("=" * 80)
    return state


def _calculate_screening_score(slots: Dict[str, Any], severity_breakdown: Dict[str, Any]) -> float:
    """
    Calculate screening score (0-10) based on symptom patterns.
    
    Generic screening criteria (not disorder-specific):
    - Symptom count and severity
    - Duration and persistence
    - Functional impairment
    - Distress level
    
    Returns: Score 0-10 where ≥7 indicates clinical level
    """
    score = 0.0
    
    # Factor 1: Severity metrics (max 4 points)
    total_score = severity_breakdown.get("total_score", 0)
    if total_score >= 8:
        score += 4
    elif total_score >= 5:
        score += 2.5
    elif total_score >= 3:
        score += 1.5
    
    # Factor 2: Duration (max 2 points)
    duration_score = severity_breakdown.get("duration_score", 0)
    if duration_score == 3:  # ≥6 months
        score += 2
    elif duration_score == 2:  # 2-6 months
        score += 1.5
    elif duration_score == 1:  # 2 weeks - 2 months
        score += 1
    
    # Factor 3: Functional impairment (max 2 points)
    impairment = slots.get("impairment", {})
    if impairment.get("work") or impairment.get("relationships") or impairment.get("daily_activities"):
        score += 2
    
    # Factor 4: Number of symptom domains (max 2 points)
    symptom_count = len(slots.get("symptoms", []))
    if symptom_count >= 5:
        score += 2
    elif symptom_count >= 3:
        score += 1
    
    logger.info(f"[SCREENING CALCULATION] Score: {score:.1f}/10")
    return min(score, 10.0)


def _apply_clinical_thresholds(
    screening_score: float, 
    severity_level: str,
    slots: Dict[str, Any]
) -> tuple[str, float]:
    """
    Apply clinical thresholds to determine screening result.
    
    Thresholds:
    - ≥7.0: disorder_suspected (clinical level)
    - 4.0-6.9: subclinical (monitoring needed)
    - <4.0: non_clinical (coping strategies sufficient)
    
    Also checks exclusion criteria to prevent false positives.
    
    Returns: (screening_result, confidence)
    """
    # Check exclusion criteria first
    if _has_exclusion_criteria(slots):
        logger.info("[SCREENING] Exclusion criteria met - non_clinical")
        return ("non_clinical", 0.75)
    
    # Apply thresholds
    if screening_score >= 7.0:
        confidence = 0.75 + min((screening_score - 7) * 0.05, 0.15)
        return ("disorder_suspected", confidence)
    
    elif screening_score >= 4.0:
        confidence = 0.65
        return ("subclinical", confidence)
    
    else:
        confidence = 0.70
        return ("non_clinical", confidence)


def _has_exclusion_criteria(slots: Dict[str, Any]) -> bool:
    """
    Check exclusion criteria that prevent disorder diagnosis.
    
    Exclusion criteria:
    - Only situational/reactive symptoms (clears when situation resolves)
    - Symptoms entirely explained by normal life stress
    - Recent acute stressor with immediate reaction
    - Very short duration (<2 weeks) with improving trend
    
    Returns: True if exclusion criteria met (should NOT diagnose disorder)
    """
    duration_text = slots.get("duration", "").lower()
    
    # Very short duration with no persistence
    if any(term in duration_text for term in ["vài ngày", "mấy ngày", "few days"]):
        logger.info("[EXCLUSION] Very short duration (<1 week)")
        return True
    
    # Check if symptoms are purely situational
    context = slots.get("context", "").lower()
    if any(term in context for term in ["thi cử", "exam", "presentation", "deadline"]) and \
       "thường xuyên" not in duration_text:
        logger.info("[EXCLUSION] Purely situational (exam/deadline stress)")
        return True
    
    return False


def _get_screening_message(screening_result: str, screening_score: float) -> str:
    """Generate Vietnamese message explaining screening result."""
    if screening_result == "disorder_suspected":
        return (
            f"Đánh giá sơ bộ cho thấy triệu chứng có thể liên quan đến rối loạn tâm lý (điểm: {screening_score:.1f}/10). "
            "Cần đánh giá chuyên sâu để xác định chẩn đoán chính xác."
        )
    elif screening_result == "subclinical":
        return (
            f"Triệu chứng ở mức độ dưới ngưỡng chẩn đoán (điểm: {screening_score:.1f}/10). "
            "Cần theo dõi và có thể cần hỗ trợ tâm lý nếu triệu chứng tiếp tục hoặc tệ hơn."
        )
    else:  # non_clinical
        return (
            f"Đánh giá cho thấy đây là phản ứng tự nhiên với tình huống (điểm: {screening_score:.1f}/10). "
            "Các chiến lược ứng phó và quản lý stress có thể hữu ích."
        )
