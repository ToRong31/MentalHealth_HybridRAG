"""
Dense Retrieval Node
Retrieves relevant nodes using DenseRetrieval
"""
import logging

from ..state import KGState
from src.rag.retrieval.dense_retrieval import dense_retrieval

logger = logging.getLogger(__name__)


async def dense_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve relevant nodes using DenseRetrieval (async version)
    
    Args:
        state: KGState with 'question'
    
    Returns:
        Updated state with 'dense_context'
    """
    question = state["question"]
    
    # Use async DenseRetrieval to get context
    results = await dense_retrieval.retrieve_async(question, top_k=2)
    
    state["dense_context"] = results.context
    
    return state
