from typing import List, Dict, Any, Tuple
import json

from .base_retrieval import BaseRetrieval, RetrievalResult
from src.rag.reranker.reranker import CohereReranker
from src.rag.vectors.dense_retriever import DenseRetriever
from src.rag.vectors.embeddings import device  # nếu không dùng thì có thể xoá
from src.rag.vectors.embeddings import encode_e5  # nếu không dùng thì có thể xoá

import logging
logger = logging.getLogger(__name__)

class DenseRetrieval(BaseRetrieval):
    """
    Tích hợp luôn:
      - DenseRetriever (lấy candidate từ Milvus)
      - CohereReranker (rerank)
    Dùng 1 class cho gọn.
    """

    def __init__(
        self,
        collection_name: str = "mental_health_diagnostic_support",
        milvus_top_k: int = 10,
        reranker: CohereReranker | None = None,
    ):
        """
        Args:
            collection_name: tên collection Milvus/Zilliz (default: mental_health_diagnostic_support)
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
          - metadata: thông tin kèm theo (bao gồm disease)
        """
        logger.info(f"[DENSE RETRIEVAL] Starting retrieval for query: '{query[:100]}...'")
        logger.info(f"[CONFIG] Collection: {self.dense_retriever.collection_name if hasattr(self.dense_retriever, 'collection_name') else 'unknown'}")
        logger.info(f"[CONFIG] Milvus top_k: {self.milvus_top_k}, Final top_k: {top_k}")

        # 1. Lấy candidate từ Milvus (bọc query thành list để reuse DenseRetriever cũ)
        logger.info(f"[STEP 1] Calling DenseRetriever.retrieve with query...")
        milvus_results: List[List[Tuple[int, float, str]]] = self.dense_retriever.retrieve(
            [query],
            top_k=self.milvus_top_k,
        )
        
        logger.info(f"[MILVUS] Retrieved {len(milvus_results)} result sets")
        
        # Chỉ có 1 query nên lấy phần tử đầu
        candidates_for_query = milvus_results[0] if milvus_results else []
        
        logger.info(f"[MILVUS] Got {len(candidates_for_query)} candidates for query")
        
        if not candidates_for_query:
            logger.warning("⚠️ [MILVUS] No candidates returned from Milvus!")
            logger.warning("   Possible causes:")
            logger.warning("   1. Collection is empty or doesn't exist")
            logger.warning("   2. Query embedding failed")
            logger.warning("   3. No documents match the query")
            return RetrievalResult(
                context="",
                metadata={
                    "source": self.dense_retriever.get_name_collection()
                    if hasattr(self.dense_retriever, "get_name_collection")
                    else None,
                    "diseases": [],
                    "disease_details": [],
                    "error": "No candidates from Milvus"
                },
            )

        # 2. Chuẩn hoá candidates sang dạng dict cho reranker
        logger.info(f"[STEP 2] Preparing {len(candidates_for_query)} candidates for reranking...")
        candidates_dicts: List[Dict[str, Any]] = []
        for idx, (node_id, score, disease) in enumerate(candidates_for_query):
            # Get text content for reranking
            text_content = self.dense_retriever.get_dense_context_by_id(node_id)
            logger.debug(f"   Candidate {idx+1}: node_id={node_id}, score={score:.4f}, disease={disease}, text_len={len(text_content)}")
            candidates_dicts.append(
                {
                    "chunk_id": node_id,  # Reranker expects 'chunk_id'
                    "node_id": node_id,
                    "text": text_content,  # Add text for Cohere reranking
                    "original_milvus_score": float(score),
                    "disease": disease,  # Add disease from Milvus
                }
            )

        # 3. Rerank bằng CohereReranker
        logger.info(f"[STEP 3] Reranking {len(candidates_dicts)} candidates with Cohere...")
        reranked = self.reranker.rerank_chunks(
            query=query,
            candidates=candidates_dicts,
            top_k=top_k,
        )
        
        logger.info(f"[RERANK] Got {len(reranked)} reranked results (requested top_k={top_k})")

        # 4. Build dense context từ các node sau rerank với disease từ Milvus
        logger.info(f"[STEP 4] Building context from {len(reranked)} reranked chunks...")
        context_parts = []
        diseases = []  # Collect unique diseases
        disease_details = []  # Detailed disease info per chunk
        
        for idx, c in enumerate(reranked):
            chunk_id = c.get("chunk_id") or c.get("node_id")  # Support both keys
            cohere_score = float(c["cohere_score"])
            disease_name = c.get("disease", "")  # Get disease from reranked results
            answer_text = self.dense_retriever.get_dense_context_by_id(chunk_id)
            
            logger.debug(f"   Chunk {idx+1}: chunk_id={chunk_id}, cohere_score={cohere_score:.4f}, disease={disease_name}")
            
            # Collect unique diseases
            if disease_name and disease_name not in diseases:
                diseases.append(disease_name)
            
            disease_details.append({
                "chunk_id": chunk_id,
                "disease": disease_name,
                "score": cohere_score,
            })
            
            # Build context with disease
            if disease_name:
                context_parts.append(
                    f"[Disease: {disease_name}] Answer (ID: {chunk_id}, Score: {cohere_score:.4f}): {answer_text}"
                )
            else:
                context_parts.append(
                    f"Answer (ID: {chunk_id}, Score: {cohere_score:.4f}): {answer_text}"
                )

        dense_context = "\n".join(context_parts)
        
        logger.info(f"✅ [DONE] Built context with {len(context_parts)} chunks, total length: {len(dense_context)} chars")
        logger.info(f"   Diseases detected: {diseases}")

        return RetrievalResult(
            context=dense_context,
            metadata={
                "source": self.dense_retriever.get_name_collection()
                if hasattr(self.dense_retriever, "get_name_collection")
                else None,
                "diseases": diseases,  # List of unique diseases detected
                "disease_details": disease_details,  # Detailed per-chunk disease info
            },
        )

    def get_name(self):
        return "DenseRetrieval"
