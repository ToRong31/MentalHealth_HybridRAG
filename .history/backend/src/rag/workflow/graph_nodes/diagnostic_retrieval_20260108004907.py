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
    
    logger.info("=" * 80)
    logger.info(f"[DIAGNOSTIC RETRIEVAL] Starting retrieval")
    logger.info(f"[QUERY] Original: {state.get('question', 'N/A')}")
    logger.info(f"[QUERY] Rewritten: {rewritten_query}")
    logger.info(f"[SLOTS] Available: {list(state.get('slots', {}).keys())}")
    logger.info(f"[ASSESSMENT] Category: {state.get('assessment_category', 'N/A')}")
    logger.info("=" * 80)
    
    if not rewritten_query or rewritten_query.strip() == "":
        logger.error("❌ [CRITICAL] No query available for retrieval!")
        logger.error(f"   - rewritten_query: '{rewritten_query}'")
        logger.error(f"   - question: '{state.get('question', 'N/A')}'")
        state["diagnostic_chunks"] = ""
        state["diagnostic_diseases"] = []
        state["diagnostic_disease_details"] = []
        return state
    
    try:
        logger.info(f"🔬 Calling diagnostic_retrieval.retrieve_async with query: '{rewritten_query[:100]}...'")
        
        # Retrieve from diagnostic collection
        diagnostic_results = await diagnostic_retrieval.retrieve_async(rewritten_query, top_k=5)
        
        logger.info(f"✅ retrieve_async completed. Result type: {type(diagnostic_results)}")
        logger.info(f"   - Has context: {hasattr(diagnostic_results, 'context')}")
        logger.info(f"   - Has metadata: {hasattr(diagnostic_results, 'metadata')}")
        
        diagnostic_chunks_text = diagnostic_results.context
        
        # Extract diseases from metadata
        diseases = diagnostic_results.metadata.get("diseases", [])
        disease_details = diagnostic_results.metadata.get("disease_details", [])
        
        logger.info(f"📊 Retrieval stats:")
        logger.info(f"   - Context length: {len(diagnostic_chunks_text)} chars")
        logger.info(f"   - Detected diseases: {diseases}")
        logger.info(f"   - Disease details count: {len(disease_details)}")
        
        if not diagnostic_chunks_text or len(diagnostic_chunks_text) < 10:
            logger.warning("⚠️ Retrieved context is empty or too short!")
            logger.warning(f"   - Context: '{diagnostic_chunks_text}'")
            logger.warning(f"   - This may indicate:")
            logger.warning(f"     1. No matching documents in collection")
            logger.warning(f"     2. Query embedding failed")
            logger.warning(f"     3. Milvus connection issues")
        else:
            logger.info(f"✅ Successfully retrieved {len(diagnostic_chunks_text)} chars of diagnostic context")
            logger.info(f"   - Preview: {diagnostic_chunks_text[:200]}...")
        
        state["diagnostic_chunks"] = diagnostic_chunks_text
        state["diagnostic_diseases"] = diseases
        state["diagnostic_disease_details"] = disease_details
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ [ERROR] Exception in diagnostic retrieval: {e}", exc_info=True)
        logger.error(f"   - Query was: '{rewritten_query}'")
        logger.error(f"   - Exception type: {type(e).__name__}")
        logger.error("=" * 80)
        state["diagnostic_chunks"] = ""
        state["diagnostic_diseases"] = []
        state["diagnostic_disease_details"] = []
    
    logger.info("=" * 80)
    return state
