from langgraph.graph import StateGraph, END
from typing import Literal

from .state import KGState
from .graph_nodes import (
    safety_check_node,
    crisis_response_node,
    not_mental_health_node,
    encode_node,
    graph_retrieval_node,
    answer_with_graph_node,
)


def route_after_safety_check(state: KGState) -> Literal["crisis_response", "not_mental_health", "graph_retrieval"]:
    """
    Routing logic sau khi check safety:
    - Nếu high-risk -> crisis_response
    - Nếu không phải mental health -> not_mental_health
    - Nếu OK -> tiếp tục graph_retrieval
    """
    if state.get("is_high_risk", False):
        return "crisis_response"
    
    if not state.get("is_mental_health_related", True):
        return "not_mental_health"
    
    return "graph_retrieval"


def build_kg_graph():
    """
    Build Knowledge Graph RAG workflow
    
    Workflow:
    1. safety_check -> Route based on risk/relevance
    2a. If high-risk -> crisis_response -> END
    2b. If not mental health -> not_mental_health -> END  
    2c. If safe & relevant -> graph_retrieval -> answer -> END
    
    Graph retrieval integrates:
    - Encode query to embedding
    - Milvus vector search for anchor nodes
    - Rerank anchors
    - Expand subgraph in Neo4j
    - Build context string
    """
    builder = StateGraph(KGState)

    # Add nodes
    builder.add_node("safety_check", safety_check_node)
    builder.add_node("crisis_response", crisis_response_node)
    builder.add_node("not_mental_health", not_mental_health_node)
    builder.add_node("graph_retrieval", graph_retrieval_node)
    builder.add_node("answer", answer_with_graph_node)

    # Entry point
    builder.set_entry_point("safety_check")

    # Conditional routing after safety check
    builder.add_conditional_edges(
        "safety_check",
        route_after_safety_check,
        {
            "crisis_response": "crisis_response",
            "not_mental_health": "not_mental_health",
            "graph_retrieval": "graph_retrieval",
        },
    )

    # Crisis and non-relevant queries end immediately
    builder.add_edge("crisis_response", END)
    builder.add_edge("not_mental_health", END)

    # Normal flow: retrieval -> answer
    builder.add_edge("graph_retrieval", "answer")
    builder.add_edge("answer", END)

    return builder.compile()
