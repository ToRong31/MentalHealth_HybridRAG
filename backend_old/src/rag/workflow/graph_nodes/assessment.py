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


def detect_severity_from_query(query: str) -> str:
    """
    Detect severity level from query text.
    
    Returns:
        "mild", "moderate", "severe", or "unknown"
    """
    query_lower = query.lower()
    
    # Very severe indicators
    very_severe_keywords = ["profound", "extreme", "overwhelming", "critical", "maximum intensity", "very severe"]
    if any(keyword in query_lower for keyword in very_severe_keywords):
        return "severe"  # Treat very severe as severe for boost logic
    
    # Severe indicators
    severe_keywords = ["severe", "marked", "significant", "substantial", "high intensity", "intense", "severe intensity"]
    if any(keyword in query_lower for keyword in severe_keywords):
        return "severe"
    
    # Moderate indicators
    moderate_keywords = ["moderate", "moderate intensity", "intermediate", "some", "partial"]
    if any(keyword in query_lower for keyword in moderate_keywords):
        return "moderate"
    
    # Mild indicators
    mild_keywords = ["mild", "slight", "minor", "temporary", "transient", "brief", "minimal", "low intensity", "mild intensity"]
    if any(keyword in query_lower for keyword in mild_keywords):
        return "mild"
    
    return "unknown"


