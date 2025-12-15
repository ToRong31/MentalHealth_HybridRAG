"""
Encode Node
Encodes query to embedding vector
"""
import asyncio
import logging

from ..state import KGState
from src.rag.vectors.embeddings import encode_e5

logger = logging.getLogger(__name__)


async def encode_node(state: KGState) -> KGState:
    """
    Encode query to embedding vector (async version)
    
    Args:
        state: KGState with 'question'
    
    Returns:
        Updated state with 'query_embedding'
    """
    q = state["question"]
    # Run encoding in executor to avoid blocking
    loop = asyncio.get_event_loop()
    emb = await loop.run_in_executor(None, lambda: encode_e5([f"query: {q}"])[0])
    state["query_embedding"] = emb.tolist()
    return state
