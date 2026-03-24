"""
Query Rewriter Node
Rewrite user query with slots and conversation memory before retrieval
"""
import logging
from typing import Dict, Any

from src.rag.llm.answer_nodes.query_rewriter import rewrite_query_with_slots

logger = logging.getLogger(__name__)


async def query_rewriter_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Rewrite query using slots and conversation memory.
    
    Args:
        state: State dict with 'question', 'slots', 'conversation_buffer', 'summary_context'
    
    Returns:
        Updated state with 'rewritten_query'
    """
    question = state["question"]
    slots = state.get("slots", {})
    conversation_buffer = state.get("conversation_buffer", [])
    summary_context = state.get("summary_context", "")
    
    logger.info("🔄 Rewriting query with slots and conversation memory...")
    
    # Rewrite query with slots AND conversation memory
    rewritten_query = await rewrite_query_with_slots(
        original_question=question,
        slots=slots,
        conversation_buffer=conversation_buffer,
        summary_context=summary_context
    )
    
    # Store rewritten query in state
    state["rewritten_query"] = rewritten_query
    
    # Log result
    if rewritten_query != question:
        logger.info(f"✅ Query rewritten successfully")
    else:
        logger.info(f"ℹ️  Query unchanged (no context available)")
    
    return state