def apply_severity_boost(item: Dict[str, Any], query_severity: str) -> float:
    """
    Apply severity-based boost/penalty to item's cohere_score.
    
    Logic (Option 2 - Increased multipliers):
    - Mild query: Boost items with score 1-3 (×1.5), penalize items with score 4-5 (×0.6)
    - Moderate query: Neutral (no boost/penalty)
    - Severe query: Boost items with score 4-5 (×1.5), don't penalize items with score 1-3 (neutral)
    
    Args:
        item: Item dict with original_score and cohere_score
        query_severity: "mild", "moderate", "severe", or "unknown"
    
    Returns:
        Adjusted cohere_score (weight multiplier)
    """
    original_score = item.get("original_score", 0.0)
    cohere_score = item.get("cohere_score") or item.get("rerank_score") or item.get("milvus_score", 0.0)
    
    # Skip emergency items (score 99) - they should always be considered
    if original_score == 99:
        return cohere_score
    
    # Skip items with score -1
    if original_score == -1:
        return cohere_score
    
    # Apply boost/penalty based on severity match
    # Option 2: Increased multipliers to widen gap between adjustment and diagnose
    # Boost: 1.2x → 1.5x (50% increase instead of 20%)
    # Penalty: 0.7x → 0.6x (40% decrease instead of 30%)
    if query_severity == "mild":
        # Mild query: prefer lower scores (1-3), penalize higher scores (4-5)
        if original_score <= 3:
            # Boost: multiply by 1.5 (50% increase)
            return min(cohere_score * 1.5, 1.0)  # Cap at 1.0
        elif original_score >= 4:
            # Penalize: multiply by 0.6 (40% decrease)
            return cohere_score * 0.6
    
    elif query_severity == "severe":
        # Severe query: prefer higher scores (4-5), don't penalize lower scores (1-3)
        # Reason: If only score 3.0 items are matched, penalizing them would make score too low
        if original_score >= 4:
            # Boost: multiply by 1.5 (50% increase)
            return min(cohere_score * 1.5, 1.0)  # Cap at 1.0
        elif original_score <= 3:
            # Don't penalize: keep original weight (neutral)
            # This allows score 3.0 items to contribute normally if score 5.0 items are not matched
            return cohere_score
    
    # Moderate or unknown: no boost/penalty
    return cohere_score


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
                
                # Step 3: Calculate scores for each type using weighted average
                logger.info("[STEP 3] Calculating type scores using weighted average")
                type_scores = {
                    "normal_stress": 0.0,
                    "adjustment_reaction": 0.0,
                }
                
                type_score_details = {
                    "normal_stress": [],
                    "adjustment_reaction": [],
                }
                
                # Filter items theo similarity threshold (lấy hết items có cohere_score > threshold)
                # Cohere rerank đã sắp xếp items theo relevance từ cao xuống thấp
                # Chỉ tính items có similarity đủ cao để đảm bảo độ chính xác
                # Reduced from 0.5 to 0.4 to keep more items, especially score 5.0 items for severe cases
                SIMILARITY_THRESHOLD = 0.4  # Chỉ tính items có cohere_score > 0.4
                
                filtered_items = []
                for item in reranked:
                    # Lấy cohere_score (từ Cohere Rerank API) làm weight
                    cohere_score = item.get("cohere_score") or item.get("rerank_score") or item.get("milvus_score", 0.0)
                    
                    # Chỉ tính items có similarity đủ cao
                    if cohere_score > SIMILARITY_THRESHOLD:
                        filtered_items.append(item)
                
                logger.info(f"[FILTER] Total reranked items: {len(reranked)}, "
                           f"Items after similarity filter (> {SIMILARITY_THRESHOLD}): {len(filtered_items)}")
                
                # Step 3a: Detect severity from query and apply boost/penalty
                query_severity = detect_severity_from_query(rewritten_query)
                logger.info(f"[SEVERITY DETECTION] Query severity: {query_severity}")
                
                # Apply severity-based boost/penalty to filtered items
                boosted_items = []
                for item in filtered_items:
                    original_cohere_score = item.get("cohere_score") or item.get("rerank_score") or item.get("milvus_score", 0.0)
                    adjusted_cohere_score = apply_severity_boost(item, query_severity)
                    
                    # Update item with adjusted score
                    item["cohere_score"] = adjusted_cohere_score
                    item["original_cohere_score"] = original_cohere_score  # Keep original for logging
                    
                    # Log boost/penalty if significant
                    if abs(adjusted_cohere_score - original_cohere_score) > 0.01:
                        boost_pct = ((adjusted_cohere_score - original_cohere_score) / original_cohere_score * 100) if original_cohere_score > 0 else 0
                        logger.debug(f"[SEVERITY BOOST] {item.get('text', '')[:30]}: "
                                   f"score={item.get('original_score', 0)}, "
                                   f"weight={original_cohere_score:.4f} → {adjusted_cohere_score:.4f} "
                                   f"({boost_pct:+.1f}%)")
                    
                    boosted_items.append(item)
                
                logger.info(f"[SEVERITY BOOST] Applied to {len(boosted_items)} items")
                
                # Track tổng weight cho mỗi type (cần để tính weighted average)
                normal_stress_total_weight = 0.0
                adjustment_reaction_total_weight = 0.0
                
                for item in boosted_items:
                    item_type = item.get("type", "").lower()
                    original_score = item.get("original_score", 0.0)
                    chunk_id = item.get("chunk_id", "")
                    title = item.get("text", "")
                    
                    # Xử lý score đặc biệt
                    # Bỏ qua score -1 (không tính)
                    if original_score == -1:
                        continue
                    
                    # Xử lý score 99 (emergency cases): Cap thành 10
                    # Score 99 thường là emergency cases (ví dụ: "Homicidal ideation", "Suicidal ideation")
                    # Cap thành 10 để tránh score quá cao nhưng vẫn phản ánh mức độ nghiêm trọng
                    if original_score == 99:
                        capped_score = 10
                    else:
                        capped_score = original_score
                    
                    # Lấy cohere_score làm weight (từ Cohere Rerank API)
                    cohere_score = item.get("cohere_score") or item.get("rerank_score") or item.get("milvus_score", 0.0)
                    
                    # Tính weighted contribution
                    weighted_contribution = capped_score * cohere_score
                    
                    if "normal" in item_type or "stress" in item_type:
                        type_scores["normal_stress"] += weighted_contribution  # Weighted sum
                        normal_stress_total_weight += cohere_score  # Track tổng weight
                        type_score_details["normal_stress"].append({
                            "chunk_id": chunk_id,
                            "title": title,
                            "score": capped_score,
                            "weight": cohere_score,
                            "weighted_contribution": weighted_contribution,
                        })
                    elif "adjustment" in item_type or "điều chỉnh" in item_type:
                        type_scores["adjustment_reaction"] += weighted_contribution  # Weighted sum
                        adjustment_reaction_total_weight += cohere_score  # Track tổng weight
                        type_score_details["adjustment_reaction"].append({
                            "chunk_id": chunk_id,
                            "title": title,
                            "score": capped_score,
                            "weight": cohere_score,
                            "weighted_contribution": weighted_contribution,
                        })
                
                # Tính weighted average
                # Final scores = weighted average (không phụ thuộc số lượng items)
                if normal_stress_total_weight > 0:
                    type_scores["normal_stress"] = type_scores["normal_stress"] / normal_stress_total_weight
                else:
                    type_scores["normal_stress"] = 0.0
                
                if adjustment_reaction_total_weight > 0:
                    type_scores["adjustment_reaction"] = type_scores["adjustment_reaction"] / adjustment_reaction_total_weight
                else:
                    type_scores["adjustment_reaction"] = 0.0
                
                logger.info(f"[SCORES] normal_stress: {type_scores['normal_stress']:.2f}, "
                           f"adjustment_reaction: {type_scores['adjustment_reaction']:.2f}")
                logger.info(f"[SCORE DETAILS] Normal stress items: {len(type_score_details['normal_stress'])}, "
                           f"Adjustment reaction items: {len(type_score_details['adjustment_reaction'])}")
                logger.info(f"[SEVERITY MATCH] Query severity: {query_severity}, "
                           f"Applied boost/penalty to items based on severity alignment")
                logger.info(f"[TOP ITEMS] Normal stress top 3:")
                for i, detail in enumerate(type_score_details["normal_stress"][:3], 1):
                    logger.info(f"  {i}. {detail['title']}: score={detail['score']}, weight={detail.get('weight', 0):.4f}, "
                               f"contribution={detail.get('weighted_contribution', 0):.2f}")
                logger.info(f"[TOP ITEMS] Adjustment reaction top 3:")
                for i, detail in enumerate(type_score_details["adjustment_reaction"][:3], 1):
                    logger.info(f"  {i}. {detail['title']}: score={detail['score']}, weight={detail.get('weight', 0):.4f}, "
                               f"contribution={detail.get('weighted_contribution', 0):.2f}")
                
                # Step 4: Determine category based on scores
                normal_stress_score = type_scores["normal_stress"]
                adjustment_reaction_score = type_scores["adjustment_reaction"]
                
                state["normal_stress_score"] = normal_stress_score
                state["adjustment_reaction_score"] = adjustment_reaction_score
                state["normal_stress_score_details"] = type_score_details["normal_stress"]  # Chi tiết các chunks
                state["adjustment_reaction_score_details"] = type_score_details["adjustment_reaction"]  # Chi tiết các chunks
                state["normal_response_chunks"] = reranked  # Save retrieved chunks
                
                # Routing logic: if any score > threshold, go to diagnostic_retrieval (severe symptoms)
                # Threshold: 4.15 (adjusted based on current score distribution 3.5-5.0)
                # Có thể điều chỉnh sau khi test
                THRESHOLD = 4.15
                if normal_stress_score > THRESHOLD or adjustment_reaction_score > THRESHOLD:
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

