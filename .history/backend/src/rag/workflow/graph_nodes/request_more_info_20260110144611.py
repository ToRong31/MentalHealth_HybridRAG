"""
Request More Info Node
Return follow-up questions when insufficient REQUIRED slots are filled
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


# Emotion mapping: English -> Vietnamese
EMOTION_MAPPING = {
    "anxious": "lo lắng",
    "sad": "buồn bã",
    "stressed": "căng thẳng",
    "depressed": "trầm cảm",
    "angry": "tức giận",
    "frustrated": "thất vọng",
    "hopeless": "vô vọng",
    "overwhelmed": "choáng ngợp",
    "tired": "mệt mỏi",
    "exhausted": "kiệt sức",
    "worried": "lo lắng",
    "nervous": "bồn chồn",
    "fearful": "sợ hãi",
    "panicked": "hoảng loạn",
    "guilty": "tội lỗi",
    "irritable": "cáu kỉnh",
    "restless": "bồn chồn",
    "lonely": "cô đơn",
}


def build_empathy_from_slots(slots: Dict[str, Any]) -> str:
    """
    Intelligent fallback: Build empathy preamble from existing slots
    Follows user's specification from scenario
    """
    emotion = slots.get("emotion", "")
    presenting_problem = slots.get("presenting_problem", "")
    trigger = slots.get("trigger", "")
    current_stressors = slots.get("current_stressors", "")
    
    # Map English emotion to Vietnamese
    emotion_vi = ""
    if emotion and emotion.lower() in EMOTION_MAPPING:
        emotion_vi = EMOTION_MAPPING[emotion.lower()]
    
    # Case 1: Has emotion + (presenting_problem OR trigger OR current_stressors)
    if emotion_vi and (presenting_problem or trigger or current_stressors):
        return f"Mình nghe bạn đang cảm thấy {emotion_vi}, và những điều gần đây đang xảy ra có vẻ đã ảnh hưởng đến bạn khá nhiều."
    
    # Case 2: Has only emotion
    if emotion_vi:
        return f"Mình nghe bạn đang cảm thấy {emotion_vi}."
    
    # Case 3: Has presenting_problem or stressors but no emotion
    if presenting_problem or trigger or current_stressors:
        return "Mình nghe những gì bạn chia sẻ và hiểu rằng những điều gần đây đã ảnh hưởng đến bạn khá nhiều."
    
    # Case 4: Insufficient data - generic empathy (safe default)
    return "Mình nghe những gì bạn chia sẻ và hiểu rằng điều này có thể đang khiến bạn khá nặng lòng."


# Mapping: slot -> Vietnamese question (SPECIFIC, not generic)
SLOT_QUESTIONS = {
    # Stage 1: Presenting (Initial Assessment)
    "emotion": "Bạn đang cảm thấy cảm xúc gì cụ thể? (ví dụ: buồn, lo lắng, tức giận, mệt mỏi...)",
    "presenting_problem": "Vấn đề chính khiến bạn tìm đến hỗ trợ là gì?",
    "primary_mood": "Trạng thái tâm trạng tổng thể của bạn hiện tại như thế nào?",
    
    # Stage 2: Timeline
    "frequency": "Tình trạng này diễn ra với tần suất như thế nào? (mỗi ngày, vài lần/tuần, thỉnh thoảng...)",
    "duration": "Tình trạng này đã kéo dài bao lâu rồi? (số ngày, tuần, hoặc tháng cụ thể)",
    "onset": "Tình trạng này bắt đầu từ khi nào? (số ngày/tuần/tháng trước, hoặc thời điểm cụ thể)",
    "symptom_fluctuation": "Triệu chứng có thay đổi theo thời gian không? (liên tục, lúc tốt lúc xấu, theo chu kỳ...)",
    
    # Stage 3: Severity
    "intensity": "Mức độ nghiêm trọng của triệu chứng này? (nhẹ, trung bình, nặng, rất nặng)",
    "distress_level": "Mức độ khó chịu/đau khổ mà bạn đang trải qua? (có thể cho điểm từ 0-10)",
    "stress_level": "Mức độ căng thẳng hiện tại của bạn? (thấp, trung bình, cao, quá tải)",
    
    # Stage 4: Functioning/Impact
    "daily_functioning": "Khả năng thực hiện các hoạt động hàng ngày của bạn có bị ảnh hưởng không? (ví dụ: tắm rửa, ăn uống, dọn dẹp)",
    "work_school_impact": "Tình trạng này có ảnh hưởng đến công việc hoặc học tập của bạn không? (vắng mặt, giảm năng suất, khó tập trung...)",
    "social_functioning": "Các mối quan hệ và hoạt động xã hội của bạn có bị ảnh hưởng không? (tránh gặp bạn bè, xung đột gia đình...)",
    "self_care_functioning": "Bạn vẫn tự chăm sóc vệ sinh cá nhân và ăn uống đầy đủ được không?",
    
    # Stage 5: Context
    "trigger": "Có sự kiện hoặc tình huống nào cụ thể khiến bạn cảm thấy như vậy không?",
    "current_stressors": "Hiện tại bạn đang phải đối mặt với áp lực gì? (công việc, gia đình, tài chính...)",
    "recent_life_events": "Gần đây có sự kiện quan trọng nào xảy ra trong cuộc sống bạn không? (chuyển nhà, mất việc, chia tay...)",
    
    # Stage 6: Exclusion Criteria
    "substance_use_any": "Bạn có sử dụng rượu, thuốc lá, hoặc chất kích thích nào không?",
    "medical_history_any": "Bạn có tiền sử bệnh lý nào không? (tuyến giáp, tim mạch, tiểu đường...)",
    "medication_changes": "Gần đây bạn có thay đổi thuốc hoặc bắt đầu dùng thuốc mới không?",
    "caffeine_nicotine_use": "Bạn có uống cà phê, trà, hoặc hút thuốc lá không? Mức độ ra sao?",
    
    # Stage 7: Support/Coping
    "support_system": "Bạn có người thân, bạn bè, hoặc ai đó để chia sẻ và hỗ trợ không?",
    "coping_mechanisms": "Bạn thường làm gì để đối phó với căng thẳng? (tập thể dục, nghe nhạc, nói chuyện...)",
    
    # Stage 8: Screens
    "mania_like_symptoms": "Bạn có trải qua giai đoạn nào ngủ ít nhưng vẫn tràn đầy năng lượng, bốc đồng, hoặc suy nghĩ chạy nhanh không?",
    "psychotic_like_symptoms": "Bạn có nghe thấy hoặc nhìn thấy điều gì mà người khác không thấy không? Hoặc có cảm giác bị theo dõi/đe dọa không?",
    
    # Additional fields
    "sleep_quality": "Giấc ngủ của bạn như thế nào? (khó ngủ, thức giấc nhiều, ngủ quá nhiều...)",
    "energy_level": "Mức năng lượng của bạn hiện tại? (rất thấp, mệt mỏi, bình thường, cao)",
    "appetite_changes": "Khẩu vị ăn uống của bạn có thay đổi không? (ăn ít hơn, ăn nhiều hơn, không thay đổi)",
}


def generate_questions_from_slots(missing_slots: List[str], max_questions: int = 3) -> List[str]:
    """
    Generate natural follow-up questions from missing REQUIRED slots.
    Fallback when LLM doesn't generate questions.
    
    STRICT RULES:
    - Maximum 3 questions per turn
    - Questions must be SPECIFIC to the missing slot
    - Prioritize Stage 1-3 slots over others
    
    Args:
        missing_slots: List of missing required slot names
        max_questions: Maximum number of questions to generate (default 3)
    
    Returns:
        List of Vietnamese questions to ask (max 3)
    """
    # Prioritization: Stage 1-2 (presenting, timeline) > Stage 3-4 (severity, functioning) > Stage 5-8
    PRIORITY_ORDER = [
        # Stage 1-2: Most critical
        "emotion", "presenting_problem", "primary_mood",
        "onset", "duration", "frequency",
        # Stage 3: Severity
        "intensity", "distress_level", "stress_level",
        # Stage 4: Functioning
        "daily_functioning", "work_school_impact", "social_functioning",
        # Stage 5: Context
        "trigger", "current_stressors", "recent_life_events",
        # Stage 6-8: Exclusion & screens
        "substance_use_any", "medical_history_any", "medication_changes",
        "support_system", "coping_mechanisms",
        "mania_like_symptoms", "psychotic_like_symptoms",
    ]
    
    # Sort missing slots by priority
    prioritized_slots = []
    for slot in PRIORITY_ORDER:
        if slot in missing_slots:
            prioritized_slots.append(slot)
    
    # Add remaining slots not in priority list
    for slot in missing_slots:
        if slot not in prioritized_slots:
            prioritized_slots.append(slot)
    
    # Generate questions for top N slots
    questions = []
    for slot in prioritized_slots[:max_questions]:
        if slot in SLOT_QUESTIONS:
            questions.append(SLOT_QUESTIONS[slot])
        else:
            # Fallback if slot not in mapping
            logger.warning(f"⚠️ No question template for slot: {slot}")
    
    return questions


async def request_more_info_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Handle insufficient REQUIRED slots by returning follow-up questions.
    Questions have been filtered to only ask about REQUIRED_SLOTS.
    
    ENFORCES:
    - Minimum 1 question if required slots missing
    - Maximum 3 questions per turn
    - Questions must be SPECIFIC (not generic)
    - Empathy-based preamble instead of generic opening
    
    Args:
        state: State dict with follow_up_questions (already filtered for REQUIRED), required_missing_slots
    
    Returns:
        Updated state with answer containing follow-up questions and done=True
    """
    follow_up_questions = state.get("follow_up_questions", [])
    required_missing = state.get("required_missing_slots", [])
    slots = state.get("slots", {})
    empathy_preamble_vi = state.get("empathy_preamble_vi", "")
    
    logger.info(f"Insufficient REQUIRED slots filled. Requesting more information.")
    logger.info(f"Missing REQUIRED slots: {required_missing[:10]}...")  # Show first 10
    
    # STRICT ENFORCEMENT: If required slots missing but NO questions → Auto-generate
    if required_missing and not follow_up_questions:
        logger.warning(f"⚠️ CRITICAL: {len(required_missing)} required slots missing but NO follow-up questions!")
        logger.warning(f"   This should not happen - LLM validation failed")
        logger.warning(f"   Auto-generating fallback questions...")
        follow_up_questions = generate_questions_from_slots(required_missing, max_questions=3)
        logger.info(f"   → Generated {len(follow_up_questions)} fallback questions")
    
    # LIMIT ENFORCEMENT: Ensure max 3 questions
    if len(follow_up_questions) > 3:
        logger.warning(f"⚠️ Too many questions ({len(follow_up_questions)}), trimming to 3")
        follow_up_questions = follow_up_questions[:3]
    
    # ========== EMPATHY PREAMBLE SELECTION ==========
    # Priority: 1. LLM-generated → 2. Slot-based fallback → 3. Generic default
    empathy = ""
    if empathy_preamble_vi and empathy_preamble_vi.strip() and "?" not in empathy_preamble_vi:
        # Use LLM-generated empathy (validated: not empty, no question marks)
        empathy = empathy_preamble_vi.strip()
        logger.info(f"✅ Using LLM-generated empathy: '{empathy[:50]}...'")
    else:
        # Fallback: Build from slots
        empathy = build_empathy_from_slots(slots)
        logger.info(f"🔄 Using slot-based fallback empathy: '{empathy[:50]}...'")
    
    # Build response with follow-up questions
    if follow_up_questions:
        # Natural Vietnamese response with empathy preamble
        if len(follow_up_questions) == 1:
            # Single question - more natural
            answer = f"{empathy}\n\nĐể mình hiểu rõ hơn và cùng bạn tìm hướng phù hợp, bạn cho mình biết thêm:\n\n{follow_up_questions[0]}"
        else:
            # Multiple questions - numbered list
            question_list = "\n".join([f"{i}. {q}" for i, q in enumerate(follow_up_questions, 1)])
            answer = f"{empathy}\n\nĐể mình hiểu rõ hơn và cùng bạn tìm hướng phù hợp, bạn cho mình biết thêm:\n\n{question_list}"
    else:
        # Final fallback (should rarely reach here)
        logger.error("❌ CRITICAL: No questions generated even after fallback!")
        answer = "Bạn có thể chia sẻ thêm về:\n\n1. Tình trạng này bắt đầu từ khi nào?\n2. Đã kéo dài bao lâu rồi?\n3. Mức độ nghiêm trọng ra sao?"
    
    logger.info(f"Requesting more info with {len(follow_up_questions)} SPECIFIC questions")
    for i, q in enumerate(follow_up_questions, 1):
        logger.info(f"  Q{i}: {q[:80]}...")
    
    # Update state
    state["answer"] = answer
    state["done"] = True
    state["needs_more_info"] = True  # Flag to indicate this is a request for more info
    
    return state
