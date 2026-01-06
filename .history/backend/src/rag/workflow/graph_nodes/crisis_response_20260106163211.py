"""
Crisis Response Node
Node wrapper for crisis response logic
"""
from typing import Dict, Any

from src.rag.llm.answer_nodes.crisis_response import get_crisis_response_message


async def crisis_response_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Return crisis response message for high-risk cases.
    
    Args:
        state: State dict
    
    Returns:
        Updated state with crisis response message
    """
    # Get crisis response message from logic layer
    message = await get_crisis_response_message()
    
    # Update state
    state["answer"] = message
    state["skip_translation"] = True  # Response already in user-facing language
    state["done"] = True
    
    return state
