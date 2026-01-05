"""
Assessment Module - Disorder Likelihood Classification (Score-Based)

This module provides functions to assess whether symptoms indicate:
- normal_stress: Normal stress response (route to normal coping advice)
- adjustment_reaction: Adjustment to life event (route to adjustment support)
- possible_disorder: Some indicators, needs monitoring (route to diagnostic)
- likely_disorder: Meets disorder criteria (route to diagnostic)

Logic:
1. Match symptoms/factors from normal_responses.jsonl database
2. Calculate max_item_score and total_score (sum of item scores + duration score)
3. Parse duration into D score (0-3)
4. Apply decision rules:
   - Normal/Low Risk: max_item_score ≤ 3 AND D ≤ 1 AND total_score ≤ 4
   - Otherwise: Route to diagnostic or support based on type

PREREQUISITE: is_diagnosis_ready() = True (from slots.py)
"""

from typing import Dict, Any, Tuple, List
import re
import logging

logger = logging.getLogger(__name__)


def parse_duration_score(duration_text: str) -> int:
    """
    Parse duration text into a score D.
    
    Args:
        duration_text: Duration description from slots (e.g., "3 tuần", "6 tháng", "vài ngày")
    
    Returns:
        D score:
        - 0: < 2 weeks (Transient/Acute)
        - 1: 2 weeks to < 1 month (Short-term)
        - 2: 1 month to < 6 months (Medium-term)
        - 3: ≥ 6 months (Chronic)
    """
    if not duration_text:
        logger.warning("Empty duration text, defaulting to D=0")
        return 0
    
    duration_lower = duration_text.lower()
    
    # Extract numbers from text
    numbers = re.findall(r'\d+', duration_lower)
    
    # D = 3: ≥ 6 months (Chronic)
    chronic_terms = [
        "năm", "year", "years",
        "6 tháng", "7 tháng", "8 tháng", "9 tháng", "10 tháng", "11 tháng", "12 tháng",
        "nhiều tháng", "many months", "several months"
    ]
    if any(term in duration_lower for term in chronic_terms):
        logger.debug(f"Duration '{duration_text}': Chronic (≥6 months) → D=3")
        return 3
    
    # Check for specific month numbers ≥ 6
    if "tháng" in duration_lower or "month" in duration_lower:
        for num_str in numbers:
            num = int(num_str)
            if num >= 6:
                logger.debug(f"Duration '{duration_text}': {num} months → D=3")
                return 3
            elif num >= 1:
                # 1-5 months → D=2
                logger.debug(f"Duration '{duration_text}': {num} months → D=2")
                return 2
    
    # D = 2: 1 month to < 6 months (Medium-term)
    medium_terms = ["tháng", "month", "3 tuần", "4 tuần", "5 tuần"]
    if any(term in duration_lower for term in medium_terms):
        logger.debug(f"Duration '{duration_text}': Medium-term (1-6 months) → D=2")
        return 2
    
    # D = 1: 2 weeks to < 1 month (Short-term)
    short_terms = ["2 tuần", "3 tuần", "hai tuần", "ba tuần", "2 week", "3 week"]
    if any(term in duration_lower for term in short_terms):
        logger.debug(f"Duration '{duration_text}': Short-term (2 weeks - 1 month) → D=1")
        return 1
    
    # D = 0: < 2 weeks (Transient/Acute)
    acute_terms = [
        "ngày", "day", "days", "hôm", "vài ngày", "few days",
        "1 tuần", "một tuần", "1 week", "one week", "mấy ngày"
    ]
    if any(term in duration_lower for term in acute_terms):
        logger.debug(f"Duration '{duration_text}': Transient/Acute (<2 weeks) → D=0")
        return 0
    
    # Default: Assume acute if unclear
    logger.warning(f"Duration '{duration_text}': Unable to parse clearly, defaulting to D=0")
    return 0


def calculate_scores(matched_items: List[Dict[str, Any]], duration_score: int) -> Tuple[int, int]:
    """
    Calculate max_item_score and total_score.
    
    Args:
        matched_items: List of matched items from normal_responses.jsonl
        duration_score: D score from parse_duration_score()
    
    Returns:
        Tuple of (max_item_score, total_score)
        - max_item_score: Highest individual score among matched items
        - total_score: Sum(item.score) + duration_score
    """
    if not matched_items:
        logger.info("No matched items, scores = (0, duration_score)")
        return (0, duration_score)
    
    item_scores = [item.get("score", 0) for item in matched_items]
    max_item_score = max(item_scores) if item_scores else 0
    total_score = sum(item_scores) + duration_score
    
    logger.info(f"Calculated scores: max_item_score={max_item_score}, sum(items)={sum(item_scores)}, D={duration_score}, total={total_score}")
    
    return (max_item_score, total_score)


