from typing import List, Dict, Any

from pymilvus import connections, Collection

from src.config import MILVUS_URI, MILVUS_TOKEN, MILVUS_DB, MILVUS_COLLECTION

if not MILVUS_URI or not MILVUS_TOKEN:
    raise RuntimeError("Set MILVUS_URI and MILVUS_TOKEN environment variables")

connections.connect(
    alias="default",
    uri=MILVUS_URI,
    token=MILVUS_TOKEN,
    secure=True,
    db_name=MILVUS_DB,
)

col = Collection(MILVUS_COLLECTION)
col.load()


def milvus_search(q_vec, limit: int = 10, threshold: float = 0.8) -> List[Dict[str, Any]]:
    """
    Search in Milvus and return candidate anchors as:
    [{ 'node_id': int, 'original_milvus_score': float }, ...]
    """
    res = col.search(
        data=[q_vec],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"ef": 128}},
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
