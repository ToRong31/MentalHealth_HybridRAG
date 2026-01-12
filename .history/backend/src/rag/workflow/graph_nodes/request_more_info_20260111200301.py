"""
Request More Info Node
Return follow-up questions when insufficient REQUIRED slots are filled
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


# Emotion mapping: English → Vietnamese
EMOTION_MAP = {
    "anxious": "lo lắng",
    "anxiety": "lo lắng",
    "worried": "lo lắng",
    "nervous": "bồn chồn",
    
    "sad": "buồn",
    "sadness": "buồn bã",
    "depressed": "trầm buồn",
    "down": "chán nản",
    "unhappy": "không vui",
    "hopeless": "tuyệt vọng",
    
    "stressed": "căng thẳng",
    "overwhelmed": "quá tải",
    "pressure": "áp lực",
    
    "angry": "tức giận",
    "irritable": "cáu gắt",
    "frustrated": "bực bội",
    
    "tired": "mệt mỏi",
    "exhausted": "kiệt sức",
    "fatigue": "mệt mỏi",
    
    "scared": "sợ hãi",
    "fearful": "lo sợ",
    "panic": "hoảng loạn",
    
    "numb": "tê liệt",
    "empty": "trống rỗng",
    "disconnected": "mất kết nối",
}


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
    Used as fallback when LLM fails to generate questions.
    
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
    
    # If still no questions, use generic Stage 1-2 questions
    if not questions:
        questions = [
            "Tình trạng này bắt đầu từ khi nào? (số ngày/tuần/tháng)",
            "Đã kéo dài bao lâu rồi?",
            "Mức độ nghiêm trọng ra sao?"
        ][:max_questions]
    
    return questions


def filter_redundant_questions(questions: List[str], slots: Dict[str, Any]) -> List[str]:
    """
    Filter out questions that ask about slots already filled.
    Uses keyword matching to detect if a question is about an already-filled slot.
    
    Args:
        questions: List of follow-up questions
        slots: Current slot values
        
    Returns:
        Filtered questions with redundant ones removed
    """
    from src.rag.utils.slots import is_empty_slot
    
    filtered = []
    
    # Build mapping of keywords to slots
    slot_keywords = {
        "self_care_functioning": ["ăn uống", "vệ sinh", "tắm", "chăm sóc", "ăn", "tắm rửa"],
        "medical_history_any": ["bệnh nền", "tiền sử", "bệnh lý", "bệnh"],
        "medical_history": ["bệnh nền", "tiền sử", "bệnh lý"],
        "substance_use_any": ["chất kích thích", "ma túy", "rượu", "thuốc"],
        "substance_use": ["chất kích thích", "ma túy", "rượu"],
        "caffeine_nicotine_use": ["cà phê", "cafe", "thuốc lá", "hút thuốc"],
        "frequency": ["tần suất", "bao lâu", "mỗi ngày", "hàng ngày"],
        "onset": ["bắt đầu", "từ khi nào"],
        "duration": ["kéo dài", "đã bao lâu"],
        "intensity": ["mức độ", "nghiêm trọng"],
        "work_school_impact": ["công việc", "học tập", "làm việc"],
        "daily_functioning": ["hoạt động hàng ngày", "sinh hoạt"],
        "social_functioning": ["quan hệ", "bạn bè", "xã hội"],
    }
    
    for question in questions:
        question_lower = question.lower()
        is_redundant = False
        
        # Check if question asks about an already-filled slot
        for slot_name, keywords in slot_keywords.items():
            slot_value = slots.get(slot_name)
            
            # Skip if slot is empty
            if is_empty_slot(slot_value):
                continue
            
            # Check if question contains keywords for this slot
            if any(kw in question_lower for kw in keywords):
                logger.info(f"[FILTER] Question about '{slot_name}' (already filled: {slot_value}): '{question[:60]}'")
                is_redundant = True
                break
        
        if not is_redundant:
            filtered.append(question)
        else:
            logger.info(f"   → Removed redundant question")
    
    return filtered


def build_empathy_from_slots(slots: Dict[str, Any]) -> str:
    """
    Build empathy preamble from existing slots when LLM does not provide one.
    RULE: Only use data that exists, do not fabricate.
    
    Args:
        slots: Existing slots dict
    
    Returns:
        Vietnamese empathy sentence (1-2 sentences)
    """
    if not slots:
        return "Mình nghe những gì bạn chia sẻ và hiểu rằng điều này có thể đang khiến bạn khá nặng lòng."
    
    # Extract available data
    emotions = slots.get("emotion", [])
    presenting = slots.get("presenting_problem", [])
    trigger = slots.get("trigger", [])
    current_stressors = slots.get("current_stressors", [])
    work_impact = slots.get("work_school_impact", [])
    social_impact = slots.get("social_functioning", [])
    duration = slots.get("duration", [])
    intensity = slots.get("intensity", [])
    
    # Build empathy based on what's available
    parts = []
    
    # 1. Try emotion-based empathy
    if emotions:
        emotion_en = emotions[0] if isinstance(emotions, list) else emotions
        emotion_vi = EMOTION_MAP.get(emotion_en.lower(), "khó khăn")
        
        # Check for context
        if trigger or current_stressors:
            context = (trigger[0] if trigger else current_stressors[0]) if isinstance(trigger or current_stressors, list) else ""
            if context and len(context) < 50:  # Only if short
                return f"Mình nghe bạn đang cảm thấy {emotion_vi}, và có vẻ {context} đang ảnh hưởng đến bạn khá nhiều."
        
        # With impact
        if work_impact or social_impact:
            return f"Mình nghe bạn đang cảm thấy {emotion_vi}, và điều này đang ảnh hưởng đến nhiều khía cạnh trong cuộc sống của bạn."
        
        # With duration or intensity
        if duration and len(duration[0]) < 30:
            return f"Mình nghe bạn đã phải trải qua cảm giác {emotion_vi} trong {duration[0]}, điều đó hẳn rất nặng nề."
        
        if intensity:
            return f"Mình nghe bạn đang cảm thấy {emotion_vi}, và có vẻ điều này đang tác động khá mạnh đến bạn."
        
        # Simple emotion acknowledgment
        return f"Mình nghe bạn đang cảm thấy {emotion_vi}, điều đó hẳn là không dễ chịu."
    
    # 2. Try presenting_problem-based empathy
    if presenting:
        problem = presenting[0] if isinstance(presenting, list) else presenting
        if len(problem) < 50:  # Only if concise
            if work_impact or social_impact:
                return f"Có vẻ vấn đề về {problem} đang ảnh hưởng đến nhiều khía cạnh trong cuộc sống của bạn."
            return f"Mình nghe bạn đang gặp khó khăn với {problem}, điều đó hẳn đang khiến bạn khá lo lắng."
    
    # 3. Try impact-based empathy
    if work_impact or social_impact:
        return "Mình nghe những thay đổi gần đây đang ảnh hưởng đến công việc và các mối quan hệ của bạn, điều đó hẳn rất khó khăn."
    
    # 4. Fallback: generic but safe
    return "Mình nghe những gì bạn chia sẻ và hiểu rằng điều này có thể đang khiến bạn khá nặng lòng."


async def request_more_info_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Handle insufficient REQUIRED slots by returning follow-up questions.
    Now includes empathy preamble before questions.
    
    ENFORCES:
    - Empathy preamble from LLM or fallback
    - Minimum 1 question if required slots missing
    - Maximum 3 questions per turn
    - Questions must be SPECIFIC (not generic)
    - FILTERS OUT questions about already-filled slots
    
    Args:
        state: State dict with follow_up_questions, required_missing_slots, empathy_preamble_vi
    
    Returns:
        Updated state with answer containing empathy + follow-up questions
    """
    follow_up_questions = state.get("follow_up_questions", [])
    required_missing = state.get("required_missing_slots", [])
    empathy_preamble = state.get("empathy_preamble_vi", "")
    slots = state.get("slots", {})
    
    logger.info(f"Insufficient REQUIRED slots filled. Requesting more information.")
    logger.info(f"Missing REQUIRED slots: {required_missing[:10]}...")
    
    # ========== FILTER REDUNDANT QUESTIONS ==========
    if follow_up_questions:
        original_count = len(follow_up_questions)
        follow_up_questions = filter_redundant_questions(follow_up_questions, slots)
        if len(follow_up_questions) < original_count:
            logger.info(f"[FILTER] Removed {original_count - len(follow_up_questions)} redundant questions")
    
    # ========== EMPATHY PREAMBLE SELECTION (3-tier fallback) ==========
    # Tier 1: Use LLM-generated empathy (preferred)
    if empathy_preamble and empathy_preamble.strip():
        logger.info(f"✅ Using LLM-generated empathy: '{empathy_preamble[:80]}...'")
        final_empathy = empathy_preamble.strip()
    
    # Tier 2: Build from existing slots (fallback)
    elif slots:
        logger.info("⚠️ No LLM empathy, building from existing slots")
        final_empathy = build_empathy_from_slots(slots)
        logger.info(f"   Generated: '{final_empathy[:80]}...'")
    
    # Tier 3: Generic safe empathy (last resort)
    else:
        logger.warning("⚠️ No empathy from LLM and no slots, using generic fallback")
        final_empathy = "Mình nghe những gì bạn chia sẻ và hiểu rằng điều này có thể đang khiến bạn khá nặng lòng."
    
    # Validate empathy is not a question
    if "?" in final_empathy:
        logger.warning(f"⚠️ Empathy contains '?', removing: '{final_empathy}'")
        final_empathy = final_empathy.replace("?", ".").strip()
    
    # ========== QUESTION ENFORCEMENT (existing logic) ==========
    if required_missing and not follow_up_questions:
        logger.warning(f"⚠️ CRITICAL: {len(required_missing)} required slots missing but NO follow-up questions!")
        logger.warning(f"   Auto-generating fallback questions...")
        follow_up_questions = generate_questions_from_slots(required_missing, max_questions=3)
        logger.info(f"   → Generated {len(follow_up_questions)} fallback questions")
    
    if len(follow_up_questions) > 3:
        logger.warning(f"⚠️ Too many questions ({len(follow_up_questions)}), trimming to 3")
        follow_up_questions = follow_up_questions[:3]
    
    # ========== BUILD FINAL ANSWER WITH EMPATHY ==========
    if follow_up_questions:
        if len(follow_up_questions) == 1:
            # Single question format with markdown
            answer = (
                f"{final_empathy}\n\n"
                f"**Để mình hiểu rõ hơn và cùng bạn tìm hướng phù hợp, bạn cho mình biết thêm:**\n\n"
                f"▸ {follow_up_questions[0]}\n"
            )
        else:
            # Multiple questions format with numbered list markdown
            answer = f"{final_empathy}\n\n**Để mình hiểu rõ hơn, bạn có thể chia sẻ thêm:**\n\n"
            for i, question in enumerate(follow_up_questions, 1):
                answer += f"{i}. {question}\n\n"
    else:
        # Final fallback (should rarely reach here)
        logger.error("❌ CRITICAL: No questions generated even after fallback!")
        answer = (
            f"{final_empathy}\n\n"
            f"**Để mình hiểu rõ hơn, bạn có thể chia sẻ thêm về:**\n\n"
            f"1. Tình trạng này bắt đầu từ khi nào? (số ngày/tuần/tháng)\n"
            f"2. Đã kéo dài bao lâu rồi?\n"
            f"3. Mức độ nghiêm trọng ra sao?"
        )
    
    logger.info(f"✅ Built answer with empathy + {len(follow_up_questions)} questions")
    logger.info(f"   Empathy: {final_empathy[:80]}...")
    for i, q in enumerate(follow_up_questions, 1):
        logger.info(f"   Q{i}: {q[:60]}...")
    
    # Update state
    state["answer"] = answer
    state["done"] = True
    state["needs_more_info"] = True
    
    return state
