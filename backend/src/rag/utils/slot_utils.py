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
    
    UPDATED LOGIC: 
    - If we have REQUIRED missing slots, keep ALL follow-up questions
    - The LLM already generated contextually appropriate questions
    - We trust the LLM's judgment on what to ask
    
    Args:
        follow_up_questions: All generated follow-up questions
        relevant_missing_slots: All relevant missing slots
    
    Returns:
        All follow-up questions if ANY required slot is missing, otherwise empty list
    """
    if not follow_up_questions:
        return []
    
    if not relevant_missing_slots:
        return []
    
    required_set = set(REQUIRED_SLOTS)
    
    # Check if ANY of the missing slots is REQUIRED
    has_required_missing = any(slot in required_set for slot in relevant_missing_slots)
    
    if has_required_missing:
        # Keep ALL questions - LLM already filtered them contextually
        return follow_up_questions
    else:
        # All missing slots are optional - don't ask now
        return []
