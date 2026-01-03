"""
Personal/Theoretical Classifier Node
Node wrapper for personal/theoretical classification logic
"""
from typing import Dict, Any
import logging

from src.rag.llm.answer_nodes.router import classify_personal_theoretical

logger = logging.getLogger(__name__)


async def router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Classify query nature (personal or theoretical).
    
    This node determines if the user is asking about their own mental health situation (personal)
    or seeking general knowledge/education (theoretical).
    
    Args:
        state: State dict with question, query_type, conversation_buffer, summary_context
    
    Returns:
        Updated state with query_nature, reasoning
    """
    question = state.get("question", "")
    query_type = state.get("query_type", "follow_up")
    buffer = state.get("conversation_buffer", [])
    summary = state.get("summary_context", "")
    
    # Call logic function
    result = await classify_personal_theoretical(
        question=question,
        query_type=query_type,
        conversation_buffer=buffer,
        summary_context=summary
    )
    
    # Update state with result
    state.update(result)
    
    query_nature = result.get("query_nature", "personal")
    reasoning = result.get("reasoning", "")
    
    logger.info(f"Query nature: {query_nature} - {reasoning}")
    
    return state
