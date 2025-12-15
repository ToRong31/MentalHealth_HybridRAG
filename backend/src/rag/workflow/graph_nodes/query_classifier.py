"""
Query Classifier Node
Node wrapper for query classification logic
"""
from typing import Dict, Any

from src.rag.llm.answer_nodes.query_classifier import classify_query_type


async def query_classifier_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Classify query type (follow_up, topic_change, off_topic) using LLM.
    
    Args:
        state: State dict with question, conversation_buffer, summary_context
    
    Returns:
        Updated state with query_type, is_topic_change, is_off_topic, should_enhance_query
    """
    question = state.get("question", "")
    buffer = state.get("conversation_buffer", [])
    summary = state.get("summary_context", "")
    
    # Call logic function
    result = await classify_query_type(
        question=question,
        conversation_buffer=buffer,
        summary_context=summary
    )
    
    # Update state with result
    state.update(result)
    
    return state
