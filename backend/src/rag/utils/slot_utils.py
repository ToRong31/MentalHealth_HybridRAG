"""
Utility functions to filter follow-up questions based on required slots
"""
from typing import List

# Import REQUIRED_SLOTS from slots.py
from src.rag.utils.slots import REQUIRED_SLOTS


def filter_follow_up_for_required_only(
    follow_up_questions: List[str],
    relevant_missing_slots: List[str]
) -> List[str]:
    """
    Filter follow-up questions to keep only those about REQUIRED_SLOTS.
    Used when REQUIRED slots are not yet sufficient.
    
    Assumes follow_up_questions are in same order as relevant_missing_slots (1:1 mapping).
    
    Args:
        follow_up_questions: All generated follow-up questions (ordered by slot)
        relevant_missing_slots: All relevant missing slots (ordered)
    
    Returns:
        Filtered list of questions that correspond to REQUIRED slots only
    """
    if not follow_up_questions or not relevant_missing_slots:
        return follow_up_questions
    
    required_set = set(REQUIRED_SLOTS)
    
    # Filter questions based on whether corresponding slot is REQUIRED
    filtered = []
    for i, slot_name in enumerate(relevant_missing_slots):
        if slot_name in required_set and i < len(follow_up_questions):
            filtered.append(follow_up_questions[i])
    
    return filtered
