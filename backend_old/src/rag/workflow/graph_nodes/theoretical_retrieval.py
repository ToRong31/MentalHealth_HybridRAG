"""
Theoretical Knowledge Node
Retrieves chunks for theoretical questions about mental health concepts
(e.g., "What is depression?", "What is bipolar disorder?")
"""
import logging
from typing import Dict, Any

from ..state import KGState
from src.rag.retrieval.dense_retrieval import DenseRetrieval
from src.rag.llm.answer_nodes.theoretical_query_rewriter import rewrite_theoretical_query

logger = logging.getLogger(__name__)

# Initialize theoretical retrieval
theoretical_retrieval = DenseRetrieval(collection_name="mental_health_diagnostic_support")


async def theoretical_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve theoretical knowledge chunks.
    
    NEW: Now includes query rewriting for better retrieval!
    - Translates Vietnamese to English
    - Expands with clinical terminology
    - Resolves coreferences using conversation context
    - Adds question-type specific keywords
    
    Args:
        state: KGState with question, conversation_buffer, summary_context
    
    Returns:
        Updated state with theoretical_chunks and rewritten_query
    """
    original_question = state.get("question", "")
    conversation_buffer = state.get("conversation_buffer", [])
    summary_context = state.get("summary_context", "")
    
    logger.info(f"📚 Starting theoretical retrieval for: {original_question}")
    
    try:
        # STEP 1: Rewrite query for better retrieval
        logger.info("🔄 Rewriting theoretical query...")
        rewritten_query = await rewrite_theoretical_query(
            original_question=original_question,
            conversation_buffer=conversation_buffer,
            summary_context=summary_context
        )
        
        # Store rewritten query in state
        state["rewritten_query"] = rewritten_query
        
        if rewritten_query != original_question:
            logger.info(f"✅ Query enhanced for retrieval")
        else:
            logger.info(f"ℹ️  Using original query (no enhancement needed)")
        
        # STEP 2: Retrieve from theoretical collection using rewritten query
        logger.info(f"🔍 Retrieving with query: {rewritten_query[:100]}...")
        theoretical_results = await theoretical_retrieval.retrieve_async(rewritten_query, top_k=5)
        theoretical_chunks_text = theoretical_results.context
        
        logger.info(f"✅ Retrieved theoretical context (length: {len(theoretical_chunks_text)} chars)")
        
        # Store results in state
        state["theoretical_chunks"] = theoretical_chunks_text
        state["theoretical_metadata"] = theoretical_results.metadata
        
    except Exception as e:
        logger.error(f"❌ Error in theoretical retrieval: {e}", exc_info=True)
        state["theoretical_chunks"] = ""
        state["theoretical_metadata"] = {}
        state["retrieval_failed"] = True
    
    return state