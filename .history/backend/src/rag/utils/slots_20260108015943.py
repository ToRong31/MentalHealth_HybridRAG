from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# DSM-5 STAGE FLOW CONSTANTS
# ============================================================================

# Stage order for structured intake (DSM-5 based)
STAGE_FLOW = [
    "presenting",     # What brings you here
    "timeline",       # When, how long, pattern
    "severity",       # How severe (distress + intensity)
    "functioning",    # Impairment (DSM-5 Criterion B)
    "context",        # Triggers, stressors, life events
    "exclusion",      # Rule out medical/substance (DSM-5 Criterion D)
    "support_coping", # Resources available
    "screens"         # Cross-cutting symptoms (mania, psychosis)
]

# Diagnostic slots organized by stage
DIAGNOSTIC_SLOTS = {
    "presenting": [
        "presenting_problem",
        "emotion",
        "primary_mood"
    ],
    "timeline": [
        "onset",
        "duration",
        "frequency",
        "symptom_fluctuation",
        "time_of_day_pattern"
    ],
    "severity": [
        "intensity",
        "distress_level",
        "stress_level"
    ],
    "functioning": [
        "daily_functioning",
        "work_school_impact",
        "social_functioning",
        "self_care_functioning"
    ],
    "somatic": [
        "physical_symptoms",
        "sleep_quality",
        "sleep_duration",
        "energy_level",
        "appetite_changes"
    ],
    "context": [
        "trigger",
        "current_stressors",
        "recent_life_events"
    ],
    "support_coping": [
        "support_system",
        "coping_mechanisms",
        "coping_effectiveness",
        "need"
    ],
    "exclusion": [
        "substance_use_any",
        "substance_use",
        "medical_history_any",
        "medical_history",
        "medication_changes",
        "caffeine_nicotine_use",
        "current_treatment",
        "medication"
    ],
    "screens": [
        "mania_like_symptoms",
        "psychotic_like_symptoms"
    ],
    "history": [
        "history_of_trauma"
    ]
}

# Required slots per stage (MUST be filled before moving to next stage)
REQUIRED_SLOTS_BY_STAGE = {
    "presenting": [
        "presenting_problem",
        "emotion",
        "primary_mood"
    ],
    "timeline": [
        "onset",
        "duration",
        "frequency",
        "symptom_fluctuation"
    ],
    "severity": [
        "intensity",
        "distress_level",
        "stress_level"
    ],
    "functioning": [
        "daily_functioning",
        "work_school_impact",
        "social_functioning",
        "self_care_functioning"
    ],
    "context": [
        "trigger",
        "current_stressors",
        "recent_life_events"
    ],
    "exclusion": [
        "substance_use_any",
        "medical_history_any",
        "medication_changes",
        "caffeine_nicotine_use"
    ],
    "support_coping": [
        "support_system",
        "coping_mechanisms"
    ],
    "screens": [
        "mania_like_symptoms",
        "psychotic_like_symptoms"
    ]
}

# Flatten for legacy compatibility
REQUIRED_SLOTS = [s for stage in STAGE_FLOW for s in REQUIRED_SLOTS_BY_STAGE.get(stage, [])]

# Tri-state fields (not lists)
TRI_STATE_FIELDS = {
    "substance_use_any",
    "medical_history_any",
    "mania_like_symptoms",
    "psychotic_like_symptoms"
}

# Valid tri-state values
TRI_STATES = {"yes", "no", "unknown"}


