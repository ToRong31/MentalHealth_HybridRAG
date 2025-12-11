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
