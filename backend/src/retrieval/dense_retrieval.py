from typing import List, Dict, Any, Tuple

from .base_retriever import BaseRetriever, RetrievalResult
from src.reranker.reranker import CohereReranker
from src.vectors.dense_retriever import DenseRetriever
from src.vectors.embeddings import device  # hoặc import device từ nơi bạn định nghĩa
from src.vectors.embeddings import encode_e5


class DenseRetrieval(BaseRetriever):
    """
    Tích hợp luôn:
      - DenseRetriever (lấy candidate từ Milvus)
      - CohereReranker (rerank)
    Dùng 1 class cho gọn.
    """

    def __init__(
        self,
        collection_name: str = "chat_16k",
        milvus_top_k: int = 10,
        reranker: CohereReranker | None = None,
    ):
        """
        Args:
            collection_name: tên collection Milvus/Zilliz (vd: "chat_16k")
            milvus_top_k: số candidate lấy từ Milvus trước khi rerank
            reranker: có thể truyền CohereReranker custom, mặc định tạo mới.
        """
        self.dense_retriever = DenseRetriever(collection_name=collection_name)
        self.reranker = reranker or CohereReranker()
        self.milvus_top_k = milvus_top_k

    def retrieve(
        self,
        queries: List[str],
        top_k: int = 10,
    ) -> List[List[Tuple[int, float]]]:
        """
        Trả về list kết quả cho mỗi query sau khi rerank:
        [
          [(node_id1, cohere_score1), (node_id2, cohere_score2), ...],  # query 1
          [(...), ...],                                                # query 2
          ...
        ]
        """
        # 1. Lấy candidate từ Milvus
        milvus_results: List[List[Tuple[int, float]]] = self.dense_retriever.retrieve(
            queries,
            top_k=self.milvus_top_k,
        )

        all_reranked: List[List[Tuple[int, float]]] = []

        # 2. Rerank từng query
        for query, candidates_for_query in zip(queries, milvus_results):
            candidates_dicts: List[Dict[str, Any]] = []
            for node_id, score in candidates_for_query:
                candidates_dicts.append(
                    {
                        "node_id": node_id,
                        "original_milvus_score": float(score),
                        # Nếu sau này có text thì thêm:
                        # "text": node_text,
                    }
                )

            reranked = self.reranker.rerank_anchors(
                query=query,
                candidates=candidates_dicts,
                top_k=top_k,
            )

            one_query_reranked: List[Tuple[int, float]] = [
                (c["node_id"], float(c["cohere_score"])) for c in reranked
            ]
            all_reranked.append(one_query_reranked)
        
            # Build dense context for each query after reranking
        dense_contexts = []
        for reranked in all_reranked:
            context_parts = []
            for node_id, score in reranked:
                answer_text = self.dense_retriever.get_dense_context_by_id(node_id)
                context_parts.append(f"Answer (ID: {node_id}, Score: {score:.4f}): {answer_text}")
            dense_context = "\n".join(context_parts)
            dense_contexts.append(dense_context)

        return RetrievalResult(
            context=dense_contexts,
            metadata={"source": self.dense_retriever.get_name_collection}
        )
    
    def get_name(self):
        return "DenseRetrievel"
    

dense_retrieval = DenseRetrieval()

    