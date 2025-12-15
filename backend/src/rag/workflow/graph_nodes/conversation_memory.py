"""
Conversation Memory Node
Node wrapper for conversation memory update logic
"""
from typing import Dict, Any

from src.rag.llm.answer_nodes.conversation_memory import update_conversation_memory


async def conversation_memory_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Update conversation buffer and summary context.
    
    Args:
        state: State dict with question, answer, query_type, conversation_buffer, summary_context
    
    Returns:
        Updated state with conversation_buffer and summary_context
    """
    query_type = state.get("query_type")
    question = state.get("question", "")
    answer = state.get("answer", "")
    current_buffer = state.get("conversation_buffer", [])
    current_summary = state.get("summary_context", "")
    
    # Call logic function
    result = await update_conversation_memory(
        query_type=query_type,
        question=question,
        answer=answer,
        current_buffer=current_buffer,
        current_summary=current_summary
    )
    
    # Update state with result
    state.update(result)
    
    return state
