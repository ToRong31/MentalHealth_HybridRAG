from typing import Any, Dict, List, Optional


def get_default_slots() -> Dict[str, Any]:
    """
    Return default empty slots structure.
    """
    return {
        "emotion": [],
        "primary_mood": None,
        "intensity": None,
        "trigger": None,
        "duration": None,
        "impact": None,
        "risk_level": "none",
        "need": None,
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
        "stress_level": None,
        "suicidal_ideation": None,
        "self_harm_thoughts": None,
        "current_treatment": None,
        "medication": None,
    }


def build_slot_context(slots: Dict[str, Any]) -> str:
    """
    Build formatted context string from slots for answer generation.
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
        context_parts.append(f"Duration: {slots['duration']}")
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

    # Needs
    if slots.get("need"):
        context_parts.append(f"What they need: {slots['need']}")

    if not context_parts:
        return ""

    return "Additional Context from User's Message:\n" + "\n".join(f"- {part}" for part in context_parts)


def get_slot_keywords(slots: Dict[str, Any]) -> List[str]:
    """
    Extract keywords from slots for rerank bonus calculation.
    Maps slot values to relevant keywords that might appear in node names.
    
    Args:
        slots: Slot dictionary
    
    Returns:
        List of keywords for matching against node names
    """
    keywords = []
    
    if not slots:
        return keywords
    
    # Sleep-related keywords
    if slots.get("sleep_quality") or slots.get("sleep_duration"):
        keywords.extend(["sleep", "insomnia", "bedtime", "rest", "night", "caffeine", "melatonin"])
    
    # Emotion/mood keywords
    emotions = slots.get("emotion", [])
    if emotions:
        # Add emotion names directly
        keywords.extend([e.lower() for e in emotions])
        # Add related terms
        keywords.extend(["mood", "feeling", "emotion", "anxiety", "depression", "stress"])
    
    primary_mood = slots.get("primary_mood")
    if primary_mood:
        keywords.append(primary_mood.lower())
    
    # Stress-related keywords
    if slots.get("stress_level") or slots.get("current_stressors"):
        keywords.extend(["stress", "pressure", "workload", "tension", "worry"])
    
    # Energy/fatigue keywords
    if slots.get("energy_level"):
        energy = slots.get("energy_level", "").lower()
        if "low" in energy or "thấp" in energy:
            keywords.extend(["fatigue", "tired", "exhaustion", "energy"])
    
    # Physical symptoms keywords
    physical = slots.get("physical_symptoms", [])
    if physical:
        keywords.extend([s.lower() for s in physical])
        keywords.extend(["symptom", "physical", "body"])
    
    # Social keywords
    if slots.get("social_isolation") or slots.get("social_withdrawal"):
        keywords.extend(["social", "isolation", "lonely", "withdrawal", "connection"])
    
    # Coping keywords
    if slots.get("coping_mechanisms"):
        keywords.extend(["coping", "strategy", "technique", "manage", "handle"])
    
    # Trigger keywords (if specific)
    trigger = slots.get("trigger")
    if trigger:
        trigger_lower = trigger.lower()
        # Add common trigger-related terms
        if "work" in trigger_lower or "công việc" in trigger_lower:
            keywords.extend(["work", "job", "career", "professional"])
        if "family" in trigger_lower or "gia đình" in trigger_lower:
            keywords.extend(["family", "relationship", "home"])
        if "school" in trigger_lower or "học" in trigger_lower:
            keywords.extend(["school", "study", "education", "academic"])
    
    # Remove duplicates and empty strings
    keywords = list(set([k for k in keywords if k]))
    
    return keywords

