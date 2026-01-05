from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Phân loại slots để quản lý luồng hội thoại tốt hơn
DIAGNOSTIC_SLOTS = {
    "symptoms": ["emotion", "primary_mood", "physical_symptoms", "intensity"],
    "context": ["duration", "trigger", "impact", "daily_functioning"],
    # QUAN TRỌNG: Nhóm này giúp tránh chẩn đoán sai
    "differential": [
        "substance_use",        # Có dùng rượu/bia/chất kích thích không?
        "medical_history",      # Có bệnh nền (tim mạch, tuyến giáp) không?
        "recent_life_events",   # Có biến cố lớn (mất việc, chia tay) không?
        "symptom_fluctuation"   # Triệu chứng liên tục hay ngắt quãng?
    ]
}

# Required slots that must be filled before retrieval
# Bao gồm recent_life_events để phân biệt Stress vs Disorder
# Bao gồm trigger để phân biệt situational vs endogenous
# Bao gồm functional impairment để đánh giá severity chính xác
REQUIRED_SLOTS = [
    "emotion",
    "duration",
    "trigger",  # NEW: Cần để phân biệt situational stress vs disorder
    "impact",
    "intensity",
    "recent_life_events",  # Bắt buộc để phân biệt stress/adjustment vs disorder
]


def get_default_slots() -> Dict[str, Any]:
    """
    Return default empty slots structure.
    All slots initialized as None or empty list to support merging.
    risk_level default is 'unknown' to avoid false sense of safety.
    """
    return {
        "emotion": [],
        "primary_mood": None,
        "intensity": None,
        "trigger": None,
        "duration": None,
        "impact": None,
        "risk_level": "unknown",  # Changed from "none" to "unknown" - avoid false safety
        "need": None,
        "stress_level": None,
        "physical_symptoms": [],
        "sleep_quality": None,
        "sleep_duration": None,
        "energy_level": None,
        "appetite_changes": None,
        "daily_functioning": None,
        "work_school_impact": None,
        "support_system": None,
        "family_support": None,
        "friend_support": None,
        "social_isolation": None,
        "social_withdrawal": None,
        "coping_mechanisms": [],
        "coping_effectiveness": None,
        "current_stressors": [],
        "suicidal_ideation": None,
        "self_harm_thoughts": None,
        "current_treatment": None,
        "medication": None,
        # Differential diagnosis slots - để tránh chẩn đoán sai
        "substance_use": None,           # Rượu/bia/cafein/thuốc
        "medical_history": None,         # Bệnh nền: tim mạch, tuyến giáp, etc.
        "recent_life_events": None,      # Biến cố lớn: mất việc, chia tay, etc.
        "symptom_fluctuation": None,     # Liên tục hay ngắt quãng
        "history_of_trauma": None,       # Chấn thương tâm lý trong quá khứ
        # Derived fields để kiểm soát chẩn đoán
        "diagnostic_confidence": "low",  # low/medium/high
        "potential_differentials": [],   # Danh sách các bệnh có thể nhầm lẫn
        "duration_certainty": "vague",   # vague/approximate/specific
    }


