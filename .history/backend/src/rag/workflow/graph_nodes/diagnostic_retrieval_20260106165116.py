"""
Diagnostic Check Node
Retrieves chunks from mental_health_diagnostic_support
Only retrieves, does NOT analyze or conclude
"""
import logging
from typing import Dict, Any

from ..state import KGState
from src.rag.retrieval.dense_retrieval import DenseRetrieval

logger = logging.getLogger(__name__)

# Initialize diagnostic retrieval
diagnostic_retrieval = DenseRetrieval(collection_name="mental_health_diagnostic_support")


async def diagnostic_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve diagnostic chunks based on symptoms
    
    Args:
        state: KGState with rewritten_query
    
    Returns:
        Updated state with diagnostic_chunks only
    """
    rewritten_query = state.get("rewritten_query", state.get("question", ""))
    
    logger.info(f"🔬 Retrieving diagnostic chunks for query: {rewritten_query}")
    
    try:
        # Retrieve from diagnostic collection
        diagnostic_results = await diagnostic_retrieval.retrieve_async(rewritten_query, top_k=5)
        diagnostic_chunks_text = diagnostic_results.context
        
        # Extract diseases from metadata
        diseases = diagnostic_results.metadata.get("diseases", [])
        disease_details = diagnostic_results.metadata.get("disease_details", [])
        
        logger.info(f"✅ Retrieved diagnostic context (length: {len(diagnostic_chunks_text)})")
        logger.info(f"📋 Retrieved diseases: {diseases}")
        logger.info(f"🔍 Query used: '{rewritten_query}'")
        
        # Debug: log first 200 chars of chunks to see what was retrieved
        logger.debug(f"📄 Chunk preview: {diagnostic_chunks_text[:200]}...")
        
        state["diagnostic_chunks"] = diagnostic_chunks_text
        state["diagnostic_diseases"] = diseases
        state["diagnostic_disease_details"] = disease_details
        
    except Exception as e:
        logger.error(f"❌ Error in diagnostic retrieval: {e}", exc_info=True)
        state["diagnostic_chunks"] = ""
        state["diagnostic_diseases"] = []
        state["diagnostic_disease_details"] = []
    
    return state
