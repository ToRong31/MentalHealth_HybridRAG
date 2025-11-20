from langgraph.graph import StateGraph, END
from typing import Literal

from .state import KGState
from .graph_nodes import (
    safety_check_node,
    crisis_response_node,
    not_mental_health_node,
    encode_node,
    milvus_rerank_node,
    neo4j_subgraph_node,
    build_subgraph_context_node,
    answer_node,
)


def route_after_safety_check(state: KGState) -> Literal["crisis_response", "not_mental_health", "encode"]:
    """
    Routing logic sau khi check safety:
    - Nếu high-risk -> crisis_response
    - Nếu không phải mental health -> not_mental_health
    - Nếu OK -> tiếp tục encode
    """
    if state.get("is_high_risk", False):
        return "crisis_response"
    
    if not state.get("is_mental_health_related", True):
        return "not_mental_health"
    
    return "encode"


def build_kg_graph():
    builder = StateGraph(KGState)

    # Thêm các node
    builder.add_node("safety_check", safety_check_node)
    builder.add_node("crisis_response", crisis_response_node)
    builder.add_node("not_mental_health", not_mental_health_node)
    builder.add_node("encode", encode_node)
    builder.add_node("milvus_rerank", milvus_rerank_node)
    builder.add_node("neo4j_subgraph", neo4j_subgraph_node)
    builder.add_node("build_subgraph_context", build_subgraph_context_node)
    builder.add_node("answer", answer_node)

    # Entry point là safety check
    builder.set_entry_point("safety_check")

    # Routing sau safety check
    builder.add_conditional_edges(
        "safety_check",
        route_after_safety_check,
        {
            "crisis_response": "crisis_response",
            "not_mental_health": "not_mental_health",
            "encode": "encode",
        },
    )

    # Crisis response và not mental health kết thúc luôn
    builder.add_edge("crisis_response", END)
    builder.add_edge("not_mental_health", END)

    # Normal flow tiếp tục như cũ
    builder.add_edge("encode", "milvus_rerank")
    builder.add_edge("milvus_rerank", "neo4j_subgraph")
    builder.add_edge("neo4j_subgraph", "build_subgraph_context")
    builder.add_edge("build_subgraph_context", "answer")
    builder.add_edge("answer", END)

    return builder.compile()