def merge_slots(existing_slots: Optional[Dict[str, Any]], new_slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge new slots into existing slots (append/update instead of replace).
    
    Rules:
    - List fields (emotion, physical_symptoms, etc.): Append unique values (fixed dedup)
    - Scalar fields: Update only if new value is not None/empty
    - Special fields (risk_level, intensity): Normalize then merge by "max severity wins"
    - Preserve existing values when new value is None
    
    Args:
        existing_slots: Current slots from state (may be None on first turn)
        new_slots: Newly extracted slots from current turn
    
    Returns:
        Merged slots dictionary
    """
    # Severity mapping for risk/intensity comparison
    SEVERITY_ORDER = {
        "risk_level": ["unknown", "none", "low", "medium", "high"],
        "intensity": ["low", "medium", "high", "very_high"],
        "stress_level": ["low", "moderate", "high", "overwhelming"]
    }
    
    # Normalization mappings for intensity (handle flexible LLM outputs)
    INTENSITY_NORMALIZE = {
        # Low variants
        "nhẹ": "low", "nhe": "low", "thấp": "low", "mild": "low", "slight": "low",
        "ít": "low", "không nhiều": "low", "minimal": "low",
        
        # Medium variants  
        "trung bình": "medium", "trung binh": "medium", "vừa": "medium", "moderate": "medium",
        "bình thường": "medium", "average": "medium", "fair": "medium",
        
        # High variants
        "cao": "high", "mạnh": "high", "nặng": "high", "severe": "high", "strong": "high",
        "khá cao": "high", "khá nặng": "high", "quite high": "high",
        "nghiêm trọng": "high", "serious": "high", "significant": "high",
        
        # Very high variants
        "rất cao": "very_high", "rất nặng": "very_high", "cực kỳ": "very_high",
        "very high": "very_high", "extreme": "very_high", "intense": "very_high",
        "không chịu nổi": "very_high", "unbearable": "very_high"
    }
    
    def normalize_intensity(value: str) -> str:
        """Normalize intensity value to standard levels, handling flexible descriptions."""
        if not value or not isinstance(value, str):
            return value
            
        value_lower = value.lower().strip()
        
        # Direct match
        if value_lower in INTENSITY_NORMALIZE:
            return INTENSITY_NORMALIZE[value_lower]
        
        # Partial match - check if any key is substring
        for key, normalized in INTENSITY_NORMALIZE.items():
            if key in value_lower:
                # Handle compound descriptions like "trung bình đến cao"
                # Return the higher severity if multiple found
                if "cao" in value_lower or "nặng" in value_lower or "nghiêm trọng" in value_lower:
                    return "high"
                elif "trung bình" in value_lower or "vừa" in value_lower:
                    return "medium"
                return normalized
        
        # Check for numeric scale (e.g., "7/10", "8 out of 10")
        import re
        numeric_match = re.search(r'(\d+)\s*[/\\]\s*(\d+)', value_lower)
        if numeric_match:
            score = int(numeric_match.group(1))
            max_score = int(numeric_match.group(2))
            ratio = score / max_score
            if ratio >= 0.8:
                return "very_high"
            elif ratio >= 0.6:
                return "high"
            elif ratio >= 0.4:
                return "medium"
            else:
                return "low"
        
        # Default: return original value (will be handled by exception in merge)
        logger.warning(f"[NORMALIZE] Could not normalize intensity: '{value}' - keeping original")
        return value
    
    # Initialize with defaults if no existing slots
    if not existing_slots:
        merged = get_default_slots()
    else:
        merged = existing_slots.copy()
    
    # Merge each slot
    for key, new_value in new_slots.items():
        existing_value = merged.get(key)
        
        # Skip if new value is None or "none" or empty
        if new_value is None or new_value == "none" or new_value == []:
            continue
        
        # SPECIAL: Normalize intensity before processing
        if key == "intensity" and isinstance(new_value, str):
            new_value = normalize_intensity(new_value)
            logger.debug(f"[NORMALIZE] intensity: original='{new_slots.get('intensity')}' → normalized='{new_value}'")
        
        # Handle list fields - append unique values (FIXED: proper dedup)
        if isinstance(new_value, list):
            if not existing_value:
                # Remove duplicates from new_value itself
                merged[key] = list(dict.fromkeys(new_value))  # Preserves order
            elif isinstance(existing_value, list):
                # Existing value is a list - append unique items
                existing_set = set(existing_value)
                for item in new_value:
                    if item and item not in existing_set:
                        merged[key].append(item)
                        existing_set.add(item)  # FIXED: Update set after adding
            else:
                # existing_value is NOT a list (corrupted data) - replace with new list
                logger.warning(f"[MERGE SLOTS] Slot '{key}' has non-list value: {type(existing_value)}. Replacing with new list.")
                merged[key] = list(dict.fromkeys(new_value))
        
        # Handle severity fields - merge by "max severity wins"
        elif key in SEVERITY_ORDER:
            severity_list = SEVERITY_ORDER[key]
            try:
                existing_idx = severity_list.index(existing_value) if existing_value in severity_list else -1
                new_idx = severity_list.index(new_value) if new_value in severity_list else -1
                # Keep the higher severity
                if new_idx > existing_idx:
                    merged[key] = new_value
                elif new_idx == -1 and existing_idx == -1:
                    # Both not in list → keep newer value
                    merged[key] = new_value
            except (ValueError, TypeError):
                # If comparison fails, update with new value
                merged[key] = new_value
        
        # Handle scalar fields - update with new non-empty values
        else:
            # Always update scalar fields with new non-empty values
            # This allows updating/refining information across turns
            merged[key] = new_value
    
    return merged


def build_slot_context(slots: Dict[str, Any]) -> str:
    """
    Build formatted context string from slots for answer generation.
    Includes differential diagnosis info to guide LLM away from premature diagnosis.
    """
    if not slots:
        return ""

    context_parts: List[str] = []

    # Core emotional
    if slots.get("emotion"):
        context_parts.append(f"Emotions: {', '.join(slots['emotion'])}")
    if slots.get("primary_mood"):
        context_parts.append(f"Primary mood: {slots['primary_mood']}")
    if slots.get("intensity"):
        context_parts.append(f"Intensity: {slots['intensity']}")
    if slots.get("trigger"):
        context_parts.append(f"Trigger: {slots['trigger']}")
    if slots.get("duration"):
        duration_certainty = slots.get("duration_certainty", "vague")
        context_parts.append(f"Duration: {slots['duration']} (certainty: {duration_certainty})")
    if slots.get("impact"):
        context_parts.append(f"Impact: {slots['impact']}")

    # Physical & functional
    if slots.get("physical_symptoms"):
        context_parts.append(f"Physical symptoms: {', '.join(slots['physical_symptoms'])}")
    if slots.get("sleep_quality"):
        context_parts.append(f"Sleep quality: {slots['sleep_quality']}")
    if slots.get("sleep_duration"):
        context_parts.append(f"Sleep duration: {slots['sleep_duration']}")
    if slots.get("energy_level"):
        context_parts.append(f"Energy level: {slots['energy_level']}")
    if slots.get("daily_functioning"):
        context_parts.append(f"Daily functioning: {slots['daily_functioning']}")
    if slots.get("work_school_impact"):
        context_parts.append(f"Work/school impact: {slots['work_school_impact']}")

    # Social & support
    if slots.get("support_system"):
        context_parts.append(f"Support system: {slots['support_system']}")
    if slots.get("social_isolation") is True:
        context_parts.append("Social isolation: Yes")
    if slots.get("social_withdrawal") is True:
        context_parts.append("Social withdrawal: Yes")

    # Coping
    if slots.get("coping_mechanisms"):
        context_parts.append(f"Coping mechanisms: {', '.join(slots['coping_mechanisms'])}")
    if slots.get("current_stressors"):
        context_parts.append(f"Current stressors: {', '.join(slots['current_stressors'])}")
    if slots.get("stress_level"):
        context_parts.append(f"Stress level: {slots['stress_level']}")

    # Differential diagnosis information (CRITICAL FOR PREVENTING PREMATURE DIAGNOSIS)
    if slots.get("recent_life_events"):
        context_parts.append(f"Recent life events: {slots['recent_life_events']}")
    if slots.get("substance_use"):
        context_parts.append(f"Substance use: {slots['substance_use']}")
    if slots.get("medical_history"):
        context_parts.append(f"Medical history: {slots['medical_history']}")
    if slots.get("symptom_fluctuation"):
        context_parts.append(f"Symptom pattern: {slots['symptom_fluctuation']}")
    
    # Diagnostic caution flags
    diagnostic_confidence = slots.get("diagnostic_confidence", "low")
    context_parts.append(f"⚠️ Diagnostic confidence: {diagnostic_confidence}")
    
    # Needs
    if slots.get("need"):
        context_parts.append(f"What they need: {slots['need']}")

    if not context_parts:
        return ""

    return "Additional Context from User's Message:\n" + "\n".join(f"- {part}" for part in context_parts)


def get_slot_keywords(slots: Dict[str, Any]) -> List[str]:
    """
    Extract keywords from slots for rerank bonus calculation (STAGE-AWARE).
    Only adds disorder/diagnosis keywords when sufficient criteria met.
    Otherwise, prioritizes coping/stress management keywords.
    
    Args:
        slots: Slot dictionary
    
    Returns:
        List of keywords for matching against node names
    """
    keywords = []
    
    if not slots:
        return keywords
    
    # Check if we should use disorder-specific keywords
    diagnosis_ready = is_diagnosis_ready(slots)
    
    # Sleep-related keywords
    if slots.get("sleep_quality") or slots.get("sleep_duration"):
        # Always add general sleep hygiene keywords
        keywords.extend(["sleep", "bedtime", "rest", "night", "caffeine", "melatonin", "sleep hygiene"])
        # Only add disorder keyword if criteria met
        if diagnosis_ready:
            keywords.append("insomnia")
    
    # Emotion/mood keywords (STAGE-AWARE)
    emotions = slots.get("emotion", [])
    if emotions:
        # Add emotion names directly
        keywords.extend([e.lower() for e in emotions])
        # Add general coping keywords (ALWAYS)
        keywords.extend(["mood", "feeling", "emotion", "coping", "stress management"])
        
        # Only add disorder keywords if diagnosis-ready
        if diagnosis_ready:
            keywords.extend(["anxiety", "depression", "disorder"])
        else:
            # Focus on stress/adjustment/coping
            keywords.extend(["stress", "adjustment", "support", "wellbeing"])
    
    primary_mood = slots.get("primary_mood")
    if primary_mood:
        keywords.append(primary_mood.lower())
    
    # Stress-related keywords
    if slots.get("stress_level") or slots.get("current_stressors"):
        keywords.extend(["stress", "pressure", "workload", "tension", "worry", "stress management", "relaxation"])
    
    # Energy/fatigue keywords
    if slots.get("energy_level"):
        energy = slots.get("energy_level", "").lower()
        if "low" in energy or "thấp" in energy:
            keywords.extend(["fatigue", "tired", "exhaustion", "energy", "rest"])
    
    # Physical symptoms keywords
    physical = slots.get("physical_symptoms", [])
    if physical:
        keywords.extend([s.lower() for s in physical])
        # Emphasize psychoeducation over diagnosis
        keywords.extend(["symptom", "physical", "body", "psychoeducation"])
    
    # Social keywords
    if slots.get("social_isolation") or slots.get("social_withdrawal"):
        keywords.extend(["social", "isolation", "lonely", "withdrawal", "connection", "social support"])
    
    # Coping keywords (ALWAYS PRIORITIZE)
    if slots.get("coping_mechanisms"):
        keywords.extend(["coping", "strategy", "technique", "manage", "handle", "skills"])
    
    # Trigger keywords (if specific)
    trigger = slots.get("trigger")
    if trigger:
        trigger_lower = trigger.lower()
        # Add common trigger-related terms
        if "work" in trigger_lower or "công việc" in trigger_lower:
            keywords.extend(["work", "job", "career", "professional", "work-life balance"])
        if "family" in trigger_lower or "gia đình" in trigger_lower:
            keywords.extend(["family", "relationship", "home", "communication"])
        if "school" in trigger_lower or "học" in trigger_lower:
            keywords.extend(["school", "study", "education", "academic", "learning"])
    
    # Remove duplicates and empty strings
    keywords = list(dict.fromkeys([k for k in keywords if k]))  # Preserve order
    
    return keywords


def validate_duration(duration_text: Optional[str]) -> Tuple[bool, str]:
    """
    Kiểm tra xem duration có cụ thể không.
    ROBUST: Prioritize concrete time information (numbers + units) over vague wording.
    
    Args:
        duration_text: Duration string from slot
    
    Returns:
        Tuple of (is_specific, certainty_level)
        - is_specific: True if duration has concrete time info
        - certainty_level: 'specific', 'approximate', 'vague'
    """
    if not duration_text:
        return False, "vague"
    
    duration_lower = duration_text.lower()
    
    # Check for numbers (including Vietnamese numbers like "vài")
    has_digit = any(char.isdigit() for char in duration_text)
    vietnamese_numbers = ["một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín", "mười"]
    has_vietnamese_num = any(num in duration_lower for num in vietnamese_numbers)
    has_number = has_digit or has_vietnamese_num
    
    # Time units (specific and approximate)
    specific_units = ["tháng", "month", "năm", "year"]
    approximate_units = ["tuần", "week", "ngày", "day"]
    
    # PRIORITY 1: Has number + specific time unit (months/years) → SPECIFIC
    # Examples: "5–6 tháng", "khoảng 2 năm", "3 months"
    if has_number and any(unit in duration_lower for unit in specific_units):
        return True, "specific"
    
    # PRIORITY 2: Has number + approximate time unit (weeks/days) → APPROXIMATE
    # Examples: "vài tuần", "2 weeks", "5 ngày"
    if has_number and any(unit in duration_lower for unit in approximate_units):
        return True, "approximate"
    
    # PRIORITY 3: Has approximate modifiers with time units → APPROXIMATE
    # Examples: "vài lần/tuần", "several weeks"
    approximate_modifiers = ["vài", "several", "khoảng", "around", "about", "some"]
    if any(mod in duration_lower for mod in approximate_modifiers):
        if any(unit in duration_lower for unit in specific_units + approximate_units):
            return True, "approximate"
    
    # PRIORITY 4: Only vague terms without concrete time → VAGUE
    # Examples: "dạo này", "recently", "lately"
    vague_terms = ["lately", "gần đây", "dạo này", "recently", "just now", "mới đây"]
    if any(term in duration_lower for term in vague_terms):
        # Check if there's ANY concrete time info to salvage
        if has_number or any(unit in duration_lower for unit in specific_units + approximate_units):
            return True, "approximate"  # Has some time info despite vague wording
        return False, "vague"
    
    # Default: treat as approximate if text has substance
    if len(duration_text) > 5:
        return True, "approximate"
    
    return False, "vague"


def has_sufficient_slots(slots: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """
    Check if required slots are filled sufficiently for retrieval.
    UPDATED: Added trigger to REQUIRED, checks functional impairment.
    
    Args:
        slots: Slot dictionary
    
    Returns:
        Tuple of (is_sufficient, required_missing_slots, differential_missing_slots)
        - is_sufficient: True if enough info to provide supportive response
        - required_missing_slots: Critical slots still missing
        - differential_missing_slots: Differential diagnosis slots missing
    """
    if not slots:
        return False, REQUIRED_SLOTS.copy(), []
    
    required_missing = []
    differential_missing = []
    
    # Check core required slots
    for slot_name in REQUIRED_SLOTS:
        value = slots.get(slot_name)
        
        # Special handling for duration - validate quality
        if slot_name == "duration":
            is_specific, certainty = validate_duration(value)
            if not is_specific:
                required_missing.append("specific_duration")
            # Always update certainty level (not just when vague)
            slots["duration_certainty"] = certainty
            continue
        
        # Check if slot is actually filled (not None, not empty list, not "none")
        if value is None or value == [] or value == "none":
            required_missing.append(slot_name)
    
    # Check functional impairment (CRITICAL for severity assessment)
    # UPGRADED: Now treated as REQUIRED (not just differential)
    # Need at least ONE of: daily_functioning or work_school_impact
    daily_func = slots.get("daily_functioning")
    work_impact = slots.get("work_school_impact")
    
    has_functional_info = (
        (daily_func is not None and daily_func != "none" and daily_func != [] and daily_func != "") or
        (work_impact is not None and work_impact != "none" and work_impact != [] and work_impact != "")
    )
    
    if not has_functional_info:
        required_missing.append("functional_impairment")  # CHANGED: Now REQUIRED
        logger.debug(f"[FUNCTIONAL CHECK] Missing functional impairment: daily_functioning={daily_func}, work_school_impact={work_impact}")
    else:
        logger.debug(f"[FUNCTIONAL CHECK] Has functional info: daily_functioning={daily_func is not None}, work_school_impact={work_impact is not None}")
    
    # Check differential diagnosis slots (CRITICAL for preventing misdiagnosis)
    # UPGRADED: Medical exclusion now MORE STRICT
    physical_symptoms = slots.get("physical_symptoms", [])
    
    # If physical symptoms present → MUST have BOTH medical_history AND substance_use
    if physical_symptoms and len(physical_symptoms) > 0:
        if not slots.get("medical_history"):
            required_missing.append("medical_history")  # UPGRADED: Now REQUIRED if physical symptoms
        if not slots.get("substance_use"):
            required_missing.append("substance_use")  # UPGRADED: Now REQUIRED if physical symptoms
    else:
        # No physical symptoms → still check but less strict
        # Missing these is OK if no physical manifestations
        if not slots.get("medical_history"):
            differential_missing.append("medical_history_optional")
        if not slots.get("substance_use"):
            differential_missing.append("substance_use_optional")
    
    # Logic: Sufficient if:
    # 1. ALL required slots filled (NO missing required slots) - CRITICAL for accurate assessment
    # 2. AND at most 1 differential slot missing (allows some flexibility)
    # 
    # Rationale: 
    # - Cannot assess accurately without emotion, duration, trigger, intensity, impact, recent_life_events
    # - Missing trigger → cannot differentiate situational stress vs disorder
    # - Missing recent_life_events → cannot rule out adjustment reaction
    # - Missing intensity/impact → cannot assess severity
    is_sufficient = len(required_missing) == 0 and len(differential_missing) <= 1
    
    return is_sufficient, required_missing, differential_missing


def is_diagnosis_ready(slots: Dict[str, Any]) -> bool:
    """
    Kiểm tra xem có đủ điều kiện để đưa ra chẩn đoán disorder-specific không.
    Chỉ trả về True khi:
    1. Duration đủ cụ thể và dài (>= 2 weeks for most disorders)
    2. Có impairment rõ ràng (daily_functioning hoặc work_school_impact)
    3. Đã loại trừ nguyên nhân vật lý/substance
    4. Có pattern ổn định (không phải acute stress)
    
    Args:
        slots: Slot dictionary
    
    Returns:
        True if ready for disorder-specific diagnosis/treatment
    """
    if not slots:
        return False
    
    # 1. Check duration - must be specific and prolonged
    duration = slots.get("duration")
    is_specific, certainty = validate_duration(duration)
    if not is_specific or certainty == "vague":
        return False
    
    # Check if duration indicates chronicity (contains month/year or >= 2 weeks)
    if duration:
        duration_lower = duration.lower()
        has_chronic_marker = any(term in duration_lower for term in 
            ["tháng", "month", "năm", "year", "chronic", "mãn tính"])
        has_two_weeks = "2" in duration and any(term in duration_lower for term in ["week", "tuần"])
        
        if not (has_chronic_marker or has_two_weeks):
            # Duration too short for disorder diagnosis
            return False
    
    # 2. Check impairment - must have clear functional impact
    has_impairment = (
        slots.get("daily_functioning") in ["moderate", "severe", "moderate_impairment"] or
        slots.get("work_school_impact") in ["moderate", "severe", "unable"]
    )
    if not has_impairment:
        return False
    
    # 3. Check differential exclusion - must have checked medical/substance
    has_checked_exclusion = (
        slots.get("medical_history") is not None or
        slots.get("substance_use") is not None
    )
    if not has_checked_exclusion:
        return False
    
    # 4. Check for acute stress (if recent life event within days, likely adjustment not disorder)
    recent_events = slots.get("recent_life_events", "")
    if recent_events:
        recent_lower = recent_events.lower()
        acute_markers = ["hôm qua", "yesterday", "tuần này", "this week", "vừa mới", "just"]
        if any(marker in recent_lower for marker in acute_markers):
            # Too acute - likely stress/adjustment reaction
            return False
    
    # All criteria met - ready for disorder-specific assessment
    return True


def build_query_context_from_slots(slots: Dict[str, Any]) -> str:
    """
    Build natural language context from slots for query rewriting.
    
    Args:
        slots: Slot dictionary
    
    Returns:
        Natural language string describing user's situation
    """
    if not slots:
        return ""
    
    parts = []
    
    # Emotion and mood
    emotions = slots.get("emotion", [])
    primary_mood = slots.get("primary_mood")
    if emotions or primary_mood:
        if primary_mood:
            parts.append(f"feeling {primary_mood}")
        elif emotions:
            parts.append(f"experiencing {', '.join(emotions)}")
    
    # Intensity
    intensity = slots.get("intensity")
    if intensity:
        parts.append(f"at {intensity} intensity")
    
    # Duration
    duration = slots.get("duration")
    if duration:
        parts.append(f"for {duration}")
    
    # Trigger
    trigger = slots.get("trigger")
    if trigger:
        parts.append(f"triggered by {trigger}")
    
    # Impact
    impact = slots.get("impact")
    if impact:
        parts.append(f"impacting: {impact}")
    
    # Stress level
    stress_level = slots.get("stress_level")
    if stress_level:
        parts.append(f"stress level: {stress_level}")
    
    # Physical symptoms
    physical = slots.get("physical_symptoms", [])
    if physical:
        parts.append(f"with physical symptoms: {', '.join(physical)}")
    
    # Sleep issues
    sleep_quality = slots.get("sleep_quality")
    if sleep_quality and sleep_quality != "good":
        parts.append(f"sleep quality: {sleep_quality}")
    
    # What they need
    need = slots.get("need")
    if need:
        parts.append(f"seeking: {need}")
    
    if not parts:
        return ""
    
    return " | ".join(parts)

