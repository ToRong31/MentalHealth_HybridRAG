"""
Graph Retrieval Implementation
Implement GraphRAG retriever using Knowledge Graph
"""
import logging
from typing import Dict, Any, List, Optional

from .base_retrieval import BaseRetrieval, RetrievalResult
from src.rag.vectors.embeddings import encode_e5
from src.rag.vectors.milvus_client import milvus_search
from src.rag.graph.neo4j_client import get_node_names_from_neo4j
from src.rag.graph.graph_retriever import graph_retriever
from src.rag.reranker.reranker import reranker

logger = logging.getLogger(__name__)


class GraphRetrieval(BaseRetrieval):
    """
    GraphRAG retriever
    Pipeline: Query → E5 Embed → Milvus Search → Rerank → Expand Subgraph → Build Context
    """
    
    def __init__(
        self,
        milvus_limit: int = 50,
        milvus_threshold: float = 0.8,
        rerank_top_k: int = 3
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
        
        # Debug: Store Milvus scores before reranking
        milvus_scores = [
            {
                "node_id": c["node_id"],
                "name": c["name"],
                "milvus_score": c.get("original_milvus_score", 0.0)
            }
            for c in candidates
        ]
        
        # Step 4: Rerank anchors with Cohere
        rerank_top_k = kwargs.get('rerank_top_k', self.rerank_top_k)
        anchors = reranker.rerank_anchors(query, candidates, top_k=rerank_top_k)
        
        # Step 4.5: Apply slot-based rerank bonus (light rerank)
        slots = kwargs.get('slots')
        if slots:
            anchors = self._apply_slot_rerank_bonus(anchors, slots)
        
        # Debug: Store rerank scores
        rerank_scores = [
            {
                "node_id": a["node_id"],
                "name": a["name"],
                "milvus_score": a.get("original_milvus_score", 0.0),
                "rerank_score": a.get("cohere_score", 0.0),
                "slot_bonus": a.get("slot_bonus", 0.0),
                "final_score": a.get("final_score", a.get("cohere_score", 0.0))
            }
            for a in anchors
        ]
        
        # Step 5: Expand subgraph from anchors
        anchor_ids = [a["node_id"] for a in anchors]
        nodes, rels = graph_retriever.retrieve_subgraph(anchor_ids)
        
        # Step 6: Build context string (without scores)
        context = graph_retriever.build_context(nodes, rels, anchors)
        
        # Return result with metadata (including debug scores)
        return RetrievalResult(
            context=context,
            metadata={
                "anchors": anchors,
                "nodes_count": len(nodes),
                "rels_count": len(rels),
                "milvus_candidates": len(candidates),
                "milvus_scores": milvus_scores,  # Debug: Milvus scores
                "rerank_scores": rerank_scores,  # Debug: Rerank scores
                "retriever": self.get_name()
            }
        )
    
    def _apply_slot_rerank_bonus(
        self, 
        anchors: List[Dict[str, Any]], 
        slots: Dict[str, Any],
        bonus_weight: float = 0.05
    ) -> List[Dict[str, Any]]:
        """
        Apply light rerank bonus based on slots.
        Matches slot keywords against node names and adds small bonus to scores.
        
        Args:
            anchors: List of reranked anchors (from Cohere rerank)
            slots: Slot dictionary with user information
            bonus_weight: Weight for slot bonus (default 0.05 = 5% boost)
        
        Returns:
            Reranked anchors with slot bonus applied
        """
        try:
            from src.rag.utils.slots import get_slot_keywords
            
            # Get keywords from slots
            slot_keywords = get_slot_keywords(slots)
            
            if not slot_keywords:
                logger.debug("No slot keywords found, skipping slot rerank bonus")
                return anchors
            
            logger.debug(f"Applying slot rerank bonus with keywords: {slot_keywords[:5]}...")
            
            # Apply bonus to each anchor
            for anchor in anchors:
                node_name = anchor.get("name", "").lower()
                bonus = 0.0
                
                # Count keyword matches in node name
                matches = sum(1 for keyword in slot_keywords if keyword in node_name)
                
                if matches > 0:
                    # Bonus proportional to number of matches (capped)
                    bonus = min(bonus_weight * matches, bonus_weight * 3)  # Max 3x bonus
                    anchor["slot_bonus"] = bonus
                    
                    # Calculate final score (Cohere score + bonus)
                    cohere_score = anchor.get("cohere_score", 0.0)
                    anchor["final_score"] = cohere_score + bonus
                else:
                    anchor["slot_bonus"] = 0.0
                    anchor["final_score"] = anchor.get("cohere_score", 0.0)
            
            # Re-sort by final score (Cohere score + slot bonus)
            anchors_sorted = sorted(
                anchors,
                key=lambda x: x.get("final_score", x.get("cohere_score", 0.0)),
                reverse=True
            )
            
            logger.debug(f"Slot rerank bonus applied. Top anchor: {anchors_sorted[0].get('name')} "
                        f"(cohere: {anchors_sorted[0].get('cohere_score', 0.0):.3f}, "
                        f"bonus: {anchors_sorted[0].get('slot_bonus', 0.0):.3f}, "
                        f"final: {anchors_sorted[0].get('final_score', 0.0):.3f})")
            
            return anchors_sorted
            
        except Exception as e:
            logger.warning(f"Error applying slot rerank bonus: {e}, returning original anchors")
            return anchors
    
    def get_name(self) -> str:
        """Return retriever name"""
        return "GraphRetrieval"


# Global instance for easy import
graph_retrieval = GraphRetrieval()

