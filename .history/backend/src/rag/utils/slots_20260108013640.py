from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# DSM-5 Aligned Slot Groups for Structured Intake
# Organized by diagnostic pillars: Symptoms, Timeline, Severity, Impairment, Exclusion
DIAGNOSTIC_SLOTS = {
    # 1) PRESENTING - Chief complaint and core emotions
    "presenting": [
        "presenting_problem",  # One-sentence chief complaint
        "emotion",
        "primary_mood"
    ],

    # 2) TIMELINE/COURSE - When, how long, how often
    "timeline": [
        "onset",               # When symptoms started
        "duration",            # How long
        "frequency",           # How often (daily, weekly, episodic)
        "symptom_fluctuation", # Constant vs fluctuating
        "time_of_day_pattern"  # When worst (optional)
    ],

    # 3) SEVERITY - How intense/distressing
    "severity": [
        "intensity",
        "distress_level",      # Subjective distress (0-10 or mild/moderate/severe)
        "stress_level"
    ],

    # 4) IMPAIRMENT/FUNCTIONING - Impact on life domains
    "functioning": [
        "daily_functioning",
        "work_school_impact",
        "social_functioning",  # Relationships/social activities
        "self_care_functioning" # Eating, hygiene, self-care
    ],

    # 5) SOMATIC/BIO - Physical symptoms
    "somatic": [
        "physical_symptoms",
        "sleep_quality",
        "sleep_duration",
        "energy_level",
        "appetite_changes"
    ],

    # 6) CONTEXT - Triggers, stressors, life events
    "context": [
        "trigger",
        "current_stressors",
        "recent_life_events"
    ],

    # 7) EXCLUSION - Rule out medical/substance causes (CRITICAL for differential diagnosis)
    "exclusion": [
        "substance_use_any",     # Gateway: yes/no/unknown
        "substance_use",         # Details if yes
        "medical_history_any",   # Gateway: yes/no/unknown
        "medical_history",       # Details if yes
        "medication_changes",    # Recent med changes
        "caffeine_nicotine_use"  # Stimulant use
    ],

    # 8) SUPPORT/COPING - Resources and strategies
    "support_coping": [
        "support_system",
        "coping_mechanisms",
        "coping_effectiveness",
        "need"
    ],

    # 9) CROSS-CUTTING SCREENS - Screen for comorbidities
    "screens": [
        "mania_like_symptoms",    # Screen for bipolar
        "psychotic_like_symptoms" # Screen for psychosis
    ]
}

# Stage flow order - chatbot asks in this sequence
STAGE_FLOW = [
    "presenting",
    "timeline",
    "severity",
    "functioning",
    "somatic",
    "context",
    "exclusion",
    "support_coping",
    "screens"
]

# Required slots per stage (must be filled before moving to diagnosis)
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
        "coping_mechanisms",
        "coping_effectiveness",
        "need"
    ],
    "screens": [
        "mania_like_symptoms",
        "psychotic_like_symptoms"
    ]
}

# Flatten for backward compatibility
REQUIRED_SLOTS = [s for stage in STAGE_FLOW if stage in REQUIRED_SLOTS_BY_STAGE for s in REQUIRED_SLOTS_BY_STAGE[stage]]

# Tri-state values for yes/no/unknown slots
TRI_STATES = {"yes", "no", "unknown"}


