"""
Query Similarity Check Node
Checks similarity between query and conversation context using embedding
"""
import asyncio
import logging
from typing import Dict, Any

from src.rag.utils.memory import (
    format_buffer_for_context,
    format_summary_context,
    calculate_query_similarity,
)

logger = logging.getLogger(__name__)


async def query_similarity_check_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check similarity between query and conversation context using embedding.
    Hybrid approach: if similarity >= 0.8, classify as follow_up (skip LLM).
    If similarity < 0.8, set flag to call classify_query_node (LLM).
    
    Logic:
    - Nếu không có buffer/summary → skip, không enhance
    - Nếu có buffer/summary:
      * Tính similarity (embedding)
      * >= 0.8 → follow_up (skip LLM)
      * < 0.8 → set flag để gọi classify_query_node (LLM)
    
    Args:
        state: KGState with 'question', 'conversation_buffer', 'summary_context'
    
    Returns:
        Updated state with 'query_similarity', 'query_type', 'should_enhance_query', 'is_topic_change', 'is_off_topic'
    """
    question = state.get("question", "")
    buffer = state.get("conversation_buffer", [])
    summary = state.get("summary_context", "")
    
    # If no buffer and no summary, this is the first message
    # Skip similarity check, don't enhance query
    if not buffer and not summary:
        logger.info("No conversation history, skipping similarity check")
        return {
            "query_similarity": None,
            "query_type": None,
            "should_enhance_query": False,
            "is_topic_change": False,
            "is_off_topic": False
        }
    
    # Build conversation context from buffer + summary
    buffer_text = format_buffer_for_context(buffer)
    summary_text = format_summary_context(summary)
    
    conversation_context_parts = []
    if summary_text:
        conversation_context_parts.append(summary_text)
    if buffer_text:
        conversation_context_parts.append(buffer_text)
    
    conversation_context = "\n\n".join(conversation_context_parts)
    
    # Calculate similarity using embedding (run in executor to avoid blocking)
    try:
        loop = asyncio.get_event_loop()
        similarity = await loop.run_in_executor(
            None,
            lambda: calculate_query_similarity(question, conversation_context)
        )
        
        logger.info(f"Query similarity score: {similarity:.3f}")
        
        state["query_similarity"] = similarity
        
        # Hybrid approach: >= 0.8 → follow_up (skip LLM)
        if similarity >= 0.8:
            logger.info(f"High similarity ({similarity:.3f} >= 0.8), classifying as follow_up (skipping LLM)")
            return {
                "query_similarity": similarity,
                "query_type": "follow_up",
                "should_enhance_query": True,
                "is_topic_change": False,
                "is_off_topic": False
            }
        else:
            # Low similarity (< 0.8) → need LLM to classify
            # Set flag to call classify_query_node
            logger.info(f"Low similarity ({similarity:.3f} < 0.8), will call LLM classifier")
            # Don't set query_type yet, let classify_query_node decide
            return {
                "query_similarity": similarity,
                "query_type": None,  # Will be set by classify_query_node
                "should_enhance_query": None,  # Will be set by classify_query_node
                "is_topic_change": False,
                "is_off_topic": False
            }
            
    except Exception as e:
        logger.error(f"Error in query_similarity_check_node: {e}", exc_info=True)
        # Fallback: default to follow_up if error
        return {
            "query_similarity": 0.0,
            "query_type": "follow_up",
            "should_enhance_query": True,
            "is_topic_change": False,
            "is_off_topic": False
        }
