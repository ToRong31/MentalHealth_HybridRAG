from typing import List, Dict, Any, Optional
import logging

from pymilvus import connections, Collection, utility

from src.rag.config import rag_settings

logger = logging.getLogger(__name__)

if not rag_settings.MILVUS_URI:
    raise RuntimeError("Set MILVUS_URI environment variable")

# Global state for lazy loading
_connected = False
_col: Optional[Collection] = None


def _ensure_connection():
    """Ensure connection to Milvus (lazy)"""
    global _connected
    if _connected:
        return
    
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
    _connected = True
    logger.info("Connected to Milvus")


def get_collection() -> Collection:
    """Get collection (lazy loading, will fail if collection doesn't exist)"""
    global _col
    if _col is None:
        _ensure_connection()
        
        if rag_settings.MILVUS_COLLECTION not in utility.list_collections():
            raise RuntimeError(
                f"Collection '{rag_settings.MILVUS_COLLECTION}' does not exist. \n"
                f"Please run the ingestion pipeline first to create embeddings.\n"
                f"From /app directory, run: python3 run_ingestion.py"
            )
        
        _col = Collection(rag_settings.MILVUS_COLLECTION)
        _col.load()
        logger.info(f"Loaded collection: {rag_settings.MILVUS_COLLECTION}")
    
    return _col


def milvus_search(q_vec, limit: int = 10, threshold: float = 0.8) -> List[Dict[str, Any]]:
    """
    Search in Milvus and return candidate anchors as:
    [{ 'node_id': int, 'original_milvus_score': float }, ...]
    """
    col = get_collection()
    
    res = col.search(
        data=[q_vec],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"ef": rag_settings.HNSW_EF}},
        limit=limit,
        output_fields=[],
    )


    hits = res[0]
    candidates = []

    # ⚠️ adjust comparator depending on whether score is distance or similarity
    for h in hits:
        score = float(h.distance)
        node_id = h.id
        if score >= threshold:   # or <= if distance
            candidates.append({
                "node_id": node_id,
                "original_milvus_score": score,
            })

    return candidates