def get_default_slots() -> Dict[str, Any]:
    """
    Return default empty slots structure.
    All slots initialized as None or empty list to support merging.
    risk_level default is 'unknown' to avoid false sense of safety.
    """
    return {
        "emotion": [],
        "primary_mood": [],  # Changed to list - mood can evolve over conversation
        "intensity": [],  # Changed to list - intensity can vary across symptoms
        "trigger": [],  # Changed to list - user can have multiple triggers
        "duration": [],  # Changed to list - different symptoms may have different durations
        "impact": [],  # Changed to list - multiple impact areas
        "risk_level": [],  # Changed to list - risk can change over conversation
        "need": [],  # Changed to list - user may have multiple needs
        "stress_level": [],  # Changed to list - stress can vary
        "physical_symptoms": [],
        "sleep_quality": [],  # Changed to list - can describe multiple sleep issues
        "sleep_duration": [],  # Changed to list - sleep duration can vary
        "energy_level": [],  # Changed to list - energy can fluctuate
        "appetite_changes": [],  # Changed to list - multiple appetite changes
        "daily_functioning": [],  # Changed to list - functioning in different areas
        "work_school_impact": [],  # Changed to list - multiple impact areas
        "support_system": [],  # Changed to list - multiple support sources
        "family_support": [],  # Changed to list - various family support aspects
        "friend_support": [],  # Changed to list - various friend support aspects
        "social_isolation": None,  # Boolean - keep as scalar
        "social_withdrawal": None,  # Boolean - keep as scalar
        "coping_mechanisms": [],
        "coping_effectiveness": [],  # Changed to list - effectiveness of different coping strategies
        "current_stressors": [],
        "suicidal_ideation": None,  # Boolean - keep as scalar for safety
        "self_harm_thoughts": None,  # Boolean - keep as scalar for safety
        "current_treatment": [],  # Changed to list - user may have multiple treatments
        "medication": [],  # Changed to list - user may take multiple medications
        # Differential diagnosis slots - để tránh chẩn đoán sai
        "substance_use": [],  # Changed to list - can use multiple substances
        "medical_history": [],  # Changed to list - can have multiple conditions
        "recent_life_events": [],  # Changed to list - can have multiple life events
        "symptom_fluctuation": [],  # Changed to list - different symptoms have different patterns
        "history_of_trauma": [],  # Changed to list - can have multiple traumatic experiences
        # Derived fields để kiểm soát chẩn đoán
        "diagnostic_confidence": "low",  # low/medium/high - scalar derived field
        "potential_differentials": [],   # Danh sách các bệnh có thể nhầm lẫn
        "duration_certainty": "vague",   # vague/approximate/specific - scalar derived field
    }


