"""
Not Mental Health Node
Node wrapper for non-mental health response logic
"""
from typing import Dict, Any

from src.rag.llm.answer_nodes.not_mental_health import get_not_mental_health_message


async def not_mental_health_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Return message for non-mental health questions.
    
    Args:
        state: State dict
    
    Returns:
        Updated state with not mental health message
    """
    # Get message from logic layer
    message = await get_not_mental_health_message()
    
    # Update state
    state["answer"] = message
    state["skip_translation"] = True  # Response already in user-facing language
    state["done"] = True
    
    return state
