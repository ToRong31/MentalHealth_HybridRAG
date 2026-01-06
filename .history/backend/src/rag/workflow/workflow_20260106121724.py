from langgraph.graph import StateGraph, END
from typing import Literal

from .state import KGState
from .graph_nodes import (
    encode_node,
    graph_retrieval_node,
    translate_question_node,
    translate_answer_node,
    dense_retrieval_node,
    query_similarity_check_node,
    safety_check_node,
    crisis_response_node,
    not_mental_health_node,
    answer_with_graph_node,
    answer_with_dense_node,
    slot_filling_node,
    query_rewriter_node,
    conversation_memory_node,
    request_more_info_node,
    diagnostic_check_node,
    disease_conclusion_node,
    treatment_retrieval_node,
    answer_with_treatment_node,
)
    


def route_after_query_similarity_check(state: KGState) -> Literal["safety_check"]:
    """
    Routing logic sau khi check query similarity:
    - Always go to safety_check (query_classifier removed)
    """
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


def route_after_slot_filling(state: KGState) -> Literal["query_rewriter", "request_more_info"]:
    """
    Routing logic sau khi slot filling:
    - Nếu đủ slots -> query_rewriter (rewrite query với slots + conversation)
    - Nếu thiếu slots -> request_more_info (hỏi thêm)
    """
    has_sufficient = state.get("has_sufficient_slots", False)
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[ROUTING] route_after_slot_filling: has_sufficient_slots = {has_sufficient}")
    logger.info(f"[ROUTING] has_sufficient_slots in state.keys(): {'has_sufficient_slots' in state}")
    logger.info(f"[ROUTING] All slot-related keys: {[k for k in state.keys() if 'slot' in k.lower()]}")
    logger.info(f"[ROUTING] Direct access state['has_sufficient_slots']: {state.get('has_sufficient_slots', 'KEY NOT FOUND')}")
    logger.info(f"[ROUTING] Will route to: {'query_rewriter' if has_sufficient else 'request_more_info'}")
    
    if has_sufficient:
        return "query_rewriter"
    else:
        return "request_more_info"