def merge_slots(existing_slots: Optional[Dict[str, Any]], new_slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge new slots into existing slots (append/update instead of replace).
    
    CRITICAL FIXES:
    - NO LONGER SKIP "no"/"none" answers - these are valid data points
    - Only skip: None, empty string, or empty list
    - Derive *_current fields from severity lists for max severity comparison
    
    Rules:
    - List fields: Append unique values (deduplicate)
    - Tri-state fields: Update if new value is more informative
    - Scalar fields: Update only if new value not None/empty
    - Severity fields: Derive *_current = max from list
    
    Args:
        existing_slots: Current slots from state (may be None on first turn)
        new_slots: Newly extracted slots from current turn
    
    Returns:
        Merged slots dictionary
    """
    # Severity mapping for comparison (ordered low to high)
    SEVERITY_ORDER = {
        "risk_level": ["unknown", "none", "low", "medium", "high"],
        "intensity": ["unknown", "low", "medium", "high", "very_high", "overwhelming"],
        "intensity_current": ["unknown", "low", "medium", "high", "very_high", "overwhelming"],
        "stress_level": ["unknown", "low", "moderate", "high", "overwhelming"],
        "stress_level_current": ["unknown", "low", "moderate", "high", "overwhelming"],
        "distress_level": ["unknown", "mild", "moderate", "severe", "extreme"],
        "distress_level_current": ["unknown", "mild", "moderate", "severe", "extreme"]
    }
    
    # Initialize with defaults if no existing slots
    if not existing_slots:
        merged = get_default_slots()
    else:
        merged = existing_slots.copy()
    
    # Helper: compute max severity from list
    def max_severity(key: str, values: list) -> str:
        """Find highest severity value in list based on SEVERITY_ORDER."""
        order = SEVERITY_ORDER.get(key, [])
        if not order:
            return "unknown"
        best = "unknown"
        best_idx = -1
        for v in values:
            if isinstance(v, str) and v.lower() in order:
                idx = order.index(v.lower())
                if idx > best_idx:
                    best_idx = idx
                    best = v.lower()
        return best if best_idx >= 0 else "unknown"
    
    # Merge each slot
    for key, new_value in new_slots.items():
        existing_value = merged.get(key)
        
        # Skip if new value is None or "none" or empty
        if new_value is None or new_value == "none" or new_value == []:
            continue
        
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
        moods = slots['primary_mood']
        if isinstance(moods, list) and moods:
            context_parts.append(f"Primary moods: {', '.join(moods)}")
        elif isinstance(moods, str):  # Backward compatibility
            context_parts.append(f"Primary mood: {moods}")
    if slots.get("intensity"):
        intensities = slots['intensity']
        if isinstance(intensities, list) and intensities:
            context_parts.append(f"Intensity levels: {', '.join(intensities)}")
        elif isinstance(intensities, str):  # Backward compatibility
            context_parts.append(f"Intensity: {intensities}")
    if slots.get("trigger"):
        triggers = slots['trigger']
        if isinstance(triggers, list) and triggers:
            context_parts.append(f"Triggers: {', '.join(triggers)}")
        elif isinstance(triggers, str):  # Backward compatibility
            context_parts.append(f"Trigger: {triggers}")
    if slots.get("duration"):
        durations = slots['duration']
        duration_certainty = slots.get("duration_certainty", "vague")
        if isinstance(durations, list) and durations:
            context_parts.append(f"Durations: {', '.join(durations)} (certainty: {duration_certainty})")
        elif isinstance(durations, str):  # Backward compatibility
            context_parts.append(f"Duration: {durations} (certainty: {duration_certainty})")
    if slots.get("impact"):
        impacts = slots['impact']
        if isinstance(impacts, list) and impacts:
            context_parts.append(f"Impacts: {', '.join(impacts)}")
        elif isinstance(impacts, str):  # Backward compatibility
            context_parts.append(f"Impact: {impacts}")

    # Physical & functional
    if slots.get("physical_symptoms"):
        context_parts.append(f"Physical symptoms: {', '.join(slots['physical_symptoms'])}")
    if slots.get("sleep_quality"):
        quality = slots['sleep_quality']
        if isinstance(quality, list) and quality:
            context_parts.append(f"Sleep quality: {', '.join(quality)}")
        elif isinstance(quality, str):  # Backward compatibility
            context_parts.append(f"Sleep quality: {quality}")
    if slots.get("sleep_duration"):
        duration = slots['sleep_duration']
        if isinstance(duration, list) and duration:
            context_parts.append(f"Sleep duration: {', '.join(duration)}")
        elif isinstance(duration, str):  # Backward compatibility
            context_parts.append(f"Sleep duration: {duration}")
    if slots.get("energy_level"):
        energy = slots['energy_level']
        if isinstance(energy, list) and energy:
            context_parts.append(f"Energy levels: {', '.join(energy)}")
        elif isinstance(energy, str):  # Backward compatibility
            context_parts.append(f"Energy level: {energy}")
    if slots.get("daily_functioning"):
        functioning = slots['daily_functioning']
        if isinstance(functioning, list) and functioning:
            context_parts.append(f"Daily functioning: {', '.join(functioning)}")
        elif isinstance(functioning, str):  # Backward compatibility
            context_parts.append(f"Daily functioning: {functioning}")
    if slots.get("work_school_impact"):
        impact = slots['work_school_impact']
        if isinstance(impact, list) and impact:
            context_parts.append(f"Work/school impact: {', '.join(impact)}")
        elif isinstance(impact, str):  # Backward compatibility
            context_parts.append(f"Work/school impact: {impact}")

    # Social & support
    if slots.get("support_system"):
        support = slots['support_system']
        if isinstance(support, list) and support:
            context_parts.append(f"Support system: {', '.join(support)}")
        elif isinstance(support, str):  # Backward compatibility
            context_parts.append(f"Support system: {support}")
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
        stress = slots['stress_level']
        if isinstance(stress, list) and stress:
            context_parts.append(f"Stress levels: {', '.join(stress)}")
        elif isinstance(stress, str):  # Backward compatibility
            context_parts.append(f"Stress level: {stress}")

    # Differential diagnosis information (CRITICAL FOR PREVENTING PREMATURE DIAGNOSIS)
    if slots.get("recent_life_events"):
        events = slots['recent_life_events']
        if isinstance(events, list) and events:
            context_parts.append(f"Recent life events: {', '.join(events)}")
        elif isinstance(events, str):  # Backward compatibility
            context_parts.append(f"Recent life events: {events}")
    if slots.get("substance_use"):
        substances = slots['substance_use']
        if isinstance(substances, list) and substances:
            context_parts.append(f"Substance use: {', '.join(substances)}")
        elif isinstance(substances, str):  # Backward compatibility
            context_parts.append(f"Substance use: {substances}")
    if slots.get("medical_history"):
        history = slots['medical_history']
        if isinstance(history, list) and history:
            context_parts.append(f"Medical history: {', '.join(history)}")
        elif isinstance(history, str):  # Backward compatibility
            context_parts.append(f"Medical history: {history}")
    if slots.get("symptom_fluctuation"):
        fluctuation = slots['symptom_fluctuation']
        if isinstance(fluctuation, list) and fluctuation:
            context_parts.append(f"Symptom patterns: {', '.join(fluctuation)}")
        elif isinstance(fluctuation, str):  # Backward compatibility
            context_parts.append(f"Symptom pattern: {fluctuation}")
    
    # Diagnostic caution flags
    diagnostic_confidence = slots.get("diagnostic_confidence", "low")
    context_parts.append(f"⚠️ Diagnostic confidence: {diagnostic_confidence}")
    
    # Needs
    if slots.get("need"):
        needs = slots['need']
        if isinstance(needs, list) and needs:
            context_parts.append(f"What they need: {', '.join(needs)}")
        elif isinstance(needs, str):  # Backward compatibility
            context_parts.append(f"What they need: {needs}")

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


def validate_duration(duration_text: Optional[str]) -> Tuple[bool, str]:
    """
    Kiểm tra xem duration có cụ thể không.
    
    Args:
        duration_text: Duration string or list from slot
    
    Returns:
        Tuple of (is_specific, certainty_level)
        - is_specific: True if duration is specific enough
        - certainty_level: 'specific', 'approximate', 'vague'
    """
    if not duration_text:
        return False, "vague"
    
    # If list, check the most specific duration
    if isinstance(duration_text, list):
        if not duration_text:
            return False, "vague"
        # Check all durations and return best certainty
        best_is_specific = False
        best_certainty = "vague"
        for dur in duration_text:
            if dur:
                is_spec, cert = validate_duration(dur)  # Recursive call
                if cert == "specific":
                    return True, "specific"
                elif cert == "approximate" and best_certainty == "vague":
                    best_is_specific = is_spec
                    best_certainty = cert
        return best_is_specific, best_certainty
    
    duration_lower = duration_text.lower()
    
    # Vague terms -> not sufficient
    vague_terms = ["lately", "gần đây", "dạo này", "recently", "just now", "mới đây"]
    if any(term in duration_lower for term in vague_terms):
        return False, "vague"
    
    # Approximate terms -> acceptable but mark as approximate
    approximate_terms = ["vài", "several", "khoảng", "around", "about", "tuần", "week"]
    if any(term in duration_lower for term in approximate_terms):
        return True, "approximate"
    
    # Specific terms (numbers, months, years) -> best
    specific_terms = ["tháng", "month", "năm", "year", "ngày", "day"]
    has_number = any(char.isdigit() for char in duration_text)
    if has_number and any(term in duration_lower for term in specific_terms):
        return True, "specific"
    
    # Default: treat as approximate if it has some substance
    if len(duration_text) > 5:  # Not just "1-2 words"
        return True, "approximate"
    
    return False, "vague"


def has_sufficient_slots(slots: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """
    Check if required slots are filled sufficiently for retrieval.
    FIXED: Now properly validates duration and checks differential slots.
    
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
            # Handle both list and string
            if isinstance(value, list):
                if not value or len(value) == 0:
                    required_missing.append("duration")
                    continue
                # Check if any duration is specific
                is_specific, certainty = validate_duration(value)
            else:
                is_specific, certainty = validate_duration(value)
            
            if not is_specific:
                required_missing.append("specific_duration")
                # Update slot certainty for later use
                if slots.get("duration_certainty") == "vague":
                    slots["duration_certainty"] = certainty
            continue
        
        # Check if slot is actually filled (handle both list and scalar)
        is_empty = False
        if isinstance(value, list):
            # List slot: must have at least one non-empty item
            is_empty = len(value) == 0 or all(not item for item in value)
        else:
            # Scalar slot: must not be None, empty string, or "none"
            is_empty = value is None or value == "" or value == "none"
        
        if is_empty:
            required_missing.append(slot_name)
            logger.debug(f"[SLOT CHECK] Required slot '{slot_name}' is empty: {value}")
    
    # Check functional impairment (CRITICAL for severity assessment)
    # UPGRADED: Now treated as REQUIRED (not just differential)
    # Need at least ONE of: daily_functioning or work_school_impact
    daily_func = slots.get("daily_functioning", [])
    work_impact = slots.get("work_school_impact", [])
    
    has_functional_info = (
        (isinstance(daily_func, list) and len(daily_func) > 0 and any(item for item in daily_func)) or
        (isinstance(daily_func, str) and daily_func and daily_func != "none") or
        (isinstance(work_impact, list) and len(work_impact) > 0 and any(item for item in work_impact)) or
        (isinstance(work_impact, str) and work_impact and work_impact != "none")
    )
    
    if not has_functional_info:
        required_missing.append("functional_impairment")  # CHANGED: Now REQUIRED
        logger.debug(f"[FUNCTIONAL CHECK] Missing functional impairment: daily_functioning={daily_func}, work_school_impact={work_impact}")
    else:
        logger.debug(f"[FUNCTIONAL CHECK] Has functional info: daily_functioning={daily_func}, work_school_impact={work_impact}")
    
    # Check differential diagnosis slots (CRITICAL for preventing misdiagnosis)
    # If physical symptoms present, MUST check medical exclusion
    physical_symptoms = slots.get("physical_symptoms", [])
    if physical_symptoms and len(physical_symptoms) > 0:
        medical_history = slots.get("medical_history", [])
        substance_use = slots.get("substance_use", [])
        has_medical_check = (
            (isinstance(medical_history, list) and len(medical_history) > 0) or
            (isinstance(substance_use, list) and len(substance_use) > 0)
        )
        if not has_medical_check:
            differential_missing.append("medical_exclusion")
    
    # NOTE: recent_life_events is already checked in REQUIRED_SLOTS loop above
    # No need to check again here to avoid duplicate
    
    # Logic: Sufficient ONLY if ALL required slots AND functional impairment are filled
    # STRICT: Must have ZERO missing required slots (no tolerance)
    # Also require at most 1 differential missing (lenient for differential)
    is_sufficient = len(required_missing) == 0 and len(differential_missing) <= 1
    
    logger.info(f"[SLOT SUFFICIENCY CHECK]")
    logger.info(f"  Required missing ({len(required_missing)}): {required_missing}")
    logger.info(f"  Differential missing ({len(differential_missing)}): {differential_missing}")
    logger.info(f"  Is sufficient: {is_sufficient}")
    logger.info(f"  Current slots: emotion={slots.get('emotion')}, duration={slots.get('duration')}, impact={slots.get('impact')}, intensity={slots.get('intensity')}, recent_life_events={slots.get('recent_life_events')}")
    
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

