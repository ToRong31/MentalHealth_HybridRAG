"""
Treatment Retrieval Node
Retrieves treatment guidance by disease keyword from Milvus
Uses disease field filtering instead of vector search
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

from pymilvus import Collection

from ..state import KGState
from src.rag.config import rag_settings

logger = logging.getLogger(__name__)


async def treatment_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve treatment chunks filtered by disease field in Milvus
    
    Args:
        state: KGState with detected_disease
    
    Returns:
        Updated state with treatment_chunks, treatment_node_ids
    """
    detected_disease = state.get("detected_disease", "")
    
    if not detected_disease:
        logger.warning("⚠️ No disease detected for treatment retrieval")
        state["treatment_chunks"] = []
        state["treatment_node_ids"] = []
        return state
    
    logger.info(f"💊 Retrieving treatment guidance for disease: '{detected_disease}'")
    
    try:
        # Connect to Milvus collection
        col = Collection("mental_health_treatment_guidance")
        col.load()
        
        # Query by disease field (partial match using LIKE)
        # Escape special characters for Milvus expr
        disease_escaped = detected_disease.replace('"', '\\"').replace("'", "\\'")
        expr = f'disease like "%{disease_escaped}%"'
        
        logger.info(f"Milvus query expression: {expr}")
        
        results = col.query(
            expr=expr,
            output_fields=["node_id", "disease"],
            limit=5
        )
        
        logger.info(f"Found {len(results)} treatment records for disease: '{detected_disease}'")
        
        if not results:
            logger.warning(f"⚠️ No treatment records found for disease: '{detected_disease}'")
            state["treatment_chunks"] = []
            state["treatment_node_ids"] = []
            return state
        
        # Load full text from JSONL file
        treatment_chunks = []
        treatment_node_ids = []
        
        file_path = Path("data/raw/mental_health_treatment_guidance.jsonl")
        if file_path.exists():
            node_id_set = {r["node_id"] for r in results}
            
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
                            if text:
                                treatment_chunks.append(text)
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
