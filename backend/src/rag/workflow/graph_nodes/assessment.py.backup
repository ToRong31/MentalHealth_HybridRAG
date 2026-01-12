"""
Assessment Node - Dual Assessment for Routing + Context

This node runs after slot_filling to provide:
1. SEVERITY assessment → routing decision (no premature bypass)
2. DISORDER LIKELIHOOD → context for downstream nodes (query rewriter, LLM)

Why both?
- Severity: Determines urgency and routing (ALL cases screened)
- Disorder likelihood: Provides rich context for retrieval and answer generation
- This maintains retrieval quality while preventing premature routing bypass
"""

import logging
from typing import List, Dict, Any
from pymilvus import Collection, connections, utility
from ..state import KGState
from src.rag.utils.assessment import assess_severity_only, assess_disorder_likelihood, get_assessment_context
from src.rag.utils.normal_response_matcher import match_symptoms_to_database
from src.rag.vectors.embeddings import encode_e5
from src.rag.reranker.reranker import CohereReranker
from src.rag.config import rag_settings

logger = logging.getLogger(__name__)


async def assessment_node(state: KGState) -> KGState:
    """
    Dual assessment: Severity (for routing) + Disorder likelihood (for context).
    
    This node:
    1. Retrieves from normal_responses collection in Milvus (score > 0.7)
    2. Reranks using Cohere
    3. Calculates scores for 2 types: adjustment_reaction and normal_stress
    4. Routes based on score > 20 threshold
    5. Runs severity assessment for routing decision
    6. ALL cases then proceed to appropriate node based on scores
    
    Args:
        state: KGState with slots filled
    
    Returns:
        Updated state with:
        - severity_level, severity_breakdown, severity_confidence (for routing)
        - assessment_category, assessment_explanation, assessment_confidence (for context)
        - normal_stress_score, adjustment_reaction_score (for routing decision)
    """

    slots = state.get("slots", {})
    question = state.get("question", "")
    rewritten_query = state.get("rewritten_query", question)
    
    logger.info("=" * 80)
    logger.info("[ASSESSMENT NODE] Starting assessment with normal_responses retrieval")
    logger.info(f"[QUERY] {rewritten_query}")
    logger.info("=" * 80)
    
    # Step 1: Retrieve from normal_responses collection in Milvus
    logger.info("[STEP 1] Retrieving from normal_responses collection")
    try:
        # Connect to Milvus
        if not connections.has_connection("default"):
            connection_params = {
                "alias": "default",
                "uri": rag_settings.MILVUS_URI,
                "db_name": rag_settings.MILVUS_DB,
            }
            if rag_settings.MILVUS_TOKEN and rag_settings.MILVUS_TOKEN.strip():
                connection_params["token"] = rag_settings.MILVUS_TOKEN
                connection_params["secure"] = True
            else:
                connection_params["secure"] = False
            connections.connect(**connection_params)
        
        # Load normal_responses collection
        collection_name = "normal_responses"
        if collection_name not in utility.list_collections():
            logger.warning(f"[WARNING] Collection {collection_name} not found, skipping retrieval")
            matched_items = []
            milvus_results = []
        else:
            col = Collection(collection_name)
            col.load()
            
            # Create query embedding using rewritten query
            query_embedding = encode_e5([f"query: {rewritten_query}"])[0].tolist()
            
            # Search in Milvus
            search_results = col.search(
                data=[query_embedding],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"ef": 64}},
                limit=50,
                output_fields=["node_id", "title", "type", "severity_score"],
            )
            
            # Filter by score > 0.7
            milvus_results = []
            for hit in search_results[0]:
                similarity_score = float(hit.distance)
                if similarity_score > 0.75:
                    # Access entity fields directly (not using .get())
                    entity = hit.entity
                    
                    # Get the actual database severity_score field
                    # Note: using severity_score to avoid conflict with pymilvus internal score
                    db_score = entity.severity_score if hasattr(entity, "severity_score") else 0.0
                    
                    milvus_results.append({
                        "node_id": hit.id,
                        "title": entity.title if hasattr(entity, "title") else "",
                        "type": entity.type if hasattr(entity, "type") else "",
                        "milvus_score": similarity_score,  # Cosine similarity 0-1
                        "original_score": db_score,  # Database severity score (-1, 1-5, 99)
                    })
                    
                    # Debug: Log first few items to verify scores
                    if len(milvus_results) <= 3:
                        logger.info(f"[DEBUG] Item {len(milvus_results)}: "
                                   f"similarity={similarity_score:.4f}, "
                                   f"db_score={db_score}, "
                                   f"type={entity.type if hasattr(entity, 'type') else 'N/A'}")
            
            logger.info(f"[MILVUS] Retrieved {len(milvus_results)} items with similarity > 0.75")
            
            # Step 2: Rerank using Cohere
            if milvus_results:
                logger.info("[STEP 2] Reranking with Cohere")
                reranker = CohereReranker()
                
                # Prepare candidates for reranking
                candidates = []
                for item in milvus_results:
                    candidates.append({
                        "chunk_id": item["node_id"],
                        "text": item["title"],  # Use title as text for reranking
                        "original_milvus_score": item["milvus_score"],
                        "type": item["type"],
                        "original_score": item["original_score"],
                    })
                
                # Rerank using rewritten query (ASYNC to avoid blocking)
                reranked = await reranker.rerank_chunks(
                    query=rewritten_query,
                    candidates=candidates,
                    top_k=min(20, len(candidates))
                )
                
                logger.info(f"[COHERE] Reranked to {len(reranked)} items")
                
                # Step 3: Calculate scores for each type using field 'score' from Milvus
                logger.info("[STEP 3] Calculating type scores from field 'score'")
                type_scores = {
                    "normal_stress": 0.0,
                    "adjustment_reaction": 0.0,
                }
                
                type_score_details = {
                    "normal_stress": [],
                    "adjustment_reaction": [],
                }
                
                for item in reranked:
                    item_type = item.get("type", "").lower()
                    original_score = item.get("original_score", 0.0)  # Field 'score' from Milvus DB
                    chunk_id = item.get("chunk_id", "")
                    title = item.get("text", "")
                    
                    # Use field 'score' directly from database
                    if "normal" in item_type or "stress" in item_type:
                        type_scores["normal_stress"] += original_score
                        type_score_details["normal_stress"].append({
                            "chunk_id": chunk_id,
                            "title": title,
                            "score": original_score,
                        })
                    elif "adjustment" in item_type or "điều chỉnh" in item_type:
                        type_scores["adjustment_reaction"] += original_score
                        type_score_details["adjustment_reaction"].append({
                            "chunk_id": chunk_id,
                            "title": title,
                            "score": original_score,
                        })
                
                logger.info(f"[SCORES] normal_stress: {type_scores['normal_stress']:.2f}, "
                           f"adjustment_reaction: {type_scores['adjustment_reaction']:.2f}")
                
                # Step 4: Determine category based on scores
                normal_stress_score = type_scores["normal_stress"]
                adjustment_reaction_score = type_scores["adjustment_reaction"]
                
                state["normal_stress_score"] = normal_stress_score
                state["adjustment_reaction_score"] = adjustment_reaction_score
                state["normal_stress_score_details"] = type_score_details["normal_stress"]  # Chi tiết các chunks
                state["adjustment_reaction_score_details"] = type_score_details["adjustment_reaction"]  # Chi tiết các chunks
                state["normal_response_chunks"] = reranked  # Save retrieved chunks
                
                # Routing logic: if any score > 60, go to diagnostic_retrieval (severe symptoms)
                # Otherwise, choose the higher score category
                if normal_stress_score > 60 or adjustment_reaction_score > 60:
                    # High score indicates severe symptoms → need diagnostic assessment
                    state["assessment_category"] = "possible_disorder"
                    state["assessment_explanation"] = f"Điểm số cao (normal: {normal_stress_score:.2f}, adjustment: {adjustment_reaction_score:.2f}) - cần đánh giá chẩn đoán"
                    state["assessment_confidence"] = 0.8
                else:
                    # Both scores < 60, choose the higher category
                    if normal_stress_score > adjustment_reaction_score:
                        state["assessment_category"] = "normal_response"
                        state["assessment_explanation"] = f"Phản ứng stress bình thường (score: {normal_stress_score:.2f})"
                        state["assessment_confidence"] = min(normal_stress_score / 100, 1.0)
                    else:
                        state["assessment_category"] = "adjustment_reaction"
                        state["assessment_explanation"] = f"Phản ứng điều chỉnh (score: {adjustment_reaction_score:.2f})"
                        state["assessment_confidence"] = min(adjustment_reaction_score / 100, 1.0)
                
                matched_items = reranked
            else:
                matched_items = []
                state["normal_stress_score"] = 0.0
                state["adjustment_reaction_score"] = 0.0
                state["normal_stress_score_details"] = []
                state["adjustment_reaction_score_details"] = []
                state["normal_response_chunks"] = []  # Empty chunks if no results
                state["assessment_category"] = "possible_disorder"
                state["assessment_explanation"] = "Không tìm thấy phản ứng bình thường phù hợp"
                state["assessment_confidence"] = 0.5
    
    except Exception as e:
        logger.error(f"[ERROR] Normal responses retrieval failed: {e}", exc_info=True)
        matched_items = []
        state["normal_stress_score"] = 0.0
        state["adjustment_reaction_score"] = 0.0
        state["normal_stress_score_details"] = []
        state["adjustment_reaction_score_details"] = []
        state["normal_response_chunks"] = []  # Empty chunks on error
        state["assessment_category"] = "possible_disorder"
        state["assessment_explanation"] = f"Lỗi khi truy xuất: {str(e)}"
        state["assessment_confidence"] = 0.5
    
    # Step 5: Severity assessment (for routing decision)
    logger.info("[STEP 5] Running severity assessment (for routing)")
    try:
        severity_level, severity_breakdown, sev_confidence = assess_severity_only(slots, matched_items)
        
        state["severity_level"] = severity_level
        state["severity_breakdown"] = severity_breakdown
        state["severity_confidence"] = sev_confidence
        
        logger.info(f"[SEVERITY RESULT] Level: {severity_level}, Confidence: {sev_confidence:.2f}")
        
    except Exception as e:
        logger.error(f"[SEVERITY ASSESSMENT ERROR] {e}", exc_info=True)
        state["severity_level"] = "moderate"
        state["severity_breakdown"] = {"error": str(e)}
        state["severity_confidence"] = 0.5
    
    # Generate assessment context for prompt injection
    try:
        assessment_ctx = get_assessment_context(slots, matched_items)
        state["assessment_context"] = assessment_ctx
    except Exception as e:
        logger.error(f"[ASSESSMENT CONTEXT ERROR] {e}", exc_info=True)
        state["assessment_context"] = ""
    
    logger.info("=" * 80)
    logger.info(f"[SUMMARY] Category: {state.get('assessment_category')}, "
               f"Severity: {state.get('severity_level')}")
    logger.info(f"[SCORES] Normal Stress: {state.get('normal_stress_score', 0):.2f}, "
               f"Adjustment: {state.get('adjustment_reaction_score', 0):.2f}")
    logger.info("=" * 80)
    
    return state

