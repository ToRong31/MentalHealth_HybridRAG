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
    translate_question_node,
    translate_answer_node,
    dense_retrieval_node,
    answer_with_dense_node,
    hybrid_retrieval_node,
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
    Build Knowledge Graph RAG workflow with async support
    
    Workflow:
    1. translate_question -> Detect language (VI/EN) and translate to EN if needed
    2. safety_check -> Route based on risk/relevance
    3a. If high-risk -> crisis_response -> END
    3b. If not mental health -> not_mental_health -> END  
    3c. If safe & relevant -> graph_retrieval -> answer -> END
    
    Translation logic:
    - Vietnamese input: VI -> EN (processing) -> VI (output)
    - English input: EN (no translation) -> EN (output)
    
    Graph retrieval integrates:
    - Encode query -> Milvus search -> Rerank -> Expand subgraph
    - All async for non-blocking execution
    
    Note: hybrid_retrieval (graph + dense parallel) is available but commented out for now
    """
    builder = StateGraph(KGState)

    # Add nodes (all async now)
    builder.add_node("translate_question", translate_question_node)
    builder.add_node("translate_answer", translate_answer_node)
    builder.add_node("safety_check", safety_check_node)
    builder.add_node("crisis_response", crisis_response_node)
    builder.add_node("not_mental_health", not_mental_health_node)
    builder.add_node("graph_retrieval", graph_retrieval_node)
    # builder.add_node("hybrid_retrieval", hybrid_retrieval_node)  # Available for future use
    builder.add_node("answer", answer_with_graph_node)

    # Entry point - start with translation
    builder.set_entry_point("translate_question")
    
    # After translation, go to safety check
    builder.add_edge("translate_question", "safety_check")

    # Conditional routing after safety check
    builder.add_conditional_edges(
        "safety_check",
        route_after_safety_check,
        {
            "crisis_response": "crisis_response",
            "not_mental_health": "not_mental_health",
            "graph_retrieval": "graph_retrieval",
            # "hybrid_retrieval": "hybrid_retrieval",  # Available for future use
        },
    )

    # Crisis and non-relevant queries exit directly
    builder.add_edge("crisis_response", END)
    builder.add_edge("not_mental_health", END)

    # Normal flow: graph_retrieval -> answer -> END
    builder.add_edge("graph_retrieval", "answer")
    # builder.add_edge("hybrid_retrieval", "answer")  # Available for future use
    builder.add_edge("answer", END)

    return builder.compile()
