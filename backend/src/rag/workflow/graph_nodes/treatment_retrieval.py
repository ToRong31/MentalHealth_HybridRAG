"""
Treatment Retrieval Node
Retrieves treatment guidance by disease keyword from Milvus
Uses cosine similarity search with disease field filtering
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

from pymilvus import Collection

from ..state import KGState
from src.rag.config import rag_settings
from src.rag.vectors.embeddings import encode_e5

logger = logging.getLogger(__name__)


async def treatment_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve treatment chunks using vector search + disease field filter
    
    Args:
        state: KGState with detected_disease or disease_detected list
    
    Returns:
        Updated state with treatment_chunks, treatment_node_ids
    """
    # Get disease from state - prioritize disease_detected list
    disease_list = state.get("disease_detected", [])
    if not disease_list:
        # Fallback to detected_disease
        detected_disease = state.get("detected_disease", "")
        disease_list = [detected_disease] if detected_disease else []
    
    if not disease_list:
        logger.warning("⚠️ No disease detected for treatment retrieval")
        state["treatment_chunks"] = []
        state["treatment_node_ids"] = []
        return state
    
    # Use first disease in list (most recent/confident)
    target_disease = disease_list[0]
    logger.info(f"💊 Retrieving treatment guidance for disease: '{target_disease}'")
    
    try:
        # Get rewritten query for embedding (or use detected disease as query)
        query = state.get("rewritten_query", state.get("question", f"Cách điều trị {target_disease}"))
        
        # Encode query to vector
        encoded_query = encode_e5([f"query: {query}"])
        query_vector = encoded_query[0].tolist()
        
        # Connect to Milvus collection
        col = Collection("mental_health_treatment_guidance")
        col.load()
        
        # Build disease filter expression (support multiple diseases)
        disease_filters = []
        for disease in disease_list[:3]:  # Limit to top 3 diseases
            disease_escaped = disease.replace('"', '\\"').replace("'", "\\'")
            disease_filters.append(f'disease like "%{disease_escaped}%"')
        
        expr = " or ".join(disease_filters) if len(disease_filters) > 1 else disease_filters[0]
        logger.info(f"Milvus filter expression: {expr}")
        
        # Vector search with disease filter
        search_params = {
            "metric_type": "COSINE",
            "params": {"ef": 64}
        }
        
        results = col.search(
            data=[query_vector],
            anns_field="embedding",
            param=search_params,
            limit=5,
            expr=expr,  # Filter by disease field
            output_fields=["node_id", "disease"]
        )
        
        # Extract results
        hits = results[0] if results else []
        logger.info(f"Found {len(hits)} treatment records for disease filter with cosine search")
        
        if not hits:
            logger.warning(f"⚠️ No treatment records found for disease: {disease_list}")
            state["treatment_chunks"] = []
            state["treatment_node_ids"] = []
            return state
        
        # Load full text from JSONL file
        treatment_chunks = []
        treatment_node_ids = []
        
        file_path = Path("data/raw/mental_health_treatment_guidance.jsonl")
        if file_path.exists():
            node_id_set = {hit.entity.get("node_id") for hit in hits}
            
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                        chunk_id = int(item.get("chunk_id", -1))
                        if chunk_id in node_id_set:
                            text = item.get("text", "").strip()
                            disease = item.get("disease", "")
                            if text:
                                # Add disease prefix for clarity
                                treatment_chunks.append(f"[Disease: {disease}]\n{text}")
                                treatment_node_ids.append(chunk_id)
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"Failed to parse line in treatment file: {e}")
                        continue
        else:
            logger.error(f"❌ Treatment guidance file not found: {file_path}")
        
        logger.info(f"✅ Loaded {len(treatment_chunks)} treatment texts")
        
        state["treatment_chunks"] = treatment_chunks
        state["treatment_node_ids"] = treatment_node_ids
        
    except Exception as e:
        logger.error(f"❌ Error in treatment retrieval: {e}", exc_info=True)
        state["treatment_chunks"] = []
        state["treatment_node_ids"] = []
    
    return state
