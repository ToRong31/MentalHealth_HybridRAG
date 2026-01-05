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


def assess_disorder_likelihood(slots: Dict[str, Any]) -> Tuple[str, str, float]:
    """
    Classify whether symptoms are normal response or disorder.
    
    This function is COMPLEMENTARY to is_diagnosis_ready():
    - is_diagnosis_ready(): "Đủ điều kiện để assess chưa?" → True/False
    - assess_disorder_likelihood(): "Đây có phải disorder không?" → 4 categories
    
    Args:
        slots: Dictionary containing extracted slot information
    
    Returns:
        Tuple of (category, explanation, confidence)
        - category: "normal_response", "adjustment_reaction", "possible_disorder", "likely_disorder"
        - explanation: Vietnamese explanation of the assessment
        - confidence: 0.0-1.0
    
    Categories:
        - normal_response: Normal stress with clear trigger, short duration, mild impact
        - adjustment_reaction: Response to life event, moderate duration/impact
        - possible_disorder: Some disorder indicators, needs monitoring
        - likely_disorder: Meets disorder criteria, should see professional
    """
    
    normal_indicators = 0
    disorder_indicators = 0
    
    # 1. Duration Analysis
    duration = slots.get("duration", "")
    if duration:
        duration_lower = duration.lower()
        
        # Very short duration → likely normal stress
        very_short_terms = ["ngày", "day", "hôm", "vài ngày", "few days"]
        if any(term in duration_lower for term in very_short_terms):
            if not any(long in duration_lower for long in ["nhiều ngày", "many days", "tuần"]):
                normal_indicators += 3
                logger.debug(f"Duration '{duration}': Very short → +3 normal")
        
        # Short duration (1-2 weeks) → consider normal if trigger present
        short_terms = ["1 tuần", "2 tuần", "một tuần", "hai tuần", "1 week", "2 week"]
        if any(term in duration_lower for term in short_terms):
            normal_indicators += 2
            logger.debug(f"Duration '{duration}': Short (1-2 weeks) → +2 normal")
        
        # Medium duration (3-8 weeks) → adjustment reaction territory
        medium_terms = ["3 tuần", "4 tuần", "tháng", "month"]
        medium_exclude = ["6 tháng", "7 tháng", "8 tháng", "9 tháng", "nhiều tháng"]
        if any(term in duration_lower for term in medium_terms) and not any(ex in duration_lower for ex in medium_exclude):
            # Neither normal nor disorder - neutral
            logger.debug(f"Duration '{duration}': Medium (3-8 weeks) → adjustment territory")
        
        # Long duration (≥6 months) → consider disorder
        long_terms = ["6 tháng", "7 tháng", "8 tháng", "9 tháng", "10 tháng", "11 tháng", 
                      "năm", "year", "nhiều tháng", "many months"]
        if any(term in duration_lower for term in long_terms):
            disorder_indicators += 2
            logger.debug(f"Duration '{duration}': Long (≥6 months) → +2 disorder")
    
    # 2. Trigger/Life Event Analysis
    recent_events = slots.get("recent_life_events", "")
    if recent_events:
        event_lower = recent_events.lower()
        
        # Clear, specific triggers → normal stress response
        normal_triggers = [
            "thuyết trình", "presentation", "thi", "exam", "kiểm tra", "test",
            "deadline", "dự án", "project",
            "họp", "meeting", "phỏng vấn", "interview",
            "tranh cãi", "conflict", "cãi nhau",
            "báo cáo", "report", "nộp bài", "submission"
        ]
        if any(trigger in event_lower for trigger in normal_triggers):
            normal_indicators += 2
            logger.debug(f"Trigger '{recent_events}': Normal trigger identified → +2 normal")
        
        # Major life events → adjustment reaction
        adjustment_triggers = [
            "chia tay", "breakup", "ly hôn", "divorce",
            "mất việc", "job loss", "thất nghiệp", "unemployed",
            "chuyển nhà", "moving", "di chuyển",
            "mất người thân", "loss", "qua đời", "death",
            "bệnh nặng", "illness", "tai nạn", "accident"
        ]
        if any(trigger in event_lower for trigger in adjustment_triggers):
            # Major life event - not normal stress but not necessarily disorder
            logger.debug(f"Trigger '{recent_events}': Major life event → adjustment reaction")
    else:
        # No identifiable trigger → lean toward disorder
        disorder_indicators += 1
        logger.debug("No clear trigger identified → +1 disorder")
    
    # 3. Daily Functioning & Impairment
    daily_functioning = slots.get("daily_functioning", "")
    work_impact = slots.get("work_school_impact", "")
    
    # Minimal impairment → normal
    if daily_functioning in ["normal", "bình thường"] or work_impact in ["none", "minimal", "không", "ít"]:
        normal_indicators += 1
        logger.debug(f"Functioning '{daily_functioning}' / Work impact '{work_impact}': Minimal impairment → +1 normal")
    
    # Mild impairment → could be normal or adjustment
    elif daily_functioning in ["mild", "mild_impairment", "nhẹ"] or work_impact in ["mild", "nhẹ"]:
        # Neutral - doesn't add to either side
        logger.debug(f"Functioning '{daily_functioning}' / Work impact '{work_impact}': Mild impairment → neutral")
    
    # Moderate to severe impairment → disorder
    elif daily_functioning in ["moderate", "severe", "vừa", "nặng"] or work_impact in ["moderate", "severe", "unable", "vừa", "nặng", "không thể"]:
        disorder_indicators += 2
        logger.debug(f"Functioning '{daily_functioning}' / Work impact '{work_impact}': Significant impairment → +2 disorder")
    
    # 4. Symptom Pattern & Fluctuation
    symptom_fluctuation = slots.get("symptom_fluctuation", "")
    if symptom_fluctuation:
        pattern_lower = symptom_fluctuation.lower()
        
        # Episodic/situational → normal
        situational_terms = ["tình huống", "situational", "thỉnh thoảng", "sometimes", 
                             "khi", "when", "lúc", "moment", "đôi khi"]
        if any(term in pattern_lower for term in situational_terms):
            normal_indicators += 1
            logger.debug(f"Pattern '{symptom_fluctuation}': Situational/episodic → +1 normal")
        
        # Persistent/continuous → disorder
        persistent_terms = ["liên tục", "continuous", "suốt", "always", "luôn", 
                           "không ngừng", "non-stop", "hằng ngày", "daily"]
        if any(term in pattern_lower for term in persistent_terms):
            disorder_indicators += 1
            logger.debug(f"Pattern '{symptom_fluctuation}': Persistent/continuous → +1 disorder")
    
    # 5. Intensity/Severity
    intensity = slots.get("intensity", "")
    if intensity:
        intensity_lower = intensity.lower()
        
        # Low to medium intensity → normal
        if intensity in ["low", "medium", "thấp", "vừa"] or any(term in intensity_lower for term in ["nhẹ", "bình thường"]):
            normal_indicators += 1
            logger.debug(f"Intensity '{intensity}': Low to medium → +1 normal")
        
        # High to very high intensity → disorder
        elif intensity in ["high", "very_high", "cao", "rất cao"] or any(term in intensity_lower for term in ["nặng", "nghiêm trọng"]):
            disorder_indicators += 1
            logger.debug(f"Intensity '{intensity}': High to very high → +1 disorder")
    
    # 6. Physical Symptoms & Medical Factors
    physical_symptoms = slots.get("physical_symptoms", [])
    medical_history = slots.get("medical_history")
    substance_use = slots.get("substance_use")
    
    # If physical symptoms present but medical causes not ruled out → cannot conclude disorder
    if physical_symptoms and (medical_history is None or substance_use is None):
        disorder_indicators -= 1
        logger.debug("Physical symptoms present but medical causes not ruled out → -1 disorder")
    
    # 7. Risk Level (from previous assessments)
    risk_level = slots.get("risk_level", "")
    if risk_level in ["high", "very_high", "cao", "rất cao"]:
        disorder_indicators += 2
        logger.debug(f"Risk level '{risk_level}': High risk → +2 disorder")
    
    # 8. Coping & Support (protective factors)
    coping_strategies = slots.get("coping_strategies", "")
    social_support = slots.get("social_support", "")
    
    # Good coping + support → less likely to be disorder
    if coping_strategies and "effective" in str(coping_strategies).lower():
        normal_indicators += 1
        logger.debug("Effective coping strategies present → +1 normal")
    
    if social_support and social_support not in ["none", "poor", "không", "kém"]:
        normal_indicators += 1
        logger.debug(f"Social support present: '{social_support}' → +1 normal")
    
    # === DECISION LOGIC ===
    total_score = normal_indicators - disorder_indicators
    
    logger.info(f"[ASSESSMENT] Normal indicators: {normal_indicators}, Disorder indicators: {disorder_indicators}, Score: {total_score}")
    
    # Category Decision Tree
    if total_score >= 4:
        category = "normal_response"
        explanation = (
            "Các dấu hiệu cho thấy đây là phản ứng stress bình thường với tình huống cụ thể. "
            "Có trigger rõ ràng, thời gian ngắn, và mức độ ảnh hưởng nhẹ. "
            "Đây KHÔNG phải là rối loạn tâm lý."
        )
        confidence = min(0.7 + (total_score - 4) * 0.05, 0.95)
    
    elif total_score >= 1:
        category = "adjustment_reaction"
        explanation = (
            "Có thể là phản ứng điều chỉnh (adjustment reaction) với biến cố sống hoặc stress kéo dài. "
            "Đây là phản ứng tự nhiên của cơ thể nhưng có thể cần hỗ trợ để điều chỉnh tốt hơn. "
            "Chưa đủ tiêu chuẩn chẩn đoán rối loạn tâm lý."
        )
        confidence = 0.65 + (total_score - 1) * 0.05
    
    elif total_score >= -2:
        category = "possible_disorder"
        explanation = (
            "Một số dấu hiệu gợi ý khả năng rối loạn tâm lý, nhưng chưa đủ rõ ràng để kết luận. "
            "Cần theo dõi thêm về mức độ, thời gian, và tác động. "
            "Nên tự theo dõi triệu chứng và cân nhắc tham khảo ý kiến chuyên gia nếu không cải thiện."
        )
        confidence = 0.6
    
    else:
        category = "likely_disorder"
        explanation = (
            "Các dấu hiệu đáp ứng nhiều tiêu chuẩn của rối loạn tâm lý: "
            "thời gian kéo dài, ảnh hưởng nghiêm trọng đến cuộc sống, và/hoặc mức độ nặng. "
            "Mình khuyên bạn nên gặp chuyên gia (tâm lý sư hoặc bác sĩ) để được đánh giá chính xác và hỗ trợ phù hợp."
        )
        confidence = 0.65 + min(abs(total_score) - 2, 5) * 0.05
    
    logger.info(f"[ASSESSMENT RESULT] Category: {category}, Confidence: {confidence:.2f}")
    logger.debug(f"[ASSESSMENT EXPLANATION] {explanation}")
    
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
