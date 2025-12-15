from langgraph.graph import StateGraph, END
from typing import Literal

from .state import KGState
from .graph_nodes import (
    encode_node,
    graph_retrieval_node,
    translate_question_node,
    translate_answer_node,
    dense_retrieval_node,
    hybrid_retrieval_node,
    query_similarity_check_node,
    safety_check_node,
    crisis_response_node,
    not_mental_health_node,
    answer_with_graph_node,
    answer_with_dense_node,
    slot_filling_node,
    query_classifier_node,
    conversation_memory_node,
)
    


def route_after_query_similarity_check(state: KGState) -> Literal["classify_query", "safety_check"]:
    """
    Routing logic sau khi check query similarity:
    - Nếu similarity >= 0.8 hoặc không có buffer/summary -> skip LLM, go to safety_check
    - Nếu similarity < 0.8 -> cần LLM classify, go to classify_query
    """
    query_type = state.get("query_type")
    query_similarity = state.get("query_similarity")
    
    # Nếu đã có query_type (>= 0.8 hoặc không có buffer) -> skip LLM
    if query_type is not None:
        return "safety_check"
    
    # Nếu similarity < 0.8 -> cần LLM classify
    if query_similarity is not None and query_similarity < 0.8:
        return "classify_query"
    
    # Fallback: go to safety_check
    return "safety_check"


def route_after_safety_check(state: KGState) -> Literal["crisis_response", "not_mental_health", "slot_filling"]:
    """
    Routing logic sau khi check safety:
    - Nếu high-risk -> crisis_response
    - Nếu không phải mental health -> not_mental_health
    - Nếu OK -> slot_filling (để extract thông tin trước khi retrieval)
    """
    if state.get("is_high_risk", False):
        return "crisis_response"
    
    if not state.get("is_mental_health_related", True):
        return "not_mental_health"
    
    return "slot_filling"


def build_kg_graph():
    """
    Build Knowledge Graph RAG workflow with conversation memory support
    
    Workflow:
    1. translate_question -> Detect language (VI/EN), translate to EN if needed
    2. query_similarity_check -> Check similarity with conversation context (embedding)
    3. route_after_query_similarity_check -> Route based on similarity:
       3a. If similarity >= 0.8 or no buffer -> skip LLM, go to safety_check
       3b. If similarity < 0.8 -> classify_query (LLM) -> safety_check
    4. safety_check -> Check if mental health related and risk level (with conditional enhancement)
    5. route_after_safety_check -> Route based on safety_check results:
       5a. If high-risk -> crisis_response -> END
       5b. If not mental health -> not_mental_health -> END  
       5c. If safe & relevant -> slot_filling -> graph_retrieval -> answer -> conversation_memory -> translate_answer -> END
    
    Conversation Memory:
    - query_similarity_check: Check if query is follow-up, topic_change, or off_topic
    - classify_query: LLM classify query type (only if similarity < 0.8)
    - safety_check: Conditional enhancement based on query_type
    - graph_retrieval: Conditional enhancement for retrieval
    - answer: Enhanced with buffer + summary context
    - conversation_memory: Update buffer + summary, handle topic change
    
    Slot filling (after safety check passes):
    - Extract structured information (emotion, trigger, duration, etc.)
    - Identify missing information
    - Generate contextually relevant follow-up questions if needed
    
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
    builder.add_node("query_similarity_check", query_similarity_check_node)
    builder.add_node("classify_query", query_classifier_node)
    builder.add_node("safety_check", safety_check_node)
    builder.add_node("slot_filling", slot_filling_node)  # Chạy sau safety_check
    builder.add_node("crisis_response", crisis_response_node)
    builder.add_node("not_mental_health", not_mental_health_node)
    builder.add_node("graph_retrieval", graph_retrieval_node)
    # builder.add_node("hybrid_retrieval", hybrid_retrieval_node)  # Available for future use
    builder.add_node("answer", answer_with_graph_node)
    builder.add_node("conversation_memory", conversation_memory_node)
    builder.add_node("translate_answer", translate_answer_node)

    # Entry point - start with translation
    builder.set_entry_point("translate_question")
    
    # Sequential flow: translate -> query_similarity_check
    builder.add_edge("translate_question", "query_similarity_check")
    
    # Conditional routing after query similarity check
    builder.add_conditional_edges(
        "query_similarity_check",
        route_after_query_similarity_check,
        {
            "classify_query": "classify_query",  # Nếu similarity < 0.8
            "safety_check": "safety_check",  # Nếu similarity >= 0.8 hoặc không có buffer
        },
    )
    
    # classify_query always goes to safety_check
    builder.add_edge("classify_query", "safety_check")

    # Conditional routing after safety check
    builder.add_conditional_edges(
        "safety_check",
        route_after_safety_check,
        {
            "crisis_response": "crisis_response",
            "not_mental_health": "not_mental_health",
            "slot_filling": "slot_filling",  # Chỉ chạy nếu safe & relevant
        },
    )

    # Crisis and non-relevant queries exit directly
    builder.add_edge("crisis_response", END)
    builder.add_edge("not_mental_health", END)

    # Normal flow: slot_filling -> graph_retrieval -> answer -> conversation_memory -> translate_answer -> END
    builder.add_edge("slot_filling", "graph_retrieval")
    builder.add_edge("graph_retrieval", "answer")
    builder.add_edge("answer", "conversation_memory")  # Update buffer + summary
    builder.add_edge("conversation_memory", END)
    # builder.add_edge("conversation_memory", "translate_answer")
    # builder.add_edge("translate_answer", END)

    return builder.compile()