def get_default_slots() -> Dict[str, Any]:
    """
    Return default empty slots structure (DSM-5 based).
    All slots initialized as [] (lists) or "unknown" (tri-states).
    """
    return {
        # A. PRESENTING / CORE
        "presenting_problem": [],
        "emotion": [],
        "primary_mood": [],
        
        # B. TIMELINE / COURSE
        "onset": [],
        "duration": [],
        "frequency": [],
        "symptom_fluctuation": [],
        "time_of_day_pattern": [],
        
        # C. SEVERITY
        "intensity": [],
        "distress_level": [],
        "stress_level": [],
        
        # D. IMPAIRMENT / FUNCTIONING
        "daily_functioning": [],
        "work_school_impact": [],
        "social_functioning": [],
        "self_care_functioning": [],
        
        # E. SOMATIC / BIO
        "physical_symptoms": [],
        "sleep_quality": [],
        "sleep_duration": [],
        "energy_level": [],
        "appetite_changes": [],
        
        # F. CONTEXT / PSYCHOSOCIAL
        "trigger": [],
        "current_stressors": [],
        "recent_life_events": [],
        
        # G. SUPPORT / COPING
        "support_system": [],
        "coping_mechanisms": [],
        "coping_effectiveness": [],
        "need": [],
        
        # H. EXCLUSION CRITERIA (TRI-STATE + details)
        "substance_use_any": "unknown",      # TRI-STATE
        "substance_use": [],
        "medical_history_any": "unknown",    # TRI-STATE
        "medical_history": [],
        "medication_changes": [],
        "caffeine_nicotine_use": [],
        "current_treatment": [],
        "medication": [],
        
        # I. CROSS-CUTTING SCREENS (TRI-STATE)
        "mania_like_symptoms": "unknown",    # TRI-STATE
        "psychotic_like_symptoms": "unknown", # TRI-STATE
        
        # J. HISTORY
        "history_of_trauma": [],
        
        # K. DERIVED FIELDS
        "diagnostic_confidence": "low",
        "potential_differentials": [],
        "duration_certainty": "vague",
        "intake_complete": False
    }