def determine_route_type(matched_items: List[Dict[str, Any]]) -> str:
    """
    Determine routing type based on most frequent 'type' in matched items.
    
    Args:
        matched_items: List of matched items from normal_responses.jsonl
    
    Returns:
        "normal_stress" or "adjustment_reaction" based on majority
    """
    if not matched_items:
        logger.info("No matched items, defaulting to 'normal_stress'")
        return "normal_stress"
    
    type_counts = {"normal_stress": 0, "adjustment_reaction": 0}
    
    for item in matched_items:
        item_type = item.get("type", "").replace(" ", "_")  # "normal stress" → "normal_stress"
        if item_type in type_counts:
            type_counts[item_type] += 1
    
    # Return the type with higher count
    route_type = max(type_counts, key=type_counts.get)
    
    logger.info(f"Type distribution: {type_counts} → Route to '{route_type}'")
    
    return route_type


def assess_disorder_likelihood(slots: Dict[str, Any], matched_items: List[Dict[str, Any]] = None) -> Tuple[str, str, float]:
    """
    Classify whether symptoms are normal response or disorder using score-based logic.
    
    This function is COMPLEMENTARY to is_diagnosis_ready():
    - is_diagnosis_ready(): "Đủ điều kiện để assess chưa?" → True/False
    - assess_disorder_likelihood(): "Đây có phải disorder không?" → 4 categories
    
    Args:
        slots: Dictionary containing extracted slot information
        matched_items: List of matched items from normal_responses.jsonl database
    
    Returns:
        Tuple of (category, explanation, confidence)
        - category: "normal_stress", "adjustment_reaction", "possible_disorder", "likely_disorder"
        - explanation: Vietnamese explanation of the assessment
        - confidence: 0.0-1.0
    
    Decision Rules:
        - Normal/Low Risk: max_item_score ≤ 3 AND D ≤ 1 AND total_score ≤ 4
          → Route to "normal_stress" or "adjustment_reaction" based on type
        - Otherwise: Route to "possible_disorder" or "likely_disorder" for diagnostic
    """
    
    # Handle empty matched_items
    if matched_items is None:
        matched_items = []
        logger.warning("No matched_items provided, will use only duration-based assessment")
    
    # Check for emergency situations (score 99)
    emergency_items = [item for item in matched_items if item.get("score", 0) == 99]
    if emergency_items:
        emergency_titles = [item.get("title", "") for item in emergency_items]
        logger.critical(f"EMERGENCY: Detected critical symptoms: {emergency_titles}")
        return (
            "likely_disorder",
            f"⚠️ CẢNH BÁO: Phát hiện dấu hiệu nghiêm trọng ({', '.join(emergency_titles)}). "
            "Đây là tình huống khẩn cấp cần được chuyên gia y tế đánh giá ngay lập tức. "
            "Vui lòng liên hệ hotline khủng hoảng hoặc đến cơ sở y tế gần nhất.",
            0.95
        )
    
    # Step 1: Parse duration score
    duration_text = slots.get("duration", "")
    D = parse_duration_score(duration_text)
    
    # Step 2: Calculate scores
    max_item_score, total_score = calculate_scores(matched_items, D)
    
    # Step 3: Determine route type
    route_type = determine_route_type(matched_items)
    
    # Step 4: Apply decision rules
    logger.info(f"[DECISION] max_item_score={max_item_score}, D={D}, total_score={total_score}")
    
    # === DECISION LOGIC ===
    # Normal/Low Risk: max_item_score ≤ 3 AND D ≤ 1 AND total_score ≤ 4
    if max_item_score <= 3 and D <= 1 and total_score <= 4:
        category = route_type  # "normal_stress" or "adjustment_reaction"
        
        if route_type == "normal_stress":
            explanation = (
                "Các dấu hiệu cho thấy đây là phản ứng stress bình thường với tình huống cụ thể. "
                "Triệu chứng có mức độ nhẹ, thời gian ngắn, và chưa ảnh hưởng nghiêm trọng đến cuộc sống. "
                "Đây KHÔNG phải là rối loạn tâm lý."
            )
            confidence = 0.75
        else:  # adjustment_reaction
            explanation = (
                "Đây có thể là phản ứng điều chỉnh (adjustment reaction) với biến cố sống hoặc áp lực. "
                "Đây là phản ứng tự nhiên nhưng bạn có thể cần hỗ trợ để thích nghi tốt hơn. "
                "Chưa đủ tiêu chuẩn chẩn đoán rối loạn tâm lý."
            )
            confidence = 0.70
        
        logger.info(f"[RESULT] Category: {category} (Normal/Low Risk) - Confidence: {confidence:.2f}")
        
    # High scores or long duration → Need professional assessment
    else:
        # Determine severity: possible_disorder vs likely_disorder
        if max_item_score >= 5 or D >= 3 or total_score >= 8:
            category = "likely_disorder"
            explanation = (
                "Các dấu hiệu cho thấy khả năng cao đây là rối loạn tâm lý cần được chuyên gia đánh giá: "
                f"Triệu chứng có mức độ cao (điểm cao nhất: {max_item_score}), "
                f"thời gian kéo dài (mức độ: {D}), "
                f"và tổng điểm đánh giá là {total_score}. "
                "Mình khuyên bạn nên gặp chuyên gia (tâm lý sư hoặc bác sĩ) để được đánh giá chính xác và hỗ trợ phù hợp."
            )
            confidence = 0.75 + min((total_score - 8) * 0.02, 0.15)
        else:
            category = "possible_disorder"
            explanation = (
                "Một số dấu hiệu gợi ý khả năng rối loạn tâm lý, nhưng chưa đủ rõ ràng để kết luận. "
                f"Triệu chứng có mức độ trung bình (điểm: {max_item_score}), "
                f"thời gian: mức {D}, tổng điểm: {total_score}. "
                "Cần theo dõi thêm về mức độ, thời gian, và tác động. "
                "Nên tự theo dõi triệu chứng và cân nhắc tham khảo ý kiến chuyên gia nếu không cải thiện."
            )
            confidence = 0.60
        
        logger.info(f"[RESULT] Category: {category} (Needs Assessment) - Confidence: {confidence:.2f}")
    
    # Log matched items for debugging
    if matched_items:
        item_summary = [f"{item.get('title', 'Unknown')} (score={item.get('score', 0)}, type={item.get('type', 'N/A')})" 
                       for item in matched_items[:5]]
        logger.debug(f"Matched items (first 5): {item_summary}")
    
    return (category, explanation, confidence)


