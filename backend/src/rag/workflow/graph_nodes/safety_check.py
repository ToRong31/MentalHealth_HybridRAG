"""
Safety Check Node
Node wrapper for safety check logic
"""
from typing import Dict, Any

from src.rag.llm.answer_nodes.safety_check import process_safety_check


async def safety_check_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Check if question is mental health related and high-risk.
    
    Args:
        state: State dict with question, query_type, conversation context
    
    Returns:
        Updated state with is_mental_health_related and is_high_risk flags
    """
    # Extract parameters from state
    question = state["question"]
    query_type = state.get("query_type")
    should_enhance = state.get("should_enhance_query", False)
    buffer = state.get("conversation_buffer", [])
    summary = state.get("summary_context", "")
    
    # Call logic function
    result = await process_safety_check(
        question=question,
        query_type=query_type,
        should_enhance=should_enhance,
        conversation_buffer=buffer,
        summary_context=summary
    )
    
    # Update state with result
    state.update(result)
    
    return state