def merge_slots(existing_slots: Optional[Dict[str, Any]], new_slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge new slots into existing slots (append/update instead of replace).
    
    FIXED RULES:
    - List fields: Append unique values (preserve "no ..." strings)
    - Tri-state fields: Update only if more informative
    - Scalar fields: Update only if new value is not None/empty
    - NEVER skip "no" or "none" strings (they are valid data)
    
    Args:
        existing_slots: Current slots from state
        new_slots: Newly extracted slots
    
    Returns:
        Merged slots dictionary
    """
    SEVERITY_ORDER = {
        "intensity": ["mild", "moderate", "severe", "very_severe", "overwhelming"],
        "distress_level": ["none", "mild", "moderate", "severe"],
        "stress_level": ["low", "moderate", "high", "overwhelming"]
    }
    
    if not existing_slots:
        merged = get_default_slots()
    else:
        merged = existing_slots.copy()
    
    for key, new_value in new_slots.items():
        # Skip only if truly empty (NOT if "no"/"none" string)
        if new_value is None:
            continue
        if isinstance(new_value, str) and new_value.strip() == "":
            continue
        if isinstance(new_value, list) and len(new_value) == 0:
            continue
        
        existing_value = merged.get(key)
        
        # Handle tri-state fields (substance_use_any, etc.)
        if key in TRI_STATE_FIELDS:
            new_lower = new_value.lower() if isinstance(new_value, str) else "unknown"
            if new_lower not in TRI_STATES:
                new_lower = "unknown"
            
            existing_lower = existing_value.lower() if isinstance(existing_value, str) else "unknown"
            
            # Tri-state priority: "yes" > "no" > "unknown"
            priority = {"yes": 3, "no": 2, "unknown": 1}
            if priority.get(new_lower, 0) > priority.get(existing_lower, 0):
                merged[key] = new_lower
            continue
        
        # Handle list fields (most slots)
        if isinstance(new_value, list):
            existing_list = existing_value if isinstance(existing_value, list) else []
            
            # Merge lists: append unique values
            combined = existing_list.copy()
            for item in new_value:
                if item and item not in combined:
                    combined.append(item)
            
            merged[key] = combined
            
            # For severity fields, also compute "_current" scalar (max severity)
            if key in SEVERITY_ORDER:
                best_severity = None
                best_idx = -1
                for val in combined:
                    val_lower = str(val).lower().strip()
                    if val_lower in SEVERITY_ORDER[key]:
                        idx = SEVERITY_ORDER[key].index(val_lower)
                        if idx > best_idx:
                            best_idx = idx
                            best_severity = val_lower
                merged[key + "_current"] = best_severity or "unknown"
            
            continue
        
        # Handle scalar fields (diagnostic_confidence, duration_certainty, etc.)
        if isinstance(new_value, (str, int, float, bool)):
            # For severity scalars, apply max logic
            if key in SEVERITY_ORDER:
                existing_str = str(existing_value).lower() if existing_value else ""
                new_str = str(new_value).lower()
                
                order = SEVERITY_ORDER[key]
                existing_idx = order.index(existing_str) if existing_str in order else -1
                new_idx = order.index(new_str) if new_str in order else -1
                
                if new_idx > existing_idx:
                    merged[key] = new_value
            else:
                # Regular scalar: update if not empty
                if new_value or (isinstance(new_value, bool)):
                    merged[key] = new_value
            continue
    
    return merged


def build_slot_context(slots: Dict[str, Any]) -> str:
    """
    Build formatted context string from slots for answer generation.
    REDESIGNED: Uses DSM-5 stage structure with 41 slots.
    """
    if not slots:
        return ""

    context_parts: List[str] = []

    # GROUP A: Presenting Problem (Stage 1)
    if slots.get("presenting_problem"):
        context_parts.append(f"Presenting Problem: {slots['presenting_problem']}")
    if slots.get("emotion"):
        emotions = slots['emotion']
        if isinstance(emotions, list):
            context_parts.append(f"Emotions: {', '.join(emotions)}")
        else:
            context_parts.append(f"Emotion: {emotions}")
    if slots.get("primary_mood"):
        moods = slots['primary_mood']
        if isinstance(moods, list):
            context_parts.append(f"Primary Moods: {', '.join(moods)}")
        else:
            context_parts.append(f"Primary Mood: {moods}")

    # GROUP B: Timeline (Stage 2)
    if slots.get("onset"):
        context_parts.append(f"Onset: {slots['onset']}")
    if slots.get("duration"):
        durations = slots['duration']
        if isinstance(durations, list):
            context_parts.append(f"Duration: {', '.join(durations)}")
        else:
            context_parts.append(f"Duration: {durations}")
    if slots.get("frequency"):
        context_parts.append(f"Frequency: {slots['frequency']}")
    if slots.get("symptom_fluctuation"):
        fluctuation = slots['symptom_fluctuation']
        if isinstance(fluctuation, list):
            context_parts.append(f"Symptom Patterns: {', '.join(fluctuation)}")
        else:
            context_parts.append(f"Symptom Pattern: {fluctuation}")

    # GROUP C: Severity (Stage 3)
    if slots.get("intensity"):
        intensities = slots['intensity']
        if isinstance(intensities, list):
            context_parts.append(f"Intensity: {', '.join(intensities)}")
        else:
            context_parts.append(f"Intensity: {intensities}")
    if slots.get("distress_level"):
        context_parts.append(f"Distress Level: {slots['distress_level']}")
    if slots.get("intensity_current"):
        context_parts.append(f"Current Intensity (0-10): {slots['intensity_current']}")

    # GROUP D: Functional Impairment (Stage 4)
    if slots.get("daily_functioning"):
        functioning = slots['daily_functioning']
        if isinstance(functioning, list):
            context_parts.append(f"Daily Functioning: {', '.join(functioning)}")
        else:
            context_parts.append(f"Daily Functioning: {functioning}")
    if slots.get("social_functioning"):
        context_parts.append(f"Social Functioning: {slots['social_functioning']}")
    if slots.get("work_school_impact"):
        impact = slots['work_school_impact']
        if isinstance(impact, list):
            context_parts.append(f"Work/School Impact: {', '.join(impact)}")
        else:
            context_parts.append(f"Work/School Impact: {impact}")
    if slots.get("self_care_functioning"):
        context_parts.append(f"Self-Care Functioning: {slots['self_care_functioning']}")

    # GROUP E: Associated Somatic Symptoms (Stage 4)
    if slots.get("physical_symptoms"):
        symptoms = slots['physical_symptoms']
        if isinstance(symptoms, list):
            context_parts.append(f"Physical Symptoms: {', '.join(symptoms)}")
        else:
            context_parts.append(f"Physical Symptoms: {symptoms}")
    if slots.get("sleep_quality"):
        quality = slots['sleep_quality']
        if isinstance(quality, list):
            context_parts.append(f"Sleep Quality: {', '.join(quality)}")
        else:
            context_parts.append(f"Sleep Quality: {quality}")
    if slots.get("sleep_duration"):
        duration = slots['sleep_duration']
        if isinstance(duration, list):
            context_parts.append(f"Sleep Duration: {', '.join(duration)}")
        else:
            context_parts.append(f"Sleep Duration: {duration}")
    if slots.get("energy_level"):
        energy = slots['energy_level']
        if isinstance(energy, list):
            context_parts.append(f"Energy Levels: {', '.join(energy)}")
        else:
            context_parts.append(f"Energy Level: {energy}")

    # GROUP F: Context (Stage 5)
    if slots.get("trigger"):
        triggers = slots['trigger']
        if isinstance(triggers, list):
            context_parts.append(f"Triggers: {', '.join(triggers)}")
        else:
            context_parts.append(f"Trigger: {triggers}")
    if slots.get("recent_life_events"):
        events = slots['recent_life_events']
        if isinstance(events, list):
            context_parts.append(f"Recent Life Events: {', '.join(events)}")
        else:
            context_parts.append(f"Recent Life Events: {events}")
    if slots.get("current_stressors"):
        stressors = slots['current_stressors']
        if isinstance(stressors, list):
            context_parts.append(f"Current Stressors: {', '.join(stressors)}")
        else:
            context_parts.append(f"Current Stressors: {stressors}")
    if slots.get("stress_level"):
        stress = slots['stress_level']
        if isinstance(stress, list):
            context_parts.append(f"Stress Levels: {', '.join(stress)}")
        else:
            context_parts.append(f"Stress Level: {stress}")

    # GROUP G: Support & Coping (Stage 7)
    if slots.get("support_system"):
        support = slots['support_system']
        if isinstance(support, list):
            context_parts.append(f"Support System: {', '.join(support)}")
        else:
            context_parts.append(f"Support System: {support}")
    if slots.get("social_isolation") is True:
        context_parts.append("Social Isolation: Yes")
    if slots.get("social_withdrawal") is True:
        context_parts.append("Social Withdrawal: Yes")
    if slots.get("coping_mechanisms"):
        mechanisms = slots['coping_mechanisms']
        if isinstance(mechanisms, list):
            context_parts.append(f"Coping Mechanisms: {', '.join(mechanisms)}")
        else:
            context_parts.append(f"Coping Mechanisms: {mechanisms}")

    # GROUP H: Exclusion Criteria (Stage 6) - TRI-STATE FIELDS
    if slots.get("substance_use_any"):
        context_parts.append(f"Substance Use (Any): {slots['substance_use_any']}")
    if slots.get("substance_use"):
        substances = slots['substance_use']
        if isinstance(substances, list):
            context_parts.append(f"Substance Details: {', '.join(substances)}")
        else:
            context_parts.append(f"Substance Details: {substances}")
    if slots.get("caffeine_nicotine_use"):
        context_parts.append(f"Caffeine/Nicotine Use: {slots['caffeine_nicotine_use']}")
    if slots.get("medical_history_any"):
        context_parts.append(f"Medical History (Any): {slots['medical_history_any']}")
    if slots.get("medical_history"):
        history = slots['medical_history']
        if isinstance(history, list):
            context_parts.append(f"Medical Details: {', '.join(history)}")
        else:
            context_parts.append(f"Medical Details: {history}")
    if slots.get("medication_changes"):
        context_parts.append(f"Recent Medication Changes: {slots['medication_changes']}")

    # GROUP I: Screening Questions (Stage 8) - TRI-STATE FIELDS
    if slots.get("mania_like_symptoms"):
        context_parts.append(f"Mania-like Symptoms: {slots['mania_like_symptoms']}")
    if slots.get("psychotic_like_symptoms"):
        context_parts.append(f"Psychotic-like Symptoms: {slots['psychotic_like_symptoms']}")

    # GROUP J: Historical Context (for later use)
    if slots.get("past_episodes"):
        episodes = slots['past_episodes']
        if isinstance(episodes, list):
            context_parts.append(f"Past Episodes: {', '.join(episodes)}")
        else:
            context_parts.append(f"Past Episodes: {episodes}")
    if slots.get("treatment_history"):
        history = slots['treatment_history']
        if isinstance(history, list):
            context_parts.append(f"Treatment History: {', '.join(history)}")
        else:
            context_parts.append(f"Treatment History: {history}")
    if slots.get("family_history"):
        fam_history = slots['family_history']
        if isinstance(fam_history, list):
            context_parts.append(f"Family History: {', '.join(fam_history)}")
        else:
            context_parts.append(f"Family History: {fam_history}")

    # GROUP K: Derived/State Fields
    if slots.get("need"):
        needs = slots['need']
        if isinstance(needs, list):
            context_parts.append(f"What They Need: {', '.join(needs)}")
        else:
            context_parts.append(f"What They Need: {needs}")
    if slots.get("impact"):
        impacts = slots['impact']
        if isinstance(impacts, list):
            context_parts.append(f"Impact: {', '.join(impacts)}")
        else:
            context_parts.append(f"Impact: {impacts}")

    # Metadata
    current_stage = get_current_stage(slots)
    if current_stage != "complete":
        context_parts.append(f"📍 Current Intake Stage: {current_stage}")
    else:
        context_parts.append(f"✅ Intake Complete")

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
    
    primary_moods = slots.get("primary_mood", [])
    if primary_moods:
        if isinstance(primary_moods, list):
            keywords.extend([m.lower() for m in primary_moods if m])
        elif isinstance(primary_moods, str):  # Backward compatibility
            keywords.append(primary_moods.lower())
    
    # Stress-related keywords
    stress_level = slots.get("stress_level", [])
    current_stressors = slots.get("current_stressors", [])
    has_stress_info = (
        (isinstance(stress_level, list) and len(stress_level) > 0) or
        (isinstance(stress_level, str) and stress_level) or
        (isinstance(current_stressors, list) and len(current_stressors) > 0)
    )
    if has_stress_info:
        keywords.extend(["stress", "pressure", "workload", "tension", "worry", "stress management", "relaxation"])
    
    # Energy/fatigue keywords
    energy_levels = slots.get("energy_level", [])
    if energy_levels:
        energy_list = energy_levels if isinstance(energy_levels, list) else [energy_levels]
        for energy in energy_list:
            if energy:
                energy_lower = energy.lower()
                if "low" in energy_lower or "thấp" in energy_lower:
                    keywords.extend(["fatigue", "tired", "exhaustion", "energy", "rest"])
                    break  # Only add once
    
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
    triggers = slots.get("trigger", [])
    if triggers:
        # Handle both list and string (backward compatibility)
        trigger_list = triggers if isinstance(triggers, list) else [triggers]
        for trigger in trigger_list:
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


def validate_duration(duration_text: Optional[Any]) -> Tuple[bool, str]:
    """
    Check if duration is specific enough for DSM-5 criteria.
    
    FIXED LOGIC:
    1. Check for number + time unit FIRST → specific
    2. Then check vague terms
    3. Then check approximate terms
    
    Args:
        duration_text: Duration string or list
    
    Returns:
        Tuple of (is_specific, certainty_level)
        - is_specific: True if duration meets minimum specificity
        - certainty_level: 'specific', 'approximate', 'vague'
    """
    if not duration_text:
        return False, "vague"
    
    # Handle list: check most specific duration
    if isinstance(duration_text, list):
        best_certainty = "vague"
        best_specific = False
        for d in duration_text:
            is_spec, cert = validate_duration(d)
            if cert == "specific":
                return True, "specific"
            if cert == "approximate" and best_certainty == "vague":
                best_certainty = "approximate"
                best_specific = True
        return best_specific, best_certainty
    
    duration_lower = str(duration_text).lower()
    
    # Priority 1: Specific (number + time unit) → BEST
    has_number = any(char.isdigit() for char in duration_text)
    time_units = ["day", "days", "week", "weeks", "month", "months", "year", "years",
                  "ngày", "tuần", "tháng", "năm"]
    if has_number and any(unit in duration_lower for unit in time_units):
        return True, "specific"
    
    # Priority 2: Vague terms → INSUFFICIENT
    vague_terms = ["lately", "recently", "just now", "gần đây", "dạo này", "mới đây"]
    if any(term in duration_lower for term in vague_terms):
        return False, "vague"
    
    # Priority 3: Approximate terms → ACCEPTABLE
    approximate_terms = ["several", "few", "about", "around", "approximately", 
                        "vài", "khoảng"]
    if any(term in duration_lower for term in approximate_terms):
        return True, "approximate"
    
    # Default: if has substance (length > 5), treat as approximate
    if len(duration_text) > 5:
        return True, "approximate"
    
    return False, "vague"


def is_empty_slot(value: Any) -> bool:
    """
    Check if a slot value is considered empty/missing.
    
    Rules:
    - None → empty
    - Empty string → empty
    - "unknown" (tri-state) → empty
    - Empty list [] → empty
    - List with only empty strings → empty
    - "no ..." string → NOT empty (valid data)
    
    Args:
        value: Slot value to check
    
    Returns:
        True if slot is empty/missing
    """
    if value is None:
        return True
    
    if isinstance(value, str):
        v = value.strip().lower()
        if v == "":
            return True
        # Tri-state: "unknown" is empty, but "yes"/"no" are valid
        if v in TRI_STATES:
            return v == "unknown"
        # Regular string: "none" without context is empty, but "no ..." is valid
        # Simple heuristic: if string contains space, it's descriptive (valid)
        if v == "none":
            return True
        return False
    
    if isinstance(value, list):
        if len(value) == 0:
            return True
        # List with only empty/whitespace strings
        return all(not str(x).strip() for x in value)
    
    if isinstance(value, bool):
        return False  # Booleans are always valid
    
    return False


def next_missing_slot(slots: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Find the next missing required slot following stage flow.
    
    Args:
        slots: Current slot dictionary
    
    Returns:
        Tuple of (stage_name, slot_name) or (None, None) if all complete
    """
    for stage in STAGE_FLOW:
        required_in_stage = REQUIRED_SLOTS_BY_STAGE.get(stage, [])
        
        for slot_name in required_in_stage:
            # Special handling for duration: must be specific
            if slot_name == "duration":
                is_specific, certainty = validate_duration(slots.get("duration"))
                slots["duration_certainty"] = certainty
                if not is_specific:
                    return stage, "duration"
                continue
            
            # Special handling for detail slots: only required if _any = "yes"
            if slot_name == "substance_use":
                if slots.get("substance_use_any", "unknown").lower() == "yes":
                    if is_empty_slot(slots.get("substance_use")):
                        return stage, "substance_use"
                continue
            
            if slot_name == "medical_history":
                if slots.get("medical_history_any", "unknown").lower() == "yes":
                    if is_empty_slot(slots.get("medical_history")):
                        return stage, "medical_history"
                continue
            
            # Regular slot check
            if is_empty_slot(slots.get(slot_name)):
                return stage, slot_name
    
    return None, None


def is_intake_complete(slots: Dict[str, Any]) -> bool:
    """
    Check if all required slots are filled (intake complete).
    
    Args:
        slots: Slot dictionary
    
    Returns:
        True if all required slots filled
    """
    stage, missing = next_missing_slot(slots)
    complete = (missing is None)
    slots["intake_complete"] = complete
    return complete


def get_current_stage(slots: Dict[str, Any]) -> str:
    """
    Determine current stage in intake flow based on filled slots.
    
    Args:
        slots: Slot dictionary
    
    Returns:
        Current stage name (or "complete" if all done)
    """
    stage, _ = next_missing_slot(slots)
    return stage if stage else "complete"


def has_sufficient_slots(slots: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """
    Check if required slots are filled sufficiently for retrieval.
    REDESIGNED: Uses stage-based logic for DSM-5 intake flow.
    
    Workflow:
    1. Gather all required slots from all stages (union)
    2. Check which required slots are missing using is_empty_slot()
    3. Return first missing slot via next_missing_slot()
    
    Args:
        slots: Slot dictionary
    
    Returns:
        Tuple of (is_sufficient, required_missing_slots, differential_missing_slots)
        - is_sufficient: True if all required slots filled across all stages
        - required_missing_slots: Critical slots still missing
        - differential_missing_slots: Always [] (kept for backward compatibility)
    
    Backward Compatibility:
        - Still returns 3-tuple format
        - differential_missing_slots always [] (obsolete with new tri-state design)
    """
    if not slots:
        # Return all required slots from all stages
        all_required = []
        for stage_slots in REQUIRED_SLOTS_BY_STAGE.values():
            all_required.extend(stage_slots)
        return False, all_required, []
    
    # Gather all required slots across all stages
    all_required_slots = set()
    for stage_slots in REQUIRED_SLOTS_BY_STAGE.values():
        all_required_slots.update(stage_slots)
    
    # Check which required slots are missing
    required_missing = []
    for slot_name in all_required_slots:
        value = slots.get(slot_name)
        if is_empty_slot(slot_name, value):
            required_missing.append(slot_name)
            logger.debug(f"[SLOT CHECK] Required slot '{slot_name}' is empty: {value}")
    
    # Determine sufficiency: all required slots must be filled
    is_sufficient = len(required_missing) == 0
    
    # Differential missing is deprecated (tri-state design handles exclusion)
    differential_missing = []
    
    logger.info(f"[SLOT SUFFICIENCY CHECK]")
    logger.info(f"  Required missing ({len(required_missing)}): {required_missing}")
    logger.info(f"  Is sufficient: {is_sufficient}")
    logger.info(f"  Current stage: {get_current_stage(slots)}")
    logger.info(f"  Next missing slot: {next_missing_slot(slots)}")
    
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
    duration = slots.get("duration", [])
    is_specific, certainty = validate_duration(duration)
    if not is_specific or certainty == "vague":
        return False
    
    # Check if duration indicates chronicity (contains month/year or >= 2 weeks)
    if duration:
        # Handle both list and string
        duration_list = duration if isinstance(duration, list) else [duration]
        has_chronic = False
        for dur in duration_list:
            if dur:
                duration_lower = dur.lower()
                has_chronic_marker = any(term in duration_lower for term in 
                    ["tháng", "month", "năm", "year", "chronic", "mãn tính"])
                has_two_weeks = "2" in duration_lower and any(term in duration_lower for term in ["week", "tuần"])
                
                if has_chronic_marker or has_two_weeks:
                    has_chronic = True
                    break
        
        if not has_chronic:
            # Duration too short for disorder diagnosis
            return False
    
    # 2. Check impairment - must have clear functional impact
    daily_func = slots.get("daily_functioning", [])
    work_impact = slots.get("work_school_impact", [])
    
    # Check if any value indicates impairment
    daily_func_list = daily_func if isinstance(daily_func, list) else [daily_func]
    work_impact_list = work_impact if isinstance(work_impact, list) else [work_impact]
    
    has_impairment = (
        any(val in ["moderate", "severe", "moderate_impairment"] for val in daily_func_list if val) or
        any(val in ["moderate", "severe", "unable"] for val in work_impact_list if val)
    )
    if not has_impairment:
        return False
    
    # 3. Check differential exclusion - must have checked medical/substance
    medical_history = slots.get("medical_history", [])
    substance_use = slots.get("substance_use", [])
    has_checked_exclusion = (
        (isinstance(medical_history, list) and len(medical_history) > 0) or
        (isinstance(substance_use, list) and len(substance_use) > 0) or
        (isinstance(medical_history, str) and medical_history) or  # Backward compat
        (isinstance(substance_use, str) and substance_use)  # Backward compat
    )
    if not has_checked_exclusion:
        return False
    
    # 4. Check for acute stress (if recent life event within days, likely adjustment not disorder)
    recent_events = slots.get("recent_life_events", [])
    if recent_events:
        # Handle both list and string
        events_list = recent_events if isinstance(recent_events, list) else [recent_events]
        acute_markers = ["hôm qua", "yesterday", "tuần này", "this week", "vừa mới", "just"]
        for event in events_list:
            if event:
                recent_lower = event.lower()
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
    primary_moods = slots.get("primary_mood", [])
    if emotions or primary_moods:
        if primary_moods:
            moods_list = primary_moods if isinstance(primary_moods, list) else [primary_moods]
            if moods_list:
                parts.append(f"feeling {', '.join(moods_list)}")
        elif emotions:
            parts.append(f"experiencing {', '.join(emotions)}")
    
    # Intensity
    intensities = slots.get("intensity", [])
    if intensities:
        intensity_list = intensities if isinstance(intensities, list) else [intensities]
        if intensity_list:
            parts.append(f"at {', '.join(intensity_list)} intensity")
    
    # Duration
    durations = slots.get("duration", [])
    if durations:
        duration_list = durations if isinstance(durations, list) else [durations]
        if duration_list:
            parts.append(f"for {', '.join(duration_list)}")
    
    # Trigger
    triggers = slots.get("trigger")
    if triggers:
        if isinstance(triggers, list) and triggers:
            parts.append(f"triggered by {', '.join(triggers)}")
        elif isinstance(triggers, str):  # Backward compatibility
            parts.append(f"triggered by {triggers}")
    
    # Impact
    impacts = slots.get("impact", [])
    if impacts:
        impact_list = impacts if isinstance(impacts, list) else [impacts]
        if impact_list:
            parts.append(f"impacting: {', '.join(impact_list)}")
    
    # Stress level
    stress_levels = slots.get("stress_level", [])
    if stress_levels:
        stress_list = stress_levels if isinstance(stress_levels, list) else [stress_levels]
        if stress_list:
            parts.append(f"stress level: {', '.join(stress_list)}")
    
    # Physical symptoms
    physical = slots.get("physical_symptoms", [])
    if physical:
        parts.append(f"with physical symptoms: {', '.join(physical)}")
    
    # Sleep issues
    sleep_qualities = slots.get("sleep_quality", [])
    if sleep_qualities:
        quality_list = sleep_qualities if isinstance(sleep_qualities, list) else [sleep_qualities]
        quality_list = [q for q in quality_list if q and q != "good"]
        if quality_list:
            parts.append(f"sleep quality: {', '.join(quality_list)}")
    
    # What they need
    needs = slots.get("need", [])
    if needs:
        need_list = needs if isinstance(needs, list) else [needs]
        if need_list:
            parts.append(f"seeking: {', '.join(need_list)}")
    
    if not parts:
        return ""
    
    return " | ".join(parts)

