"""
LangGraph Nodes for Graph-based RAG Workflow
Refactored to use modular components
"""
from typing import Dict, Any

from .state import KGState
from src.vectors.embeddings import encode_e5
from src.retrieval.graph_retrieval import graph_retrieval
from src.llm.answer_nodes import (
    safety_check_node,
    crisis_response_node,
    not_mental_health_node,
    answer_with_graph_node
)


# --- Encoding node ---

def encode_node(state: KGState) -> KGState:
    """
    Encode query to embedding vector
    
    Args:
        state: KGState with 'question'
    
    Returns:
        Updated state with 'query_embedding'
    """
    q = state["question"]
    emb = encode_e5([f"query: {q}"])[0]
    state["query_embedding"] = emb.tolist()
    return state


# --- Retrieval node ---

def graph_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve graph context using GraphRetrieval
    
    Args:
        state: KGState with 'question'
    
    Returns:
        Updated state with 'graph_context', 'anchors', 'nodes', 'rels'
    """
    question = state["question"]
    
    # Use GraphRetrieval to get context
    result = graph_retrieval.retrieve(question)
    
    # Update state
    state["graph_context"] = result.context
    state["anchors"] = result.metadata.get("anchors", [])
    state["nodes_count"] = result.metadata.get("nodes_count", 0)
    state["rels_count"] = result.metadata.get("rels_count", 0)
    
    return state


# --- Export all nodes ---

__all__ = [
    # Safety nodes (from llm.answer_nodes)
    'safety_check_node',
    'crisis_response_node',
    'not_mental_health_node',
    
    # Encoding
    'encode_node',
    
    # Retrieval
    'graph_retrieval_node',
    
    # Answer generation
    'answer_with_graph_node',
]