def route_after_diagnostic_check(state: KGState) -> Literal["disease_conclusion", "graph_retrieval"]:
    """
    Routing logic after diagnostic check:
    - If confidence >= 0.75 -> disease_conclusion (high confidence diagnosis)
    - If confidence < 0.75 -> graph_retrieval (low confidence, fallback to graph with apology)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    confidence = state.get("diagnostic_confidence", 0.0)
    
    if confidence >= 0.75:
        logger.info(f"[ROUTING] High confidence ({confidence:.2f}) -> disease_conclusion")
        return "disease_conclusion"
    else:
        logger.info(f"[ROUTING] Low confidence ({confidence:.2f}) -> graph_retrieval with apology")
        # Set flag for apology prefix
        state["needs_apology_prefix"] = True
        return "graph_retrieval"


def route_after_disease_conclusion(state: KGState) -> Literal["treatment_retrieval", "graph_retrieval"]:
    """
    Routing logic after disease conclusion (user response to treatment confirmation):
    - If user wants treatment -> treatment_retrieval
    - If user declines -> graph_retrieval (provide general guidance)
    
    Note: This requires user's next message to be processed.
    For now, we assume user_wants_treatment flag is set by intent detection.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    user_wants_treatment = state.get("user_wants_treatment", False)
    
    if user_wants_treatment:
        logger.info("[ROUTING] User wants treatment -> treatment_retrieval")
        return "treatment_retrieval"
    else:
        logger.info("[ROUTING] User declined treatment -> graph_retrieval")
        return "graph_retrieval"


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
       5c. If safe & relevant -> slot_filling -> route_after_slot_filling
    6. route_after_slot_filling:
       6a. If REQUIRED slots insufficient -> request_more_info -> END
       6b. If REQUIRED slots sufficient -> query_rewriter -> retrieval -> answer -> conversation_memory -> END
    
    Conversation Memory:
    - query_similarity_check: Check if query is follow-up, topic_change, or off_topic
    - classify_query: LLM classify query type (only if similarity < 0.8)
    - safety_check: Conditional enhancement based on query_type
    - query_rewriter: Uses last 3 buffer pairs + summary + slots to rewrite query
    - retrieval: Uses rewritten query (with slots + conversation context)
    - answer: Enhanced with chunks + slots + last 3 buffer pairs + summary
    - conversation_memory: Update buffer + summary, handle topic change
    
    Slot filling (after safety check passes):
    - Extract structured information (emotion, trigger, duration, etc.)
    - Separate into REQUIRED vs OPTIONAL missing slots
    - Check if REQUIRED slots are sufficiently filled (at least 5/8)
    
    Two-phase follow-up strategy:
    - Phase 1 (Before retrieval): If REQUIRED slots insufficient → request_more_info
      * Only ask about REQUIRED_SLOTS (emotion, mood, intensity, trigger, duration, impact, need, stress)
      * User must complete these before retrieval happens
    
    - Phase 2 (After answer): If REQUIRED slots sufficient → proceed with answer
      * Generate answer from retrieval
      * Append optional follow-up questions at the end (e.g., sleep, coping, support)
      * These don't block the answer, just gather additional context for future turns
    
    Query Rewriting (separate node):
    - Runs after slot filling when REQUIRED slots are sufficient
    - Combines: filled slots + last 3 conversation pairs + summary context
    - Example: "Tôi buồn quá" → "Tôi đang cảm thấy rất buồn trong thời gian gần đây"
    - Also runs for follow-up messages
    - Improves retrieval quality by providing rich context
    - Rewritten query is used by both dense_retrieval and graph_retrieval nodes
    
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
    # builder.add_node("classify_query", query_classifier_node)  # Commented out - not in ea286d2
    builder.add_node("safety_check", safety_check_node)
    builder.add_node("slot_filling", slot_filling_node)  # Chạy sau safety_check
    builder.add_node("crisis_response", crisis_response_node)
    builder.add_node("not_mental_health", not_mental_health_node)
    builder.add_node("request_more_info", request_more_info_node)  # Hỏi thêm nếu thiếu slots
    builder.add_node("query_rewriter", query_rewriter_node)  # Rewrite query với slots + conversation
    
    # Diagnostic and treatment nodes
    builder.add_node("diagnostic_check", diagnostic_check_node)
    builder.add_node("disease_conclusion", disease_conclusion_node)
    builder.add_node("treatment_retrieval", treatment_retrieval_node)
    builder.add_node("answer_with_treatment", answer_with_treatment_node)
    
    # Graph retrieval and answer nodes
    builder.add_node("graph_retrieval", graph_retrieval_node)
    builder.add_node("answer_with_graph", answer_with_graph_node)
    
    # Legacy dense retrieval (kept for backward compatibility)
    builder.add_node("dense_retrieval", dense_retrieval_node)
    builder.add_node("answer", answer_with_dense_node)
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
            "safety_check": "safety_check",  # Always go to safety_check
        },
    )
    
    # classify_query removed - not in ea286d2
    # builder.add_edge("classify_query", "safety_check")

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

    # Conditional routing after slot filling
    builder.add_conditional_edges(
        "slot_filling",
        route_after_slot_filling,
        {
            "query_rewriter": "query_rewriter",  # Đủ slots -> rewrite query
            "request_more_info": "request_more_info",  # Thiếu slots -> hỏi thêm
        },
    )

    # Request more info exits directly (no retrieval)
    builder.add_edge("request_more_info", END)

    # NEW DIAGNOSTIC FLOW: query_rewriter -> diagnostic_check -> route based on confidence
    builder.add_edge("query_rewriter", "diagnostic_check")
    
    # Route after diagnostic check based on confidence threshold (0.75)
    builder.add_conditional_edges(
        "diagnostic_check",
        route_after_diagnostic_check,
        {
            "disease_conclusion": "disease_conclusion",  # High confidence (>=0.75)
            "graph_retrieval": "graph_retrieval",  # Low confidence (<0.75) with apology
        },
    )
    
    # Route after disease conclusion based on user confirmation
    # Note: This requires multi-turn conversation handling
    # For now, assumes user_wants_treatment flag is set
    builder.add_conditional_edges(
        "disease_conclusion",
        route_after_disease_conclusion,
        {
            "treatment_retrieval": "treatment_retrieval",  # User wants treatment
            "graph_retrieval": "graph_retrieval",  # User declines treatment
        },
    )
    
    # Treatment flow: treatment_retrieval -> answer_with_treatment -> END
    builder.add_edge("treatment_retrieval", "answer_with_treatment")
    builder.add_edge("answer_with_treatment", END)
    
    # Graph flow: graph_retrieval -> answer_with_graph -> END
    builder.add_edge("graph_retrieval", "answer_with_graph")
    builder.add_edge("answer_with_graph", END)

    # Legacy dense flow (commented out, replaced by diagnostic flow)
    # builder.add_edge("query_rewriter", "dense_retrieval")
    # builder.add_edge("dense_retrieval", "answer")
    # builder.add_edge("answer", "conversation_memory")
    # builder.add_edge("conversation_memory", END)

    return builder.compile()
