"""
Theoretical Knowledge Node
Retrieves chunks for theoretical questions about mental health concepts
(e.g., "What is depression?", "What is bipolar disorder?")
"""
import logging
from typing import Dict, Any

from ..state import KGState
from src.rag.retrieval.dense_retrieval import DenseRetrieval

logger = logging.getLogger(__name__)

# Initialize theoretical retrieval
theoretical_retrieval = DenseRetrieval(collection_name="mental_health_diagnostic_support")


async def theoretical_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve theoretical knowledge chunks
    
    Args:
        state: KGState with rewritten_query
    
    Returns:
        Updated state with theoretical_chunks
    """
    rewritten_query = state.get("rewritten_query", state.get("question", ""))
    
    logger.info(f"📚 Retrieving theoretical knowledge for query: {rewritten_query}")
    
    try:
        # Retrieve from theoretical collection
        theoretical_results = await theoretical_retrieval.retrieve_async(rewritten_query, top_k=5)
        theoretical_chunks_text = theoretical_results.context
        
        logger.info(f"✅ Retrieved theoretical context (length: {len(theoretical_chunks_text)})")
        
        state["theoretical_chunks"] = theoretical_chunks_text
        state["theoretical_metadata"] = theoretical_results.metadata
        
    except Exception as e:
        logger.error(f"❌ Error in theoretical retrieval: {e}", exc_info=True)
        state["theoretical_chunks"] = ""
        state["theoretical_metadata"] = {}
    
    return state