"""
Hybrid Retrieval Node
Retrieves context using both graph and dense retrieval in parallel
"""
import logging

from ..state import KGState
from src.rag.retrieval.hybrid_retrieval import hybrid_retrieval

logger = logging.getLogger(__name__)


async def hybrid_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve context using both graph and dense retrieval in parallel (hybrid search)
    
    Args:
        state: KGState with 'question'
    
    Returns:
        Updated state with 'combined_context' and metadata from both retrievers
    """
    question = state["question"]
    
    logger.info(f"Starting hybrid retrieval for: {question[:50]}...")
    
    # Use HybridRetrieval to get combined context
    result = await hybrid_retrieval.retrieve_async(question)
    
    # Update state with combined context
    state["combined_context"] = result.context
    state["graph_context"] = result.metadata.get("graph_metadata", {}).get("context", "")
    state["dense_context"] = result.metadata.get("dense_metadata", {}).get("context", "")
    state["retrieval_metadata"] = result.metadata
    
    logger.info(f"Hybrid retrieval completed in {result.metadata.get('execution_time', 0):.2f}s")
    
    return state
