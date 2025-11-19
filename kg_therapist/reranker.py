from typing import List, Dict, Any

# Replace with real Cohere rerank if you want
class CohereReranker:
    def rerank_anchors(self, query: str, candidates: List[Dict[str, Any]], top_k: int):
        ranked = sorted(
            candidates,
            key=lambda x: x["original_milvus_score"],
            reverse=True,
        )
        for c in ranked:
            c["cohere_score"] = float(c["original_milvus_score"])
        return ranked[:top_k]


reranker = CohereReranker()
