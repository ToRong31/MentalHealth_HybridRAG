"""
Dense Retrieval Node
Retrieves relevant nodes using DenseRetrieval with rewritten query
"""
import logging

from ..state import KGState
from src.rag.retrieval.dense_retrieval import DenseRetrieval

logger = logging.getLogger(__name__)

# Create default dense retrieval instance
dense_retrieval = DenseRetrieval(collection_name="mental_health_diagnostic_support")


async def dense_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve relevant nodes using DenseRetrieval (async version)
    Uses rewritten query from query_rewriter node (includes slots + conversation context)
    
    Args:
        state: KGState with 'question', 'rewritten_query' (optional)
    
    Returns:
        Updated state with 'dense_context'
    """
    question = state["question"]
    rewritten_query = state.get("rewritten_query")
    
    # Use rewritten query if available (from query_rewriter), otherwise use original
    query_for_retrieval = rewritten_query if rewritten_query else question
    
    if rewritten_query:
        logger.info(f"🔍 Retrieving with rewritten query")
    else:
        logger.info(f"🔍 Retrieving with original query")
    
    logger.debug(f"Query: {query_for_retrieval}")
    
    # Use async DenseRetrieval to get context
    results = await dense_retrieval.retrieve_async(query_for_retrieval, top_k=2)
    
    state["dense_context"] = results.context
    
    return state
