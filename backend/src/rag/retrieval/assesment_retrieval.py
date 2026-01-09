from typing import List, Dict, Any, Tuple
import logging

from .base_retrieval import BaseRetrieval, RetrievalResult
from src.rag.reranker.reranker import CohereReranker
from src.rag.vectors.dense_retriever import DenseRetriever

logger = logging.getLogger(__name__)


class AssessmentRetrieval(BaseRetrieval):
    """
    Assessment/Normal Response Retrieval
    Retrieves from 'normal_response' collection with fields: node_id, type, text
    Used for general responses, psychoeducation, and non-diagnostic queries
    """

    def __init__(
        self,
        collection_name: str = "normal_response",
        milvus_top_k: int = 50,
        reranker: CohereReranker | None = None,
        context_file: str | None = None,
    ):
        """
        Initialize Assessment Retrieval
        
        Args:
            collection_name: Milvus collection name (default: normal_response)
            milvus_top_k: Number of candidates to retrieve from Milvus before reranking
            reranker: Optional custom CohereReranker instance
            context_file: Optional path to context file (default: auto-detect from collection name)
        """
        self.dense_retriever = DenseRetriever(
            collection_name=collection_name,
            context_file=context_file
        )
        self.reranker = reranker or CohereReranker()
        self.milvus_top_k = milvus_top_k
        self.collection_name = collection_name

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> RetrievalResult:
        """
        Retrieve and rerank from normal_response collection
        
        Args:
            query: User's question
            top_k: Number of final results after reranking
        
        Returns:
            RetrievalResult containing:
                - context: Formatted context string
                - metadata: Additional information (types, node_ids, scores)
        """
        logger.info(f"[ASSESSMENT RETRIEVAL] Starting retrieval for query: '{query[:100]}...'")
        logger.info(f"[CONFIG] Collection: {self.collection_name}")
        logger.info(f"[CONFIG] Milvus top_k: {self.milvus_top_k}, Final top_k: {top_k}")

        # Step 1: Retrieve candidates from Milvus
        logger.info(f"[STEP 1] Retrieving candidates from Milvus collection: {self.collection_name}")
        milvus_results: List[List[Tuple[int, float, str]]] = self.dense_retriever.retrieve(
            [query],
            top_k=self.milvus_top_k,
        )
        
        logger.info(f"[MILVUS] Retrieved {len(milvus_results)} result sets")
        
        # Get candidates for single query
        candidates_for_query = milvus_results[0] if milvus_results else []
        
        logger.info(f"[MILVUS] Got {len(candidates_for_query)} candidates")
        
        if not candidates_for_query:
            logger.warning("⚠️ [MILVUS] No candidates returned!")
            logger.warning("   Possible causes:")
            logger.warning("   1. Collection 'normal_response' is empty or doesn't exist")
            logger.warning("   2. Query embedding failed")
            logger.warning("   3. No documents match the query")
            return RetrievalResult(
                context="",
                metadata={
                    "source": self.collection_name,
                    "types": [],
                    "error": "No candidates from Milvus"
                },
            )

        # Step 2: Prepare candidates for reranking
        logger.info(f"[STEP 2] Preparing {len(candidates_for_query)} candidates for reranking...")
        candidates_dicts: List[Dict[str, Any]] = []
        
        for idx, (node_id, score, response_type) in enumerate(candidates_for_query):
            # Get text content for reranking
            text_content = self.dense_retriever.get_dense_context_by_id(node_id)
            
            logger.debug(
                f"   Candidate {idx+1}: node_id={node_id}, "
                f"score={score:.4f}, type={response_type}, text_len={len(text_content)}"
            )
            
            candidates_dicts.append({
                "chunk_id": node_id,  # Reranker expects 'chunk_id'
                "node_id": node_id,
                "text": text_content,  # Text for Cohere reranking
                "type": response_type,  # Response type (general, psychoeducation, etc.)
                "original_milvus_score": float(score),
            })

        # Step 3: Rerank with CohereReranker
        logger.info(f"[STEP 3] Reranking {len(candidates_dicts)} candidates with Cohere...")
        reranked = self.reranker.rerank_chunks(
            query=query,
            candidates=candidates_dicts,
            top_k=top_k,
        )
        
        logger.info(f"[RERANK] Got {len(reranked)} reranked results (requested top_k={top_k})")

        # Step 4: Build context from reranked results
        logger.info(f"[STEP 4] Building context from {len(reranked)} reranked chunks...")
        context_parts = []
        types = []  # Collect unique types
        type_details = []  # Detailed info per chunk
        
        for idx, chunk in enumerate(reranked):
            chunk_id = chunk.get("chunk_id") or chunk.get("node_id")
            cohere_score = float(chunk["cohere_score"])
            response_type = chunk.get("type", "general")
            text_content = self.dense_retriever.get_dense_context_by_id(chunk_id)
            
            logger.debug(
                f"   Chunk {idx+1}: chunk_id={chunk_id}, "
                f"cohere_score={cohere_score:.4f}, type={response_type}"
            )
            
            # Collect unique types
            if response_type and response_type not in types:
                types.append(response_type)
            
            # Store detailed type information
            type_details.append({
                "node_id": chunk_id,
                "type": response_type,
                "score": cohere_score,
            })
            
            # Build context with type information
            if response_type:
                context_parts.append(
                    f"[Type: {response_type}] Response (ID: {chunk_id}, Score: {cohere_score:.4f}):\n{text_content}"
                )
            else:
                context_parts.append(
                    f"Response (ID: {chunk_id}, Score: {cohere_score:.4f}):\n{text_content}"
                )

        assessment_context = "\n\n".join(context_parts)
        
        logger.info(f"✅ [DONE] Built context with {len(context_parts)} chunks")
        logger.info(f"   Total length: {len(assessment_context)} chars")
        logger.info(f"   Response types: {types}")

        return RetrievalResult(
            context=assessment_context,
            metadata={
                "source": self.collection_name,
                "types": types,  # List of unique response types
                "type_details": type_details,  # Detailed per-chunk type info (includes node_ids)
                "count": len(reranked),
            },
        )

    def get_name(self) -> str:
        """Return retriever name"""
        return "AssessmentRetrieval"
