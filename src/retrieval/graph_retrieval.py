"""
Graph Retrieval Implementation
Implement GraphRAG retriever using Knowledge Graph
"""
from typing import Dict, Any, List

from .base_retriever import BaseRetriever, RetrievalResult
from src.vectors.embeddings import encode_e5
from src.vectors.milvus_client import milvus_search
from src.graph.neo4j_client import get_node_names_from_neo4j
from src.graph.graph_retriever import graph_retriever
from src.reranker.reranker import reranker


class GraphRetrieval(BaseRetriever):
    """
    GraphRAG retriever
    Pipeline: Query → E5 Embed → Milvus Search → Rerank → Expand Subgraph → Build Context
    """
    
    def __init__(
        self,
        milvus_limit: int = 10,
        milvus_threshold: float = 0.8,
        rerank_top_k: int = 5
    ):
        """
        Initialize Graph Retriever
        
        Args:
            milvus_limit: Max candidates from Milvus
            milvus_threshold: Minimum similarity score
            rerank_top_k: Top K after reranking
        """
        self.milvus_limit = milvus_limit
        self.milvus_threshold = milvus_threshold
        self.rerank_top_k = rerank_top_k
    
    def retrieve(self, query: str, **kwargs) -> RetrievalResult:
        """
        Retrieve graph context for query
        
        Args:
            query: User's question
            **kwargs: Additional parameters (can override defaults)
        
        Returns:
            RetrievalResult with graph context and metadata
        """
        # Step 1: Encode query to embedding
        query_embedding = encode_e5([f"query: {query}"])[0]
        
        # Step 2: Search Milvus for candidate anchor nodes
        milvus_limit = kwargs.get('milvus_limit', self.milvus_limit)
        milvus_threshold = kwargs.get('milvus_threshold', self.milvus_threshold)
        
        candidates = milvus_search(
            query_embedding.tolist(),
            limit=milvus_limit,
            threshold=milvus_threshold
        )
        
        if not candidates:
            # No anchors found
            return RetrievalResult(
                context="",
                metadata={
                    "anchors": [],
                    "nodes_count": 0,
                    "rels_count": 0,
                    "retriever": self.get_name()
                }
            )
        
        # Step 3: Get node names from Neo4j
        node_ids = [c["node_id"] for c in candidates]
        name_map = get_node_names_from_neo4j(node_ids)
        
        for c in candidates:
            c["name"] = name_map.get(c["node_id"], f"Node_{c['node_id']}")
        
        # Step 4: Rerank anchors
        rerank_top_k = kwargs.get('rerank_top_k', self.rerank_top_k)
        anchors = reranker.rerank_anchors(query, candidates, top_k=rerank_top_k)
        
        # Step 5: Expand subgraph from anchors
        anchor_ids = [a["node_id"] for a in anchors]
        nodes, rels = graph_retriever.retrieve_subgraph(anchor_ids)
        
        # Step 6: Build context string
        context = graph_retriever.build_context(nodes, rels, anchors)
        
        # Return result with metadata
        return RetrievalResult(
            context=context,
            metadata={
                "anchors": anchors,
                "nodes_count": len(nodes),
                "rels_count": len(rels),
                "milvus_candidates": len(candidates),
                "retriever": self.get_name()
            }
        )
    
    def get_name(self) -> str:
        """Return retriever name"""
        return "GraphRetrieval"


# Global instance for easy import
graph_retrieval = GraphRetrieval()

