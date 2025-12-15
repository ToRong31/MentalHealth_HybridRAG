"""
Slot Filling Node
Node wrapper for slot filling logic
"""
from typing import Dict, Any

from src.rag.llm.answer_nodes.slot_filling import process_slot_filling


async def slot_filling_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Extract structured information (slots) from user question.
    
    Args:
        state: State dict with question
    
    Returns:
        Updated state with slots, missing_slots, relevant_missing_slots, follow_up_questions
    """
    question = state["question"]
    
    # Call logic function
    result = await process_slot_filling(question)
    
    # Update state with result
    state.update(result)
    
    return state