def should_retrieve_disorder_content(slots: Dict[str, Any]) -> bool:
    """
    Decide whether to retrieve disorder-specific content or normal coping content.
    
    This function integrates with is_diagnosis_ready() from slots.py.
    
    Args:
        slots: Dictionary containing extracted slot information
    
    Returns:
        True if should retrieve disorder content
        False if should focus on coping/stress management
    
    Logic:
        1. Check is_diagnosis_ready() first
        2. If True, run assess_disorder_likelihood()
        3. Route based on category:
           - normal_response, adjustment_reaction → False (coping content)
           - possible_disorder, likely_disorder → True (disorder content)
    """
    from .slots import is_diagnosis_ready
    
    # Prerequisite: Must have sufficient data
    if not is_diagnosis_ready(slots):
        logger.info("[RETRIEVAL DECISION] Not diagnosis-ready → focus on information gathering")
        return False
    
    # Assess disorder likelihood
    category, explanation, confidence = assess_disorder_likelihood(slots)
    
    # Route based on category
    if category in ["normal_response", "adjustment_reaction"]:
        logger.info(f"[RETRIEVAL DECISION] Category '{category}' → retrieve COPING/STRESS content")
        return False
    
    elif category in ["possible_disorder", "likely_disorder"]:
        logger.info(f"[RETRIEVAL DECISION] Category '{category}' → retrieve DISORDER content")
        return True
    
    else:
        # Fallback - default to False (safer to not pathologize)
        logger.warning(f"[RETRIEVAL DECISION] Unknown category '{category}' → default to coping content")
        return False


def get_assessment_context(slots: Dict[str, Any]) -> str:
    """
    Generate assessment context string for prompt injection.
    
    Args:
        slots: Dictionary containing extracted slot information
    
    Returns:
        Formatted string with assessment information for LLM prompt
    """
    from .slots import is_diagnosis_ready
    
    if not is_diagnosis_ready(slots):
        return "Assessment: Insufficient information for disorder assessment. Focus on information gathering."
    
    category, explanation, confidence = assess_disorder_likelihood(slots)
    
    context = f"""
Assessment Category: {category}
Assessment Explanation: {explanation}
Confidence Level: {confidence:.2f}

Response Guidelines:
"""
    
    if category == "normal_response":
        context += """- VALIDATE: Acknowledge this is a normal response to the situation
- NORMALIZE: Reassure that many people experience this
- EDUCATE: Explain this is NOT a disorder
- COPING: Provide practical coping strategies
- REASSURE: Explain symptoms typically improve when situation resolves"""
    
    elif category == "adjustment_reaction":
        context += """- VALIDATE: Acknowledge the challenge of the life event
- EDUCATE: Explain adjustment reactions vs disorders
- SUPPORT: Provide adjustment and coping guidance
- TIMELINE: Mention typical improvement timeline (weeks to months)
- MONITOR: Suggest self-monitoring and seeking help if worsens"""
    
    elif category == "possible_disorder":
        context += """- CAUTIOUS: Some indicators present but not conclusive
- EDUCATE: Mention the symptoms could be related to...
- NO DIAGNOSIS: Emphasize only professionals can diagnose
- MONITOR: Recommend self-monitoring for X weeks
- REFER: Suggest seeing professional if symptoms persist or worsen"""
    
    elif category == "likely_disorder":
        context += """- ACKNOWLEDGE: Symptoms suggest possible disorder
- CAUTION: Only professionals can provide definitive diagnosis
- RECOMMEND: Strongly encourage seeing therapist or doctor
- SUPPORT: Provide interim coping strategies while awaiting appointment
- NORMALIZE HELP-SEEKING: Reassure that seeking help is strength"""
    
    return context
