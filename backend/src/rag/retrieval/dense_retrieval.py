from typing import List, Dict, Any, Tuple

from .base_retriever import BaseRetriever, RetrievalResult
from src.rag.reranker.reranker import CohereReranker
from src.rag.vectors.dense_retriever import DenseRetriever
from src.rag.vectors.embeddings import device  # nếu không dùng thì có thể xoá
from src.rag.vectors.embeddings import encode_e5  # nếu không dùng thì có thể xoá


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
        query: str,
        top_k: int = 2,
    ) -> RetrievalResult:
        """
        Nhận 1 query string, trả về RetrievalResult:
          - context: 1 chuỗi context dense đã build từ các node rerank
          - metadata: thông tin kèm theo
        """

        # 1. Lấy candidate từ Milvus (bọc query thành list để reuse DenseRetriever cũ)
        milvus_results: List[List[Tuple[int, float]]] = self.dense_retriever.retrieve(
            [query],
            top_k=self.milvus_top_k,
        )
        # Chỉ có 1 query nên lấy phần tử đầu
        candidates_for_query = milvus_results[0]

        # 2. Chuẩn hoá candidates sang dạng dict cho reranker
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

        # 3. Rerank bằng CohereReranker
        reranked = self.reranker.rerank_anchors(
            query=query,
            candidates=candidates_dicts,
            top_k=top_k,
        )

        # 4. Build dense context từ các node sau rerank
        context_parts = []
        for c in reranked:
            node_id = c["node_id"]
            cohere_score = float(c["cohere_score"])
            answer_text = self.dense_retriever.get_dense_context_by_id(node_id)
            context_parts.append(
                f"Answer (ID: {node_id}, Score: {cohere_score:.4f}): {answer_text}"
            )

        dense_context = "\n".join(context_parts)

        return RetrievalResult(
            context=dense_context,
            metadata={
                "source": self.dense_retriever.get_name_collection()
                if hasattr(self.dense_retriever, "get_name_collection")
                else None
            },
        )

    def get_name(self):
        return "DenseRetrieval"


dense_retrieval = DenseRetrieval()
